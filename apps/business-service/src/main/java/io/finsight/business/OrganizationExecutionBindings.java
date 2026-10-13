package io.finsight.business;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.bind.annotation.*;
import java.util.*;

/** Internal preparation for scoped tools. Does not dispatch or authorize a native run. */
@RestController
class OrganizationExecutionBindings {
    record Create(@NotNull UUID id,@NotBlank @Pattern(regexp="sha256:[a-f0-9]{64}") String manifest_digest) {}
    record Access(@NotNull UUID thread_id,@NotBlank @Pattern(regexp="sha256:[a-f0-9]{64}") String manifest_digest) {}
    private final JdbcTemplate db;
    private final OrganizationResearchDrafts drafts;
    private final OrganizationProjects projects;
    private final TransactionTemplate tx;
    OrganizationExecutionBindings(JdbcTemplate db,OrganizationResearchDrafts drafts,OrganizationProjects projects,PlatformTransactionManager manager) {
        this.db=db;this.drafts=drafts;this.projects=projects;this.tx=new TransactionTemplate(manager);
    }
    private Map<String,Object> binding(UUID id) {
        return db.queryForList("SELECT b.*,d.project_id,d.organization_id,d.manifest_text,d.title,d.question FROM organization_execution_binding b JOIN organization_research_draft d ON d.id=b.draft_id WHERE b.id=?",id)
            .stream().findFirst().orElseThrow(()->new ApiFailure(404,"执行绑定不可访问"));
    }
    private Map<String,Object> view(Map<String,Object> row) {
        return Map.of("contract_version","organization_execution_binding.v1","execution_id",row.get("id"),
            "thread_id",row.get("id"),"draft_id",row.get("draft_id"),"project_id",row.get("project_id"),
            "organization_id",row.get("organization_id"),"manifest_digest","sha256:"+row.get("manifest_digest"),
            "status",Boolean.TRUE.equals(row.get("closed"))?"closed":"bound","native_execution_enabled",false);
    }
    Map<String,Object> preparation(String actor,UUID project,UUID id) {
        return tx.execute(status->{
            var saved=binding(id);
            if(!project.equals(saved.get("project_id"))||!actor.equals(saved.get("principal")))throw new ApiFailure(404,"执行绑定不可访问");
            var grant=drafts.materialAccess(actor,project,(UUID)saved.get("draft_id"));
            if(Boolean.TRUE.equals(binding(id).get("closed")))throw new ApiFailure(409,"执行绑定已关闭");
            var result=new HashMap<String,Object>(view(saved));
            result.put("manifest_text",saved.get("manifest_text"));result.put("inputs",grant.get("inputs"));
            result.put("title",saved.get("title"));result.put("question",saved.get("question"));return result;
        });
    }
    @PostMapping("/v1/workspaces/projects/{project}/research-drafts/{draft}/execution-bindings")
    Object create(HttpServletRequest request,@PathVariable UUID project,@PathVariable UUID draft,@Valid @RequestBody Create body) {
        String actor=(String)request.getAttribute("owner");
        String digest=Delegation.digest((byte[])request.getAttribute("originalBody"));
        return tx.execute(status->{
            var grant=drafts.materialAccess(actor,project,draft); // Locks organization/project before all binding writes.
            if(!body.manifest_digest().equals(grant.get("manifest_digest")))throw new ApiFailure(409,"准备单输入摘要不匹配");
            int inserted=db.update("INSERT INTO organization_execution_binding(id,draft_id,principal,request_digest,manifest_digest) VALUES(?,?,?,?,?) ON CONFLICT DO NOTHING",
                body.id(),draft,actor,digest,body.manifest_digest().substring(7));
            var saved=binding(body.id());
            if(!draft.equals(saved.get("draft_id"))||!actor.equals(saved.get("principal"))||!digest.equals(saved.get("request_digest")))throw new ApiFailure(409,"执行标识已用于其他绑定");
            if(inserted==1)db.update("INSERT INTO organization_project_audit(project_id,actor,action,target,revision) SELECT id,?,'execution_bind',?,revision FROM organization_project WHERE id=?",actor,body.id().toString(),project);
            return view(saved); // Closed bindings remain closed even after identical replay.
        });
    }
    @PostMapping("/v1/workspaces/projects/{project}/execution-bindings/{id}/close")
    Object close(HttpServletRequest request,@PathVariable UUID project,@PathVariable UUID id) {
        String actor=(String)request.getAttribute("owner");
        return tx.execute(status->{
            var member=projects.researchMember(actor,project,true); // Closing remains possible after project archival.
            var saved=binding(id);
            if(!project.equals(saved.get("project_id")))throw new ApiFailure(404,"执行绑定不可访问");
            if(!actor.equals(saved.get("principal"))&&!Boolean.TRUE.equals(member.get("can_manage")))throw new ApiFailure(403,"需要绑定发起人或项目管理权限");
            if(db.update("UPDATE organization_execution_binding SET closed=true,closed_at=now() WHERE id=? AND NOT closed",id)==1)
                db.update("INSERT INTO organization_project_audit(project_id,actor,action,target,revision) VALUES(?,?,'execution_close',?,?)",project,actor,id.toString(),member.get("revision"));
            return view(binding(id));
        });
    }
    @PostMapping("/v1/runtime/organization-executions/{id}/access")
    Object access(@PathVariable UUID id,@Valid @RequestBody Access body) {
        if(!id.equals(body.thread_id()))throw new ApiFailure(404,"执行绑定不可访问");
        return tx.execute(status->{
            var saved=binding(id);
            if(!body.manifest_digest().equals("sha256:"+saved.get("manifest_digest")))throw new ApiFailure(404,"执行绑定不可访问");
            Map<String,Object> grant;
            try { grant=drafts.materialAccess(saved.get("principal").toString(),(UUID)saved.get("project_id"),(UUID)saved.get("draft_id")); }
            catch(ApiFailure e) { throw new ApiFailure(404,"执行绑定或所选资料当前不可用"); }
            // Close uses the same project lock. Check again after obtaining it.
            if(Boolean.TRUE.equals(binding(id).get("closed")))throw new ApiFailure(404,"执行绑定或所选资料当前不可用");
            var result=new HashMap<String,Object>(view(saved));result.put("manifest_text",saved.get("manifest_text"));
            result.put("inputs",grant.get("inputs"));return result;
        });
    }
}
