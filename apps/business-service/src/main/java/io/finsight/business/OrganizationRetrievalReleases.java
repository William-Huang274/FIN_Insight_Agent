package io.finsight.business;

import com.fasterxml.jackson.databind.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.bind.annotation.*;
import java.util.*;

/** Append-only index identity. Publication bytes remain Python-owned.
 * Registration is a server-only bridge operation, never a runtime credential.
 */
@RestController
@RequestMapping("/v1/workspaces/projects/{projectId}/retrieval-releases")
class OrganizationRetrievalReleases {
    record Publish(@NotNull UUID id, @NotNull UUID source_draft_id,
        @NotNull @Pattern(regexp="[a-f0-9]{64}") String index_digest,
        @NotNull @Pattern(regexp="[a-f0-9]{64}") String matrix_sha256,
        @NotNull @Pattern(regexp="text-embedding-v4|qwen3\\.7-text-embedding") String model,
        @Min(1024) @Max(1024) int dimensions,
        @NotNull @Pattern(regexp="organization-(text-6000|library-chunks)\\.v1") String projection) {}
    private final JdbcTemplate db;
    private final OrganizationProjects projects;
    private final ObjectMapper json;
    private final TransactionTemplate tx;
    OrganizationRetrievalReleases(JdbcTemplate db, OrganizationProjects projects,
            ObjectMapper json, PlatformTransactionManager manager) {
        this.db=db;this.projects=projects;this.json=json;this.tx=new TransactionTemplate(manager);
    }
    private String actor(HttpServletRequest request) {
        String actor=(String)request.getAttribute("owner");
        if(actor==null||actor.equals("local-pilot"))throw new ApiFailure(403,"索引发布需要独立身份");
        return actor;
    }
    private JsonNode parse(Object text) {
        try{return json.readTree(text.toString());}catch(Exception e){throw new IllegalStateException(e);}
    }
    private Map<String,Object> visibleDraft(String actor,UUID project,UUID draft) {
        return db.queryForList(OrganizationResearchDrafts.VISIBLE+" AND d.id=?",
            project,actor,actor,project,actor,draft).stream().findFirst()
            .orElseThrow(()->new ApiFailure(404,"索引资料或准备单不可访问"));
    }
    @PostMapping
    Object publish(HttpServletRequest request,@PathVariable UUID projectId,@Valid @RequestBody Publish body) {
        String actor=actor(request);
        String digest=Delegation.digest((byte[])request.getAttribute("originalBody"));
        return tx.execute(status->{
            projects.researchPreparation(actor,projectId,true);
            var project=projects.project(actor,projectId,true);
            var draft=visibleDraft(actor,projectId,body.source_draft_id());
            var contract=json.createObjectNode().put("release_id",body.id().toString())
                .put("index_digest",body.index_digest()).put("matrix_sha256",body.matrix_sha256())
                .put("model",body.model()).put("dimensions",body.dimensions()).put("projection",body.projection());
            var inputs=parse(draft.get("manifest_text")).path("inputs");
            int inserted=db.update("""
                INSERT INTO organization_retrieval_release
                (id,project_id,organization_id,source_draft_id,created_by,request_digest,contract,inputs)
                VALUES(?,?,?,?,?,?,?::jsonb,?::jsonb) ON CONFLICT DO NOTHING
                """,body.id(),projectId,project.get("organization_id"),body.source_draft_id(),actor,digest,contract.toString(),inputs.toString());
            var saved=db.queryForMap("SELECT * FROM organization_retrieval_release WHERE id=?",body.id());
            if(!projectId.equals(saved.get("project_id"))||!actor.equals(saved.get("created_by"))||!digest.equals(saved.get("request_digest")))
                throw new ApiFailure(409,"索引发布标识已使用，不得覆盖旧版本");
            if(inserted==1)db.update("INSERT INTO organization_project_audit(project_id,actor,action,target,revision) VALUES(?,?,'retrieval_release_publish',?,?)",
                projectId,actor,body.id().toString(),project.get("revision"));
            return contract;
        });
    }
    @GetMapping
    Object list(HttpServletRequest request,@PathVariable UUID projectId) {
        String actor=actor(request);projects.project(actor,projectId,false);
        var rows=db.queryForList("SELECT r.contract,r.inputs,r.created_at FROM organization_retrieval_release r WHERE r.project_id=? AND EXISTS ("+
            OrganizationResearchDrafts.VISIBLE+" AND d.id=r.source_draft_id) ORDER BY r.created_at DESC,r.id LIMIT 100",
            projectId,projectId,actor,actor,projectId,actor);
        return Map.of("items",rows.stream().map(r->{
            var value=(com.fasterxml.jackson.databind.node.ObjectNode)parse(r.get("contract"));
            value.put("published_at",r.get("created_at").toString());
            var ids=value.putArray("resource_ids");
            parse(r.get("inputs")).forEach(i->ids.add(i.path("resource_id").asText()));
            return value;
        }).toList());
    }
    JsonNode freeze(UUID project,UUID id,JsonNode inputs) {
        var row=db.queryForList("SELECT * FROM organization_retrieval_release WHERE id=? AND project_id=?",id,project)
            .stream().findFirst().orElseThrow(()->new ApiFailure(404,"索引发布版本不可访问"));
        if(!parse(row.get("inputs")).equals(inputs))
            throw new ApiFailure(409,"索引与所选资料版本不一致，请发布对应索引；未替换原件");
        return parse(row.get("contract"));
    }
}
