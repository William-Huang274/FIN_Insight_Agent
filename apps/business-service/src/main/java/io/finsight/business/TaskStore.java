package io.finsight.business;

import com.fasterxml.jackson.databind.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import java.util.*;

@Repository
class TaskStore {
    record Task(UUID id, String owner, UUID project, UUID key, String fingerprint, String title, String question, JsonNode binding, String created) {}
    record Command(UUID task, String phase, UUID operation, String request, String status, JsonNode response) {}
    private final JdbcTemplate db;
    private final ObjectMapper json;
    private final TransactionTemplate transaction;
    TaskStore(JdbcTemplate db, ObjectMapper json, PlatformTransactionManager manager) {
        this.db = db; this.json = json; transaction = new TransactionTemplate(manager);
    }
    private JsonNode parse(String value) {
        try { return value == null ? null : json.readTree(value); }
        catch (Exception e) { throw new IllegalStateException("invalid_stored_json", e); }
    }
    private final org.springframework.jdbc.core.RowMapper<Task> tasks = (r, n) -> new Task(
        r.getObject("id", UUID.class), r.getString("owner_id"), r.getObject("project_id", UUID.class), r.getObject("submission_key", UUID.class),
        r.getString("fingerprint"), r.getString("title"), r.getString("question"), parse(r.getString("binding")), r.getTimestamp("created_at").toInstant().toString());
    Task byKey(String owner, UUID key) {
        return db.query("SELECT * FROM research_task WHERE owner_id=? AND submission_key=?", tasks, owner, key).stream().findFirst().orElse(null);
    }
    Task owned(String owner, UUID id) {
        return db.query("SELECT * FROM research_task WHERE owner_id=? AND id=?", tasks, owner, id).stream().findFirst().orElseThrow(ApiFailure::missing);
    }
    List<Task> list(String owner, UUID project, int offset) {
        return db.query("SELECT * FROM research_task WHERE owner_id=? AND project_id=? ORDER BY created_at DESC, id LIMIT 51 OFFSET ?", tasks, owner, project, offset);
    }
    Task insert(Task task, String prepare, String start) {
        // Short database transaction only; never keep locks across a remote call.
        return transaction.execute(status -> {
            int inserted = db.update("INSERT INTO research_task(id,owner_id,project_id,submission_key,fingerprint,title,question,binding) VALUES(?,?,?,?,?,?,?,?::jsonb) ON CONFLICT(owner_id,submission_key) DO NOTHING",
                task.id(), task.owner(), task.project(), task.key(), task.fingerprint(), task.title(), task.question(), task.binding().toString());
            if (inserted == 1) {
                for (var item : Map.of("prepare", prepare, "start", start).entrySet())
                    db.update("INSERT INTO research_command(task_id,phase,operation_id,request_body) VALUES(?,?,?,?)", task.id(), item.getKey(), UUID.randomUUID(), item.getValue());
            }
            return byKey(task.owner(), task.key());
        });
    }
    Command command(UUID task, String phase) {
        return db.queryForObject("SELECT * FROM research_command WHERE task_id=? AND phase=?", (r, n) -> new Command(task, phase,
            r.getObject("operation_id", UUID.class), r.getString("request_body"), r.getString("status"), parse(r.getString("response_body"))), task, phase);
    }
    boolean claim(Command c) {
        return db.update("UPDATE research_command SET status='dispatching', updated_at=now() WHERE task_id=? AND phase=? AND status='ready'", c.task(), c.phase()) == 1;
    }
    void complete(Command c, String status, JsonNode response) {
        db.update("UPDATE research_command SET status=?,response_body=?::jsonb,updated_at=now() WHERE task_id=? AND phase=? AND status IN ('dispatching','unknown')",
            status, response == null ? null : response.toString(), c.task(), c.phase());
    }
}
