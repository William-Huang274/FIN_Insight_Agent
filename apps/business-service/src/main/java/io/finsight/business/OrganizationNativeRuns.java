package io.finsight.business;

import com.fasterxml.jackson.databind.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.bind.annotation.*;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.util.*;

/** One initial orientation command. Unknown delivery never creates a second run. */
@RestController
class OrganizationNativeRuns {
    record Start(@NotBlank String research_as_of) {}
    record Admission(@NotNull UUID thread_id,@NotNull UUID run_id,@NotNull UUID operation_id,
        @NotBlank String manifest_digest,@NotBlank String configuration_digest,@NotBlank String start_request_digest) {}
    private final JdbcTemplate db;
    private final OrganizationNativeDrafts drafts;
    private final OrganizationExecutionBindings bindings;
    private final PythonIntake python;
    private final ObjectMapper json;
    private final TransactionTemplate tx;
    private final boolean enabled;
    OrganizationNativeRuns(JdbcTemplate db,OrganizationNativeDrafts drafts,OrganizationExecutionBindings bindings,
            PythonIntake python,ObjectMapper json,PlatformTransactionManager manager,
            @Value("${finsight.organization-start-enabled:false}") boolean enabled) {
        this.db=db;this.drafts=drafts;this.bindings=bindings;this.python=python;this.json=json;
        this.tx=new TransactionTemplate(manager);this.enabled=enabled;
    }
    private Map<String,Object> command(UUID id) {
        return db.queryForList("SELECT *,response::text AS result FROM organization_native_start WHERE execution_id=?",id)
            .stream().findFirst().orElseThrow(()->new ApiFailure(404,"启动命令不存在"));
    }
    private JsonNode parse(Object value) {
        try{return value==null?null:json.readTree(value.toString());}catch(java.io.IOException e){throw new IllegalStateException(e);}
    }
    private String hash(Object value){return "sha256:"+Delegation.digest(value.toString().getBytes(StandardCharsets.UTF_8));}
    private Map<String,Object> view(UUID id) {
        var c=command(id);var result=new HashMap<String,Object>();result.put("execution_id",id);
        result.put("operation_id",c.get("operation_id"));result.put("status","dispatching".equals(c.get("status"))?"unknown":c.get("status"));
        if(c.get("run_id")!=null)result.put("run_id",c.get("run_id"));
        if(c.get("result")!=null)result.put("result",parse(c.get("result")));return result;
    }
    private Map<String,Object> grant(String actor,UUID project,UUID id) {
        var result=drafts.prepared(actor,project,id);var c=command(id);
        if(!Set.of("dispatching","unknown","received").contains(c.get("status")))throw new ApiFailure(409,"启动命令未派发或已拒绝");
        result.put("start_operation_id",c.get("operation_id"));result.put("start_request",parse(c.get("request_body")));
        result.put("start_request_digest",hash(c.get("request_body")));return result;
    }
    @GetMapping("/v1/workspaces/projects/{project}/execution-bindings/{id}/start-access")
    Object access(HttpServletRequest request,@PathVariable UUID project,@PathVariable UUID id) {
        return tx.execute(status->grant((String)request.getAttribute("owner"),project,id));
    }
    @GetMapping("/v1/workspaces/projects/{project}/execution-bindings/{id}/start")
    Object get(HttpServletRequest request,@PathVariable UUID project,@PathVariable UUID id) {
        bindings.preparation((String)request.getAttribute("owner"),project,id);return view(id);
    }
    @PostMapping("/v1/workspaces/projects/{project}/execution-bindings/{id}/start")
    Object start(HttpServletRequest request,@PathVariable UUID project,@PathVariable UUID id,@Valid @RequestBody Start input) {
        if(!enabled)throw new ApiFailure(503,"组织原生启动尚未启用");
        String actor=(String)request.getAttribute("owner"),fingerprint=Delegation.digest((byte[])request.getAttribute("originalBody"));
        tx.executeWithoutResult(status->{
            var prepared=drafts.prepared(actor,project,id);
            OffsetDateTime cutoff;
            try {cutoff=OffsetDateTime.parse(input.research_as_of());}
            catch(java.time.DateTimeException e){throw new ApiFailure(422,"研究截止时间必须包含时区");}
            if(!cutoff.toLocalDate().toString().equals(parse(prepared.get("manifest_text")).path("research_as_of").asText()))
                throw new ApiFailure(409,"截止时间与固定资料日期不一致");
            boolean onDemand="organization_native_preparation.v2".equals(((JsonNode)prepared.get("prepare_request")).path("contract_version").asText());
            var payload=json.createObjectNode().put("contract_version",onDemand ? "organization_native_start.v2" : "organization_native_start.v1")
                .put("execution_id",id.toString()).put("project_id",project.toString())
                .put("manifest_digest",prepared.get("manifest_digest").toString())
                .put("configuration_digest",prepared.get("configuration_digest").toString())
                .put("prepare_operation_id",prepared.get("prepare_operation_id").toString())
                .put("research_as_of",input.research_as_of()).put("stage",onDemand ? "work_session" : "orientation");
            int inserted=db.update("INSERT INTO organization_native_start(execution_id,operation_id,fingerprint,request_body) VALUES(?,?,?,?) ON CONFLICT DO NOTHING",id,UUID.randomUUID(),fingerprint,payload.toString());
            if(!fingerprint.equals(command(id).get("fingerprint")))throw new ApiFailure(409,"该执行已有其他启动命令");
            if(inserted==1)db.update("INSERT INTO organization_project_audit(project_id,actor,action,target,revision) SELECT id,?,'native_start',?,revision FROM organization_project WHERE id=?",actor,id.toString(),project);
        });
        var c=command(id);
        if(db.update("UPDATE organization_native_start SET status='dispatching',updated_at=now() WHERE execution_id=? AND status='ready'",id)==1){
            try {var reply=python.request(actor,"POST","organization/start",c.get("request_body").toString(),(UUID)c.get("operation_id"));
                accept(id,c,reply.status(),reply.body());}
            catch(IntakeUnavailable e){unknown(id);}
        }
        bindings.preparation(actor,project,id);return view(id);
    }
    private boolean matches(UUID id,Map<String,Object> c,JsonNode result) {
        var payload=parse(c.get("request_body"));
        if(result==null||!id.toString().equals(result.path("thread_id").asText())||!id.toString().equals(result.path("execution_id").asText())
            ||!payload.path("project_id").equals(result.path("project_id"))||!payload.path("configuration_digest").equals(result.path("configuration_digest"))
            ||!c.get("operation_id").toString().equals(result.path("start_operation_id").asText())||!hash(c.get("request_body")).equals(result.path("start_request_digest").asText()))return false;
        try {UUID.fromString(result.path("run_id").asText());return true;}catch(IllegalArgumentException e){return false;}
    }
    private void unknown(UUID id){db.update("UPDATE organization_native_start SET status='unknown',updated_at=now() WHERE execution_id=? AND status='dispatching'",id);}
    private void accept(UUID id,Map<String,Object> c,int status,JsonNode response) {
        if(status==200&&matches(id,c,response)){
            UUID run=UUID.fromString(response.path("run_id").asText());
            // Native admission may win this race before the HTTP receipt arrives.
            db.update("UPDATE organization_native_start SET status='received',run_id=?,response=?::jsonb,updated_at=now() WHERE execution_id=? AND status IN ('dispatching','unknown') AND (run_id IS NULL OR run_id=?)",run,response.toString(),id,run);
            unknown(id);
        } else if(status>=400&&status<500&&!(response!=null&&"unknown".equals(response.path("submission_status").asText())))
            db.update("UPDATE organization_native_start SET status='rejected',response=?::jsonb,updated_at=now() WHERE execution_id=? AND status IN ('dispatching','unknown') AND run_id IS NULL",response==null?null:response.toString(),id);
        else unknown(id);
    }
    @PostMapping("/v1/workspaces/projects/{project}/execution-bindings/{id}/start-reconcile")
    Object reconcile(HttpServletRequest request,@PathVariable UUID project,@PathVariable UUID id) {
        String actor=(String)request.getAttribute("owner");bindings.preparation(actor,project,id);var c=command(id);
        if(Set.of("dispatching","unknown").contains(c.get("status"))){
            var reply=python.request(actor,"GET","organization/executions/"+id+"/start-state?project_id="+project,null,null);
            if(reply.status()==200&&matches(id,c,reply.body()))accept(id,c,200,reply.body());
        }
        bindings.preparation(actor,project,id);return view(id);
    }
    @PostMapping("/v1/runtime/organization-executions/{id}/admit-start")
    Object admit(@PathVariable UUID id,@Valid @RequestBody Admission input) {
        if(!enabled)throw new ApiFailure(503,"组织原生启动尚未启用");
        return tx.execute(status->{
            // Resolves the creator from saved binding, never from workload input.
            bindings.access(id,new OrganizationExecutionBindings.Access(input.thread_id(),input.manifest_digest()));
            var identity=db.queryForMap("SELECT b.principal,d.project_id FROM organization_execution_binding b JOIN organization_research_draft d ON d.id=b.draft_id WHERE b.id=?",id);
            var current=grant(identity.get("principal").toString(),(UUID)identity.get("project_id"),id);var c=command(id);
            if(!input.operation_id().equals(c.get("operation_id"))||!input.configuration_digest().equals(current.get("configuration_digest"))
                ||!input.start_request_digest().equals(current.get("start_request_digest")))throw new ApiFailure(409,"运行身份与固定启动命令不匹配");
            if(db.update("UPDATE organization_native_start SET run_id=?,updated_at=now() WHERE execution_id=? AND (run_id IS NULL OR run_id=?)",input.run_id(),id,input.run_id())!=1)
                throw new ApiFailure(409,"该命令已绑定另一运行");
            current.put("authorized_run_id",input.run_id());return current;
        });
    }
}
