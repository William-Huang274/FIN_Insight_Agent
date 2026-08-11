package finsight.gateway;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
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
            if (suffix.startsWith("/") && "POST".equals(method) && suffix.endsWith("/worker-events")) {
                String taskId = suffix.substring(1, suffix.length() - "/worker-events".length());
                handleWorkerUpdate(exchange, taskId);
                return;
            }
            if (suffix.startsWith("/") && "GET".equals(method) && suffix.endsWith("/events")) {
                String taskId = suffix.substring(1, suffix.length() - "/events".length());
                handleGetTaskEvents(exchange, taskId);
                return;
            }
            if (suffix.startsWith("/") && "POST".equals(method) && suffix.endsWith("/cancel")) {
                String taskId = suffix.substring(1, suffix.length() - "/cancel".length());
                handleCancelTask(exchange, taskId);
                return;
            }
            if (suffix.startsWith("/") && "POST".equals(method) && suffix.endsWith("/resume")) {
                String taskId = suffix.substring(1, suffix.length() - "/resume".length());
                handleResumeTask(exchange, taskId);
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
        try {
            queue.publish(task.taskId, JsonUtil.write(task.queuePayload(callback)));
            store.appendEvent(task.taskId, "system", "task accepted and queued via " + config.queueMode, task.traceId);
        } catch (Exception exc) {
            store.updateStatus(task.taskId, "FAILED", "queue_publish_failed: " + exc.getMessage());
            store.appendEvent(task.taskId, "system", "queue publish failed: " + exc.getMessage(), task.traceId);
            throw exc;
        }
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

    private void handleGetTaskEvents(HttpExchange exchange, String taskId) throws Exception {
        int afterSequence = intQuery(exchange, "after_sequence", 0, 1_000_000_000);
        int limit = intQuery(exchange, "limit", 500, 5000);
        List<Map<String, Object>> rows = new ArrayList<>();
        for (TaskEvent event : store.listEvents(taskId, afterSequence, limit)) {
            rows.add(event.toMap());
        }
        String accept = exchange.getRequestHeaders().getFirst("Accept");
        if (accept != null && accept.contains("text/event-stream")) {
            sendSse(exchange, rows);
            return;
        }
        send(exchange, 200, Map.of("task_id", taskId, "events", rows));
    }

    private void handleCancelTask(HttpExchange exchange, String taskId) throws Exception {
        ResearchTask task = store.updateStatus(taskId, "CANCEL_REQUESTED", "cancel requested");
        store.appendEvent(taskId, "system", "cancel requested", task.traceId);
        send(exchange, 202, task.toMap());
    }

    private void handleResumeTask(HttpExchange exchange, String taskId) throws Exception {
        ResearchTask existing = store.get(taskId).orElseThrow(() -> new IllegalArgumentException("task_not_found: " + taskId));
        ResearchTask task = store.updateStatus(taskId, "PENDING", "");
        String callback = callbackBase(exchange) + "/api/research/tasks/" + task.taskId + "/worker-events";
        queue.publish(task.taskId, JsonUtil.write(existing.queuePayload(callback)));
        store.appendEvent(taskId, "system", "resume requested and task re-queued via " + config.queueMode, task.traceId);
        send(exchange, 202, task.toMap());
    }

    private void handleWorkerUpdate(HttpExchange exchange, String taskId) throws Exception {
        if (!config.workerToken.isBlank()) {
            String token = exchange.getRequestHeaders().getFirst("X-Worker-Token");
            if (!config.workerToken.equals(token)) {
                send(exchange, 403, Map.of("error", "worker_token_invalid"));
                return;
            }
        }
        Map<String, Object> body = JsonUtil.readObject(readBody(exchange));
        ResearchTask updated = store.updateFromWorker(taskId, body);
        store.appendEvent(
                taskId,
                "worker",
                "status=" + updated.status + " progress=" + updated.progress,
                updated.traceId);
        for (TaskEvent event : workerEventsFromBody(taskId, updated.traceId, body)) {
            store.appendEvent(taskId, event.stream, event.message, event.traceId);
        }
        send(exchange, 200, updated.toMap());
    }

    private static List<TaskEvent> workerEventsFromBody(String taskId, String traceId, Map<String, Object> body) {
        Object raw = body.get("events");
        if (!(raw instanceof List<?> list)) {
            return List.of();
        }
        List<TaskEvent> events = new ArrayList<>();
        for (Object item : list) {
            if (!(item instanceof Map<?, ?> map)) {
                continue;
            }
            String stream = text(map.get("stream"));
            String message = text(map.get("message"));
            if (message.isBlank()) {
                continue;
            }
            events.add(TaskEvent.create(taskId, 1, firstText(map.get("trace_id"), traceId), stream, message));
        }
        return events;
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

    private static int intQuery(HttpExchange exchange, String key, int defaultValue, int maxValue) {
        String query = exchange.getRequestURI().getRawQuery();
        if (query == null || query.isBlank()) {
            return defaultValue;
        }
        for (String part : query.split("&")) {
            int index = part.indexOf('=');
            String rawKey = index >= 0 ? part.substring(0, index) : part;
            if (!key.equals(URLDecoder.decode(rawKey, StandardCharsets.UTF_8))) {
                continue;
            }
            String rawValue = index >= 0 ? part.substring(index + 1) : "";
            try {
                int value = Integer.parseInt(URLDecoder.decode(rawValue, StandardCharsets.UTF_8));
                return Math.max(0, Math.min(maxValue, value));
            } catch (NumberFormatException exc) {
                return defaultValue;
            }
        }
        return defaultValue;
    }

    private static String firstText(Object value, String defaultValue) {
        String result = text(value);
        return result.isBlank() ? defaultValue : result;
    }

    private static String text(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private static void send(HttpExchange exchange, int status, Map<String, Object> payload) throws IOException {
        byte[] bytes = JsonUtil.write(payload).getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        exchange.sendResponseHeaders(status, bytes.length);
        try (OutputStream out = exchange.getResponseBody()) {
            out.write(bytes);
        }
    }

    private static void sendSse(HttpExchange exchange, List<Map<String, Object>> events) throws IOException {
        StringBuilder builder = new StringBuilder();
        for (Map<String, Object> event : events) {
            builder.append("event: task-event\n");
            builder.append("data: ").append(JsonUtil.write(event)).append("\n\n");
        }
        builder.append("event: heartbeat\n");
        builder.append("data: {\"status\":\"ok\"}\n\n");
        byte[] bytes = builder.toString().getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "text/event-stream; charset=utf-8");
        exchange.getResponseHeaders().set("Cache-Control", "no-cache");
        exchange.sendResponseHeaders(200, bytes.length);
        try (OutputStream out = exchange.getResponseBody()) {
            out.write(bytes);
        }
    }
}
