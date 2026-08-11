package finsight.gateway;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;

final class FileTaskStore implements TaskStore {
    private final Path taskDir;
    private final Path eventDir;

    FileTaskStore(Path taskDir) {
        this.taskDir = taskDir.toAbsolutePath().normalize();
        this.eventDir = this.taskDir.getParent() == null ? this.taskDir.resolve("events") : this.taskDir.getParent().resolve("events");
    }

    @Override
    public synchronized void initialize() throws IOException {
        Files.createDirectories(taskDir);
        Files.createDirectories(eventDir);
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

    @Override
    public synchronized ResearchTask updateStatus(String taskId, String status, String errorMessage) throws IOException {
        ResearchTask existing = get(taskId).orElseThrow(() -> new IllegalArgumentException("task_not_found: " + taskId));
        ResearchTask updated = existing.withGatewayStatus(status, errorMessage);
        write(updated);
        return updated;
    }

    @Override
    public synchronized TaskEvent appendEvent(String taskId, String stream, String message, String traceId) throws IOException {
        get(taskId).orElseThrow(() -> new IllegalArgumentException("task_not_found: " + taskId));
        Files.createDirectories(eventDir);
        int sequence = nextEventSequence(taskId);
        TaskEvent event = TaskEvent.create(taskId, sequence, traceId, stream, message);
        Files.writeString(
                eventPathFor(taskId),
                JsonUtil.write(event.toMap()) + System.lineSeparator(),
                StandardCharsets.UTF_8,
                StandardOpenOption.CREATE,
                StandardOpenOption.APPEND);
        return event;
    }

    @Override
    public synchronized List<TaskEvent> listEvents(String taskId, int afterSequence, int limit) throws IOException {
        get(taskId).orElseThrow(() -> new IllegalArgumentException("task_not_found: " + taskId));
        Path path = eventPathFor(taskId);
        if (!Files.exists(path)) {
            return List.of();
        }
        int boundedLimit = Math.max(1, Math.min(5000, limit));
        List<TaskEvent> result = new ArrayList<>();
        for (String line : Files.readAllLines(path, StandardCharsets.UTF_8)) {
            if (line.isBlank()) {
                continue;
            }
            TaskEvent event = TaskEvent.fromMap(JsonUtil.readObject(line));
            if (event.sequence > Math.max(0, afterSequence)) {
                result.add(event);
            }
            if (result.size() >= boundedLimit) {
                break;
            }
        }
        return result;
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

    private Path eventPathFor(String taskId) {
        String safe = taskId.replaceAll("[^A-Za-z0-9_.-]", "_");
        return eventDir.resolve(safe + ".jsonl");
    }

    private int nextEventSequence(String taskId) throws IOException {
        Path path = eventPathFor(taskId);
        if (!Files.exists(path)) {
            return 1;
        }
        int last = 0;
        for (String line : Files.readAllLines(path, StandardCharsets.UTF_8)) {
            if (!line.isBlank()) {
                last = Math.max(last, TaskEvent.fromMap(JsonUtil.readObject(line)).sequence);
            }
        }
        return last + 1;
    }
}
