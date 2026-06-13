package finsight.gateway;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

final class ResearchTask {
    final String taskId;
    final String traceId;
    final String query;
    final String userId;
    final String caseId;
    final String mode;
    final String status;
    final int progress;
    final String memo;
    final List<Object> evidence;
    final String errorMessage;
    final Map<String, Object> metadata;
    final String createdAt;
    final String updatedAt;

    private ResearchTask(
            String taskId,
            String traceId,
            String query,
            String userId,
            String caseId,
            String mode,
            String status,
            int progress,
            String memo,
            List<Object> evidence,
            String errorMessage,
            Map<String, Object> metadata,
            String createdAt,
            String updatedAt) {
        this.taskId = taskId;
        this.traceId = traceId;
        this.query = query;
        this.userId = userId;
        this.caseId = caseId;
        this.mode = mode;
        this.status = status;
        this.progress = progress;
        this.memo = memo;
        this.evidence = evidence;
        this.errorMessage = errorMessage;
        this.metadata = metadata;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
    }

    static ResearchTask fromCreateRequest(Map<String, Object> body) {
        String query = text(body.get("query")).trim();
        if (query.isEmpty()) {
            throw new IllegalArgumentException("query_required");
        }
        String now = Instant.now().toString();
        String taskId = firstText(body.get("task_id"), "task_" + UUID.randomUUID().toString().replace("-", "").substring(0, 16));
        String traceId = firstText(body.get("trace_id"), "trace_" + UUID.randomUUID().toString().replace("-", "").substring(0, 16));
        return new ResearchTask(
                taskId,
                traceId,
                query,
                firstText(body.get("user_id"), "local_user"),
                firstText(body.get("case_id"), ""),
                firstText(body.get("mode"), "local_smoke"),
                "PENDING",
                0,
                "",
                List.of(),
                "",
                objectMap(body.get("metadata")),
                now,
                now);
    }

    ResearchTask withWorkerUpdate(Map<String, Object> body) {
        String now = Instant.now().toString();
        String nextStatus = firstText(body.get("status"), this.status).trim().toUpperCase();
        int nextProgress = intValue(body.get("progress"), this.progress);
        return new ResearchTask(
                taskId,
                traceId,
                query,
                userId,
                caseId,
                mode,
                nextStatus,
                Math.max(0, Math.min(100, nextProgress)),
                firstText(body.get("memo"), this.memo),
                objectList(body.get("evidence"), this.evidence),
                firstText(body.get("error_message"), this.errorMessage),
                metadata,
                createdAt,
                now);
    }

    ResearchTask withGatewayStatus(String status, String errorMessage) {
        String now = Instant.now().toString();
        return new ResearchTask(
                taskId,
                traceId,
                query,
                userId,
                caseId,
                mode,
                firstText(status, this.status).trim().toUpperCase(),
                progress,
                memo,
                evidence,
                firstText(errorMessage, this.errorMessage),
                metadata,
                createdAt,
                now);
    }

    Map<String, Object> toMap() {
        Map<String, Object> values = new LinkedHashMap<>();
        values.put("task_id", taskId);
        values.put("trace_id", traceId);
        values.put("query", query);
        values.put("user_id", userId);
        values.put("case_id", caseId);
        values.put("mode", mode);
        values.put("status", status);
        values.put("progress", progress);
        values.put("memo", memo);
        values.put("evidence", evidence);
        values.put("error_message", errorMessage);
        values.put("metadata", metadata);
        values.put("created_at", createdAt);
        values.put("updated_at", updatedAt);
        return values;
    }

    Map<String, Object> queuePayload(String callbackUrl) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("task_id", taskId);
        payload.put("trace_id", traceId);
        payload.put("query", query);
        payload.put("user_id", userId);
        payload.put("case_id", caseId);
        payload.put("mode", mode);
        payload.put("callback_url", callbackUrl);
        payload.put("metadata", metadata);
        return payload;
    }

    static ResearchTask fromMap(Map<String, Object> body) {
        return new ResearchTask(
                firstText(body.get("task_id"), ""),
                firstText(body.get("trace_id"), ""),
                firstText(body.get("query"), ""),
                firstText(body.get("user_id"), ""),
                firstText(body.get("case_id"), ""),
                firstText(body.get("mode"), ""),
                firstText(body.get("status"), "PENDING"),
                intValue(body.get("progress"), 0),
                firstText(body.get("memo"), ""),
                objectList(body.get("evidence"), List.of()),
                firstText(body.get("error_message"), ""),
                objectMap(body.get("metadata")),
                firstText(body.get("created_at"), ""),
                firstText(body.get("updated_at"), ""));
    }

    private static String firstText(Object value, String defaultValue) {
        String result = text(value);
        return result.isBlank() ? defaultValue : result;
    }

    private static String text(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private static int intValue(Object value, int defaultValue) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        try {
            return Integer.parseInt(text(value));
        } catch (NumberFormatException exc) {
            return defaultValue;
        }
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> objectMap(Object value) {
        if (value instanceof Map<?, ?> map) {
            Map<String, Object> result = new LinkedHashMap<>();
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                result.put(String.valueOf(entry.getKey()), entry.getValue());
            }
            return result;
        }
        return new LinkedHashMap<>();
    }

    @SuppressWarnings("unchecked")
    private static List<Object> objectList(Object value, List<Object> defaultValue) {
        if (value instanceof List<?> list) {
            return (List<Object>) list;
        }
        return defaultValue;
    }
}
