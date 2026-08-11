package finsight.gateway;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

final class TaskEvent {
    final String taskId;
    final int sequence;
    final String traceId;
    final String stream;
    final String message;
    final String createdAt;

    private TaskEvent(String taskId, int sequence, String traceId, String stream, String message, String createdAt) {
        this.taskId = taskId;
        this.sequence = sequence;
        this.traceId = traceId;
        this.stream = stream;
        this.message = message;
        this.createdAt = createdAt;
    }

    static TaskEvent create(String taskId, int sequence, String traceId, String stream, String message) {
        return new TaskEvent(
                taskId,
                Math.max(1, sequence),
                clean(traceId),
                clean(stream).isBlank() ? "worker" : clean(stream),
                clean(message),
                Instant.now().toString());
    }

    static TaskEvent fromMap(Map<String, Object> body) {
        return new TaskEvent(
                text(body.get("task_id")),
                intValue(body.get("sequence"), 0),
                text(body.get("trace_id")),
                text(body.get("stream")),
                text(body.get("message")),
                text(body.get("created_at")));
    }

    Map<String, Object> toMap() {
        Map<String, Object> values = new LinkedHashMap<>();
        values.put("task_id", taskId);
        values.put("sequence", sequence);
        values.put("trace_id", traceId);
        values.put("stream", stream);
        values.put("message", message);
        values.put("created_at", createdAt);
        return values;
    }

    private static String clean(String value) {
        return value == null ? "" : value.trim();
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
}
