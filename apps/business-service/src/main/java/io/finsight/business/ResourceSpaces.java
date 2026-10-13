package io.finsight.business;

import com.fasterxml.jackson.databind.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.web.bind.annotation.*;
import org.springframework.validation.annotation.Validated;
import java.util.*;
import java.nio.charset.StandardCharsets;

/** Business authority only. Bodies and indexes remain in the Python asset store. */
@RestController
@RequestMapping("/v1/workspaces")
@Validated
class ResourceSpaces {
    record Named(@NotNull UUID id,@NotBlank @Size(max=120) String name,@NotBlank @Size(max=80) String display_name) {}
    record Team(@NotNull UUID id,@NotNull UUID organization_id,@NotBlank @Size(max=120) String name) {}
    record Invite(@NotNull UUID token) {}
    record Join(@NotNull UUID token,@NotBlank @Size(max=80) String display_name) {}
    record Member(@NotBlank @Size(max=240) String subject,@NotNull @Pattern(regexp="manager|reader|remove") String role) {}
    record Depart(@NotBlank @Size(max=240) String subject) {}
    record Access(@NotNull @Pattern(regexp="read|publish") String action) {}
    record Publish(@NotNull UUID id,@NotNull UUID space_id,@NotBlank @Size(max=180) String title,
                   @NotNull @Pattern(regexp="files|knowledge|database") String resource_type,@NotNull JsonNode binding) {}
    record Revoke(@Min(1) int revision) {}
    private final JdbcTemplate db;
    private final ObjectMapper json;
    private final TransactionTemplate tx;
    ResourceSpaces(JdbcTemplate db,ObjectMapper json,PlatformTransactionManager manager) {this.db=db;this.json=json;tx=new TransactionTemplate(manager);}
    private String owner(HttpServletRequest r) {
        String subject=(String)r.getAttribute("owner");
        if(subject==null||subject.equals("local-pilot"))throw new ApiFailure(403,"组织空间需要独立登录身份");
        return subject;
    }
    private Map<String,Object> one(String sql,Object... args) {
        return db.queryForList(sql,args).stream().findFirst().orElseThrow(()->new ApiFailure(404,"空间或资源不可访问"));
    }
    private Map<String,Object> organization(String actor,UUID id,boolean admin) {
        var m=one("SELECT o.*,m.role FROM resource_organization o JOIN organization_member m ON m.organization_id=o.id WHERE o.id=? AND m.subject=? AND m.active",id,actor);
        if(admin&&!m.get("role").equals("admin"))throw new ApiFailure(403,"需要组织管理权限");
        return m;
    }
    private Map<String,Object> space(String actor,UUID id,boolean manage) {
        var s=one("SELECT * FROM resource_space WHERE id=?",id);
        var org=organization(actor,(UUID)s.get("organization_id"),false);
        boolean personal=s.get("kind").equals("personal"),manager;
        if(personal) {if(!actor.equals(s.get("principal")))throw new ApiFailure(404,"空间不可访问");manager=true;}
        else if(org.get("role").equals("admin"))manager=true;
        else manager=one("SELECT role FROM space_member WHERE space_id=? AND subject=?",id,actor).get("role").equals("manager");
        if(manage&&!manager)throw new ApiFailure(403,"需要空间管理权限");
        s.put("can_manage",manager);s.put("organization_name",org.get("name"));s.put("organization_admin",org.get("role").equals("admin"));
        s.remove("principal");return s;
    }
    private void audit(UUID org,String actor,String action,Object target) {
        db.update("INSERT INTO resource_space_audit(organization_id,actor,action,target) VALUES(?,?,?,?)",org,actor,action,target.toString());
    }
    private void personal(UUID org,String actor) {
        UUID id=UUID.nameUUIDFromBytes(("personal:"+org+":"+actor).getBytes(StandardCharsets.UTF_8));
        db.update("INSERT INTO resource_space(id,organization_id,name,kind,principal) VALUES(?,?,?,'personal',?) ON CONFLICT DO NOTHING",id,org,"我的工作区",actor);
    }
    @GetMapping
    Object list(HttpServletRequest r) {
        String actor=owner(r);
        var ids=db.queryForList("SELECT s.id FROM resource_space s JOIN organization_member m ON m.organization_id=s.organization_id AND m.subject=? AND m.active WHERE (s.kind='personal' AND s.principal=?) OR (s.kind='team' AND (m.role='admin' OR EXISTS(SELECT 1 FROM space_member sm WHERE sm.space_id=s.id AND sm.subject=?))) ORDER BY s.kind,s.name,s.id",UUID.class,actor,actor,actor);
        return Map.of("spaces",ids.stream().map(id->space(actor,id,false)).toList(),"organizations",db.queryForList("SELECT o.id,o.name,m.role FROM resource_organization o JOIN organization_member m ON m.organization_id=o.id WHERE m.subject=? AND m.active ORDER BY o.name,o.id",actor));
    }
    @PostMapping("/organizations")
    Object create(HttpServletRequest r,@Valid @RequestBody Named body) {
        String actor=owner(r);return tx.execute(status->{
            db.update("INSERT INTO resource_organization(id,name,created_by) VALUES(?,?,?) ON CONFLICT DO NOTHING",body.id(),body.name(),actor);
            var prior=one("SELECT * FROM resource_organization WHERE id=? FOR UPDATE",body.id());
            if(!actor.equals(prior.get("created_by"))||!body.name().equals(prior.get("name")))throw new ApiFailure(409,"组织创建标识已使用");
            db.update("INSERT INTO organization_member VALUES(?,?,?,'admin',true) ON CONFLICT DO NOTHING",body.id(),actor,body.display_name());
            organization(actor,body.id(),true);personal(body.id(),actor);audit(body.id(),actor,"organization_create",body.id());return list(r);
        });
    }
    @GetMapping("/organizations/{id}/members")
    Object members(HttpServletRequest r,@PathVariable UUID id) {organization(owner(r),id,false);return db.queryForList("SELECT subject,display_name,role,active FROM organization_member WHERE organization_id=? ORDER BY display_name,subject",id);}
    @PostMapping("/organizations/{id}/invites")
    Object invite(HttpServletRequest r,@PathVariable UUID id,@Valid @RequestBody Invite body) {
        String actor=owner(r);return tx.execute(status->{organization(actor,id,true);
            String hash=Delegation.digest(body.token().toString().getBytes(StandardCharsets.UTF_8));
            db.update("INSERT INTO organization_invite(token_hash,organization_id) VALUES(?,?) ON CONFLICT DO NOTHING",hash,id);
            var invite=one("SELECT organization_id FROM organization_invite WHERE token_hash=?",hash);
            if(!id.equals(invite.get("organization_id")))throw new ApiFailure(409,"邀请标识已使用");
            audit(id,actor,"invite_create",id);return Map.of("token",body.token(),"valid_days",7);
        });
    }
    @PostMapping("/join")
    Object join(HttpServletRequest r,@Valid @RequestBody Join body) {
        String actor=owner(r);return tx.execute(status->{
            var invite=one("SELECT * FROM organization_invite WHERE token_hash=? AND expires_at>now() FOR UPDATE",Delegation.digest(body.token().toString().getBytes(StandardCharsets.UTF_8)));
            if(invite.get("used_by")!=null&&!actor.equals(invite.get("used_by")))throw new ApiFailure(409,"邀请已使用");
            UUID org=(UUID)invite.get("organization_id");
            db.update("INSERT INTO organization_member VALUES(?,?,?,'member',true) ON CONFLICT DO NOTHING",org,actor,body.display_name());
            organization(actor,org,false);personal(org,actor);
            db.update("UPDATE organization_invite SET used_by=? WHERE token_hash=?",actor,invite.get("token_hash"));
            audit(org,actor,"member_join",actor);return list(r);
        });
    }
    @PostMapping("/organizations/{id}/remove-member")
    Object remove(HttpServletRequest r,@PathVariable UUID id,@Valid @RequestBody Depart body) {
        String actor=owner(r);return tx.execute(status->{one("SELECT id FROM resource_organization WHERE id=? FOR UPDATE",id);organization(actor,id,true);
            var member=one("SELECT role FROM organization_member WHERE organization_id=? AND subject=? AND active",id,body.subject());
            if(member.get("role").equals("admin"))throw new ApiFailure(409,"本批保留组织管理员；管理员交接尚未开放");
            db.update("UPDATE organization_member SET active=false WHERE organization_id=? AND subject=?",id,body.subject());
            audit(id,actor,"member_remove",body.subject());return Map.of("removed",true);
        });
    }
    @PostMapping("/spaces")
    Object createSpace(HttpServletRequest r,@Valid @RequestBody Team body) {
        String actor=owner(r);return tx.execute(status->{organization(actor,body.organization_id(),true);
            db.update("INSERT INTO resource_space(id,organization_id,name,kind) VALUES(?,?,?,'team') ON CONFLICT DO NOTHING",body.id(),body.organization_id(),body.name());
            var s=space(actor,body.id(),true);
            if(!body.organization_id().equals(s.get("organization_id"))||!body.name().equals(s.get("name"))||!s.get("kind").equals("team"))throw new ApiFailure(409,"空间创建标识已使用");
            audit(body.organization_id(),actor,"space_create",body.id());return s;
        });
    }
    @GetMapping("/spaces/{id}/members")
    Object spaceMembers(HttpServletRequest r,@PathVariable UUID id) {space(owner(r),id,true);return db.queryForList("SELECT sm.subject,m.display_name,sm.role FROM space_member sm JOIN resource_space s ON s.id=sm.space_id JOIN organization_member m ON m.organization_id=s.organization_id AND m.subject=sm.subject WHERE sm.space_id=? AND m.active ORDER BY m.display_name",id);}
    @PostMapping("/spaces/{id}/members")
    Object setMember(HttpServletRequest r,@PathVariable UUID id,@Valid @RequestBody Member body) {
        String actor=owner(r);return tx.execute(status->{one("SELECT id FROM resource_space WHERE id=? FOR UPDATE",id);var s=space(actor,id,true);
            if(!s.get("kind").equals("team"))throw new ApiFailure(409,"个人区不直接添加成员，请发布至团队空间");
            UUID org=(UUID)s.get("organization_id");organization(body.subject(),org,false);
            if(body.role().equals("remove"))db.update("DELETE FROM space_member WHERE space_id=? AND subject=?",id,body.subject());
            else db.update("INSERT INTO space_member VALUES(?,?,?) ON CONFLICT(space_id,subject) DO UPDATE SET role=excluded.role",id,body.subject(),body.role());
            audit(org,actor,"space_member_"+body.role(),body.subject());return spaceMembers(r,id);
        });
    }
    // These binding endpoints are not exposed by the public BFF proxy.
    @PostMapping("/spaces/{id}/access")
    Object access(HttpServletRequest r,@PathVariable UUID id,@Valid @RequestBody Access body) {return space(owner(r),id,body.action().equals("publish"));}
    @PostMapping("/resources")
    Object publish(HttpServletRequest r,@Valid @RequestBody Publish body) {
        String actor=owner(r);return tx.execute(status->{var s=space(actor,body.space_id(),true);UUID org=(UUID)s.get("organization_id");
            if(!org.toString().equals(body.binding().path("organization_id").asText())||!body.space_id().toString().equals(body.binding().path("space_id").asText()))throw new ApiFailure(422,"发布范围不匹配");
            db.update("INSERT INTO space_resource(id,space_id,created_by,title,resource_type,binding) VALUES(?,?,?,?,?,?::jsonb) ON CONFLICT DO NOTHING",body.id(),body.space_id(),actor,body.title(),body.resource_type(),body.binding().toString());
            var saved=one("SELECT *,binding::text AS encoded FROM space_resource WHERE id=?",body.id());
            try {if(!actor.equals(saved.get("created_by"))||!body.space_id().equals(saved.get("space_id"))||!body.title().equals(saved.get("title"))||!body.resource_type().equals(saved.get("resource_type"))||!body.binding().equals(json.readTree((String)saved.get("encoded"))))throw new ApiFailure(409,"发布标识已用于另一版本");}
            catch(java.io.IOException e){throw new IllegalStateException(e);}
            if(!Boolean.TRUE.equals(saved.get("active")))throw new ApiFailure(409,"发布已撤销，不能通过重试恢复");
            audit(org,actor,"resource_publish",body.id());return Map.of("id",body.id(),"revision",saved.get("revision"));
        });
    }
    @GetMapping("/spaces/{id}/resources")
    Object resources(HttpServletRequest r,@PathVariable UUID id,@RequestParam(defaultValue="") @Size(max=200) String query,
                     @RequestParam(defaultValue="") @Pattern(regexp="|files|knowledge|database") String type,@RequestParam(defaultValue="0") @Min(0) @Max(100000) int offset) {
        space(owner(r),id,false);
        var rows=db.queryForList("SELECT id,space_id,title,resource_type,revision,created_at FROM space_resource WHERE space_id=? AND active AND position(lower(?) in lower(title))>0 AND (?='' OR resource_type=?) ORDER BY created_at DESC,id LIMIT 31 OFFSET ?",id,query,type,type,offset);
        var result=new HashMap<String,Object>();result.put("items",rows.stream().limit(30).toList());result.put("next_offset",rows.size()>30?offset+30:null);return result;
    }
    @PostMapping("/resources/{id}/access")
    Object readAccess(HttpServletRequest r,@PathVariable UUID id) {
        String actor=owner(r);var row=one("SELECT *,binding::text AS encoded FROM space_resource WHERE id=? AND active",id);
        var s=space(actor,(UUID)row.get("space_id"),false);
        try {audit((UUID)s.get("organization_id"),actor,"resource_read",id);return Map.of("id",id,"revision",row.get("revision"),"binding",json.readTree((String)row.get("encoded")));}
        catch(java.io.IOException e){throw new IllegalStateException(e);}
    }
    @PostMapping("/resources/{id}/revoke")
    Object revoke(HttpServletRequest r,@PathVariable UUID id,@Valid @RequestBody Revoke body) {
        String actor=owner(r);return tx.execute(status->{var row=one("SELECT * FROM space_resource WHERE id=? FOR UPDATE",id);var s=space(actor,(UUID)row.get("space_id"),true);
            if(((Number)row.get("revision")).intValue()!=body.revision())throw new ApiFailure(409,"资源已更新，请重新读取");
            db.update("UPDATE space_resource SET active=false,revision=revision+1 WHERE id=?",id);audit((UUID)s.get("organization_id"),actor,"resource_revoke",id);return Map.of("revoked",true);
        });
    }
}
