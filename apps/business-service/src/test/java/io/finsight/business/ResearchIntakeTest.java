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
    static final String RUNTIME_SECRET = "synthetic-test-only-separate-runtime-key-32-bytes";
    static final ObjectMapper JSON = new ObjectMapper();
    @Container static final PostgreSQLContainer<?> PG = new PostgreSQLContainer<>("postgres:16.15-alpine");
    static final Map<String, ObjectNode> drafts = new ConcurrentHashMap<>();
    static final Map<String, ObjectNode> states = new ConcurrentHashMap<>();
    static final Set<String> revoked = ConcurrentHashMap.newKeySet();
    static final AtomicInteger prepares = new AtomicInteger(), starts = new AtomicInteger();
    static final Map<String,ObjectNode> organizationNative = new ConcurrentHashMap<>();
    static final Set<String> dropOrganizationPrepare = ConcurrentHashMap.newKeySet();
    static final AtomicInteger organizationCreates = new AtomicInteger();
    static final Map<String,ObjectNode> organizationRuns = new ConcurrentHashMap<>();
    static final Set<String> dropOrganizationStart = ConcurrentHashMap.newKeySet();
    static final AtomicInteger organizationStarts = new AtomicInteger();
    static final Map<String,ObjectNode> organizationContinuations = new ConcurrentHashMap<>();
    static final Set<String> dropOrganizationContinuation = ConcurrentHashMap.newKeySet();
    static final AtomicInteger organizationContinues = new AtomicInteger();
    static final Map<String,ObjectNode> reportCommands = new ConcurrentHashMap<>();
    static final Set<String> dropReportCommands = ConcurrentHashMap.newKeySet();
    static final AtomicInteger reportDispatches = new AtomicInteger();
    static final HttpServer PYTHON = fakePython();
    @DynamicPropertySource static void properties(DynamicPropertyRegistry r) {
        r.add("spring.datasource.url", PG::getJdbcUrl); r.add("spring.datasource.username", PG::getUsername); r.add("spring.datasource.password", PG::getPassword);
        r.add("finsight.shared-secret", () -> SECRET); r.add("finsight.python-url", () -> "http://127.0.0.1:"+PYTHON.getAddress().getPort());
        r.add("finsight.runtime-secret", () -> RUNTIME_SECRET);
        r.add("finsight.organization-start-enabled", () -> true);
        r.add("finsight.organization-report-actions-enabled", () -> true);
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
                    if(path.equals("organization/prepare")) {
                        var payload=(ObjectNode)JSON.readTree(bytes);String id=payload.path("execution_id").asText();
                        organizationCreates.incrementAndGet();
                        var result=JSON.createObjectNode().put("execution_id",id).put("thread_id",id)
                            .put("project_id",payload.path("project_id").asText()).put("manifest_digest",payload.path("manifest_digest").asText())
                            .put("prepare_operation_id",exchange.getRequestHeaders().getFirst("Idempotency-Key"))
                            .put("prepare_request_digest","sha256:"+Delegation.digest(bytes)).put("configuration_digest","sha256:"+"a".repeat(64))
                            .put("status","draft").put("native_execution_enabled",false);
                        organizationNative.put(id,result);
                        if(dropOrganizationPrepare.contains(id)){exchange.close();return;}
                        send(exchange,200,result);return;
                    }
                    if(path.equals("organization/start")) {
                        var payload=JSON.readTree(bytes);String id=payload.path("execution_id").asText();organizationStarts.incrementAndGet();
                        var result=JSON.createObjectNode().put("execution_id",id).put("thread_id",id)
                            .put("project_id",payload.path("project_id").asText()).put("configuration_digest",payload.path("configuration_digest").asText())
                            .put("start_operation_id",exchange.getRequestHeaders().getFirst("Idempotency-Key"))
                            .put("start_request_digest","sha256:"+Delegation.digest(bytes)).put("run_id",UUID.randomUUID().toString()).put("status","pending");
                        organizationRuns.put(id,result);if(dropOrganizationStart.contains(id)){exchange.close();return;}
                        send(exchange,200,result);return;
                    }
                    if(path.equals("organization/continue")) {
                        var payload=JSON.readTree(bytes);String id=payload.path("execution_id").asText();organizationContinues.incrementAndGet();
                        var result=JSON.createObjectNode().put("execution_id",id).put("thread_id",id)
                            .put("project_id",payload.path("project_id").asText()).put("configuration_digest",payload.path("configuration_digest").asText())
                            .put("continuation_operation_id",exchange.getRequestHeaders().getFirst("Idempotency-Key"))
                            .put("continuation_request_digest","sha256:"+Delegation.digest(bytes)).put("run_id",UUID.randomUUID().toString()).put("status","pending");
                        organizationContinuations.put(id,result);if(dropOrganizationContinuation.contains(id)){exchange.close();return;}
                        send(exchange,200,result);return;
                    }
                    if(path.equals("organization/report-actions")) {
                        var p=JSON.readTree(bytes); String id=p.path("command_id").asText(); reportDispatches.incrementAndGet();
                        var result=JSON.createObjectNode().put("execution_id",p.path("execution_id").asText())
                            .put("thread_id",p.path("execution_id").asText()).put("project_id",p.path("project_id").asText())
                            .put("configuration_digest",p.path("configuration_digest").asText()).put("report_command_id",id)
                            .put("report_action_operation_id",exchange.getRequestHeaders().getFirst("Idempotency-Key"))
                            .put("report_action_request_digest","sha256:"+Delegation.digest(bytes))
                            .put("run_id",UUID.randomUUID().toString()).put("status","pending");
                        reportCommands.put(id,result);
                        if(dropReportCommands.contains(id)){exchange.close();return;}
                        send(exchange,200,result); return;
                    }
                    if(path.startsWith("organization/executions/")&&path.contains("/report-actions/")) {
                        var result=reportCommands.get(path.substring(path.lastIndexOf('/')+1));
                        send(exchange,result==null?404:200,result==null?JSON.createObjectNode():result);return;
                    }
                    if(path.startsWith("organization/executions/")&&path.endsWith("/continuation-state")){
                        var result=organizationContinuations.get(path.split("/")[2]);send(exchange,result==null?404:200,result==null?JSON.createObjectNode():result);return;
                    }
                    if(path.startsWith("organization/executions/")&&path.endsWith("/start-state")){
                        var result=organizationRuns.get(path.split("/")[2]);send(exchange,result==null?404:200,result==null?JSON.createObjectNode():result);return;
                    }
                    if(path.startsWith("organization/executions/")) {
                        var result=organizationNative.get(path.split("/")[2]);send(exchange,result==null?404:200,result==null?JSON.createObjectNode():result);return;
                    }
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
    @Test void continuation_scope_survives_persistence_delegation_and_replay() throws Exception {
        for (String scope : List.of("omitted", "original_question", "original_plan")) {
            var body = input(UUID.randomUUID(), "scope-" + scope);
            var execution = body.putObject("execution").put("mode", "auto").put("model", "default");
            execution.putArray("branch_ids");
            if (!scope.equals("omitted")) execution.put("continuation_scope", scope);
            String key = UUID.randomUUID().toString();
            var response = request("alice", "POST", "/v1/tasks", body.toString(), key);
            assertThat(response.statusCode()).isEqualTo(200);
            var task = JSON.readTree(response.body());
            UUID id = UUID.fromString(task.path("id").asText());
            String expected = scope.equals("omitted") ? "original_question" : scope;
            var stored = JSON.readTree(store.command(id, "prepare").request()).path("session").path("execution");
            assertThat(stored.path("continuation_scope").asText()).isEqualTo(expected);
            assertThat(drafts.get(id.toString()).path("session").path("execution")).isEqualTo(stored);
            var reread = request("alice", "GET", "/v1/tasks/" + id, "", null);
            assertThat(JSON.readTree(reread.body()).path("research_options").path("execution")).isEqualTo(stored);
            int before = prepares.get();
            assertThat(request("alice", "POST", "/v1/tasks", body.toString(), key).statusCode()).isEqualTo(200);
            assertThat(prepares.get()).isEqualTo(before);
            execution.put("continuation_scope", expected.equals("original_plan") ? "original_question" : "original_plan");
            assertThat(request("alice", "POST", "/v1/tasks", body.toString(), key).statusCode()).isEqualTo(409);
        }
        var invalid = input(UUID.randomUUID(), "invalid-scope");
        var execution = invalid.putObject("execution").put("mode", "auto").put("model", "default").put("continuation_scope", "ignore_permissions");
        execution.putArray("branch_ids");
        int before = prepares.get();
        assertThat(request("alice", "POST", "/v1/tasks", invalid.toString(), UUID.randomUUID().toString()).statusCode()).isIn(400, 422);
        assertThat(prepares.get()).isEqualTo(before);
        execution.putNull("continuation_scope");
        assertThat(request("alice", "POST", "/v1/tasks", invalid.toString(), UUID.randomUUID().toString()).statusCode()).isIn(400, 422);
        assertThat(prepares.get()).isEqualTo(before);
    }
    @Test void full_catalog_option_is_explicit_typed_and_persisted() throws Exception {
        for (String selection : List.of("omitted", "false", "true")) {
            var body=input(UUID.randomUUID(),"catalog-"+selection);
            var options=body.putObject("execution").put("mode","standard").put("model","default");options.putArray("branch_ids");
            if(!selection.equals("omitted"))options.put("require_all_branches",selection.equals("true"));
            String key=UUID.randomUUID().toString();
            var response=request("alice","POST","/v1/tasks",body.toString(),key);
            assertThat(response.statusCode()).isEqualTo(200);
            UUID id=UUID.fromString(JSON.readTree(response.body()).path("id").asText());
            var saved=JSON.readTree(store.command(id,"prepare").request()).path("session").path("execution");
            assertThat(saved.path("require_all_branches").isBoolean()).isTrue();
            assertThat(saved.path("require_all_branches").asBoolean()).isEqualTo(selection.equals("true"));
            assertThat(drafts.get(id.toString()).path("session").path("execution")).isEqualTo(saved);
            int before=prepares.get();
            assertThat(request("alice","POST","/v1/tasks",body.toString(),key).statusCode()).isEqualTo(200);
            assertThat(prepares.get()).isEqualTo(before);
            options.put("require_all_branches",!selection.equals("true"));
            assertThat(request("alice","POST","/v1/tasks",body.toString(),key).statusCode()).isEqualTo(409);
        }
        for(String invalid:List.of("null","\"false\"","\"true\"","0","1","[]","{}")) {
            var body=input(UUID.randomUUID(),"invalid-catalog");
            var options=body.putObject("execution").put("mode","standard").put("model","default");options.putArray("branch_ids");
            options.set("require_all_branches",JSON.readTree(invalid));int before=prepares.get();
            assertThat(request("alice","POST","/v1/tasks",body.toString(),UUID.randomUUID().toString()).statusCode()).isIn(400,422);
            assertThat(prepares.get()).isEqualTo(before);
        }
        for(String mode:List.of("auto","selected","single")) {
            var body=input(UUID.randomUUID(),"invalid-catalog-mode");
            var options=body.putObject("execution").put("mode",mode).put("model","default").put("require_all_branches",true);
            options.putArray("branch_ids");int before=prepares.get();
            assertThat(request("alice","POST","/v1/tasks",body.toString(),UUID.randomUUID().toString()).statusCode()).isIn(400,422);
            assertThat(prepares.get()).isEqualTo(before);
        }
    }
    @Test void organization_old_prepare_bytes_and_digest_survive_new_option_support() throws Exception {
        var f=executionFixture();UUID id=UUID.randomUUID();
        workspace(f.researcher(),"POST",f.createPath(),Map.of("id",id,"manifest_digest",f.digest()),200);
        String base="/projects/"+f.project()+"/execution-bindings/"+id;
        var body=Map.of("execution",Map.of("mode","standard","model","default","branch_ids",List.of()));
        var saved=workspace(f.researcher(),"POST",base+"/prepare",body,200);
        assertThat(saved.path("execution").path("require_all_branches").isBoolean()).isTrue();
        // Reconstruct the pre-upgrade persisted representation, not a rewritten
        // API request. No new field existed in this durable command/receipt.
        var command=(ObjectNode)JSON.readTree(db.queryForObject("SELECT request_body FROM organization_native_preparation WHERE execution_id=?",String.class,id));
        ((ObjectNode)command.path("execution")).remove("require_all_branches");String oldBytes=command.toString();
        var receipt=(ObjectNode)saved.path("result").deepCopy();
        receipt.put("prepare_request_digest","sha256:"+Delegation.digest(oldBytes.getBytes(StandardCharsets.UTF_8)));
        db.update("UPDATE organization_native_preparation SET request_body=?,response=?::jsonb WHERE execution_id=?",oldBytes,receipt.toString(),id);
        int before=organizationCreates.get();
        var replay=workspace(f.researcher(),"POST",base+"/prepare",body,200);
        assertThat(replay.path("execution").has("require_all_branches")).isFalse();
        var grant=workspace(f.researcher(),"GET",base+"/preparation-access",null,200);
        assertThat(grant.path("prepare_request")).isEqualTo(command);
        assertThat(grant.path("prepare_request_digest")).isEqualTo(receipt.path("prepare_request_digest"));
        assertThat(replay.path("result").path("configuration_digest")).isEqualTo(saved.path("result").path("configuration_digest"));
        assertThat(db.queryForObject("SELECT request_body FROM organization_native_preparation WHERE execution_id=?",String.class,id)).isEqualTo(oldBytes);
        assertThat(organizationCreates.get()).isEqualTo(before);
        UUID next=UUID.randomUUID();workspace(f.researcher(),"POST",f.createPath(),Map.of("id",next,"manifest_digest",f.digest()),200);
        String other="/projects/"+f.project()+"/execution-bindings/"+next;
        var explicit=Map.of("execution",Map.of("mode","standard","model","default","branch_ids",List.of(),"require_all_branches",true));
        assertThat(workspace(f.researcher(),"POST",other+"/prepare",explicit,200).path("execution").path("require_all_branches").asBoolean()).isTrue();
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
        assertThat(db.queryForObject("SELECT count(*) FROM "+schema+".flyway_schema_history WHERE version='4' AND success",Integer.class)).isEqualTo(1);
        assertThat(db.queryForObject("SELECT count(*) FROM "+schema+".flyway_schema_history WHERE version='5' AND success",Integer.class)).isEqualTo(1);
        assertThat(db.queryForObject("SELECT count(*) FROM "+schema+".organization_research_draft",Integer.class)).isZero();
        assertThat(db.queryForObject("SELECT count(*) FROM "+schema+".flyway_schema_history WHERE version='6' AND success",Integer.class)).isEqualTo(1);
        assertThat(db.queryForObject("SELECT count(*) FROM "+schema+".organization_execution_binding",Integer.class)).isZero();
        assertThat(db.queryForObject("SELECT count(*) FROM "+schema+".flyway_schema_history WHERE version='7' AND success",Integer.class)).isEqualTo(1);
        assertThat(db.queryForObject("SELECT count(*) FROM "+schema+".organization_native_preparation",Integer.class)).isZero();
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
    @Test void project_resource_links_require_both_permissions_and_do_not_publish_personal_data() throws Exception {
        String admin="link-admin",bob="link-bob",outsider="link-outsider";
        UUID org=UUID.randomUUID(),project=UUID.randomUUID(),team=UUID.randomUUID(),resource=UUID.randomUUID();
        var created=workspace(admin,"POST","/organizations",Map.of("id",org,"name","关联组织","display_name","管理员"),200);
        UUID personal=UUID.fromString(created.path("spaces").get(0).path("id").asText());
        joinProjectOrganization(admin,bob,org);
        workspace(admin,"POST","/projects",Map.of("id",project,"organization_id",org,"name","项目","description","合成验收"),200);
        workspace(admin,"POST","/projects/"+project+"/members",Map.of("revision",1,"subject",bob,"role","viewer"),200);
        workspace(admin,"POST","/spaces",Map.of("id",team,"organization_id",org,"name","内部资料"),200);
        UUID privateResource=UUID.randomUUID();
        for(UUID space:List.of(team,personal))workspace(admin,"POST","/resources",Map.of("id",space.equals(team)?resource:privateResource,"space_id",space,"title","机密固定版本","resource_type","files",
            "binding",Map.of("organization_id",org,"space_id",space,"ref",Map.of("version_id","fixed-v1"))),200);
        String base="/projects/"+project+"/resources",link=base+"/"+resource;
        workspace(admin,"POST",base+"/"+privateResource,Map.of("revision",2,"linked",true),409);
        workspace(bob,"POST",link,Map.of("revision",2,"linked",true),403);
        workspace(admin,"POST",link,Map.of("revision",2,"linked",true),200);
        assertThat(workspace(bob,"GET",base,null,200).toString()).doesNotContain("机密","fixed-v1",resource.toString());
        workspace(bob,"POST",link+"/access",null,404);
        workspace(outsider,"GET",base,null,404);
        workspace(admin,"POST","/spaces/"+team+"/members",Map.of("subject",bob,"role","reader"),200);
        var visible=workspace(bob,"GET",base,null,200).path("items");
        assertThat(visible).hasSize(1);assertThat(visible.get(0).path("version_id").asText()).isEqualTo("fixed-v1");
        assertThat(visible.toString()).doesNotContain("binding");
        workspace(bob,"POST",link+"/access",null,200);
        assertThat(workspace(bob,"GET","/spaces/"+team+"/resources?project_id="+project,null,200).path("items")).hasSize(1);
        workspace(admin,"POST","/spaces/"+team+"/members",Map.of("subject",bob,"role","remove"),200);
        assertThat(workspace(bob,"GET",base,null,200).path("items")).isEmpty();
        workspace(bob,"POST",link+"/access",null,404);
        workspace(admin,"POST","/spaces/"+team+"/members",Map.of("subject",bob,"role","reader"),200);
        workspace(admin,"POST","/projects/"+project+"/members",Map.of("revision",3,"subject",bob,"role","remove"),200);
        workspace(bob,"GET","/spaces/"+team+"/resources?project_id="+project,null,404);
        workspace(bob,"POST",link+"/access",null,404);
        // Losing the project cannot remove a separately granted source permission.
        workspace(bob,"POST","/resources/"+resource+"/access",null,200);
        workspace(admin,"POST","/resources/"+resource+"/revoke",Map.of("revision",1),200);
        assertThat(workspace(admin,"GET",base,null,200).path("items")).isEmpty();
        workspace(admin,"POST",link+"/access",null,404);
        assertThat(db.queryForObject("SELECT count(*) FROM organization_project_resource WHERE project_id=?",Integer.class,project)).isEqualTo(1);
        workspace(admin,"POST",link,Map.of("revision",4,"linked",false),200);
        workspace(admin,"POST",link,Map.of("revision",5,"linked",true),404);
    }
    @Test void project_resource_concurrent_changes_and_cross_organization_are_safe() throws Exception {
        String admin="link-conflict";UUID org=UUID.randomUUID(),other=UUID.randomUUID(),project=UUID.randomUUID(),team=UUID.randomUUID(),foreign=UUID.randomUUID();
        for(UUID o:List.of(org,other))workspace(admin,"POST","/organizations",Map.of("id",o,"name","组织","display_name","管理者"),200);
        workspace(admin,"POST","/projects",Map.of("id",project,"organization_id",org,"name","项目","description",""),200);
        workspace(admin,"POST","/spaces",Map.of("id",team,"organization_id",org,"name","团队"),200);
        workspace(admin,"POST","/spaces",Map.of("id",foreign,"organization_id",other,"name","另一组织团队"),200);
        UUID resource=UUID.randomUUID(),foreignResource=UUID.randomUUID();
        for(UUID s:List.of(team,foreign))workspace(admin,"POST","/resources",Map.of("id",s.equals(team)?resource:foreignResource,"space_id",s,"title","发布版本","resource_type","database",
            "binding",Map.of("organization_id",s.equals(team)?org:other,"space_id",s)),200);
        String base="/projects/"+project+"/resources";
        workspace(admin,"POST",base+"/"+foreignResource,Map.of("revision",1,"linked",true),404);
        workspace(admin,"GET","/spaces/"+foreign+"/resources?project_id="+project,null,404);
        UUID secondProject=UUID.randomUUID();
        workspace(admin,"POST","/projects",Map.of("id",secondProject,"organization_id",org,"name","第二项目","description",""),200);
        workspace(admin,"POST","/projects/"+secondProject+"/resources/"+resource,Map.of("revision",1,"linked",true),200);
        try(var pool=Executors.newVirtualThreadPerTaskExecutor()) {
            String body=JSON.writeValueAsString(Map.of("revision",1,"linked",true));
            var first=pool.submit(()->request(admin,"POST","/v1/workspaces"+base+"/"+resource,body,null));
            var second=pool.submit(()->request(admin,"POST","/v1/workspaces"+base+"/"+resource,body,null));
            assertThat(List.of(first.get().statusCode(),second.get().statusCode())).containsExactlyInAnyOrder(200,409);
        }
        assertThat(db.queryForObject("SELECT count(*) FROM organization_project_resource WHERE project_id=?",Integer.class,project)).isEqualTo(1);
        workspace(admin,"POST",base+"/"+resource,Map.of("revision",2,"linked",false),200);
        workspace(admin,"POST",base+"/"+resource,Map.of("revision",1,"linked",true),409); // Late retry cannot restore an old link.
        assertThat(workspace(admin,"GET",base,null,200).path("items")).isEmpty();
        workspace(admin,"POST","/resources/"+resource+"/access",null,200); // Unlink is not revoke.
        workspace(admin,"POST","/projects/"+secondProject+"/resources/"+resource+"/access",null,200);
        workspace(admin,"POST","/projects/"+project,Map.of("revision",3,"name","项目","description","","archived",true),200);
        workspace(admin,"POST",base+"/"+resource,Map.of("revision",4,"linked",true),409);
    }
    @Test void project_resource_pagination_filters_hidden_sources_before_limit() throws Exception {
        String admin="link-pages",bob="link-pages-reader";UUID org=UUID.randomUUID(),project=UUID.randomUUID(),team=UUID.randomUUID(),hidden=UUID.randomUUID();
        workspace(admin,"POST","/organizations",Map.of("id",org,"name","分页组织","display_name","管理员"),200);joinProjectOrganization(admin,bob,org);
        workspace(admin,"POST","/projects",Map.of("id",project,"organization_id",org,"name","项目","description",""),200);
        workspace(admin,"POST","/projects/"+project+"/members",Map.of("revision",1,"subject",bob,"role","viewer"),200);
        for(UUID s:List.of(team,hidden))workspace(admin,"POST","/spaces",Map.of("id",s,"organization_id",org,"name","空间"),200);
        workspace(admin,"POST","/spaces/"+team+"/members",Map.of("subject",bob,"role","reader"),200);
        int revision=2;
        for(int i=0;i<34;i++) {
            UUID id=UUID.randomUUID(),s=i<31?team:hidden;
            workspace(admin,"POST","/resources",Map.of("id",id,"space_id",s,"title",i<31?"Visible "+i:"Secret "+i,"resource_type","knowledge","binding",Map.of("organization_id",org,"space_id",s)),200);
            workspace(admin,"POST","/projects/"+project+"/resources/"+id,Map.of("revision",revision++,"linked",true),200);
        }
        String path="/projects/"+project+"/resources?type=knowledge";
        var first=workspace(bob,"GET",path,null,200);var second=workspace(bob,"GET",path+"&offset=30",null,200);
        assertThat(first.path("items")).hasSize(30);assertThat(second.path("items")).hasSize(1);
        assertThat(second.path("next_offset").isNull()).isTrue();assertThat(first.toString()+second).doesNotContain("Secret");
        Set<String> ids=new HashSet<>();for(var r:first.path("items"))ids.add(r.path("id").asText());for(var r:second.path("items"))ids.add(r.path("id").asText());assertThat(ids).hasSize(31);
        assertThat(workspace(bob,"GET",path+"&query=Secret",null,200).path("items")).isEmpty();
        assertThat(workspace(bob,"GET",path+"&query=%25",null,200).path("items")).isEmpty();
        workspace(admin,"POST","/organizations/"+org+"/remove-member",Map.of("subject",bob),200);
        workspace(bob,"GET",path,null,404);
    }
    @Test void organization_preparation_freezes_all_inputs_and_hides_entire_draft_after_revocation() throws Exception {
        String admin="draft-admin",bob="draft-bob";UUID org=UUID.randomUUID(),project=UUID.randomUUID(),team=UUID.randomUUID(),restricted=UUID.randomUUID();
        UUID first=UUID.randomUUID(),second=UUID.randomUUID(),draft=UUID.randomUUID();
        workspace(admin,"POST","/organizations",Map.of("id",org,"name","准备组织","display_name","管理员"),200);joinProjectOrganization(admin,bob,org);
        workspace(admin,"POST","/projects",Map.of("id",project,"organization_id",org,"name","研究项目","description",""),200);
        workspace(admin,"POST","/projects/"+project+"/members",Map.of("revision",1,"subject",bob,"role","viewer"),200);
        int revision=2;
        for(UUID s:List.of(team,restricted)) {
            UUID resource=s.equals(team)?first:second;
            workspace(admin,"POST","/spaces",Map.of("id",s,"organization_id",org,"name","资料组"),200);
            workspace(admin,"POST","/resources",Map.of("id",resource,"space_id",s,"title","固定原件","resource_type","files",
                "binding",Map.of("organization_id",org,"space_id",s,"ref",Map.of("project_id",s,"kind","document","asset_id","UPLOAD::fixed","version_id","UPLOAD::v1","digest","a".repeat(64)))),200);
            workspace(admin,"POST","/projects/"+project+"/resources/"+resource,Map.of("revision",revision++,"linked",true),200);
            workspace(admin,"POST","/spaces/"+s+"/members",Map.of("subject",bob,"role","reader"),200);
        }
        String base="/projects/"+project+"/research-drafts";
        var body=Map.of("id",draft,"title","不可泄露的问题摘要","question","根据这些固定资料核对资本开支与现金流。","research_as_of","2026-09-30","resource_ids",List.of(first,second));
        int nativeTasks=db.queryForObject("SELECT count(*) FROM research_task",Integer.class);
        workspace(bob,"POST",base,body,403);
        workspace(admin,"POST","/projects/"+project+"/members",Map.of("revision",4,"subject",bob,"role","researcher"),200);
        JsonNode saved=workspace(bob,"POST",base,body,200);
        assertThat(saved.path("execution_enabled").asBoolean()).isFalse();assertThat(saved.path("status").asText()).isEqualTo("inputs_saved");
        assertThat(saved.path("manifest").path("inputs")).hasSize(2);assertThat(saved.toString()).doesNotContain("binding","thread_id","run_id");
        assertThat(workspace(bob,"POST",base,body,200)).isEqualTo(saved);
        assertThat(db.queryForObject("SELECT count(*) FROM research_task",Integer.class)).isEqualTo(nativeTasks);
        assertThat(db.queryForObject("SELECT count(*) FROM organization_project_audit WHERE project_id=? AND action='research_inputs_save'",Integer.class,project)).isEqualTo(1);
        var changed=new HashMap<String,Object>(body);changed.put("question","另外一项问题不可以占用相同的准备凭证。");
        workspace(bob,"POST",base,changed,409);
        changed=new HashMap<>(body);changed.put("id",UUID.randomUUID());changed.put("resource_ids",List.of(first,first));workspace(bob,"POST",base,changed,422);
        workspace(bob,"POST",base+"/"+draft+"/material-access",null,200);
        workspace(admin,"POST","/spaces/"+restricted+"/members",Map.of("subject",bob,"role","remove"),200);
        var hidden=workspace(bob,"GET",base,null,200);assertThat(hidden.path("items")).isEmpty();assertThat(hidden.toString()).doesNotContain("不可泄露",draft.toString());
        workspace(bob,"GET",base+"/"+draft,null,404);workspace(bob,"POST",base,body,404);
        workspace(bob,"POST",base+"/"+draft+"/material-access",null,404);
        assertThat(workspace(admin,"GET",base+"/"+draft,null,200).path("manifest_digest")).isEqualTo(saved.path("manifest_digest"));
        workspace(admin,"POST","/spaces/"+restricted+"/members",Map.of("subject",bob,"role","reader"),200);
        workspace(admin,"POST","/projects/"+project+"/members",Map.of("revision",5,"subject",bob,"role","viewer"),200);
        workspace(bob,"GET",base+"/"+draft,null,200);workspace(bob,"POST",base+"/"+draft+"/material-access",null,403);
        workspace(admin,"POST","/projects/"+project+"/resources/"+first,Map.of("revision",6,"linked",false),200);
        workspace(admin,"GET",base+"/"+draft,null,404);
        assertThat(db.queryForObject("SELECT count(*) FROM organization_research_input WHERE draft_id=?",Integer.class,draft)).isEqualTo(2);
        workspace(admin,"POST","/projects/"+project+"/resources/"+first,Map.of("revision",7,"linked",true),200);
        assertThat(workspace(admin,"GET",base+"/"+draft,null,200).path("manifest_digest")).isEqualTo(saved.path("manifest_digest"));
        workspace(admin,"POST","/resources/"+second+"/revoke",Map.of("revision",1),200);
        workspace(admin,"GET",base+"/"+draft,null,404);
    }
    @Test void preparation_replay_concurrency_archive_and_invalid_input_fail_without_execution() throws Exception {
        String admin="draft-replay";UUID org=UUID.randomUUID(),project=UUID.randomUUID(),team=UUID.randomUUID(),resource=UUID.randomUUID(),draft=UUID.randomUUID();
        workspace(admin,"POST","/organizations",Map.of("id",org,"name","组织","display_name","管理员"),200);
        workspace(admin,"POST","/projects",Map.of("id",project,"organization_id",org,"name","项目","description",""),200);
        workspace(admin,"POST","/spaces",Map.of("id",team,"organization_id",org,"name","团队"),200);
        workspace(admin,"POST","/resources",Map.of("id",resource,"space_id",team,"title","固定版本","resource_type","database",
            "binding",Map.of("organization_id",org,"space_id",team,"ref",Map.of("project_id",team,"kind","document","asset_id","UPLOAD::db","version_id","UPLOAD::db-v1","digest","b".repeat(64)))),200);
        String base="/projects/"+project+"/research-drafts";
        var body=Map.of("id",draft,"title","并发准备","question","请核对所选资料中的期间及财务单位。","research_as_of","2026-09-30","resource_ids",List.of(resource));
        workspace(admin,"POST",base,body,404); // A source permission alone does not supply a project link.
        workspace(admin,"POST","/projects/"+project+"/resources/"+resource,Map.of("revision",1,"linked",true),200);
        try(var pool=Executors.newVirtualThreadPerTaskExecutor()) {
            var calls=new ArrayList<Future<JsonNode>>();
            for(int i=0;i<5;i++)calls.add(pool.submit(()->workspace(admin,"POST",base,body,200)));
            var first=calls.getFirst().get();for(var call:calls)assertThat(call.get()).isEqualTo(first);
        }
        assertThat(db.queryForObject("SELECT count(*) FROM organization_research_draft WHERE project_id=?",Integer.class,project)).isEqualTo(1);
        var extra=new HashMap<String,Object>(body);extra.put("owner_id","arbitrary");workspace(admin,"POST",base,extra,400);
        workspace(admin,"POST","/projects/"+project,Map.of("revision",2,"name","项目","description","","archived",true),200);
        workspace(admin,"GET",base+"/"+draft,null,200);workspace(admin,"POST",base,body,409);
        workspace(admin,"POST",base+"/"+draft+"/material-access",null,409);
        workspace(admin,"GET","/projects/"+UUID.randomUUID()+"/research-drafts/"+draft,null,404);
    }
    record ExecutionFixture(String admin,String researcher,UUID org,UUID project,UUID space,UUID resource,UUID draft,String digest) {
        String createPath() {return "/projects/"+project+"/research-drafts/"+draft+"/execution-bindings";}
    }
    ExecutionFixture executionFixture() throws Exception {
        String admin="execution-admin-"+UUID.randomUUID(),researcher="execution-user-"+UUID.randomUUID();
        UUID org=UUID.randomUUID(),project=UUID.randomUUID(),space=UUID.randomUUID(),resource=UUID.randomUUID(),draft=UUID.randomUUID();
        workspace(admin,"POST","/organizations",Map.of("id",org,"name","执行组织","display_name","管理员"),200);
        joinProjectOrganization(admin,researcher,org);
        workspace(admin,"POST","/projects",Map.of("id",project,"organization_id",org,"name","研究项目","description",""),200);
        workspace(admin,"POST","/projects/"+project+"/members",Map.of("revision",1,"subject",researcher,"role","researcher"),200);
        workspace(admin,"POST","/spaces",Map.of("id",space,"organization_id",org,"name","团队"),200);
        workspace(admin,"POST","/spaces/"+space+"/members",Map.of("subject",researcher,"role","reader"),200);
        workspace(admin,"POST","/resources",Map.of("id",resource,"space_id",space,"title","固定原件","resource_type","files",
            "binding",Map.of("organization_id",org,"space_id",space,"ref",Map.of("project_id",space,"kind","document","asset_id","UPLOAD::fixed","version_id","UPLOAD::v1","digest","a".repeat(64)))),200);
        workspace(admin,"POST","/projects/"+project+"/resources/"+resource,Map.of("revision",2,"linked",true),200);
        var prepared=workspace(researcher,"POST","/projects/"+project+"/research-drafts",Map.of("id",draft,"title","执行准备","question","核对组织固定输入中的财务期间和单位。","research_as_of","2026-10-12","resource_ids",List.of(resource)),200);
        return new ExecutionFixture(admin,researcher,org,project,space,resource,draft,prepared.path("manifest_digest").asText());
    }
    @Test void retrieval_release_is_immutable_project_scoped_and_frozen_without_changing_legacy_drafts() throws Exception {
        var f=executionFixture();
        String drafts="/projects/"+f.project()+"/research-drafts",releases="/projects/"+f.project()+"/retrieval-releases";
        var legacy=workspace(f.researcher(),"GET",drafts+"/"+f.draft(),null,200);
        assertThat(legacy.path("manifest").has("retrieval_index")).isFalse();
        UUID first=UUID.randomUUID(),second=UUID.randomUUID();
        var publication=new HashMap<String,Object>(Map.of("id",first,"source_draft_id",f.draft(),
            "index_digest","b".repeat(64),"matrix_sha256","c".repeat(64),
            "model","qwen3.7-text-embedding","dimensions",1024,"projection","organization-text-6000.v1"));
        var invalidProjection=new HashMap<>(publication);
        invalidProjection.put("projection","organization-text-6000Xv1");
        workspace(f.admin(),"POST",releases,invalidProjection,400);
        workspace(f.researcher(),"POST",releases,publication,403);
        var contract=workspace(f.admin(),"POST",releases,publication,200);
        var recovered=workspace(f.admin(),"GET",releases+"/"+first,null,200);
        assertThat(recovered.path("contract")).isEqualTo(contract);
        assertThat(recovered.path("source_draft_id").asText()).isEqualTo(f.draft().toString());
        workspace(f.admin(),"GET",releases+"/"+UUID.randomUUID(),null,404);
        assertThat(workspace(f.admin(),"POST",releases,publication,200)).isEqualTo(contract);
        var changed=new HashMap<>(publication);changed.put("index_digest","d".repeat(64));
        workspace(f.admin(),"POST",releases,changed,409);
        UUID preparedId=UUID.randomUUID();
        var create=new HashMap<String,Object>(Map.of("id",preparedId,"title","固定检索版本",
            "question","核对组织固定输入中的公司期间和单位。","research_as_of","2026-10-12",
            "resource_ids",List.of(f.resource()),"retrieval_release_id",first));
        var prepared=workspace(f.researcher(),"POST",drafts,create,200);
        assertThat(prepared.path("manifest").path("retrieval_index")).isEqualTo(contract);
        changed.put("id",second);
        workspace(f.admin(),"POST",releases,changed,200);
        assertThat(workspace(f.researcher(),"POST",drafts,create,200)).isEqualTo(prepared);
        assertThat(workspace(f.researcher(),"GET",drafts+"/"+f.draft(),null,200)).isEqualTo(legacy);
        assertThat(workspace(f.researcher(),"GET",releases,null,200).path("items").size()).isEqualTo(2);
        var other=executionFixture();
        workspace(other.admin(),"GET","/projects/"+other.project()+"/retrieval-releases/"+first,null,404);
        var foreign=new HashMap<>(create);foreign.put("id",UUID.randomUUID());foreign.put("resource_ids",List.of(other.resource()));
        workspace(other.researcher(),"POST","/projects/"+other.project()+"/research-drafts",foreign,404);
        workspace(f.admin(),"POST","/spaces/"+f.space()+"/members",Map.of("subject",f.researcher(),"role","remove"),200);
        assertThat(workspace(f.researcher(),"GET",releases,null,200).path("items").size()).isZero();
        workspace(f.researcher(),"GET",releases+"/"+first,null,404);
        workspace(f.researcher(),"GET",drafts+"/"+preparedId,null,404);
    }
    @Test void focal_inputs_and_searchable_scope_are_separate_current_dependencies() throws Exception {
        var f=executionFixture();String base="/projects/"+f.project()+"/research-drafts";
        var legacy=workspace(f.researcher(),"GET",base+"/"+f.draft(),null,200);
        var ids=new ArrayList<UUID>();ids.add(f.resource());
        for(int n=0;n<18;n++) {
            UUID id=UUID.randomUUID();ids.add(id);
            workspace(f.admin(),"POST","/resources",Map.of("id",id,"space_id",f.space(),"title","候选资料"+n,"resource_type","knowledge",
                "binding",Map.of("organization_id",f.org(),"space_id",f.space(),"ref",Map.of("project_id",f.space(),"kind","document","asset_id","UPLOAD::candidate"+n,"version_id","UPLOAD::v1-"+n,"digest","b".repeat(64)))),200);
            int revision=workspace(f.admin(),"GET","/projects/"+f.project(),null,200).path("revision").asInt();
            workspace(f.admin(),"POST","/projects/"+f.project()+"/resources/"+id,Map.of("revision",revision,"linked",true),200);
        }
        var body=new HashMap<String,Object>(Map.of("id",UUID.randomUUID(),"title","两份重点资料与19份检索范围",
            "question","核对重点披露并在候选资料中寻找补充证据。","research_as_of","2026-10-12",
            "resource_ids",ids.subList(0,2),"retrieval_resource_ids",ids));
        var prepared=workspace(f.researcher(),"POST",base,body,200);
        assertThat(prepared.path("manifest").path("inputs")).hasSize(19);
        assertThat(prepared.path("manifest").path("input_selection").path("selected_resource_ids")).hasSize(2);
        assertThat(workspace(f.researcher(),"POST",base,body,200)).isEqualTo(prepared);
        assertThat(workspace(f.researcher(),"GET",base+"/"+f.draft(),null,200)).isEqualTo(legacy);
        var invalid=new HashMap<>(body);invalid.put("id",UUID.randomUUID());invalid.put("resource_ids",ids);
        workspace(f.researcher(),"POST",base,invalid,400);
        invalid.put("resource_ids",ids.subList(0,2));invalid.put("retrieval_resource_ids",ids.subList(2,19));
        workspace(f.researcher(),"POST",base,invalid,422);
        invalid.put("retrieval_resource_ids",List.of(ids.getFirst(),ids.getFirst()));
        workspace(f.researcher(),"POST",base,invalid,422);
        invalid.put("retrieval_resource_ids",List.of(ids.get(0),ids.get(1),UUID.randomUUID()));
        workspace(f.researcher(),"POST",base,invalid,404);
        var large=new ArrayList<>(ids.subList(0,2));
        while(large.size()<2048)large.add(UUID.randomUUID());
        invalid.put("retrieval_resource_ids",large);
        // >64 KiB must reach source authorization, not the old transport cap.
        workspace(f.researcher(),"POST",base,invalid,404);
        large.add(UUID.randomUUID());workspace(f.researcher(),"POST",base,invalid,400);
        var changed=new HashMap<>(body);changed.put("resource_ids",ids.subList(0,1));
        workspace(f.researcher(),"POST",base,changed,409);
        UUID execution=UUID.randomUUID();String saved=prepared.path("id").asText(),digest=prepared.path("manifest_digest").asText();
        workspace(f.researcher(),"POST",base+"/"+saved+"/execution-bindings",Map.of("id",execution,"manifest_digest",digest),200);
        assertThat(runtimeAccess(execution,digest,200).path("inputs")).hasSize(19);
        workspace(f.admin(),"POST","/resources/"+ids.getLast()+"/revoke",Map.of("revision",1),200);
        workspace(f.researcher(),"GET",base+"/"+saved,null,404);
        workspace(f.researcher(),"POST",base,body,404);
        runtimeAccess(execution,digest,404);
        assertThat(workspace(f.researcher(),"GET",base+"/"+f.draft(),null,200)).isEqualTo(legacy);
    }
    HttpResponse<String> runtimeRequest(String path,String body,String signedPath,String signingKey) throws Exception {
        var now=Instant.now();
        var claims=new JWTClaimsSet.Builder().issuer("finsight-agent-runtime").audience("finsight-java-organization-runtime").subject("finsight-agent-runtime")
            .issueTime(Date.from(now)).expirationTime(Date.from(now.plusSeconds(60))).claim("method","POST").claim("path",signedPath)
            .claim("body_sha256",Delegation.digest(body.getBytes(StandardCharsets.UTF_8))).build();
        var token=new SignedJWT(new JWSHeader(JWSAlgorithm.HS256),claims);token.sign(new MACSigner(signingKey));
        return client.send(HttpRequest.newBuilder(URI.create("http://127.0.0.1:"+port+path)).header("Authorization","Bearer "+token.serialize())
            .header("Content-Type","application/json").POST(HttpRequest.BodyPublishers.ofString(body)).build(),HttpResponse.BodyHandlers.ofString());
    }
    JsonNode runtimeAccess(UUID id,String digest,int status) throws Exception {
        String path="/v1/runtime/organization-executions/"+id+"/access";
        var reply=runtimeRequest(path,JSON.writeValueAsString(Map.of("thread_id",id,"manifest_digest",digest)),path,RUNTIME_SECRET);
        assertThat(reply.statusCode()).withFailMessage(reply.body()).isEqualTo(status);return JSON.readTree(reply.body());
    }
    @Test void execution_binding_is_idempotent_current_and_never_dispatches() throws Exception {
        var f=executionFixture();UUID id=UUID.randomUUID();var body=Map.of("id",id,"manifest_digest",f.digest());
        int tasks=db.queryForObject("SELECT count(*) FROM research_task",Integer.class);
        try(var pool=Executors.newVirtualThreadPerTaskExecutor()) {
            var calls=new ArrayList<Future<JsonNode>>();
            for(int i=0;i<5;i++)calls.add(pool.submit(()->workspace(f.researcher(),"POST",f.createPath(),body,200)));
            var first=calls.getFirst().get();for(var call:calls)assertThat(call.get()).isEqualTo(first);
            assertThat(first.path("thread_id").asText()).isEqualTo(id.toString());assertThat(first.path("native_execution_enabled").asBoolean()).isFalse();
        }
        assertThat(db.queryForObject("SELECT count(*) FROM organization_execution_binding WHERE id=?",Integer.class,id)).isEqualTo(1);
        assertThat(db.queryForObject("SELECT count(*) FROM organization_project_audit WHERE project_id=? AND action='execution_bind'",Integer.class,f.project())).isEqualTo(1);
        workspace(f.admin(),"POST",f.createPath(),body,409); // An administrator cannot replay as another principal.
        var grant=runtimeAccess(id,f.digest(),200);
        assertThat("sha256:"+Delegation.digest(grant.path("manifest_text").asText().getBytes(StandardCharsets.UTF_8))).isEqualTo(f.digest());
        assertThat(grant.path("inputs")).hasSize(1);
        runtimeAccess(id,"sha256:"+"0".repeat(64),404);
        workspace(f.admin(),"POST","/spaces/"+f.space()+"/members",Map.of("subject",f.researcher(),"role","remove"),200);
        runtimeAccess(id,f.digest(),404);
        workspace(f.admin(),"POST","/spaces/"+f.space()+"/members",Map.of("subject",f.researcher(),"role","reader"),200);
        runtimeAccess(id,f.digest(),200); // Restores reads only, never resumes a run.
        workspace(f.admin(),"POST","/projects/"+f.project()+"/members",Map.of("revision",3,"subject",f.researcher(),"role","viewer"),200);
        runtimeAccess(id,f.digest(),404);
        assertThat(db.queryForObject("SELECT count(*) FROM research_task",Integer.class)).isEqualTo(tasks);
    }
    @Test void execution_close_survives_replay_and_permission_restoration() throws Exception {
        var f=executionFixture();UUID id=UUID.randomUUID();var body=Map.of("id",id,"manifest_digest",f.digest());
        workspace(f.researcher(),"POST",f.createPath(),body,200);
        workspace(f.admin(),"POST","/projects/"+f.project(),Map.of("revision",3,"name","项目","description","","archived",true),200);
        runtimeAccess(id,f.digest(),404);
        String close="/projects/"+f.project()+"/execution-bindings/"+id+"/close";
        var closed=workspace(f.researcher(),"POST",close,null,200);assertThat(closed.path("status").asText()).isEqualTo("closed");
        assertThat(workspace(f.researcher(),"POST",close,null,200)).isEqualTo(closed);
        workspace(f.admin(),"POST","/projects/"+f.project(),Map.of("revision",4,"name","项目","description","","archived",false),200);
        assertThat(workspace(f.researcher(),"POST",f.createPath(),body,200)).isEqualTo(closed);
        runtimeAccess(id,f.digest(),404);
        assertThat(db.queryForObject("SELECT count(*) FROM organization_project_audit WHERE project_id=? AND action='execution_close'",Integer.class,f.project())).isEqualTo(1);
    }
    @Test void workload_credentials_cannot_impersonate_users_or_change_request_scope() throws Exception {
        var f=executionFixture();UUID id=UUID.randomUUID();workspace(f.researcher(),"POST",f.createPath(),Map.of("id",id,"manifest_digest",f.digest()),200);
        String path="/v1/runtime/organization-executions/"+id+"/access",body=JSON.writeValueAsString(Map.of("thread_id",id,"manifest_digest",f.digest()));
        assertThat(request(f.researcher(),"POST",path,body,null).statusCode()).isEqualTo(401);
        // Servlet path normalization must not move a business credential into the workload namespace.
        for(String alias:List.of(path.replace("runtime","%72untime"),path.replace("runtime/","runtime;alias/"),path.replace("/v1/","/v1//"),path.replace("runtime/","runtime/../runtime/")))
            assertThat(request(f.researcher(),"POST",alias,body,null).statusCode()).isBetween(400,499);
        assertThat(runtimeRequest(path,body,path,SECRET).statusCode()).isEqualTo(401);
        assertThat(runtimeRequest(path,body,path+"?unbound=true",RUNTIME_SECRET).statusCode()).isEqualTo(401);
        assertThat(runtimeRequest("/v1/workspaces/organizations","{}","/v1/workspaces/organizations",RUNTIME_SECRET).statusCode()).isEqualTo(401);
        String impersonation=JSON.writeValueAsString(Map.of("thread_id",id,"manifest_digest",f.digest(),"owner_id",f.admin()));
        assertThat(runtimeRequest(path,impersonation,path,RUNTIME_SECRET).statusCode()).isEqualTo(400);
        workspace(f.admin(),"POST","/organizations/"+f.org()+"/remove-member",Map.of("subject",f.researcher()),200);
        runtimeAccess(id,f.digest(),404);
        assertThatThrownBy(()->new RuntimeDelegation(SECRET,SECRET)).isInstanceOf(IllegalArgumentException.class);
    }
    @Test void organization_native_prepare_concurrency_pins_options_and_reauthorizes_receipts() throws Exception {
        var f=executionFixture();UUID id=UUID.randomUUID();workspace(f.researcher(),"POST",f.createPath(),Map.of("id",id,"manifest_digest",f.digest()),200);
        String base="/projects/"+f.project()+"/execution-bindings/"+id;
        var options=Map.of("mode","auto","model","default","branch_ids",List.of(),"continuation_scope","original_plan","require_all_branches",false);
        var input=Map.of("execution",options);int before=organizationCreates.get();
        try(var pool=Executors.newVirtualThreadPerTaskExecutor()) {
            var calls=new ArrayList<Future<JsonNode>>();for(int i=0;i<5;i++)calls.add(pool.submit(()->workspace(f.researcher(),"POST",base+"/prepare",input,200)));
            for(var call:calls)assertThat(call.get().path("execution")).isEqualTo(JSON.valueToTree(options));
        }
        var saved=workspace(f.researcher(),"GET",base+"/preparation",null,200);
        assertThat(saved.path("status").asText()).isEqualTo("received");assertThat(organizationCreates.get()-before).isEqualTo(1);
        assertThat(workspace(f.researcher(),"POST",base+"/prepare",input,200)).isEqualTo(saved);
        var changed=new HashMap<String,Object>(options);changed.put("model","deepseek-v4-pro");
        workspace(f.researcher(),"POST",base+"/prepare",Map.of("execution",changed),409);
        var grant=workspace(f.researcher(),"GET",base+"/preparation-access",null,200);
        assertThat(grant.path("prepare_operation_id")).isEqualTo(saved.path("operation_id"));
        assertThat(grant.path("prepare_request").path("execution")).isEqualTo(JSON.valueToTree(options));
        workspace(f.admin(),"GET",base+"/preparation-access",null,404);
        workspace(f.admin(),"POST","/spaces/"+f.space()+"/members",Map.of("subject",f.researcher(),"role","remove"),200);
        workspace(f.researcher(),"GET",base+"/preparation",null,404);
        assertThat(organizationCreates.get()-before).isEqualTo(1);
    }
    @Test void organization_native_unknown_reconciles_exact_operation_without_redispatch() throws Exception {
        var f=executionFixture();UUID id=UUID.randomUUID();workspace(f.researcher(),"POST",f.createPath(),Map.of("id",id,"manifest_digest",f.digest()),200);
        String base="/projects/"+f.project()+"/execution-bindings/"+id;
        var input=Map.of("execution",Map.of("mode","auto","model","default","branch_ids",List.of()));
        dropOrganizationPrepare.add(id.toString());int before=organizationCreates.get();
        assertThat(workspace(f.researcher(),"POST",base+"/prepare",input,200).path("status").asText()).isEqualTo("unknown");
        var original=organizationNative.get(id.toString()).deepCopy();
        organizationNative.get(id.toString()).put("prepare_operation_id",UUID.randomUUID().toString());
        assertThat(workspace(f.researcher(),"POST",base+"/reconcile",null,200).path("status").asText()).isEqualTo("unknown");
        assertThat(workspace(f.researcher(),"POST",base+"/prepare",input,200).path("status").asText()).isEqualTo("unknown");
        organizationNative.put(id.toString(),original);
        var recovered=workspace(f.researcher(),"POST",base+"/reconcile",null,200);
        assertThat(recovered.path("status").asText()).isEqualTo("received");
        assertThat(recovered.path("result").path("thread_id").asText()).isEqualTo(id.toString());
        assertThat(organizationCreates.get()-before).isEqualTo(1);
        workspace(f.researcher(),"POST",base+"/close",null,200);
        workspace(f.researcher(),"GET",base+"/preparation",null,409);
    }
    @Test void organization_continuation_lost_receipt_concurrency_and_independent_admission() throws Exception {
        var f=executionFixture();UUID id=UUID.randomUUID();
        workspace(f.researcher(),"POST",f.createPath(),Map.of("id",id,"manifest_digest",f.digest()),200);
        String base="/projects/"+f.project()+"/execution-bindings/"+id;
        workspace(f.researcher(),"POST",base+"/prepare",Map.of("execution",Map.of("mode","auto","model","default","branch_ids",List.of())),200);
        var started=workspace(f.researcher(),"POST",base+"/start",Map.of("research_as_of","2026-10-12T12:00:00Z"),200);
        var body=Map.of("previous_run_id",started.path("run_id").asText(),"checkpoint_id",UUID.randomUUID().toString(),"state_digest","sha256:"+"d".repeat(64));
        var wrong=new HashMap<String,Object>(body);wrong.put("previous_run_id",UUID.randomUUID());
        workspace(f.researcher(),"POST",base+"/continue",wrong,409);
        workspace(f.admin(),"POST",base+"/continue",body,404); // Project manager is not the saved execution principal.
        dropOrganizationContinuation.add(id.toString());int before=organizationContinues.get();
        assertThat(workspace(f.researcher(),"GET",base+"/control",null,200).path("continuation").asText()).isEqualTo("absent");
        workspace(f.admin(),"GET",base+"/control",null,404);
        assertThat(workspace(f.researcher(),"GET",f.createPath(),null,200).get(0).path("execution_id").asText()).isEqualTo(id.toString());
        assertThat(workspace(f.admin(),"GET",f.createPath(),null,200).size()).isZero();
        try(var pool=Executors.newVirtualThreadPerTaskExecutor()) {
            var calls=new ArrayList<Future<JsonNode>>();for(int i=0;i<5;i++)calls.add(pool.submit(()->workspace(f.researcher(),"POST",base+"/continue",body,200)));
            for(var call:calls)assertThat(call.get().path("status").asText()).isEqualTo("unknown");
        }
        assertThat(organizationContinues.get()-before).isEqualTo(1);
        assertThat(workspace(f.researcher(),"GET",base+"/control",null,200).path("continuation").asText()).isEqualTo("unknown");
        var grant=workspace(f.researcher(),"GET",base+"/continuation-access",null,200);
        var original=organizationContinuations.get(id.toString()).deepCopy();
        String runtime="/v1/runtime/organization-executions/"+id+"/admit-continuation";
        var admission=JSON.createObjectNode().put("thread_id",id.toString()).put("run_id",original.path("run_id").asText())
            .put("operation_id",grant.path("continuation_operation_id").asText()).put("manifest_digest",f.digest())
            .put("configuration_digest",grant.path("configuration_digest").asText()).put("continuation_request_digest",grant.path("continuation_request_digest").asText());
        assertThat(runtimeRequest(runtime,admission.toString(),runtime,RUNTIME_SECRET).statusCode()).isEqualTo(200);
        assertThat(runtimeRequest(runtime,admission.deepCopy().put("run_id",UUID.randomUUID().toString()).toString(),runtime,RUNTIME_SECRET).statusCode()).isEqualTo(409);
        organizationContinuations.get(id.toString()).put("continuation_operation_id",UUID.randomUUID().toString());
        assertThat(workspace(f.researcher(),"POST",base+"/continuation-reconcile",null,200).path("status").asText()).isEqualTo("unknown");
        organizationContinuations.put(id.toString(),original);
        assertThat(workspace(f.researcher(),"POST",base+"/continuation-reconcile",null,200).path("status").asText()).isEqualTo("received");
        assertThat(workspace(f.researcher(),"POST",base+"/continue",body,200).path("run_id")).isEqualTo(original.path("run_id"));
        wrong=new HashMap<String,Object>(body);wrong.put("checkpoint_id",UUID.randomUUID());
        workspace(f.researcher(),"POST",base+"/continue",wrong,409);
        var reads=workspace(f.researcher(),"GET",base+"/read-access",null,200);
        assertThat(reads.path("run_id")).isEqualTo(original.path("run_id"));assertThat(reads.path("run_ids").size()).isEqualTo(2);
        assertThat(workspace(f.researcher(),"GET","/projects/"+f.project()+"/research-executions",null,200).path("items").size()).isEqualTo(1);
        workspace(f.admin(),"POST","/spaces/"+f.space()+"/members",Map.of("subject",f.researcher(),"role","remove"),200);
        workspace(f.researcher(),"POST",base+"/continue",body,404);
        assertThat(runtimeRequest(runtime,admission.toString(),runtime,RUNTIME_SECRET).statusCode()).isEqualTo(404);
        assertThat(workspace(f.researcher(),"GET","/projects/"+f.project()+"/research-executions",null,200).path("items").size()).isZero();
        assertThat(organizationContinues.get()-before).isEqualTo(1);
    }
    @Test void organization_report_commands_are_durable_idempotent_version_bound_and_revocable() throws Exception {
        var f=executionFixture(); UUID execution=UUID.randomUUID();
        workspace(f.researcher(),"POST",f.createPath(),Map.of("id",execution,"manifest_digest",f.digest()),200);
        String base="/projects/"+f.project()+"/execution-bindings/"+execution, commands=base+"/report-commands";
        workspace(f.researcher(),"POST",base+"/prepare",Map.of("execution",Map.of("mode","auto","model","default","branch_ids",List.of())),200);
        var started=workspace(f.researcher(),"POST",base+"/start",Map.of("research_as_of","2026-10-12T12:00:00Z"),200);
        UUID id=UUID.randomUUID(),checkpoint=UUID.randomUUID();
        var body=new HashMap<String,Object>();
        body.put("id",id); body.put("previous_run_id",started.path("run_id").asText()); body.put("checkpoint_id",checkpoint);
        body.put("state_digest","sha256:"+"b".repeat(64)); body.put("report_version",1);
        body.put("report_digest","c".repeat(64)); body.put("action","ask"); body.put("message","解释报告的来源");
        body.put("answer_mode","quick"); body.put("target",null);
        workspace(f.admin(),"POST",commands,body,404);
        dropReportCommands.add(id.toString()); int before=reportDispatches.get();
        try(var pool=Executors.newVirtualThreadPerTaskExecutor()) {
            var calls=new ArrayList<Future<JsonNode>>();
            for(int i=0;i<5;i++)calls.add(pool.submit(()->workspace(f.researcher(),"POST",commands,body,200)));
            for(var call:calls)assertThat(call.get().path("status").asText()).isEqualTo("unknown");
        }
        assertThat(reportDispatches.get()-before).isEqualTo(1);
        var changed=new HashMap<String,Object>(body); changed.put("message","换成另一意见");
        workspace(f.researcher(),"POST",commands,changed,409);
        changed=new HashMap<>(body);changed.put("id",UUID.randomUUID());changed.put("checkpoint_id",UUID.randomUUID());
        workspace(f.researcher(),"POST",commands,changed,409); // Unknown preceding command blocks new spending.
        var grant=workspace(f.researcher(),"GET",commands+"/"+id+"/access",null,200);
        var receipt=reportCommands.get(id.toString()).deepCopy();
        String runtime="/v1/runtime/organization-executions/"+execution+"/admit-report-action";
        var admission=JSON.createObjectNode().put("command_id",id.toString()).put("thread_id",execution.toString())
            .put("run_id",receipt.path("run_id").asText()).put("operation_id",grant.path("report_action_operation_id").asText())
            .put("manifest_digest",f.digest()).put("configuration_digest",grant.path("configuration_digest").asText())
            .put("report_action_request_digest",grant.path("report_action_request_digest").asText());
        assertThat(runtimeRequest(runtime,admission.toString(),runtime,RUNTIME_SECRET).statusCode()).isEqualTo(200);
        assertThat(runtimeRequest(runtime,admission.deepCopy().put("run_id",UUID.randomUUID().toString()).toString(),runtime,RUNTIME_SECRET).statusCode()).isEqualTo(409);
        reportCommands.get(id.toString()).put("report_action_request_digest","sha256:"+"0".repeat(64));
        assertThat(workspace(f.researcher(),"POST",commands+"/"+id+"/reconcile",null,200).path("status").asText()).isEqualTo("unknown");
        reportCommands.put(id.toString(),receipt);
        assertThat(workspace(f.researcher(),"POST",commands+"/"+id+"/reconcile",null,200).path("status").asText()).isEqualTo("received");
        assertThat(workspace(f.researcher(),"POST",commands,body,200).path("run_id")).isEqualTo(receipt.path("run_id"));
        assertThat(reportDispatches.get()-before).isEqualTo(1);
        var reads=workspace(f.researcher(),"GET",base+"/read-access",null,200);
        assertThat(reads.path("run_id")).isEqualTo(receipt.path("run_id"));
        assertThat(reads.path("run_ids").size()).isEqualTo(2);
        var next=new HashMap<>(body);next.put("id",UUID.randomUUID());next.put("previous_run_id",receipt.path("run_id").asText());
        workspace(f.researcher(),"POST",commands,next,409); // Same checkpoint cannot be spent twice.
        // An explanation need not modify the report: a fresh native checkpoint
        // permits a different question with the SAME report version and digest.
        next.put("checkpoint_id",UUID.randomUUID()); next.put("message","进一步解释这份报告的单位");
        var secondQuestion=workspace(f.researcher(),"POST",commands,next,200);
        assertThat(secondQuestion.path("status").asText()).isEqualTo("received");
        next.put("id",UUID.randomUUID());next.put("previous_run_id",secondQuestion.path("run_id").asText());
        next.put("checkpoint_id",UUID.randomUUID()); next.put("action","revise");
        workspace(f.researcher(),"POST",commands,next,422); // Quick mode cannot silently revise.
        next.put("answer_mode","deep");
        var revised=workspace(f.researcher(),"POST",commands,next,200);
        assertThat(revised.path("status").asText()).isEqualTo("received");
        assertThat(revised.path("run_id")).isNotEqualTo(receipt.path("run_id"));
        assertThat(workspace(f.researcher(),"GET",base+"/read-access",null,200).path("run_ids").size()).isEqualTo(4);
        assertThat(workspace(f.researcher(),"GET",commands,null,200).path("items").size()).isEqualTo(3);
        workspace(f.admin(),"POST","/spaces/"+f.space()+"/members",Map.of("subject",f.researcher(),"role","remove"),200);
        workspace(f.researcher(),"POST",commands,body,404);
        workspace(f.researcher(),"GET",base+"/read-access",null,404);
        workspace(f.researcher(),"GET",commands+"/"+id,null,404);
        assertThat(runtimeRequest(runtime,admission.toString(),runtime,RUNTIME_SECRET).statusCode()).isEqualTo(404);
        assertThat(reportDispatches.get()-before).isEqualTo(3);
    }
    @Test void organization_viewer_reads_require_current_project_and_sources_not_creator_role() throws Exception {
        var f=executionFixture();UUID id=UUID.randomUUID();
        workspace(f.researcher(),"POST",f.createPath(),Map.of("id",id,"manifest_digest",f.digest()),200);
        String base="/projects/"+f.project()+"/execution-bindings/"+id;
        workspace(f.researcher(),"POST",base+"/prepare",Map.of("execution",Map.of("mode","auto","model","default","branch_ids",List.of())),200);
        var started=workspace(f.researcher(),"POST",base+"/start",Map.of("research_as_of","2026-10-12T12:00:00Z"),200);
        String viewer="read-viewer-"+UUID.randomUUID();joinProjectOrganization(f.admin(),viewer,f.org());
        workspace(f.admin(),"POST","/projects/"+f.project()+"/members",Map.of("revision",3,"subject",viewer,"role","viewer"),200);
        workspace(viewer,"GET",base+"/read-access",null,404); // Project visibility alone cannot expose even the title.
        assertThat(workspace(viewer,"GET","/projects/"+f.project()+"/research-executions",null,200).path("items").size()).isZero();
        workspace("unrelated-reader","GET","/projects/"+f.project()+"/research-executions",null,404);
        workspace(f.admin(),"POST","/spaces/"+f.space()+"/members",Map.of("subject",viewer,"role","reader"),200);
        var grant=workspace(viewer,"GET",base+"/read-access",null,200);
        assertThat(grant.path("reader").asText()).isEqualTo(viewer);
        assertThat(grant.path("read_contract").asText()).isEqualTo("organization_research_read.v1");
        assertThat(grant.path("run_id")).isEqualTo(started.path("run_id"));
        workspace(viewer,"GET",base+"/start-access",null,404);
        workspace(viewer,"GET",base+"/continuation-access",null,404);
        workspace(viewer,"POST",base+"/start",Map.of("research_as_of","2026-10-12T12:00:00Z"),404);
        workspace(viewer,"GET","/projects/"+UUID.randomUUID()+"/execution-bindings/"+id+"/read-access",null,404);
        workspace(f.researcher(),"POST",base+"/close",null,200);
        workspace(viewer,"GET",base+"/read-access",null,200); // Closing execution does not erase authorized history.
        workspace(f.admin(),"POST","/projects/"+f.project()+"/members",Map.of("revision",4,"subject",f.researcher(),"role","remove"),200);
        workspace(viewer,"GET",base+"/read-access",null,200); // No creator impersonation.
        workspace(f.admin(),"POST","/spaces/"+f.space()+"/members",Map.of("subject",viewer,"role","remove"),200);
        workspace(viewer,"GET",base+"/read-access",null,404);
        workspace(f.admin(),"POST","/spaces/"+f.space()+"/members",Map.of("subject",viewer,"role","reader"),200);
        workspace(f.admin(),"POST","/projects/"+f.project()+"/members",Map.of("revision",5,"subject",viewer,"role","remove"),200);
        workspace(viewer,"GET",base+"/read-access",null,404);
    }
    @Test void organization_start_concurrent_command_and_exact_runtime_admission() throws Exception {
        var f=executionFixture();UUID id=UUID.randomUUID();workspace(f.researcher(),"POST",f.createPath(),Map.of("id",id,"manifest_digest",f.digest()),200);
        String base="/projects/"+f.project()+"/execution-bindings/"+id;
        var body=Map.of("research_as_of","2026-10-12T12:00:00+08:00");
        workspace(f.researcher(),"POST",base+"/start",body,404); // No preparation record: sources alone cannot authorize a run.
        workspace(f.researcher(),"POST",base+"/prepare",Map.of("execution",Map.of("mode","auto","model","default","branch_ids",List.of())),200);
        workspace(f.researcher(),"POST",base+"/start",Map.of("research_as_of","2026-10-12"),422);
        workspace(f.researcher(),"POST",base+"/start",Map.of("research_as_of","2026-10-13T00:00:00Z"),409);
        int before=organizationStarts.get();
        try(var pool=Executors.newVirtualThreadPerTaskExecutor()){
            var calls=new ArrayList<Future<JsonNode>>();for(int i=0;i<5;i++)calls.add(pool.submit(()->workspace(f.researcher(),"POST",base+"/start",body,200)));
            for(var call:calls)call.get();
        }
        var started=workspace(f.researcher(),"GET",base+"/start",null,200);
        assertThat(started.path("status").asText()).isEqualTo("received");assertThat(organizationStarts.get()-before).isEqualTo(1);
        assertThat(workspace(f.researcher(),"POST",base+"/start",body,200)).isEqualTo(started);
        workspace(f.researcher(),"POST",base+"/start",Map.of("research_as_of","2026-10-12T13:00:00+08:00"),409);
        var grant=workspace(f.researcher(),"GET",base+"/start-access",null,200);
        String runtime="/v1/runtime/organization-executions/"+id+"/admit-start";
        var admission=JSON.createObjectNode().put("thread_id",id.toString()).put("run_id",started.path("run_id").asText())
            .put("operation_id",grant.path("start_operation_id").asText()).put("manifest_digest",f.digest())
            .put("configuration_digest",grant.path("configuration_digest").asText()).put("start_request_digest",grant.path("start_request_digest").asText());
        for(int i=0;i<2;i++)assertThat(runtimeRequest(runtime,admission.toString(),runtime,RUNTIME_SECRET).statusCode()).isEqualTo(200);
        var wrong=admission.deepCopy().put("run_id",UUID.randomUUID().toString());
        assertThat(runtimeRequest(runtime,wrong.toString(),runtime,RUNTIME_SECRET).statusCode()).isEqualTo(409);
        wrong=admission.deepCopy().put("operation_id",UUID.randomUUID().toString());
        assertThat(runtimeRequest(runtime,wrong.toString(),runtime,RUNTIME_SECRET).statusCode()).isEqualTo(409);
        assertThat(request(f.researcher(),"POST",runtime,admission.toString(),null).statusCode()).isEqualTo(401);
        workspace(f.admin(),"POST","/spaces/"+f.space()+"/members",Map.of("subject",f.researcher(),"role","remove"),200);
        assertThat(runtimeRequest(runtime,admission.toString(),runtime,RUNTIME_SECRET).statusCode()).isEqualTo(404);
        workspace(f.researcher(),"POST",base+"/start",body,404);
        assertThat(organizationStarts.get()-before).isEqualTo(1);
    }
    @Test void organization_lost_start_can_be_admitted_once_then_reconciled() throws Exception {
        var f=executionFixture();UUID id=UUID.randomUUID();workspace(f.researcher(),"POST",f.createPath(),Map.of("id",id,"manifest_digest",f.digest()),200);
        String base="/projects/"+f.project()+"/execution-bindings/"+id;
        workspace(f.researcher(),"POST",base+"/prepare",Map.of("execution",Map.of("mode","auto","model","default","branch_ids",List.of())),200);
        var body=Map.of("research_as_of","2026-10-12T12:00:00Z");dropOrganizationStart.add(id.toString());int before=organizationStarts.get();
        assertThat(workspace(f.researcher(),"POST",base+"/start",body,200).path("status").asText()).isEqualTo("unknown");
        var original=organizationRuns.get(id.toString()).deepCopy();
        var grant=workspace(f.researcher(),"GET",base+"/start-access",null,200);
        String runtime="/v1/runtime/organization-executions/"+id+"/admit-start";
        var admission=Map.of("thread_id",id,"run_id",original.path("run_id").asText(),"operation_id",grant.path("start_operation_id").asText(),
            "manifest_digest",f.digest(),"configuration_digest",grant.path("configuration_digest").asText(),"start_request_digest",grant.path("start_request_digest").asText());
        assertThat(runtimeRequest(runtime,JSON.writeValueAsString(admission),runtime,RUNTIME_SECRET).statusCode()).isEqualTo(200);
        organizationRuns.get(id.toString()).put("run_id",UUID.randomUUID().toString());
        assertThat(workspace(f.researcher(),"POST",base+"/start-reconcile",null,200).path("status").asText()).isEqualTo("unknown");
        organizationRuns.put(id.toString(),original);
        var recovered=workspace(f.researcher(),"POST",base+"/start-reconcile",null,200);
        assertThat(recovered.path("status").asText()).isEqualTo("received");
        assertThat(workspace(f.researcher(),"POST",base+"/start",body,200)).isEqualTo(recovered);
        assertThat(organizationStarts.get()-before).isEqualTo(1);
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
