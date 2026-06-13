package finsight.gateway;

import java.io.IOException;
import java.sql.SQLException;
import java.util.List;
import java.util.Optional;

interface TaskStore extends AutoCloseable {
    void initialize() throws IOException, SQLException;

    void create(ResearchTask task) throws IOException, SQLException;

    Optional<ResearchTask> get(String taskId) throws IOException, SQLException;

    ResearchTask updateFromWorker(String taskId, java.util.Map<String, Object> update) throws IOException, SQLException;

    ResearchTask updateStatus(String taskId, String status, String errorMessage) throws IOException, SQLException;

    TaskEvent appendEvent(String taskId, String stream, String message, String traceId) throws IOException, SQLException;

    List<TaskEvent> listEvents(String taskId, int afterSequence, int limit) throws IOException, SQLException;

    @Override
    default void close() throws Exception {
    }
}
