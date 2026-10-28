package io.finsight.business;

import com.fasterxml.jackson.databind.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.bind.annotation.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** One-level native child work. Uses the existing command ledger, not a task queue. */
@RestController
class OrganizationTaskCommands {
    record Claim(@NotNull JsonNode command, JsonNode fixed_input) {}
    record Catalog(@NotBlank String manifest_digest) {}
    record Lookup(@NotBlank String manifest_digest, @NotNull UUID child_thread_id,
                  UUID command_id, UUID run_id, JsonNode receipt) {}
    private final JdbcTemplate db;
    private final ObjectMapper json;
    private final OrganizationExecutionBindings bindings;
    private final TransactionTemplate tx;
    private final boolean enabled;
    OrganizationTaskCommands(JdbcTemplate db, ObjectMapper json, OrganizationExecutionBindings bindings,
            PlatformTransactionManager manager,
            @Value("${finsight.organization-task-actions-enabled:false}") boolean enabled) {
        this.db=db;this.json=json;this.bindings=bindings;this.tx=new TransactionTemplate(manager);this.enabled=enabled;
    }
    private void enabled() { if(!enabled)throw new ApiFailure(503,"按需子任务尚未启用"); }
    private JsonNode parse(Object value) {
        try{return json.readTree(value.toString());}catch(java.io.IOException e){throw new IllegalStateException(e);}
    }
    private String hash(JsonNode value) {return Delegation.digest(value.toString().getBytes(StandardCharsets.UTF_8));}
    private UUID uuid(JsonNode body,String field) {
        try{return UUID.fromString(body.path(field).asText());}
        catch(IllegalArgumentException e){throw new ApiFailure(422,"缺少合法任务身份："+field);}
    }
    private Map<String,Object> root(UUID execution,String manifest) {
        bindings.access(execution,new OrganizationExecutionBindings.Access(execution,manifest));
        return db.queryForMap("SELECT principal FROM organization_execution_binding WHERE id=? FOR UPDATE",execution);
    }
    private Map<String,Object> row(UUID execution,UUID id) {
        return db.queryForList("SELECT * FROM organization_report_command WHERE command_kind='research_task' AND execution_id=? AND id=?",execution,id)
            .stream().findFirst().orElseThrow(()->new ApiFailure(404,"子任务命令不存在"));
    }
    private Map<String,Object> origin(UUID execution,UUID child) {
        return db.queryForList("SELECT * FROM organization_report_command WHERE command_kind='research_task' AND execution_id=? AND child_thread_id=? AND task_action='create'",execution,child)
            .stream().findFirst().orElseThrow(()->new ApiFailure(404,"子任务不在该执行范围内"));
    }
    private void live(UUID execution,UUID child,boolean cancellation) {
        if(!cancellation&&!db.queryForList("SELECT id FROM organization_report_command WHERE command_kind='research_task' AND execution_id=? AND child_thread_id=? AND task_action='cancel' AND status<>'rejected'",execution,child).isEmpty())
            throw new ApiFailure(409,"子任务已停止，不可继续调用模型或读取资料");
    }
    private Map<String,Object> view(Map<String,Object> c,boolean dispatch) {
        var p=parse(c.get("request_body"));var task=origin((UUID)c.get("execution_id"),(UUID)c.get("child_thread_id"));
        var initial=parse(task.get("request_body"));var fixed=initial.get("fixed_input");
        var result=new HashMap<String,Object>();
        result.put("command_id",c.get("id"));result.put("execution_id",c.get("execution_id"));
        result.put("operation_id",c.get("operation_id"));result.put("child_thread_id",c.get("child_thread_id"));
        var organization=db.queryForObject("SELECT d.organization_id FROM organization_execution_binding b JOIN organization_research_draft d ON d.id=b.draft_id WHERE b.id=?",UUID.class,c.get("execution_id"));
        result.put("owner_id","organization:"+organization);result.put("action",c.get("task_action"));
        result.put("dispatch_allowed",dispatch);result.put("status",c.get("status"));
        result.put("cancel_requested",!db.queryForList("SELECT id FROM organization_report_command WHERE command_kind='research_task' AND execution_id=? AND child_thread_id=? AND task_action='cancel' AND status<>'rejected'",c.get("execution_id"),c.get("child_thread_id")).isEmpty());
        result.put("binding",Map.of("execution_id",c.get("execution_id"),"child_thread_id",c.get("child_thread_id"),
            "create_command_id",task.get("id"),"input_digest",fixed.path("input_digest"),"fixed_input",fixed));
        result.put("command",p.get("command"));
        if(c.get("run_id")!=null)result.put("run_id",c.get("run_id"));
        return result;
    }
    private void validate(JsonNode c,JsonNode fixed,UUID execution) {
        var fields=new HashSet<String>();c.fieldNames().forEachRemaining(fields::add);
        if(!fields.equals(Set.of("command_id","execution_id","parent_thread_id","parent_run_id","parent_checkpoint_id",
                "child_thread_id","action","root_budget_id","manifest_digest","task","checkpoint_id","message")))
            throw new ApiFailure(422,"子任务命令字段不匹配");
        if(!execution.equals(uuid(c,"execution_id"))||!execution.equals(uuid(c,"parent_thread_id"))
                ||execution.equals(uuid(c,"child_thread_id")))throw new ApiFailure(422,"仅根任务可以委派子任务");
        uuid(c,"command_id");uuid(c,"parent_run_id");uuid(c,"parent_checkpoint_id");
        String action=c.path("action").asText();
        if(!Set.of("create","continue","cancel").contains(action)||c.path("root_budget_id").asText().isBlank()
                ||!c.path("manifest_digest").asText().matches("sha256:[a-f0-9]{64}"))throw new ApiFailure(422,"子任务动作或预算引用不合法");
        if(action.equals("create")) {
            if(!c.path("task").isObject()||!c.path("checkpoint_id").isNull()||!c.path("message").asText().isEmpty()
                    ||fixed==null||!fixed.isObject()||!fixed.path("task").equals(c.get("task"))
                    ||!fixed.path("source_thread").equals(c.get("parent_thread_id"))
                    ||!fixed.path("checkpoint_id").equals(c.get("parent_checkpoint_id"))
                    ||!fixed.path("root_budget_id").equals(c.get("root_budget_id"))
                    ||!fixed.path("manifest_digest").equals(c.get("manifest_digest"))
                    ||!fixed.path("input_digest").asText().matches("[a-f0-9]{64}"))
                throw new ApiFailure(422,"子任务固定输入不一致");
        } else {
            uuid(c,"checkpoint_id");
            if(!c.path("task").isNull()||(fixed!=null&&!fixed.isNull())
                    ||(action.equals("continue")&&c.path("message").asText().isBlank())
                    ||(action.equals("cancel")&&!c.path("message").asText().isEmpty()))
                throw new ApiFailure(422,"接续不能替换原子任务");
        }
    }
    @PostMapping("/v1/runtime/organization-executions/{execution}/task-commands/claim")
    Object claim(@PathVariable UUID execution,@Valid @RequestBody Claim input) {
        enabled();validate(input.command(),input.fixed_input(),execution);
        return tx.execute(status->{
            var c=input.command();var root=root(execution,c.path("manifest_digest").asText());
            UUID id=uuid(c,"command_id"),child=uuid(c,"child_thread_id");String action=c.path("action").asText();
            var payload=json.valueToTree(input);String fingerprint=hash(payload);
            var existing=db.queryForList("SELECT * FROM organization_report_command WHERE id=?",id);
            if(!existing.isEmpty()) {
                var old=existing.getFirst();
                if(!"research_task".equals(old.get("command_kind"))||!execution.equals(old.get("execution_id"))||!fingerprint.equals(old.get("fingerprint")))
                    throw new ApiFailure(409,"命令身份已用于其他内容");
                live(execution,child,action.equals("cancel"));return view(old,false);
            }
            var parentRun=uuid(c,"parent_run_id");
            var known=db.queryForList("SELECT run_id FROM organization_native_start WHERE execution_id=? AND run_id=? UNION ALL SELECT run_id FROM organization_native_continuation WHERE execution_id=? AND run_id=? UNION ALL SELECT run_id FROM organization_report_command WHERE command_kind='report' AND execution_id=? AND run_id=?",execution,parentRun,execution,parentRun,execution,parentRun);
            if(known.isEmpty())throw new ApiFailure(409,"父运行未独立准入");
            live(execution,child,action.equals("cancel"));
            if(action.equals("create")) {
                if(db.queryForObject("SELECT count(*) FROM organization_report_command WHERE command_kind='research_task' AND execution_id=? AND task_action='create'",Integer.class,execution)>=4)
                    throw new ApiFailure(409,"本执行已达到宿主子任务上限");
            } else {
                var original=parse(origin(execution,child).get("request_body")).path("command");
                if(!original.path("root_budget_id").equals(c.get("root_budget_id"))||!original.path("manifest_digest").equals(c.get("manifest_digest")))
                    throw new ApiFailure(409,"子任务预算或资料绑定已变化");
                if(action.equals("continue")&&!db.queryForList("SELECT id FROM organization_report_command WHERE command_kind='research_task' AND execution_id=? AND child_thread_id=? AND status='dispatching'",execution,child).isEmpty())
                    throw new ApiFailure(409,"已有未知派发，请先按原命令只读核对，不能另建接续");
            }
            UUID checkpoint=uuid(c,action.equals("create")?"parent_checkpoint_id":"checkpoint_id");
            int inserted=db.update("INSERT INTO organization_report_command(id,execution_id,operation_id,principal,fingerprint,checkpoint_id,request_body,command_kind,child_thread_id,task_action,status) VALUES(?,?,?,?,?,?,?,'research_task',?,?,'dispatching') ON CONFLICT DO NOTHING",
                id,execution,UUID.randomUUID(),root.get("principal"),fingerprint,checkpoint,payload.toString(),child,action);
            if(inserted!=1)throw new ApiFailure(409,"该子任务或版本已存在命令，请只读核对");
            return view(row(execution,id),true);
        });
    }
    @PostMapping("/v1/runtime/organization-executions/{execution}/task-commands/read")
    Object read(@PathVariable UUID execution,@Valid @RequestBody Lookup input) {
        enabled();return tx.execute(status->{
            root(execution,input.manifest_digest());
            var c=input.command_id()==null?origin(execution,input.child_thread_id()):row(execution,input.command_id());
            if(!input.child_thread_id().equals(c.get("child_thread_id")))throw new ApiFailure(404,"子任务身份不匹配");
            return view(c,false);
        });
    }
    @PostMapping("/v1/runtime/organization-executions/{execution}/task-commands/catalog")
    Object catalog(@PathVariable UUID execution,@Valid @RequestBody Catalog input) {
        enabled();return tx.execute(status->{
            root(execution,input.manifest_digest());
            return db.queryForList("""
                SELECT c.id AS create_command_id,c.child_thread_id,l.id AS command_id,
                       l.operation_id,l.task_action,l.status,l.run_id
                FROM organization_report_command c
                JOIN LATERAL (SELECT * FROM organization_report_command x
                    WHERE x.command_kind='research_task' AND x.execution_id=c.execution_id
                    AND x.child_thread_id=c.child_thread_id ORDER BY x.command_sequence DESC LIMIT 1) l ON true
                WHERE c.command_kind='research_task' AND c.execution_id=? AND c.task_action='create'
                ORDER BY c.command_sequence
                """,execution);
        });
    }
    @PostMapping("/v1/runtime/organization-executions/{execution}/task-commands/admit")
    Object admit(@PathVariable UUID execution,@Valid @RequestBody Lookup input) {
        enabled();return tx.execute(status->{
            root(execution,input.manifest_digest());var c=row(execution,input.command_id());
            if(!input.child_thread_id().equals(c.get("child_thread_id"))||"cancel".equals(c.get("task_action"))||input.run_id()==null)
                throw new ApiFailure(409,"子运行身份不匹配");
            live(execution,input.child_thread_id(),false);
            if(db.update("UPDATE organization_report_command SET run_id=?,updated_at=now() WHERE id=? AND (run_id IS NULL OR run_id=?)",input.run_id(),input.command_id(),input.run_id())!=1)
                throw new ApiFailure(409,"该命令已绑定另一运行");
            return view(row(execution,input.command_id()),false);
        });
    }
    @PostMapping("/v1/runtime/organization-executions/{execution}/task-commands/accept")
    Object accept(@PathVariable UUID execution,@Valid @RequestBody Lookup input) {
        enabled();return tx.execute(status->{
            root(execution,input.manifest_digest());var c=row(execution,input.command_id());var r=input.receipt();
            if(r==null||!input.child_thread_id().equals(c.get("child_thread_id"))||!input.child_thread_id().equals(uuid(r,"thread_id")))
                throw new ApiFailure(409,"子任务回执身份不匹配");
            UUID run="cancel".equals(c.get("task_action"))?null:uuid(r,"run_id");
            if(run==null&&!"cancelled".equals(r.path("status").asText()))throw new ApiFailure(409,"停止回执不匹配");
            // Accept records transport evidence, never revives a cancelled task.
            // Subsequent admit checks the durable cancel command independently.
            if(c.get("response")!=null) {
                var previous=parse(c.get("response"));
                if(!previous.path("thread_id").equals(r.path("thread_id"))||!previous.path("run_id").equals(r.path("run_id")))
                    throw new ApiFailure(409,"重复回执改变了运行身份");
            }
            if(db.update("UPDATE organization_report_command SET status='received',run_id=?,response=?::jsonb,updated_at=now() WHERE id=? AND (run_id IS NULL OR run_id=?)",run,r.toString(),input.command_id(),run)!=1)
                throw new ApiFailure(409,"回执与已绑定运行不匹配");
            return view(row(execution,input.command_id()),false);
        });
    }
}
