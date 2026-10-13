package io.finsight.business;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.*;

/** Sole authority for NEW organization projects. Legacy personal projects stay in Python. */
@RestController
@RequestMapping("/v1/workspaces/projects")
@Validated
class OrganizationProjects {
    record Create(@NotNull UUID id, @NotNull UUID organization_id,
                  @NotBlank @Size(max=60) String name, @NotNull @Size(max=500) String description) {}
    record Edit(@Min(1) int revision, @NotBlank @Size(max=60) String name,
                @NotNull @Size(max=500) String description, @NotNull Boolean archived) {}
    record Member(@Min(1) int revision, @NotBlank @Size(max=240) String subject,
                  @NotNull @Pattern(regexp="manager|researcher|viewer|remove") String role) {}
    private final JdbcTemplate db;
    private final ObjectMapper json;
    private final TransactionTemplate tx;
    OrganizationProjects(JdbcTemplate db,ObjectMapper json,PlatformTransactionManager manager) {
        this.db=db;this.json=json;this.tx=new TransactionTemplate(manager);
    }
    private String actor(HttpServletRequest r) {
        String actor=(String)r.getAttribute("owner");
        if(actor==null||actor.equals("local-pilot"))throw new ApiFailure(403,"组织项目需要独立登录身份");
        return actor;
    }
    private Map<String,Object> one(String sql,Object... args) {
        return db.queryForList(sql,args).stream().findFirst().orElseThrow(()->new ApiFailure(404,"项目或成员不可访问"));
    }
    // One query authorizes the current membership and returns only project metadata.
    private static final String VISIBLE="""
        SELECT p.id,p.organization_id,p.name,p.description,p.archived,p.revision,p.created_at,p.updated_at,
          o.name AS organization_name,
          CASE WHEN om.role='admin' THEN 'manager' ELSE pm.role END AS role,
          (om.role='admin' OR pm.role='manager') AS can_manage
        FROM organization_project p JOIN resource_organization o ON o.id=p.organization_id
        JOIN organization_member om ON om.organization_id=p.organization_id AND om.subject=? AND om.active
        LEFT JOIN organization_project_member pm ON pm.project_id=p.id AND pm.subject=om.subject
        WHERE (om.role='admin' OR pm.subject IS NOT NULL)
        """;
    private Map<String,Object> project(String actor,UUID id,boolean manage) {
        var row=one(VISIBLE+" AND p.id=?",actor,id);
        if(manage&&!Boolean.TRUE.equals(row.get("can_manage")))throw new ApiFailure(403,"需要项目管理权限");
        // Roles define the intended business policy; shared research is not enabled yet.
        row.put("research_enabled",false);
        return row;
    }
    private void organizationLock(UUID id) {
        // Same lock as organization removal; mutations cannot authorize against a departing member.
        one("SELECT id FROM resource_organization WHERE id=? FOR UPDATE",id);
    }
    private Map<String,Object> locked(String actor,UUID id,int revision) {
        UUID org=(UUID)one("SELECT organization_id FROM organization_project WHERE id=?",id).get("organization_id");
        organizationLock(org);
        one("SELECT id FROM organization_project WHERE id=? FOR UPDATE",id);
        var row=project(actor,id,true);
        if(((Number)row.get("revision")).intValue()!=revision)throw new ApiFailure(409,"项目已更新，请重新读取后再修改；未自动重试");
        return row;
    }
    private void audit(UUID id,String actor,String action,String target,int revision) {
        db.update("INSERT INTO organization_project_audit(project_id,actor,action,target,revision) VALUES(?,?,?,?,?)",id,actor,action,target,revision);
    }
    @GetMapping
    Object list(HttpServletRequest r,@RequestParam(required=false) UUID organization_id,
                @RequestParam(defaultValue="false") boolean archived,
                @RequestParam(defaultValue="") @Size(max=200) String query,
                @RequestParam(defaultValue="0") @Min(0) @Max(100000) int offset) {
        String actor=actor(r);
        String sql=VISIBLE+" AND p.archived=? AND position(lower(?) in lower(p.name||' '||p.description))>0";
        var args=new ArrayList<Object>(List.of(actor,archived,query));
        if(organization_id!=null){sql+=" AND p.organization_id=?";args.add(organization_id);}
        args.add(offset);
        var rows=db.queryForList(sql+" ORDER BY p.created_at DESC,p.id LIMIT 31 OFFSET ?",args.toArray());
        var result=new HashMap<String,Object>();result.put("items",rows.stream().limit(30).toList());
        result.put("next_offset",rows.size()>30?offset+30:null);return result;
    }
    @GetMapping("/{id}")
    Object get(HttpServletRequest r,@PathVariable UUID id){return project(actor(r),id,false);}
    @PostMapping
    Object create(HttpServletRequest r,@Valid @RequestBody Create body) {
        String actor=actor(r);
        return tx.execute(status->{
            organizationLock(body.organization_id());
            var member=one("SELECT role FROM organization_member WHERE organization_id=? AND subject=? AND active",body.organization_id(),actor);
            if(!member.get("role").equals("admin"))throw new ApiFailure(403,"由组织管理员创建组织项目");
            String digest;
            try{digest=Delegation.digest(json.writeValueAsBytes(body));}catch(Exception e){throw new IllegalStateException(e);}
            int inserted=db.update("INSERT INTO organization_project(id,organization_id,name,description,created_by,creation_digest) VALUES(?,?,?,?,?,?) ON CONFLICT DO NOTHING",
                body.id(),body.organization_id(),body.name().trim(),body.description().trim(),actor,digest);
            var saved=one("SELECT organization_id,created_by,creation_digest FROM organization_project WHERE id=?",body.id());
            if(!body.organization_id().equals(saved.get("organization_id"))||!actor.equals(saved.get("created_by"))||!digest.equals(saved.get("creation_digest")))throw new ApiFailure(409,"项目创建标识已用于另一项提交");
            if(inserted==1)audit(body.id(),actor,"create",body.id().toString(),1);
            return project(actor,body.id(),false);
        });
    }
    @PostMapping("/{id}")
    Object edit(HttpServletRequest r,@PathVariable UUID id,@Valid @RequestBody Edit body) {
        String actor=actor(r);return tx.execute(status->{
            locked(actor,id,body.revision());
            db.update("UPDATE organization_project SET name=?,description=?,archived=?,revision=revision+1,updated_at=now() WHERE id=?",body.name().trim(),body.description().trim(),body.archived(),id);
            audit(id,actor,"edit",id.toString(),body.revision()+1);return project(actor,id,false);
        });
    }
    @GetMapping("/{id}/members")
    Object members(HttpServletRequest r,@PathVariable UUID id) {
        String actor=actor(r);project(actor,id,false);
        // Administrator access is organization-wide and explicit, not a second mutable project role.
        return db.queryForList("""
            SELECT om.subject,om.display_name,
              CASE WHEN om.role='admin' THEN 'manager' ELSE pm.role END AS role,
              (om.role='admin') AS organization_admin
            FROM organization_project p JOIN organization_member om ON om.organization_id=p.organization_id AND om.active
            LEFT JOIN organization_project_member pm ON pm.project_id=p.id AND pm.subject=om.subject
            WHERE p.id=? AND (om.role='admin' OR pm.subject IS NOT NULL)
              AND EXISTS (SELECT 1 FROM organization_member caller
                LEFT JOIN organization_project_member cp ON cp.project_id=p.id AND cp.subject=caller.subject
                WHERE caller.organization_id=p.organization_id AND caller.subject=? AND caller.active
                  AND (caller.role='admin' OR cp.subject IS NOT NULL))
            ORDER BY om.display_name,om.subject
            """,id,actor);
    }
    @PostMapping("/{id}/members")
    Object setMember(HttpServletRequest r,@PathVariable UUID id,@Valid @RequestBody Member body) {
        String actor=actor(r);return tx.execute(status->{
            var p=locked(actor,id,body.revision());UUID org=(UUID)p.get("organization_id");
            // Removal may clean an inactive member; grants always require current organization membership.
            var target=one("SELECT role,active FROM organization_member WHERE organization_id=? AND subject=?",org,body.subject());
            if(target.get("role").equals("admin"))throw new ApiFailure(409,"组织管理员的项目权限由组织角色决定");
            if(body.role().equals("remove"))db.update("DELETE FROM organization_project_member WHERE project_id=? AND subject=?",id,body.subject());
            else {
                if(!Boolean.TRUE.equals(target.get("active")))throw new ApiFailure(404,"成员已离开组织");
                db.update("INSERT INTO organization_project_member VALUES(?,?,?,?) ON CONFLICT(project_id,subject) DO UPDATE SET role=excluded.role",id,org,body.subject(),body.role());
            }
            db.update("UPDATE organization_project SET revision=revision+1,updated_at=now() WHERE id=?",id);
            audit(id,actor,"member_"+body.role(),body.subject(),body.revision()+1);
            return Map.of("id",id,"revision",body.revision()+1);
        });
    }
}
