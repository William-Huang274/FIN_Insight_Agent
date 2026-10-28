package io.finsight.business;

import com.fasterxml.jackson.databind.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.bind.annotation.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** One durable native draft command per binding; never starts or retries a run. */
@RestController
@RequestMapping("/v1/workspaces/projects/{project}/execution-bindings/{id}")
class OrganizationNativeDrafts {
    record Prepare(@NotNull @Valid ResearchTasks.Execution execution) {}
    private final JdbcTemplate db;
    private final OrganizationExecutionBindings bindings;
    private final PythonIntake python;
    private final ObjectMapper json;
    private final TransactionTemplate tx;
    OrganizationNativeDrafts(JdbcTemplate db,OrganizationExecutionBindings bindings,PythonIntake python,ObjectMapper json,PlatformTransactionManager manager) {
        this.db=db;this.bindings=bindings;this.python=python;this.json=json;this.tx=new TransactionTemplate(manager);
    }
    private Map<String,Object> command(UUID id) {
        return db.queryForList("SELECT *,response::text AS result FROM organization_native_preparation WHERE execution_id=?",id).stream()
            .findFirst().orElseThrow(()->new ApiFailure(404,"原生草稿准备记录不存在"));
    }
    private JsonNode parse(Object value) {
        try {return value==null?null:json.readTree(value.toString());}catch(java.io.IOException e){throw new IllegalStateException(e);}
    }
    private String hash(Object value) {return "sha256:"+Delegation.digest(value.toString().getBytes(StandardCharsets.UTF_8));}
    Map<String,Object> prepared(String actor,UUID project,UUID id) {
        var grant=bindings.preparation(actor,project,id);var c=command(id);
        if(!"received".equals(c.get("status")))throw new ApiFailure(409,"原生草稿尚未确认，不能启动");
        grant.put("prepare_operation_id",c.get("operation_id"));grant.put("prepare_request",parse(c.get("request_body")));
        grant.put("prepare_request_digest",hash(c.get("request_body")));
        grant.put("configuration_digest",parse(c.get("result")).path("configuration_digest").asText());return grant;
    }
    private Object view(UUID id) {
        var c=command(id);var result=new HashMap<String,Object>();result.put("execution_id",id);
        result.put("status",c.get("status").equals("dispatching")?"unknown":c.get("status"));
        result.put("operation_id",c.get("operation_id"));result.put("native_execution_enabled",false);
        result.put("execution",parse(c.get("request_body")).path("execution"));
        if(c.get("result")!=null)result.put("result",parse(c.get("result")));return result;
    }
    @GetMapping("/preparation")
    Object get(HttpServletRequest request,@PathVariable UUID project,@PathVariable UUID id) {
        bindings.preparation((String)request.getAttribute("owner"),project,id);return view(id);
    }
    @GetMapping("/preparation-access")
    Object preparationAccess(HttpServletRequest request,@PathVariable UUID project,@PathVariable UUID id) {
        var grant=bindings.preparation((String)request.getAttribute("owner"),project,id);var c=command(id);
        grant.put("prepare_operation_id",c.get("operation_id"));grant.put("prepare_request",parse(c.get("request_body")));
        grant.put("prepare_request_digest",hash(c.get("request_body")));return grant;
    }
    @PostMapping("/prepare")
    Object prepare(HttpServletRequest request,@PathVariable UUID project,@PathVariable UUID id,@Valid @RequestBody Prepare input) {
        input.execution().requireReportWorkflow();
        String actor=(String)request.getAttribute("owner"),fingerprint=Delegation.digest((byte[])request.getAttribute("originalBody"));
        tx.executeWithoutResult(status->{
            var grant=bindings.preparation(actor,project,id);
            var payload=json.createObjectNode().put("contract_version","organization_native_preparation.v1")
                .put("execution_id",id.toString()).put("project_id",project.toString()).put("manifest_digest",grant.get("manifest_digest").toString());
            payload.set("execution",json.valueToTree(input.execution()));
            int inserted=db.update("INSERT INTO organization_native_preparation(execution_id,operation_id,fingerprint,request_body) VALUES(?,?,?,?) ON CONFLICT DO NOTHING",id,UUID.randomUUID(),fingerprint,payload.toString());
            if(!command(id).get("fingerprint").equals(fingerprint))throw new ApiFailure(409,"本执行已固定其他准备内容，请核对原记录");
            if(inserted==1)db.update("INSERT INTO organization_project_audit(project_id,actor,action,target,revision) SELECT id,?,'native_prepare',?,revision FROM organization_project WHERE id=?",actor,id.toString(),project);
        });
        var c=command(id);
        if(db.update("UPDATE organization_native_preparation SET status='dispatching',updated_at=now() WHERE execution_id=? AND status='ready'",id)==1) {
            try {
                var reply=python.request(actor,"POST","organization/prepare",c.get("request_body").toString(),(UUID)c.get("operation_id"));
                accept(id,c,reply.status(),reply.body());
            } catch(IntakeUnavailable e) {complete(id,"unknown",null);}
        }
        // Reauthorize before returning a receipt if access changed during remote I/O.
        bindings.preparation(actor,project,id);return view(id);
    }
    private boolean matches(UUID id,Map<String,Object> c,JsonNode result) {
        var payload=parse(c.get("request_body"));
        return result!=null&&id.toString().equals(result.path("execution_id").asText())&&id.toString().equals(result.path("thread_id").asText())
            &&payload.path("project_id").equals(result.path("project_id"))&&payload.path("manifest_digest").equals(result.path("manifest_digest"))
            &&c.get("operation_id").toString().equals(result.path("prepare_operation_id").asText())
            &&hash(c.get("request_body")).equals(result.path("prepare_request_digest").asText())
            &&"draft".equals(result.path("status").asText())&&result.path("native_execution_enabled").isBoolean()&&!result.path("native_execution_enabled").asBoolean()
            &&result.path("configuration_digest").asText().matches("sha256:[a-f0-9]{64}");
    }
    private void complete(UUID id,String status,JsonNode response) {
        db.update("UPDATE organization_native_preparation SET status=?,response=?::jsonb,updated_at=now() WHERE execution_id=? AND status IN ('dispatching','unknown')",status,response==null?null:response.toString(),id);
    }
    private void accept(UUID id,Map<String,Object> c,int status,JsonNode result) {
        if(status==200&&matches(id,c,result))complete(id,"received",result);
        else if(status>=400&&status<500&&!(result!=null&&"unknown".equals(result.path("submission_status").asText())))complete(id,"rejected",result);
        else complete(id,"unknown",null);
    }
    @PostMapping("/reconcile")
    Object reconcile(HttpServletRequest request,@PathVariable UUID project,@PathVariable UUID id) {
        String actor=(String)request.getAttribute("owner");bindings.preparation(actor,project,id);var c=command(id);
        if(Set.of("dispatching","unknown").contains(c.get("status"))) {
            var result=python.request(actor,"GET","organization/executions/"+id+"/state?project_id="+project,null,null);
            // Absence/failure is not proof of rejection; never clear or redispatch.
            if(result.status()==200&&matches(id,c,result.body()))complete(id,"received",result.body());
        }
        bindings.preparation(actor,project,id);return view(id);
    }
}
