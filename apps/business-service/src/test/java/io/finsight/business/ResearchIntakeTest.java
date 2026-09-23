package io.finsight.business;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.nimbusds.jose.*;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jwt.*;
import com.sun.net.httpserver.*;
import org.junit.jupiter.api.*;
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
