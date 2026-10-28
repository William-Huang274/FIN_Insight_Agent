package io.finsight.business;

import com.fasterxml.jackson.databind.*;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.bind.annotation.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Current viewer authorization; never an execution or reusable bearer grant. */
@RestController
class OrganizationResearchReads {
    private final JdbcTemplate db;
    private final OrganizationResearchDrafts drafts;
    private final ObjectMapper json;
    private final TransactionTemplate tx;
    OrganizationResearchReads(JdbcTemplate db,OrganizationResearchDrafts drafts,ObjectMapper json,PlatformTransactionManager manager) {
        this.db=db;this.drafts=drafts;this.json=json;this.tx=new TransactionTemplate(manager);
    }
    private JsonNode parse(Object text) {
        try{return json.readTree(text.toString());}catch(java.io.IOException e){throw new IllegalStateException(e);}
    }
    @GetMapping("/v1/workspaces/projects/{project}/research-executions")
    Object list(HttpServletRequest request,@PathVariable UUID project,@RequestParam(defaultValue="0") int offset) {
        if(offset<0||offset>100000)throw new ApiFailure(422,"分页位置不合法");
        String actor=(String)request.getAttribute("owner");
        if(actor==null||actor.equals("local-pilot"))throw new ApiFailure(403,"组织研究需要独立登录身份");
        if(db.queryForList(OrganizationProjects.VISIBLE+" AND p.id=?",actor,project).isEmpty())throw new ApiFailure(404,"项目不可访问");
        var candidates=db.queryForList("WITH visible_drafts AS ("+OrganizationResearchDrafts.VISIBLE+") "+"""
            SELECT b.id AS execution_id,b.draft_id,d.title,COALESCE(r.run_id,c.run_id,s.run_id) AS run_id
            FROM organization_execution_binding b
            JOIN visible_drafts d ON d.id=b.draft_id
            JOIN organization_native_preparation p ON p.execution_id=b.id AND p.status='received'
            LEFT JOIN organization_native_start s ON s.execution_id=b.id
            LEFT JOIN organization_native_continuation c ON c.execution_id=b.id
            LEFT JOIN LATERAL (
                SELECT run_id FROM organization_report_command WHERE command_kind IN ('report','root_task') AND execution_id=b.id AND run_id IS NOT NULL
                ORDER BY command_sequence DESC LIMIT 1
            ) r ON true
            ORDER BY b.created_at DESC,b.id LIMIT 31 OFFSET ?
            """,project,actor,actor,project,actor,offset);
        var result=new HashMap<String,Object>();result.put("items",candidates.stream().limit(30).toList());
        result.put("next_offset",candidates.size()>30?offset+30:null);return result;
    }
    @GetMapping("/v1/workspaces/projects/{project}/execution-bindings/{id}/read-access")
    Object access(HttpServletRequest request,@PathVariable UUID project,@PathVariable UUID id) {
        String actor=(String)request.getAttribute("owner");
        if(actor==null||actor.equals("local-pilot"))throw new ApiFailure(403,"组织研究需要独立登录身份");
        return tx.execute(status->{
            var row=db.queryForList("""
                SELECT b.draft_id,b.closed,d.title,d.question,d.manifest_text,p.operation_id,p.request_body,
                       p.response::text AS receipt,s.run_id AS initial_run_id,c.run_id AS continuation_run_id,
                       COALESCE(r.run_id,c.run_id,s.run_id) AS run_id
                FROM organization_execution_binding b
                JOIN organization_research_draft d ON d.id=b.draft_id
                JOIN organization_native_preparation p ON p.execution_id=b.id AND p.status='received'
                LEFT JOIN organization_native_start s ON s.execution_id=b.id
                LEFT JOIN organization_native_continuation c ON c.execution_id=b.id
                LEFT JOIN LATERAL (
                    SELECT run_id FROM organization_report_command WHERE command_kind IN ('report','root_task') AND execution_id=b.id AND run_id IS NOT NULL
                    ORDER BY command_sequence DESC LIMIT 1
                ) r ON true
                WHERE b.id=? AND d.project_id=?
                """,id,project).stream().findFirst().orElseThrow(()->new ApiFailure(404,"研究不可访问"));
            // Reuse the same project AND every frozen source rule, without the
            // creator/researcher restriction required to spend on a new run.
            var result=new HashMap<String,Object>(drafts.readAccess(actor,project,(UUID)row.get("draft_id")));
            result.remove("id");result.remove("manifest");
            result.put("read_contract","organization_research_read.v1");result.put("reader",actor);
            result.put("execution_id",id);result.put("thread_id",id);result.put("draft_id",row.get("draft_id"));
            for(String key:List.of("title","question","manifest_text"))result.put(key,row.get(key));
            result.put("prepare_operation_id",row.get("operation_id"));
            result.put("prepare_request",parse(row.get("request_body")));
            result.put("prepare_request_digest","sha256:"+Delegation.digest(row.get("request_body").toString().getBytes(StandardCharsets.UTF_8)));
            result.put("configuration_digest",parse(row.get("receipt")).path("configuration_digest").asText());
            result.put("run_id",row.get("run_id"));
            result.put("execution_closed",Boolean.TRUE.equals(row.get("closed")));
            var runs=new LinkedHashSet<Object>();
            if(row.get("initial_run_id")!=null)runs.add(row.get("initial_run_id"));
            if(row.get("continuation_run_id")!=null)runs.add(row.get("continuation_run_id"));
            if(row.get("run_id")!=null)runs.add(row.get("run_id"));
            runs.addAll(db.queryForList("SELECT run_id FROM organization_report_command WHERE command_kind IN ('report','root_task') AND execution_id=? AND run_id IS NOT NULL ORDER BY command_sequence",
                UUID.class,id));
            result.put("run_ids",runs);return result;
        });
    }
}
