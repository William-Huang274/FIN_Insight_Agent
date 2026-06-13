package finsight.gateway;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.sql.SQLException;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.Executors;

public final class TaskGatewayServer {
    private final GatewayConfig config;
    private final TaskStore store;
    private final TaskQueue queue;

    private TaskGatewayServer(GatewayConfig config, TaskStore store, TaskQueue queue) {
        this.config = config;
        this.store = store;
        this.queue = queue;
    }

    public static void main(String[] args) throws Exception {
        GatewayConfig config = GatewayConfig.fromEnv();
        TaskStore store = config.createTaskStore();
        TaskQueue queue = config.createTaskQueue();
        TaskGatewayServer gateway = new TaskGatewayServer(config, store, queue);
        gateway.start();
    }

    void start() throws IOException, SQLException {
        store.initialize();
        HttpServer server = HttpServer.create(new InetSocketAddress(config.host, config.port), 0);
        server.createContext("/api/health", this::handleHealth);
        server.createContext("/api/research/tasks", this::handleTasks);
        server.setExecutor(Executors.newFixedThreadPool(Math.max(4, Runtime.getRuntime().availableProcessors())));
        server.start();
        System.out.println("finsight research gateway listening on http://" + config.host + ":" + config.port);
    }

    private void handleHealth(HttpExchange exchange) throws IOException {
        if (!"GET".equals(exchange.getRequestMethod())) {
            send(exchange, 405, Map.of("error", "method_not_allowed"));
            return;
        }
        send(exchange, 200, Map.of(
                "status", "ok",
                "service", "finsight-research-gateway",
                "store_mode", config.storeMode,
                "queue_mode", config.queueMode));
    }

    private void handleTasks(HttpExchange exchange) throws IOException {
        try {
            String method = exchange.getRequestMethod();
            String path = exchange.getRequestURI().getPath();
            String base = "/api/research/tasks";
            String suffix = path.length() > base.length() ? path.substring(base.length()) : "";
            if ("POST".equals(method) && suffix.isBlank()) {
                handleCreateTask(exchange);
                return;
            }
            if ("GET".equals(method) && suffix.startsWith("/")) {
                String taskId = suffix.substring(1);
                if (taskId.contains("/")) {
                    send(exchange, 404, Map.of("error", "not_found"));
                    return;
                }
                handleGetTask(exchange, taskId);
                return;
            }
            if ("POST".equals(method) && suffix.startsWith("/") && suffix.endsWith("/worker-events")) {
                String taskId = suffix.substring(1, suffix.length() - "/worker-events".length());
                handleWorkerUpdate(exchange, taskId);
                return;
            }
            send(exchange, 404, Map.of("error", "not_found"));
        } catch (IllegalArgumentException exc) {
            send(exchange, 400, Map.of("error", exc.getMessage()));
        } catch (Exception exc) {
            send(exchange, 500, Map.of("error", "internal_error", "message", exc.getMessage()));
        }
    }

    private void handleCreateTask(HttpExchange exchange) throws Exception {
        Map<String, Object> body = JsonUtil.readObject(readBody(exchange));
        ResearchTask task = ResearchTask.fromCreateRequest(body);
        store.create(task);
        String callback = callbackBase(exchange) + "/api/research/tasks/" + task.taskId + "/worker-events";
        queue.publish(task.taskId, JsonUtil.write(task.queuePayload(callback)));
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("task_id", task.taskId);
        response.put("trace_id", task.traceId);
        response.put("status", task.status);
        response.put("queue_mode", config.queueMode);
        response.put("store_mode", config.storeMode);
        send(exchange, 202, response);
    }

    private void handleGetTask(HttpExchange exchange, String taskId) throws Exception {
        Optional<ResearchTask> task = store.get(taskId);
        if (task.isEmpty()) {
            send(exchange, 404, Map.of("error", "task_not_found", "task_id", taskId));
            return;
        }
        send(exchange, 200, task.get().toMap());
    }

    private void handleWorkerUpdate(HttpExchange exchange, String taskId) throws Exception {
        if (!config.workerToken.isBlank()) {
            String token = exchange.getRequestHeaders().getFirst("X-Worker-Token");
            if (!config.workerToken.equals(token)) {
                send(exchange, 403, Map.of("error", "worker_token_invalid"));
                return;
            }
        }
        ResearchTask updated = store.updateFromWorker(taskId, JsonUtil.readObject(readBody(exchange)));
        send(exchange, 200, updated.toMap());
    }

    private static String readBody(HttpExchange exchange) throws IOException {
        return new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
    }

    private static String callbackBase(HttpExchange exchange) {
        String host = exchange.getRequestHeaders().getFirst("Host");
        if (host == null || host.isBlank()) {
            host = exchange.getLocalAddress().getHostString() + ":" + exchange.getLocalAddress().getPort();
        }
        return "http://" + host;
    }

    private static void send(HttpExchange exchange, int status, Map<String, Object> payload) throws IOException {
        byte[] bytes = JsonUtil.write(payload).getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        exchange.sendResponseHeaders(status, bytes.length);
        try (OutputStream out = exchange.getResponseBody()) {
            out.write(bytes);
        }
    }
}
