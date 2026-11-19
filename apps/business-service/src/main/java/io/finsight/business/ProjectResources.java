package io.finsight.business;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;
import java.util.*;

/** References existing publications. A project link never grants source access. */
@RestController
@RequestMapping("/v1/workspaces/projects/{projectId}/resources")
@Validated
class ProjectResources {
    record Change(@Min(1) int revision, @NotNull Boolean linked) {}
    private final JdbcTemplate db;
    private final OrganizationProjects projects;
    private final ObjectMapper json;
    private final TransactionTemplate tx;
    ProjectResources(JdbcTemplate db, OrganizationProjects projects, ObjectMapper json, PlatformTransactionManager manager) {
        this.db=db;this.projects=projects;this.json=json;this.tx=new TransactionTemplate(manager);
    }
    // Used by both project and space catalogs, before LIMIT/OFFSET. No hidden-title placeholders/counts.
    static final String SOURCE_ACCESS="""
        EXISTS (SELECT 1 FROM organization_member rm
          WHERE rm.organization_id=s.organization_id AND rm.subject=? AND rm.active
            AND ((s.kind='personal' AND s.principal=rm.subject)
              OR (s.kind='team' AND (rm.role='admin' OR EXISTS
                (SELECT 1 FROM space_member sm WHERE sm.space_id=s.id AND sm.subject=rm.subject)))))
        """;
    static final String LINK_ACCESS="EXISTS (SELECT 1 FROM organization_project_resource pr WHERE pr.resource_id=r.id AND pr.project_id=? AND EXISTS ("
        +OrganizationProjects.VISIBLE+" AND p.id=pr.project_id))";
    private String actor(HttpServletRequest request) {
        String actor=(String)request.getAttribute("owner");
        if(actor==null||actor.equals("local-pilot"))throw new ApiFailure(403,"组织项目需要独立登录身份");
        return actor;
    }
    private Map<String,Object> one(String sql,Object...args) {
        return db.queryForList(sql,args).stream().findFirst().orElseThrow(()->new ApiFailure(404,"项目资料不可访问"));
    }
    @GetMapping
    Object list(HttpServletRequest request,@PathVariable UUID projectId,
                @RequestParam(defaultValue="") @Size(max=200) String query,
                @RequestParam(defaultValue="") @Pattern(regexp="|files|knowledge|database") String type,
                @RequestParam(defaultValue="0") @Min(0) @Max(100000) int offset) {
        String actor=actor(request);projects.project(actor,projectId,false);
        var rows=db.queryForList("""
            SELECT r.id,r.space_id,s.name AS space_name,r.title,r.resource_type,r.revision,r.created_at,
              r.binding->'ref'->>'version_id' AS version_id
            FROM space_resource r JOIN resource_space s ON s.id=r.space_id
            WHERE r.active AND
            """+SOURCE_ACCESS+" AND "+LINK_ACCESS+
            " AND position(lower(?) in lower(r.title))>0 AND (?='' OR r.resource_type=?) ORDER BY r.created_at DESC,r.id LIMIT 31 OFFSET ?",
            actor,projectId,actor,query,type,type,offset);
        var result=new HashMap<String,Object>();result.put("items",rows.stream().limit(30).toList());
        result.put("next_offset",rows.size()>30?offset+30:null);return result;
    }
    @PostMapping("/{resourceId}")
    Object change(HttpServletRequest request,@PathVariable UUID projectId,@PathVariable UUID resourceId,@Valid @RequestBody Change body) {
        String actor=actor(request);
        return tx.execute(status->{
            var project=projects.locked(actor,projectId,body.revision());
            if(Boolean.TRUE.equals(project.get("archived")))throw new ApiFailure(409,"归档项目只读，请先恢复项目");
            if(body.linked()) {
                var resource=one("SELECT space_id FROM space_resource WHERE id=?",resourceId);
                // Same space lock as membership changes, then the publication lock used by revoke.
                one("SELECT id FROM resource_space WHERE id=? FOR UPDATE",resource.get("space_id"));
                one("SELECT id FROM space_resource WHERE id=? FOR UPDATE",resourceId);
                var source=one("SELECT r.space_id,s.organization_id,s.kind FROM space_resource r JOIN resource_space s ON s.id=r.space_id WHERE r.id=? AND r.active AND "+SOURCE_ACCESS,resourceId,actor);
                if(!project.get("organization_id").equals(source.get("organization_id")))throw new ApiFailure(404,"项目资料不可访问");
                if(!source.get("kind").equals("team"))throw new ApiFailure(409,"个人区资料请先明确发布至团队空间，再关联项目");
                db.update("INSERT INTO organization_project_resource(project_id,organization_id,space_id,resource_id,linked_by) VALUES(?,?,?,?,?) ON CONFLICT DO NOTHING",
                    projectId,project.get("organization_id"),source.get("space_id"),resourceId,actor);
            } else {
                // Removal changes only this project's link, including a known but now inaccessible source.
                db.update("DELETE FROM organization_project_resource WHERE project_id=? AND resource_id=?",projectId,resourceId);
            }
            db.update("UPDATE organization_project SET revision=revision+1,updated_at=now() WHERE id=?",projectId);
            db.update("INSERT INTO organization_project_audit(project_id,actor,action,target,revision) VALUES(?,?,?,?,?)",
                projectId,actor,body.linked()?"resource_link":"resource_unlink",resourceId.toString(),body.revision()+1);
            return Map.of("revision",body.revision()+1,"linked",body.linked());
        });
    }
    // Binding is private to the signed BFF read endpoint, never the browser business proxy.
    @PostMapping("/{resourceId}/access")
    Object access(HttpServletRequest request,@PathVariable UUID projectId,@PathVariable UUID resourceId) {
        String actor=actor(request);
        var row=one("SELECT r.revision,r.binding::text AS encoded,s.organization_id FROM space_resource r JOIN resource_space s ON s.id=r.space_id WHERE r.id=? AND r.active AND "+SOURCE_ACCESS+" AND "+LINK_ACCESS,
            resourceId,actor,projectId,actor);
        try {
            db.update("INSERT INTO organization_project_audit(project_id,actor,action,target,revision) SELECT id,?,'resource_read',?,revision FROM organization_project WHERE id=?",actor,resourceId.toString(),projectId);
            return Map.of("id",resourceId,"project_id",projectId,"organization_id",row.get("organization_id"),"revision",row.get("revision"),"binding",json.readTree((String)row.get("encoded")));
        } catch(java.io.IOException e){throw new IllegalStateException(e);}
    }
}
