package io.finsight.business;

import com.fasterxml.jackson.databind.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;
import java.time.LocalDate;
import java.util.*;

/** Immutable input preparation only. No native thread, queue or execution grant. */
@RestController
@RequestMapping("/v1/workspaces/projects/{projectId}/research-drafts")
@Validated
class OrganizationResearchDrafts {
    record Create(@NotNull UUID id,@NotBlank @Size(max=120) String title,
                  @NotBlank @Size(min=10,max=16000) String question,@NotNull LocalDate research_as_of,
                  @NotNull @Size(min=1,max=12) List<@NotNull UUID> resource_ids) {}
    private final JdbcTemplate db;
    private final OrganizationProjects projects;
    private final ObjectMapper json;
    private final TransactionTemplate tx;
    OrganizationResearchDrafts(JdbcTemplate db,OrganizationProjects projects,ObjectMapper json,PlatformTransactionManager manager) {
        this.db=db;this.projects=projects;this.json=json;this.tx=new TransactionTemplate(manager);
    }
    private String actor(HttpServletRequest request) {
        String actor=(String)request.getAttribute("owner");
        if(actor==null||actor.equals("local-pilot"))throw new ApiFailure(403,"研究准备需要独立登录身份");
        return actor;
    }
    private Map<String,Object> one(String sql,Object...args) {
        return db.queryForList(sql,args).stream().findFirst().orElseThrow(()->new ApiFailure(404,"准备单或所选资料不可访问"));
    }
    private JsonNode parse(Object text) {
        try{return json.readTree(text.toString());}catch(java.io.IOException e){throw new IllegalStateException(e);}
    }
    // One query checks project membership and EVERY frozen source before exposing even a title.
    // NOT EXISTS over an authorized input set also fails closed for null/absent rows.
    private static final String VISIBLE="""
        SELECT d.* FROM organization_research_draft d WHERE d.project_id=? AND EXISTS (
        """+OrganizationProjects.VISIBLE+" AND p.id=d.project_id) AND EXISTS (SELECT 1 FROM organization_research_input present WHERE present.draft_id=d.id) AND NOT EXISTS ("+
        "SELECT 1 FROM organization_research_input i WHERE i.draft_id=d.id AND NOT EXISTS ("+
        "SELECT 1 FROM space_resource r JOIN resource_space s ON s.id=r.space_id " +
        "WHERE r.id=i.resource_id AND r.space_id=i.space_id AND r.active AND r.revision=i.resource_revision AND r.binding=i.binding AND "+
        ProjectResources.SOURCE_ACCESS+" AND "+ProjectResources.LINK_ACCESS+"))";
    private Map<String,Object> draft(String actor,UUID project,UUID id) {
        return one(VISIBLE+" AND d.id=?",project,actor,actor,project,actor,id);
    }
    private Object view(Map<String,Object> row) {
        return Map.of("id",row.get("id"),"project_id",row.get("project_id"),"title",row.get("title"),
            "question",row.get("question"),"manifest",parse(row.get("manifest_text")),
            "manifest_digest","sha256:"+row.get("manifest_digest"),"created_at",row.get("created_at"),
            "status","inputs_saved","execution_enabled",false);
    }
    @GetMapping
    Object list(HttpServletRequest request,@PathVariable UUID projectId,@RequestParam(defaultValue="0") @Min(0) @Max(100000) int offset) {
        String actor=actor(request);projects.project(actor,projectId,false);
        var rows=db.queryForList(VISIBLE+" ORDER BY d.created_at DESC,d.id LIMIT 31 OFFSET ?",projectId,actor,actor,projectId,actor,offset);
        var result=new HashMap<String,Object>();result.put("items",rows.stream().limit(30).map(this::view).toList());
        result.put("next_offset",rows.size()>30?offset+30:null);return result;
    }
    @GetMapping("/{id}")
    Object get(HttpServletRequest request,@PathVariable UUID projectId,@PathVariable UUID id) {return view(draft(actor(request),projectId,id));}
    @PostMapping
    Object create(HttpServletRequest request,@PathVariable UUID projectId,@Valid @RequestBody Create body) {
        String actor=actor(request);
        if(new HashSet<>(body.resource_ids()).size()!=body.resource_ids().size())throw new ApiFailure(422,"不能重复选择资料");
        String digest=Delegation.digest((byte[])request.getAttribute("originalBody"));
        return tx.execute(status->{
            var project=projects.researchPreparation(actor,projectId,true);
            var prior=db.queryForList("SELECT * FROM organization_research_draft WHERE id=?",body.id());
            if(!prior.isEmpty()) {
                var row=prior.getFirst();
                if(!projectId.equals(row.get("project_id"))||!actor.equals(row.get("created_by"))||!digest.equals(row.get("request_digest")))throw new ApiFailure(409,"准备凭证已用于其他提交，请核对原准备单");
                return view(draft(actor,projectId,body.id())); // Replay never refreshes frozen versions or bypasses current ACL.
            }
            var ids=body.resource_ids().stream().sorted().toList();
            // Serialize against source membership/revoke changes, without holding a lock across HTTP.
            var spaces=new TreeSet<UUID>();
            for(UUID id:ids)spaces.add((UUID)one("SELECT space_id FROM space_resource WHERE id=?",id).get("space_id"));
            for(UUID space:spaces)one("SELECT id FROM resource_space WHERE id=? FOR UPDATE",space);
            var sources=new ArrayList<Map<String,Object>>();var inputs=json.createArrayNode();
            for(UUID id:ids) {
                one("SELECT id FROM space_resource WHERE id=? FOR UPDATE",id);
                var row=one("SELECT r.*,r.binding::text AS encoded,s.organization_id,s.kind FROM space_resource r JOIN resource_space s ON s.id=r.space_id WHERE r.id=? AND r.active AND "+ProjectResources.SOURCE_ACCESS+" AND "+ProjectResources.LINK_ACCESS,id,actor,projectId,actor);
                if(!project.get("organization_id").equals(row.get("organization_id"))||!row.get("kind").equals("team"))throw new ApiFailure(404,"准备单或所选资料不可访问");
                var binding=parse(row.get("encoded"));var ref=binding.path("ref");
                if(!ref.isObject()||ref.path("version_id").asText().isBlank()||!ref.path("digest").asText().matches("[a-f0-9]{64}")
                    ||!row.get("space_id").toString().equals(ref.path("project_id").asText()))throw new ApiFailure(409,"发布版本身份不完整，不能准备研究");
                var item=inputs.addObject().put("resource_id",id.toString()).put("space_id",row.get("space_id").toString())
                    .put("resource_revision",((Number)row.get("revision")).intValue()).put("title",row.get("title").toString()).put("resource_type",row.get("resource_type").toString());
                item.set("ref",ref);sources.add(row);
            }
            var manifest=json.createObjectNode().put("contract_version","organization_research_inputs.v1")
                .put("draft_id",body.id().toString()).put("project_id",projectId.toString()).put("organization_id",project.get("organization_id").toString())
                .put("research_as_of",body.research_as_of().toString()).put("visibility_policy","current_project_and_all_inputs");
            manifest.set("inputs",inputs);
            String encoded=manifest.toString(),hash=Delegation.digest(encoded.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            int inserted=db.update("INSERT INTO organization_research_draft(id,project_id,organization_id,created_by,request_digest,title,question,research_as_of,manifest_text,manifest_digest) VALUES(?,?,?,?,?,?,?,?::date,?,?) ON CONFLICT DO NOTHING",
                body.id(),projectId,project.get("organization_id"),actor,digest,body.title().trim(),body.question().trim(),body.research_as_of().toString(),encoded,hash);
            if(inserted!=1)throw new ApiFailure(409,"准备凭证已用于其他提交，请核对原准备单");
            for(var source:sources)db.update("INSERT INTO organization_research_input(draft_id,resource_id,space_id,resource_revision,binding) VALUES(?,?,?,?,?::jsonb)",
                body.id(),source.get("id"),source.get("space_id"),source.get("revision"),source.get("encoded"));
            db.update("INSERT INTO organization_project_audit(project_id,actor,action,target,revision) VALUES(?,?,'research_inputs_save',?,?)",projectId,actor,body.id().toString(),project.get("revision"));
            return view(draft(actor,projectId,body.id()));
        });
    }
    // BFF-only: current researcher role, project status and the entire frozen dependency set.
    // This response is NOT a bearer capability and must not authorize a future run.
    @PostMapping("/{id}/material-access")
    Object materialAccess(HttpServletRequest request,@PathVariable UUID projectId,@PathVariable UUID id) {
        return materialAccess(actor(request),projectId,id);
    }
    Map<String,Object> materialAccess(String actor,UUID projectId,UUID id) {
        return tx.execute(status->{
            projects.researchPreparation(actor,projectId,true);
            return readAccess(actor,projectId,id);
        });
    }
    Map<String,Object> readAccess(String actor,UUID projectId,UUID id) {
        return tx.execute(status->{
            var row=draft(actor,projectId,id);
            var inputs=db.queryForList("SELECT resource_id,binding::text AS encoded FROM organization_research_input WHERE draft_id=? ORDER BY resource_id",id);
            return Map.of("id",id,"project_id",projectId,"organization_id",row.get("organization_id"),
                "manifest_digest","sha256:"+row.get("manifest_digest"),"manifest",parse(row.get("manifest_text")),
                "inputs",inputs.stream().map(i->Map.of("resource_id",i.get("resource_id"),"binding",parse(i.get("encoded")))).toList());
        });
    }
}
