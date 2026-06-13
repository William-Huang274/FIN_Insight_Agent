package finsight.gateway;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.Map;
import java.util.Optional;

final class FileTaskStore implements TaskStore {
    private final Path taskDir;

    FileTaskStore(Path taskDir) {
        this.taskDir = taskDir.toAbsolutePath().normalize();
    }

    @Override
    public synchronized void initialize() throws IOException {
        Files.createDirectories(taskDir);
    }

    @Override
    public synchronized void create(ResearchTask task) throws IOException {
        write(task);
    }

    @Override
    public synchronized Optional<ResearchTask> get(String taskId) throws IOException {
        Path path = pathFor(taskId);
        if (!Files.exists(path)) {
            return Optional.empty();
        }
        return Optional.of(ResearchTask.fromMap(JsonUtil.readObject(Files.readString(path, StandardCharsets.UTF_8))));
    }

    @Override
    public synchronized ResearchTask updateFromWorker(String taskId, Map<String, Object> update) throws IOException {
        ResearchTask existing = get(taskId).orElseThrow(() -> new IllegalArgumentException("task_not_found: " + taskId));
        ResearchTask updated = existing.withWorkerUpdate(update);
        write(updated);
        return updated;
    }

    private void write(ResearchTask task) throws IOException {
        Files.createDirectories(taskDir);
        Path target = pathFor(task.taskId);
        Path tmp = taskDir.resolve(task.taskId + ".json.tmp");
        Files.writeString(tmp, JsonUtil.write(task.toMap()), StandardCharsets.UTF_8);
        Files.move(tmp, target, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
    }

    private Path pathFor(String taskId) {
        String safe = taskId.replaceAll("[^A-Za-z0-9_.-]", "_");
        return taskDir.resolve(safe + ".json");
    }
}
