package finsight.gateway;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;

final class JdbcTaskStore implements TaskStore {
    private final String url;
    private final String user;
    private final String password;

    JdbcTaskStore(String url, String user, String password) {
        this.url = url;
        this.user = user;
        this.password = password;
    }

    @Override
    public void initialize() throws SQLException {
        SQLException lastError = null;
        long deadlineNanos = System.nanoTime() + 60_000_000_000L;
        while (System.nanoTime() < deadlineNanos) {
            try {
                initializeOnce();
                return;
            } catch (SQLException exc) {
                lastError = exc;
                try {
                    Thread.sleep(1000L);
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    throw exc;
                }
            }
        }
        throw lastError == null ? new SQLException("jdbc_initialize_timeout") : lastError;
    }

    private void initializeOnce() throws SQLException {
        try (Connection conn = connect(); Statement stmt = conn.createStatement()) {
            stmt.executeUpdate(
                    """
                    create table if not exists research_tasks (
                        task_id varchar(96) primary key,
                        trace_id varchar(96) not null,
                        query_text text not null,
                        user_id varchar(128),
                        case_id varchar(128),
                        mode varchar(64),
                        status varchar(32) not null,
                        progress integer not null,
                        memo_text text,
                        evidence_json text,
                        error_message text,
                        metadata_json text,
                        created_at varchar(64) not null,
                        updated_at varchar(64) not null
                    )
                    """);
            stmt.executeUpdate(
                    """
                    create table if not exists research_task_events (
                        task_id varchar(96) not null,
                        sequence integer not null,
                        trace_id varchar(96),
                        stream varchar(64) not null,
                        message text not null,
                        created_at varchar(64) not null,
                        primary key (task_id, sequence)
                    )
                    """);
        }
    }

    @Override
    public void create(ResearchTask task) throws SQLException {
        try (Connection conn = connect();
             PreparedStatement stmt = conn.prepareStatement(
                     """
                     insert into research_tasks (
                         task_id, trace_id, query_text, user_id, case_id, mode, status, progress,
                         memo_text, evidence_json, error_message, metadata_json, created_at, updated_at
                     ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                     """)) {
            bindTask(stmt, task);
            stmt.executeUpdate();
        }
    }

    @Override
    public Optional<ResearchTask> get(String taskId) throws SQLException {
        try (Connection conn = connect();
             PreparedStatement stmt = conn.prepareStatement("select * from research_tasks where task_id = ?")) {
            stmt.setString(1, taskId);
            try (ResultSet rs = stmt.executeQuery()) {
                if (!rs.next()) {
                    return Optional.empty();
                }
                return Optional.of(taskFromRow(rs));
            }
        }
    }

    @Override
    public ResearchTask updateFromWorker(String taskId, Map<String, Object> update) throws SQLException {
        ResearchTask existing = get(taskId).orElseThrow(() -> new IllegalArgumentException("task_not_found: " + taskId));
        ResearchTask updated = existing.withWorkerUpdate(update);
        try (Connection conn = connect();
             PreparedStatement stmt = conn.prepareStatement(
                     """
                     update research_tasks
                     set status = ?, progress = ?, memo_text = ?, evidence_json = ?, error_message = ?, updated_at = ?
                     where task_id = ?
                     """)) {
            stmt.setString(1, updated.status);
            stmt.setInt(2, updated.progress);
            stmt.setString(3, updated.memo);
            stmt.setString(4, JsonUtil.write(updated.evidence));
            stmt.setString(5, updated.errorMessage);
            stmt.setString(6, updated.updatedAt);
            stmt.setString(7, updated.taskId);
            stmt.executeUpdate();
        }
        return updated;
    }

    @Override
    public ResearchTask updateStatus(String taskId, String status, String errorMessage) throws SQLException {
        ResearchTask existing = get(taskId).orElseThrow(() -> new IllegalArgumentException("task_not_found: " + taskId));
        ResearchTask updated = existing.withGatewayStatus(status, errorMessage);
        try (Connection conn = connect();
             PreparedStatement stmt = conn.prepareStatement(
                     """
                     update research_tasks
                     set status = ?, error_message = ?, updated_at = ?
                     where task_id = ?
                     """)) {
            stmt.setString(1, updated.status);
            stmt.setString(2, updated.errorMessage);
            stmt.setString(3, updated.updatedAt);
            stmt.setString(4, updated.taskId);
            stmt.executeUpdate();
        }
        return updated;
    }

    @Override
    public TaskEvent appendEvent(String taskId, String stream, String message, String traceId) throws SQLException {
        ResearchTask task = get(taskId).orElseThrow(() -> new IllegalArgumentException("task_not_found: " + taskId));
        try (Connection conn = connect()) {
            int sequence = nextEventSequence(conn, taskId);
            TaskEvent event = TaskEvent.create(taskId, sequence, traceId == null || traceId.isBlank() ? task.traceId : traceId, stream, message);
            try (PreparedStatement stmt = conn.prepareStatement(
                    """
                    insert into research_task_events (task_id, sequence, trace_id, stream, message, created_at)
                    values (?, ?, ?, ?, ?, ?)
                    """)) {
                stmt.setString(1, event.taskId);
                stmt.setInt(2, event.sequence);
                stmt.setString(3, event.traceId);
                stmt.setString(4, event.stream);
                stmt.setString(5, event.message);
                stmt.setString(6, event.createdAt);
                stmt.executeUpdate();
            }
            return event;
        }
    }

    @Override
    public List<TaskEvent> listEvents(String taskId, int afterSequence, int limit) throws SQLException {
        get(taskId).orElseThrow(() -> new IllegalArgumentException("task_not_found: " + taskId));
        int boundedLimit = Math.max(1, Math.min(5000, limit));
        List<TaskEvent> events = new ArrayList<>();
        try (Connection conn = connect();
             PreparedStatement stmt = conn.prepareStatement(
                     """
                     select task_id, sequence, trace_id, stream, message, created_at
                     from research_task_events
                     where task_id = ? and sequence > ?
                     order by sequence asc
                     limit ?
                     """)) {
            stmt.setString(1, taskId);
            stmt.setInt(2, Math.max(0, afterSequence));
            stmt.setInt(3, boundedLimit);
            try (ResultSet rs = stmt.executeQuery()) {
                while (rs.next()) {
                    events.add(TaskEvent.fromMap(Map.of(
                            "task_id", rs.getString("task_id"),
                            "sequence", rs.getInt("sequence"),
                            "trace_id", rs.getString("trace_id") == null ? "" : rs.getString("trace_id"),
                            "stream", rs.getString("stream"),
                            "message", rs.getString("message"),
                            "created_at", rs.getString("created_at"))));
                }
            }
        }
        return events;
    }

    private Connection connect() throws SQLException {
        if (user == null || user.isBlank()) {
            return DriverManager.getConnection(url);
        }
        return DriverManager.getConnection(url, user, password == null ? "" : password);
    }

    private static void bindTask(PreparedStatement stmt, ResearchTask task) throws SQLException {
        stmt.setString(1, task.taskId);
        stmt.setString(2, task.traceId);
        stmt.setString(3, task.query);
        stmt.setString(4, task.userId);
        stmt.setString(5, task.caseId);
        stmt.setString(6, task.mode);
        stmt.setString(7, task.status);
        stmt.setInt(8, task.progress);
        stmt.setString(9, task.memo);
        stmt.setString(10, JsonUtil.write(task.evidence));
        stmt.setString(11, task.errorMessage);
        stmt.setString(12, JsonUtil.write(task.metadata));
        stmt.setString(13, task.createdAt);
        stmt.setString(14, task.updatedAt);
    }

    private static ResearchTask taskFromRow(ResultSet rs) throws SQLException {
        return ResearchTask.fromMap(Map.ofEntries(
                Map.entry("task_id", rs.getString("task_id")),
                Map.entry("trace_id", rs.getString("trace_id")),
                Map.entry("query", rs.getString("query_text")),
                Map.entry("user_id", rs.getString("user_id") == null ? "" : rs.getString("user_id")),
                Map.entry("case_id", rs.getString("case_id") == null ? "" : rs.getString("case_id")),
                Map.entry("mode", rs.getString("mode") == null ? "" : rs.getString("mode")),
                Map.entry("status", rs.getString("status")),
                Map.entry("progress", rs.getInt("progress")),
                Map.entry("memo", rs.getString("memo_text") == null ? "" : rs.getString("memo_text")),
                Map.entry("evidence", JsonUtil.readObject("{\"items\":" + nullToArray(rs.getString("evidence_json")) + "}").get("items")),
                Map.entry("error_message", rs.getString("error_message") == null ? "" : rs.getString("error_message")),
                Map.entry("metadata", JsonUtil.readObject(nullToObject(rs.getString("metadata_json")))),
                Map.entry("created_at", rs.getString("created_at")),
                Map.entry("updated_at", rs.getString("updated_at"))));
    }

    private static int nextEventSequence(Connection conn, String taskId) throws SQLException {
        try (PreparedStatement stmt = conn.prepareStatement(
                "select coalesce(max(sequence), 0) as last_sequence from research_task_events where task_id = ?")) {
            stmt.setString(1, taskId);
            try (ResultSet rs = stmt.executeQuery()) {
                if (rs.next()) {
                    return rs.getInt("last_sequence") + 1;
                }
            }
        }
        return 1;
    }

    private static String nullToArray(String value) {
        return value == null || value.isBlank() ? "[]" : value;
    }

    private static String nullToObject(String value) {
        return value == null || value.isBlank() ? "{}" : value;
    }
}
