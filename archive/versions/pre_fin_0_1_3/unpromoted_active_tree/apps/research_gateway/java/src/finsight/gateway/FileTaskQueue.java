package finsight.gateway;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.Instant;

final class FileTaskQueue implements TaskQueue {
    private final Path pendingDir;

    FileTaskQueue(Path queueDir) {
        this.pendingDir = queueDir.toAbsolutePath().normalize().resolve("pending");
    }

    @Override
    public synchronized void publish(String taskId, String payloadJson) throws IOException {
        Files.createDirectories(pendingDir);
        String safeTaskId = taskId.replaceAll("[^A-Za-z0-9_.-]", "_");
        String name = Instant.now().toEpochMilli() + "_" + safeTaskId + ".json";
        Path tmp = pendingDir.resolve(name + ".tmp");
        Path target = pendingDir.resolve(name);
        Files.writeString(tmp, payloadJson, StandardCharsets.UTF_8);
        Files.move(tmp, target, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
    }
}
