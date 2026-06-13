package finsight.gateway;

import java.io.IOException;
import java.sql.SQLException;
import java.util.Optional;

interface TaskStore extends AutoCloseable {
    void initialize() throws IOException, SQLException;

    void create(ResearchTask task) throws IOException, SQLException;

    Optional<ResearchTask> get(String taskId) throws IOException, SQLException;

    ResearchTask updateFromWorker(String taskId, java.util.Map<String, Object> update) throws IOException, SQLException;

    @Override
    default void close() throws Exception {
    }
}
