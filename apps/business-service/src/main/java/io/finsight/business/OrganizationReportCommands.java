package io.finsight.business;

import com.fasterxml.jackson.databind.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.bind.annotation.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Explicit version-bound questions/revisions; unknown dispatches are query-only. */
@RestController
class OrganizationReportCommands {
    record Target(@NotNull UUID request_id, @NotBlank @Size(max=300) String citation_id,
        @Min(1) int base_version, @NotBlank @Pattern(regexp="[a-f0-9]{64}") String base_digest,
        @NotNull UUID base_checkpoint) {}
    record Create(@NotNull UUID id, @NotNull UUID previous_run_id, @NotNull UUID checkpoint_id,
        @NotBlank @Pattern(regexp="sha256:[a-f0-9]{64}") String state_digest,
        @Min(1) int report_version, @NotBlank @Pattern(regexp="[a-f0-9]{64}") String report_digest,
        @NotBlank @Pattern(regexp="ask|revise") String action,
        @NotBlank @Size(max=16000) String message,
        @NotBlank @Pattern(regexp="quick|deep") String answer_mode, @Valid Target target) {}
    record Admission(@NotNull UUID command_id, @NotNull UUID thread_id, @NotNull UUID run_id,
        @NotNull UUID operation_id, @NotBlank String manifest_digest,
        @NotBlank String configuration_digest, @NotBlank String report_action_request_digest) {}

    private final JdbcTemplate db;
    private final OrganizationNativeDrafts drafts;
    private final OrganizationExecutionBindings bindings;
    private final PythonIntake python;
    private final ObjectMapper json;
    private final TransactionTemplate tx;
    private final boolean enabled;

    OrganizationReportCommands(JdbcTemplate db, OrganizationNativeDrafts drafts,
            OrganizationExecutionBindings bindings, PythonIntake python, ObjectMapper json,
            PlatformTransactionManager manager,
            @Value("${finsight.organization-report-actions-enabled:false}") boolean enabled) {
        this.db=db; this.drafts=drafts; this.bindings=bindings; this.python=python; this.json=json;
        this.tx=new TransactionTemplate(manager); this.enabled=enabled;
    }
    private JsonNode parse(Object value) {
        try { return value==null?null:json.readTree(value.toString()); }
        catch(java.io.IOException e) { throw new IllegalStateException(e); }
    }
    private String hash(Object value) {
        return "sha256:"+Delegation.digest(value.toString().getBytes(StandardCharsets.UTF_8));
    }
    private Map<String,Object> command(UUID execution, UUID id) {
        return db.queryForList("SELECT *,response::text AS result FROM organization_report_command WHERE id=? AND execution_id=?",id,execution)
            .stream().findFirst().orElseThrow(()->new ApiFailure(404,"报告操作不存在"));
    }
    private Map<String,Object> view(Map<String,Object> c) {
        var p=parse(c.get("request_body")); var value=new HashMap<String,Object>();
        for(String key:List.of("id","execution_id","operation_id","command_sequence"))value.put(key,c.get(key));
        value.put("status","dispatching".equals(c.get("status"))?"unknown":c.get("status"));
        for(String key:List.of("action","report_version","checkpoint_id"))value.put(key,p.get(key));
        if(c.get("run_id")!=null)value.put("run_id",c.get("run_id"));
        if(c.get("result")!=null)value.put("result",parse(c.get("result")));
        return value;
    }
    private Map<String,Object> grant(String actor, UUID project, UUID execution, UUID id) {
        var value=drafts.prepared(actor,project,execution); var c=command(execution,id);
        if(!actor.equals(c.get("principal")))throw new ApiFailure(404,"报告操作不可访问");
        if(!Set.of("dispatching","unknown","received").contains(c.get("status")))
            throw new ApiFailure(409,"报告操作未派发或已拒绝");
        value.put("report_command_id",id); value.put("report_action_operation_id",c.get("operation_id"));
        value.put("report_action_request",parse(c.get("request_body")));
        value.put("report_action_request_digest",hash(c.get("request_body")));
        return value;
    }
    private void requireEnabled() {
        if(!enabled)throw new ApiFailure(503,"组织报告交互尚未启用");
    }
    private void validate(Create input) {
        if(input.action().equals("revise")&&!input.answer_mode().equals("deep"))
            throw new ApiFailure(422,"修订需要完整修订流程");
        var t=input.target();
        if(t!=null&&(!input.action().equals("revise")||!t.request_id().equals(input.id())
                ||t.base_version()!=input.report_version()||!t.base_digest().equals(input.report_digest())
                ||!t.base_checkpoint().equals(input.checkpoint_id())))
            throw new ApiFailure(422,"局部修订目标与请求基线不一致");
    }
    private UUID previousRun(UUID execution) {
        var commands=db.queryForList("SELECT status,run_id FROM organization_report_command WHERE execution_id=? AND status<>'rejected' ORDER BY command_sequence DESC LIMIT 1",execution);
        if(!commands.isEmpty()) {
            var c=commands.getFirst();
            if(!"received".equals(c.get("status"))||c.get("run_id")==null)
                throw new ApiFailure(409,"先核对上一条报告操作，不会再次派发");
            return (UUID)c.get("run_id");
        }
        var continuation=db.queryForList("SELECT status,run_id FROM organization_native_continuation WHERE execution_id=?",execution);
        if(!continuation.isEmpty()) {
            var c=continuation.getFirst();
            if(!"received".equals(c.get("status"))||c.get("run_id")==null)
                throw new ApiFailure(409,"先核对研究接续回执");
            return (UUID)c.get("run_id");
        }
        return (UUID)db.queryForList("SELECT run_id FROM organization_native_start WHERE execution_id=? AND status='received' AND run_id IS NOT NULL",execution)
            .stream().findFirst().orElseThrow(()->new ApiFailure(409,"先核对研究运行回执")).get("run_id");
    }
    @PostMapping("/v1/workspaces/projects/{project}/execution-bindings/{execution}/report-commands")
    Object create(HttpServletRequest request, @PathVariable UUID project, @PathVariable UUID execution,
                  @Valid @RequestBody Create input) {
        requireEnabled(); validate(input);
        String actor=(String)request.getAttribute("owner");
        String fingerprint=Delegation.digest(json.valueToTree(input).toString().getBytes(StandardCharsets.UTF_8));
        tx.executeWithoutResult(status->{
            var prepared=drafts.prepared(actor,project,execution); // Current project/source locks.
            var existing=db.queryForList("SELECT execution_id,fingerprint FROM organization_report_command WHERE id=?",input.id());
            if(!existing.isEmpty()) {
                if(!execution.equals(existing.getFirst().get("execution_id"))
                        ||!fingerprint.equals(existing.getFirst().get("fingerprint")))
                    throw new ApiFailure(409,"同一请求标识不能提交其他报告操作");
                return;
            }
            if(!input.previous_run_id().equals(previousRun(execution)))
                throw new ApiFailure(409,"前序运行已变化，请刷新报告后重试");
            if(!db.queryForList("SELECT id FROM organization_report_command WHERE execution_id=? AND checkpoint_id=? AND status<>'rejected'",execution,input.checkpoint_id()).isEmpty())
                throw new ApiFailure(409,"该报告快照已有操作，请核对原记录");
            var start=db.queryForMap("SELECT request_body FROM organization_native_start WHERE execution_id=?",execution);
            var payload=json.valueToTree(input);
            var body=(com.fasterxml.jackson.databind.node.ObjectNode)payload;
            body.remove("id");
            body.put("contract_version","organization_report_action.v1").put("command_id",input.id().toString())
                .put("execution_id",execution.toString()).put("project_id",project.toString())
                .put("manifest_digest",prepared.get("manifest_digest").toString())
                .put("configuration_digest",prepared.get("configuration_digest").toString())
                .put("prepare_operation_id",prepared.get("prepare_operation_id").toString())
                .put("research_as_of",parse(start.get("request_body")).path("research_as_of").asText());
            if(db.update("INSERT INTO organization_report_command(id,execution_id,operation_id,principal,fingerprint,checkpoint_id,request_body) VALUES(?,?,?,?,?,?,?) ON CONFLICT DO NOTHING",
                input.id(),execution,UUID.randomUUID(),actor,fingerprint,input.checkpoint_id(),body.toString())!=1)
                throw new ApiFailure(409,"报告操作标识或快照已被占用，请核对原记录");
            db.update("INSERT INTO organization_project_audit(project_id,actor,action,target,revision) SELECT id,?,'report_action',?,revision FROM organization_project WHERE id=?",actor,input.id().toString(),project);
        });
        var c=command(execution,input.id());
        if(db.update("UPDATE organization_report_command SET status='dispatching',updated_at=now() WHERE id=? AND status='ready'",input.id())==1) {
            try {
                var reply=python.request(actor,"POST","organization/report-actions",c.get("request_body").toString(),(UUID)c.get("operation_id"));
                accept(execution,input.id(),c,reply.status(),reply.body());
            } catch(IntakeUnavailable e) { unknown(input.id()); }
        }
        bindings.preparation(actor,project,execution); return view(command(execution,input.id()));
    }
    @GetMapping("/v1/workspaces/projects/{project}/execution-bindings/{execution}/report-commands")
    Object list(HttpServletRequest request,@PathVariable UUID project,@PathVariable UUID execution) {
        bindings.preparation((String)request.getAttribute("owner"),project,execution);
        return Map.of("items",db.queryForList("SELECT *,response::text AS result FROM organization_report_command WHERE execution_id=? ORDER BY command_sequence DESC LIMIT 100",execution)
            .stream().map(this::view).toList(),"enabled",enabled);
    }
    @GetMapping("/v1/workspaces/projects/{project}/execution-bindings/{execution}/report-commands/{id}")
    Object get(HttpServletRequest request,@PathVariable UUID project,@PathVariable UUID execution,@PathVariable UUID id) {
        bindings.preparation((String)request.getAttribute("owner"),project,execution);
        return view(command(execution,id));
    }
    @GetMapping("/v1/workspaces/projects/{project}/execution-bindings/{execution}/report-commands/{id}/access")
    Object access(HttpServletRequest request,@PathVariable UUID project,@PathVariable UUID execution,@PathVariable UUID id) {
        return tx.execute(status->grant((String)request.getAttribute("owner"),project,execution,id));
    }
    private void unknown(UUID id) {
        db.update("UPDATE organization_report_command SET status='unknown',updated_at=now() WHERE id=? AND status='dispatching'",id);
    }
    private boolean matches(UUID execution,Map<String,Object> c,JsonNode result) {
        var p=parse(c.get("request_body"));
        if(result==null||!execution.toString().equals(result.path("thread_id").asText())
                ||!execution.toString().equals(result.path("execution_id").asText())
                ||!c.get("id").toString().equals(result.path("report_command_id").asText())
                ||!c.get("operation_id").toString().equals(result.path("report_action_operation_id").asText())
                ||!hash(c.get("request_body")).equals(result.path("report_action_request_digest").asText())
                ||!p.path("project_id").equals(result.path("project_id"))
                ||!p.path("configuration_digest").equals(result.path("configuration_digest")))return false;
        try { return !UUID.fromString(result.path("run_id").asText()).toString().equals(p.path("previous_run_id").asText()); }
        catch(IllegalArgumentException e) { return false; }
    }
    private void accept(UUID execution,UUID id,Map<String,Object> c,int status,JsonNode result) {
        if(status==200&&matches(execution,c,result)) {
            UUID run=UUID.fromString(result.path("run_id").asText());
            try {
                db.update("UPDATE organization_report_command SET status='received',run_id=?,response=?::jsonb,updated_at=now() WHERE id=? AND status IN ('dispatching','unknown') AND (run_id IS NULL OR run_id=?)",run,result.toString(),id,run);
            } catch(DuplicateKeyException e) {
                // A receipt naming another command's run is not proof of success.
                unknown(id);
                return;
            }
            unknown(id);
        } else if(status>=400&&status<500&&!(result!=null&&"unknown".equals(result.path("submission_status").asText())))
            db.update("UPDATE organization_report_command SET status='rejected',response=?::jsonb,updated_at=now() WHERE id=? AND status IN ('dispatching','unknown') AND run_id IS NULL",result==null?null:result.toString(),id);
        else unknown(id);
    }
    @PostMapping("/v1/workspaces/projects/{project}/execution-bindings/{execution}/report-commands/{id}/reconcile")
    Object reconcile(HttpServletRequest request,@PathVariable UUID project,@PathVariable UUID execution,@PathVariable UUID id) {
        String actor=(String)request.getAttribute("owner");
        bindings.preparation(actor,project,execution); var c=command(execution,id);
        if(Set.of("dispatching","unknown").contains(c.get("status"))) {
            var reply=python.request(actor,"GET","organization/executions/"+execution+"/report-actions/"+id+"?project_id="+project,null,null);
            if(reply.status()==200&&matches(execution,c,reply.body()))accept(execution,id,c,200,reply.body());
        }
        bindings.preparation(actor,project,execution); return view(command(execution,id));
    }
    @PostMapping("/v1/runtime/organization-executions/{execution}/admit-report-action")
    Object admit(@PathVariable UUID execution,@Valid @RequestBody Admission input) {
        requireEnabled();
        try { return tx.execute(status->{
            bindings.access(execution,new OrganizationExecutionBindings.Access(input.thread_id(),input.manifest_digest()));
            var identity=db.queryForMap("SELECT b.principal,d.project_id FROM organization_execution_binding b JOIN organization_research_draft d ON d.id=b.draft_id WHERE b.id=?",execution);
            var current=grant(identity.get("principal").toString(),(UUID)identity.get("project_id"),execution,input.command_id());
            var c=command(execution,input.command_id());
            if(!input.operation_id().equals(c.get("operation_id"))
                    ||!input.configuration_digest().equals(current.get("configuration_digest"))
                    ||!input.report_action_request_digest().equals(current.get("report_action_request_digest"))
                    ||input.run_id().toString().equals(parse(c.get("request_body")).path("previous_run_id").asText()))
                throw new ApiFailure(409,"运行身份与固定报告操作不匹配");
            if(db.update("UPDATE organization_report_command SET run_id=?,updated_at=now() WHERE id=? AND (run_id IS NULL OR run_id=?)",input.run_id(),input.command_id(),input.run_id())!=1)
                throw new ApiFailure(409,"该操作已绑定另一运行");
            current.put("authorized_run_id",input.run_id()); return current;
        }); } catch(DuplicateKeyException e) {
            throw new ApiFailure(409,"原生运行已被另一报告操作占用");
        }
    }
}
