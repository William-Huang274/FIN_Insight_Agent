package io.finsight.business;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.nimbusds.jose.*;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jwt.*;
import com.sun.net.httpserver.*;
import org.junit.jupiter.api.*;
import org.flywaydb.core.Flyway;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.*;
import org.springframework.transaction.PlatformTransactionManager;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.*;
import java.net.*;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import static org.assertj.core.api.Assertions.*;

/** Real HTTP, Spring, Flyway and PostgreSQL; only the Python execution server is scripted. */
@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT)
@Testcontainers
class ResearchIntakeTest {
    static final String SECRET = "synthetic-test-only-delegation-key-32-bytes";
    static final ObjectMapper JSON = new ObjectMapper();
    @Container static final PostgreSQLContainer<?> PG = new PostgreSQLContainer<>("postgres:16.15-alpine");
    static final Map<String, ObjectNode> drafts = new ConcurrentHashMap<>();
    static final Map<String, ObjectNode> states = new ConcurrentHashMap<>();
    static final Set<String> revoked = ConcurrentHashMap.newKeySet();
    static final AtomicInteger prepares = new AtomicInteger(), starts = new AtomicInteger();
    static final HttpServer PYTHON = fakePython();
    @DynamicPropertySource static void properties(DynamicPropertyRegistry r) {
        r.add("spring.datasource.url", PG::getJdbcUrl); r.add("spring.datasource.username", PG::getUsername); r.add("spring.datasource.password", PG::getPassword);
        r.add("finsight.shared-secret", () -> SECRET); r.add("finsight.python-url", () -> "http://127.0.0.1:"+PYTHON.getAddress().getPort());
    }
    @LocalServerPort int port;
    @Autowired TaskStore store;
    @Autowired JdbcTemplate db;
    @Autowired PlatformTransactionManager manager;
    private final HttpClient client = HttpClient.newHttpClient();

    static HttpServer fakePython() {
        try {
            var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
            server.createContext("/api/v1/internal-research/", exchange -> {
                try {
                    String path = exchange.getRequestURI().getPath().replace("/api/v1/internal-research/", "");
                    byte[] bytes = exchange.getRequestBody().readAllBytes();
                    var token = SignedJWT.parse(exchange.getRequestHeaders().getFirst("Authorization").substring(7));
                    assertThat(token.verify(new com.nimbusds.jose.crypto.MACVerifier(SECRET))).isTrue();
                    var claims = token.getJWTClaimsSet();
                    assertThat(claims.getIssuer()).isEqualTo("finsight-java");
                    assertThat(claims.getAudience()).containsExactly("finsight-python-intake");
                    assertThat(claims.getStringClaim("path")).isEqualTo(exchange.getRequestURI().toString());
                    assertThat(claims.getStringClaim("body_sha256")).isEqualTo(Delegation.digest(bytes));
                    assertThat(claims.getStringClaim("operation_id")).isEqualTo(Objects.requireNonNullElse(exchange.getRequestHeaders().getFirst("Idempotency-Key"), ""));
                    String project = path.startsWith("projects/") ? path.split("/")[1] : "";
                    if (revoked.contains(project)) { send(exchange,404,JSON.createObjectNode()); return; }
                    if (path.endsWith("/binding")) { send(exchange,200,binding()); return; }
                    if (path.startsWith("projects/")) { send(exchange,200,JSON.createObjectNode().put("project_id",project)); return; }
                    if (path.startsWith("receipts/")) { send(exchange,200,JSON.createObjectNode().put("status","unknown")); return; }
                    if (path.startsWith("tasks/")) { var state=states.get(path.split("/")[1]); send(exchange,state==null?404:200,state==null?JSON.createObjectNode():state); return; }
                    ObjectNode body=(ObjectNode)JSON.readTree(bytes); String id=body.path("task_id").asText();
                    if (path.equals("prepare")) {
                        prepares.incrementAndGet(); drafts.put(id,body);
                        var state=JSON.createObjectNode().put("task_id",id).put("thread_id",id).put("project_id",body.path("project_id").asText()).put("prepared",true)
                            .put("prepare_operation_id",exchange.getRequestHeaders().getFirst("Idempotency-Key"));
                        state.set("binding",body.path("binding")); state.putArray("runs"); states.put(id,state);
                        var result=state.deepCopy().put("status","draft");
                        if (body.path("session").path("title").asText().startsWith("drop-prepare")) { exchange.close(); return; }
                        if (body.path("session").path("title").asText().equals("receipt-unknown")) {
                            send(exchange,409,JSON.createObjectNode().put("submission_status","unknown").put("detail","Existing dispatch requires reconciliation")); return;
                        }
                        send(exchange,200,result); return;
                    }
                    if (path.equals("start")) {
                        starts.incrementAndGet();
                        var run=JSON.createObjectNode().put("run_id",UUID.randomUUID().toString()).put("status","pending")
                            .put("operation_id",exchange.getRequestHeaders().getFirst("Idempotency-Key"));
                        ((com.fasterxml.jackson.databind.node.ArrayNode)states.get(id).get("runs")).add(run);
                        if (drafts.get(id).path("session").path("title").asText().startsWith("drop-start")) { exchange.close(); return; }
                        send(exchange,200,body.deepCopy().put("run_id",run.path("run_id").asText()).put("status","pending")); return;
                    }
                    send(exchange,404,JSON.createObjectNode());
                } catch (Throwable e) { exchange.close(); throw new RuntimeException(e); }
            });
            server.setExecutor(Executors.newCachedThreadPool()); server.start(); return server;
        } catch(Exception e) { throw new ExceptionInInitializerError(e); }
    }
    static ObjectNode binding() { return JSON.createObjectNode().put("snapshot_ref","sha256:"+"a".repeat(64)).put("research_as_of","2025-12-31T00:00:00+00:00"); }
    static void send(HttpExchange e,int status,JsonNode body) throws Exception {
        byte[] bytes=body.toString().getBytes(StandardCharsets.UTF_8); e.getResponseHeaders().set("Content-Type","application/json");
        e.sendResponseHeaders(status,bytes.length); e.getResponseBody().write(bytes); e.close();
    }
    @AfterAll static void close() { PYTHON.stop(0); ((ExecutorService)PYTHON.getExecutor()).shutdownNow(); }
    String token(String owner,String method,String path,String body,String key, String audience) throws Exception {
        Instant now=Instant.now();
        var c=new JWTClaimsSet.Builder().issuer("finsight-workbench").audience(audience).subject(owner)
            .issueTime(Date.from(now)).expirationTime(Date.from(now.plusSeconds(60))).claim("method",method).claim("path",path)
            .claim("body_sha256",Delegation.digest(body.getBytes(StandardCharsets.UTF_8))).claim("operation_id",key==null?"":key).build();
        var t=new SignedJWT(new JWSHeader(JWSAlgorithm.HS256),c);t.sign(new MACSigner(SECRET));return t.serialize();
    }
    HttpResponse<String> request(String owner,String method,String path,String body,String key) throws Exception {
        return raw(method,path,body,key,token(owner,method,path,body,key,"finsight-java"));
    }
    HttpResponse<String> raw(String method,String path,String body,String key,String token) throws Exception {
        var builder=HttpRequest.newBuilder(URI.create("http://127.0.0.1:"+port+path)).header("Authorization","Bearer "+token).header("Content-Type","application/json")
            .method(method,HttpRequest.BodyPublishers.ofString(body));if(key!=null)builder.header("Idempotency-Key",key);
        return client.send(builder.build(),HttpResponse.BodyHandlers.ofString());
    }
    ObjectNode input(UUID project,String title) {
        return JSON.createObjectNode().put("project_id",project.toString()).put("title",title).put("question","Deterministic integration question, not financial evidence.");
    }
    JsonNode create(String title) throws Exception {
        var response=request("alice","POST","/v1/tasks",input(UUID.randomUUID(),title).toString(),UUID.randomUUID().toString());
        assertThat(response.statusCode()).isEqualTo(200);return JSON.readTree(response.body());
    }
    @Test void concurrent_duplicate_submission_and_start_dispatch_once() throws Exception {
        UUID project=UUID.randomUUID();String key=UUID.randomUUID().toString(),body=input(project,"concurrent").toString();int before=prepares.get();
        List<Future<HttpResponse<String>>> futures=new ArrayList<>();
        try(var pool=Executors.newVirtualThreadPerTaskExecutor()) {
            for(int i=0;i<20;i++)futures.add(pool.submit(()->request("alice","POST","/v1/tasks",body,key)));
            Set<String> ids=new HashSet<>();
            for(var f:futures){var response=f.get();assertThat(response.statusCode()).isEqualTo(200);ids.add(JSON.readTree(response.body()).path("id").asText());}
            assertThat(ids).hasSize(1);assertThat(prepares.get()-before).isEqualTo(1);
            String id=ids.iterator().next();int beforeRuns=starts.get();futures.clear();
            for(int i=0;i<20;i++)futures.add(pool.submit(()->request("alice","POST","/v1/tasks/"+id+"/start","{}",null)));
            for(var f:futures)assertThat(f.get().statusCode()).isEqualTo(200);
            assertThat(starts.get()-beforeRuns).isEqualTo(1);
            assertThat(request("alice","POST","/v1/tasks",input(project,"changed").toString(),key).statusCode()).isEqualTo(409);
            var reopened=new TaskStore(db,JSON,manager);assertThat(reopened.owned("alice",UUID.fromString(id)).project()).isEqualTo(project);
            assertThat(reopened.command(UUID.fromString(id),"start").status()).isEqualTo("received");
        }
    }

    JsonNode workspace(String actor,String method,String path,Object body,int status) throws Exception {
        var response=request(actor,method,"/v1/workspaces"+path,body==null?"":JSON.writeValueAsString(body),null);
        assertThat(response.statusCode()).as(response.body()).isEqualTo(status);
        return response.body().isBlank()?JSON.createObjectNode():JSON.readTree(response.body());
    }
    @Test void organization_spaces_enforce_live_membership_private_default_and_revocation() throws Exception {
        String alice="space-alice",bob="space-bob",eve="space-eve";UUID org=UUID.randomUUID(),team=UUID.randomUUID(),invite=UUID.randomUUID();
        var created=workspace(alice,"POST","/organizations",Map.of("id",org,"name","研究组织","display_name","Alice"),200);
        String personal=created.path("spaces").get(0).path("id").asText();
        workspace(bob,"POST","/spaces/"+personal+"/access",Map.of("action","read"),404);
        workspace("local-pilot","GET","",null,403);
        workspace(alice,"POST","/organizations/"+org+"/invites",Map.of("token",invite),200);
        workspace(bob,"POST","/join",Map.of("token",invite,"display_name","Bob"),200);
        workspace(eve,"POST","/join",Map.of("token",invite,"display_name","Eve"),409);
        workspace(bob,"POST","/spaces/"+personal+"/access",Map.of("action","read"),404);
        workspace(bob,"POST","/organizations/"+org+"/invites",Map.of("token",UUID.randomUUID()),403);
        workspace(alice,"POST","/spaces",Map.of("id",team,"organization_id",org,"name","行业组"),200);
        workspace(bob,"GET","/spaces/"+team+"/resources",null,404);
        workspace(alice,"POST","/spaces/"+team+"/members",Map.of("subject",bob,"role","reader"),200);
        workspace(bob,"POST","/spaces/"+team+"/access",Map.of("action","publish"),403);
        UUID resource=UUID.randomUUID();var publication=Map.of("id",resource,"space_id",team,"title","固定披露版本","resource_type","files",
            "binding",Map.of("organization_id",org,"space_id",team,"ref",Map.of("version_id","synthetic-pinned-version")));
        workspace(alice,"POST","/resources",publication,200);workspace(alice,"POST","/resources",publication,200);
        var catalogue=workspace(bob,"GET","/spaces/"+team+"/resources",null,200);
        assertThat(catalogue.path("items").size()).isEqualTo(1);assertThat(catalogue.toString()).doesNotContain("binding","synthetic-pinned-version");
        assertThat(workspace(bob,"POST","/resources/"+resource+"/access",null,200).path("binding").path("ref").path("version_id").asText()).isEqualTo("synthetic-pinned-version");
        workspace(eve,"POST","/resources/"+resource+"/access",null,404);
        workspace(bob,"POST","/resources/"+resource+"/revoke",Map.of("revision",1),403);
        workspace(alice,"POST","/resources/"+resource+"/revoke",Map.of("revision",2),409);
        workspace(alice,"POST","/resources/"+resource+"/revoke",Map.of("revision",1),200);
        workspace(bob,"POST","/resources/"+resource+"/access",null,404);
        workspace(alice,"POST","/resources",publication,409);
        assertThat(workspace(bob,"GET","/spaces/"+team+"/resources",null,200).path("items").size()).isZero();
        workspace(alice,"POST","/organizations/"+org+"/remove-member",Map.of("subject",bob),200);
        workspace(bob,"GET","/spaces/"+team+"/resources",null,404);
        workspace(bob,"POST","/join",Map.of("token",invite,"display_name","Bob"),404);
        assertThat(db.queryForObject("SELECT count(*) FROM resource_space_audit WHERE organization_id=?",Integer.class,org)).isGreaterThan(5);
    }
    @Test void separate_organizations_and_removed_space_member_do_not_inherit_access() throws Exception {
        String admin="org-admin",member="org-member";UUID org=UUID.randomUUID(),team=UUID.randomUUID(),invite=UUID.randomUUID();
        workspace(admin,"POST","/organizations",Map.of("id",org,"name","独立组织","display_name","管理员"),200);
        workspace(member,"POST","/organizations",Map.of("id",UUID.randomUUID(),"name","另一个组织","display_name","成员"),200);
        workspace(member,"GET","/organizations/"+org+"/members",null,404);
        workspace(admin,"POST","/organizations/"+org+"/invites",Map.of("token",invite),200);
        workspace(member,"POST","/join",Map.of("token",invite,"display_name","成员"),200);
        workspace(admin,"POST","/spaces",Map.of("id",team,"organization_id",org,"name","共享组"),200);
        workspace(admin,"POST","/spaces/"+team+"/members",Map.of("subject",member,"role","manager"),200);
        workspace(member,"POST","/spaces/"+team+"/access",Map.of("action","publish"),200);
        workspace(admin,"POST","/spaces/"+team+"/members",Map.of("subject",member,"role","remove"),200);
        workspace(member,"POST","/spaces/"+team+"/access",Map.of("action","read"),404);
        workspace(admin,"POST","/organizations/"+org+"/remove-member",Map.of("subject",admin),409);
    }
    void joinProjectOrganization(String admin,String member,UUID org) throws Exception {
        UUID invite=UUID.randomUUID();
        workspace(admin,"POST","/organizations/"+org+"/invites",Map.of("token",invite),200);
        workspace(member,"POST","/join",Map.of("token",invite,"display_name",member),200);
    }
    @Test void upgrading_v2_keeps_existing_organization_space_records() {
        String schema="upgrade_"+UUID.randomUUID().toString().replace("-","");
        Flyway.configure().dataSource(PG.getJdbcUrl(),PG.getUsername(),PG.getPassword())
            .schemas(schema).defaultSchema(schema).target("2").load().migrate();
        UUID org=UUID.randomUUID(),space=UUID.randomUUID();
        db.update("INSERT INTO "+schema+".resource_organization(id,name,created_by) VALUES(?,?,'alice')",org,"原组织");
        db.update("INSERT INTO "+schema+".resource_space(id,organization_id,name,kind,principal) VALUES(?,?,'原个人区','personal','alice')",space,org);
        Flyway.configure().dataSource(PG.getJdbcUrl(),PG.getUsername(),PG.getPassword())
            .schemas(schema).defaultSchema(schema).load().migrate();
        assertThat(db.queryForObject("SELECT name FROM "+schema+".resource_space WHERE id=?",String.class,space)).isEqualTo("原个人区");
        assertThat(db.queryForObject("SELECT count(*) FROM "+schema+".organization_project",Integer.class)).isZero();
        assertThat(db.queryForObject("SELECT count(*) FROM "+schema+".flyway_schema_history WHERE version='3' AND success",Integer.class)).isEqualTo(1);
        // The isolated Testcontainers database is discarded at test completion.
    }
    @Test void project_roles_live_org_membership_and_space_permissions_are_independent() throws Exception {
        String admin="project-admin",bob="project-bob",eve="project-eve";UUID org=UUID.randomUUID(),id=UUID.randomUUID(),space=UUID.randomUUID();
        workspace(admin,"POST","/organizations",Map.of("id",org,"name","项目组织","display_name","管理者"),200);
        joinProjectOrganization(admin,bob,org);joinProjectOrganization(admin,eve,org);
        var body=Map.of("id",id,"organization_id",org,"name","AI 基础设施","description","合成项目");
        workspace(bob,"POST","/projects",body,403);
        workspace(admin,"POST","/projects",body,200);
        workspace(bob,"GET","/projects/"+id,null,404);
        assertThat(workspace(bob,"GET","/projects",null,200).path("items")).isEmpty();
        workspace(admin,"POST","/projects/"+id+"/members",Map.of("revision",1,"subject",bob,"role","viewer"),200);
        assertThat(workspace(bob,"GET","/projects/"+id,null,200).path("can_manage").asBoolean()).isFalse();
        workspace(bob,"POST","/projects/"+id,Map.of("revision",2,"name","越权","description","","archived",false),403);
        workspace(bob,"POST","/projects/"+id+"/members",Map.of("revision",2,"subject",eve,"role","manager"),403);
        workspace(admin,"POST","/projects/"+id+"/members",Map.of("revision",2,"subject",bob,"role","manager"),200);
        workspace(bob,"POST","/projects/"+id+"/members",Map.of("revision",3,"subject",eve,"role","researcher"),200);
        assertThat(workspace(eve,"GET","/projects/"+id,null,200).path("research_enabled").asBoolean()).isFalse();
        workspace(admin,"POST","/spaces",Map.of("id",space,"organization_id",org,"name","独立资料权限"),200);
        workspace(bob,"GET","/spaces/"+space+"/resources",null,404);
        workspace(admin,"POST","/organizations/"+org+"/remove-member",Map.of("subject",bob),200);
        workspace(bob,"GET","/projects/"+id,null,404);
        workspace(bob,"GET","/projects/"+id+"/members",null,404);
        workspace(bob,"POST","/projects/"+id+"/members",Map.of("revision",4,"subject",eve,"role","remove"),404);
        workspace(admin,"POST","/projects/"+id+"/members",Map.of("revision",4,"subject",bob,"role","manager"),404);
        workspace(admin,"POST","/projects/"+id+"/members",Map.of("revision",4,"subject",eve,"role","remove"),200);
        workspace(eve,"GET","/projects/"+id,null,404);
        workspace("local-pilot","GET","/projects",null,403);
    }
    @Test void project_creation_retry_preserves_edits_and_concurrent_writes_require_reload() throws Exception {
        String admin="project-conflict";UUID org=UUID.randomUUID(),id=UUID.randomUUID();
        workspace(admin,"POST","/organizations",Map.of("id",org,"name","组织","display_name","管理员"),200);
        var create=Map.of("id",id,"organization_id",org,"name","原名称","description","");
        try(var pool=Executors.newVirtualThreadPerTaskExecutor()) {
            List<Future<JsonNode>> results=new ArrayList<>();
            for(int i=0;i<8;i++)results.add(pool.submit(()->workspace(admin,"POST","/projects",create,200)));
            for(var r:results)assertThat(r.get().path("revision").asInt()).isEqualTo(1);
            List<Future<HttpResponse<String>>> edits=new ArrayList<>();
            for(int i=0;i<2;i++){
                String body=JSON.writeValueAsString(Map.of("revision",1,"name","修改"+i,"description","","archived",true));
                edits.add(pool.submit(()->request(admin,"POST","/v1/workspaces/projects/"+id,body,null)));
            }
            assertThat(List.of(edits.get(0).get().statusCode(),edits.get(1).get().statusCode())).containsExactlyInAnyOrder(200,409);
        }
        var replay=workspace(admin,"POST","/projects",create,200);
        assertThat(replay.path("archived").asBoolean()).isTrue();assertThat(replay.path("revision").asInt()).isEqualTo(2);
        assertThat(workspace(admin,"GET","/projects?organization_id="+org,null,200).path("items")).isEmpty();
        assertThat(workspace(admin,"GET","/projects?archived=true&organization_id="+org,null,200).path("items")).hasSize(1);
        workspace(admin,"POST","/projects/"+id,Map.of("revision",2,"name","恢复","description","","archived",false),200);
        workspace(admin,"POST","/projects",Map.of("id",id,"organization_id",org,"name","不同提交","description",""),409);
        assertThat(db.queryForObject("SELECT count(*) FROM organization_project_audit WHERE project_id=?",Integer.class,id)).isEqualTo(3);
    }
    @Test void project_cross_org_assignment_and_pagination_are_scoped() throws Exception {
        String admin="project-pages",outsider="project-outsider";UUID org=UUID.randomUUID(),other=UUID.randomUUID();
        workspace(admin,"POST","/organizations",Map.of("id",org,"name","分页组织","display_name","管理者"),200);
        workspace(outsider,"POST","/organizations",Map.of("id",other,"name","外部组织","display_name","其他管理员"),200);
        UUID id=UUID.randomUUID();
        workspace(admin,"POST","/projects",Map.of("id",id,"organization_id",org,"name","重复名称","description","范围检查"),200);
        workspace(outsider,"GET","/projects/"+id,null,404);
        workspace(admin,"POST","/projects/"+id+"/members",Map.of("revision",1,"subject",outsider,"role","manager"),404);
        workspace(admin,"POST","/projects/"+id+"/members",Map.of("revision",1,"subject",admin,"role","remove"),409);
        for(int i=0;i<30;i++)workspace(admin,"POST","/projects",Map.of("id",UUID.randomUUID(),"organization_id",org,"name","重复名称","description","合成分页"),200);
        var first=workspace(admin,"GET","/projects?organization_id="+org,null,200);
        var second=workspace(admin,"GET","/projects?organization_id="+org+"&offset=30",null,200);
        assertThat(first.path("items")).hasSize(30);assertThat(first.path("next_offset").asInt()).isEqualTo(30);
        assertThat(second.path("items")).hasSize(1);assertThat(second.path("next_offset").isNull()).isTrue();
        Set<String> ids=new HashSet<>();for(var p:first.path("items"))ids.add(p.path("id").asText());for(var p:second.path("items"))ids.add(p.path("id").asText());assertThat(ids).hasSize(31);
        assertThat(workspace(outsider,"GET","/projects?organization_id="+org,null,200).path("items")).isEmpty();
        assertThat(workspace(admin,"GET","/projects?query=%25",null,200).path("items")).isEmpty();
    }
    @Test void lost_prepare_response_recovers_only_deterministic_thread() throws Exception {
        var task=create("drop-prepare");String path="/v1/tasks/"+task.path("id").asText();int before=prepares.get();
        assertThat(task.path("prepare").path("status").asText()).isEqualTo("unknown");
        assertThat(JSON.readTree(request("alice","POST",path+"/prepare","{}",null).body()).path("prepare").path("status").asText()).isEqualTo("unknown");
        var reconciled=JSON.readTree(request("alice","POST",path+"/reconcile","{}",null).body());
        assertThat(reconciled.path("prepare").path("status").asText()).isEqualTo("received");
        assertThat(reconciled.path("thread_id").asText()).isEqualTo(task.path("id").asText());assertThat(prepares.get()).isEqualTo(before);
    }
    @Test void existing_unknown_python_receipt_is_not_misclassified_as_rejection() throws Exception {
        var task=create("receipt-unknown");
        assertThat(task.path("prepare").path("status").asText()).isEqualTo("unknown");
        int before=prepares.get();
        var reconciled=JSON.readTree(request("alice","POST","/v1/tasks/"+task.path("id").asText()+"/reconcile","{}",null).body());
        assertThat(reconciled.path("prepare").path("status").asText()).isEqualTo("received");
        assertThat(prepares.get()).isEqualTo(before);
    }
    @Test void lost_start_response_never_replays_and_reconciles_exact_operation() throws Exception {
        var task=create("drop-start");String id=task.path("id").asText(),path="/v1/tasks/"+id;int before=starts.get();
        var unknown=JSON.readTree(request("alice","POST",path+"/start","{}",null).body());
        assertThat(unknown.path("start").path("status").asText()).isEqualTo("unknown");
        request("alice","POST",path+"/start","{}",null);
        // A newer unrelated run must never be selected as the business result.
        ((com.fasterxml.jackson.databind.node.ArrayNode)states.get(id).get("runs")).add(JSON.createObjectNode().put("run_id",UUID.randomUUID().toString()).put("operation_id",UUID.randomUUID().toString()));
        var reconciled=JSON.readTree(request("alice","POST",path+"/reconcile","{}",null).body());
        assertThat(reconciled.path("start").path("status").asText()).isEqualTo("received");
        assertThat(reconciled.path("start").path("result").path("run_id").asText()).isEqualTo(states.get(id).path("runs").get(0).path("run_id").asText());
        assertThat(starts.get()-before).isEqualTo(1);
    }
    @Test void unknown_without_proof_stays_unknown_after_new_repository_and_read_only_checks() throws Exception {
        var task=create("drop-start-no-proof");UUID id=UUID.fromString(task.path("id").asText());String path="/v1/tasks/"+id;
        request("alice","POST",path+"/start","{}",null);states.remove(id.toString());int count=starts.get();
        var reopened=new TaskStore(db,JSON,manager);
        assertThat(reopened.command(id,"start").status()).isEqualTo("unknown");
        for(int i=0;i<3;i++)assertThat(JSON.readTree(request("alice","POST",path+"/reconcile","{}",null).body()).path("start").path("status").asText()).isEqualTo("unknown");
        assertThat(starts.get()).isEqualTo(count);
    }
    @Test void owner_project_and_live_access_fail_closed() throws Exception {
        var task=create("ownership");String path="/v1/tasks/"+task.path("id").asText(),project=task.path("project_id").asText();
        assertThat(request("bob","GET",path,"",null).statusCode()).isEqualTo(404);
        assertThat(JSON.readTree(request("alice","GET","/v1/tasks?project_id="+UUID.randomUUID(),"",null).body()).path("items")).isEmpty();
        revoked.add(project);
        assertThat(request("alice","GET",path,"",null).statusCode()).isEqualTo(404);
        assertThat(request("alice","POST",path+"/start","{}",null).statusCode()).isEqualTo(404);
    }
    @Test void signed_body_path_audience_and_operation_cannot_be_tampered() throws Exception {
        String path="/v1/tasks",body=input(UUID.randomUUID(),"tampering").toString(),key=UUID.randomUUID().toString();
        String jwt=token("alice","POST",path,body,key,"finsight-java");
        assertThat(raw("POST",path,body+" ",key,jwt).statusCode()).isEqualTo(401);
        assertThat(raw("POST",path,body,UUID.randomUUID().toString(),jwt).statusCode()).isEqualTo(401);
        assertThat(raw("POST",path+"/"+UUID.randomUUID()+"/start",body,key,jwt).statusCode()).isEqualTo(401);
        assertThat(raw("POST",path,body,key,token("alice","POST",path,body,key,"finsight-python-intake")).statusCode()).isEqualTo(401);
    }
}
