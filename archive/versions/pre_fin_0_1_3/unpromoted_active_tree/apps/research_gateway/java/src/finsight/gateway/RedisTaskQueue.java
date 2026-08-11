package finsight.gateway;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.net.Socket;
import java.nio.charset.StandardCharsets;

final class RedisTaskQueue implements TaskQueue {
    private final String host;
    private final int port;
    private final String queueKey;

    RedisTaskQueue(String host, int port, String queueKey) {
        this.host = host;
        this.port = port;
        this.queueKey = queueKey;
    }

    @Override
    public void publish(String taskId, String payloadJson) throws IOException {
        try (Socket socket = new Socket(host, port);
             BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8));
             BufferedReader reader = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8))) {
            writeCommand(writer, "LPUSH", queueKey, payloadJson);
            String response = reader.readLine();
            if (response == null || response.startsWith("-")) {
                throw new IOException("redis_lpush_failed: " + response);
            }
        }
    }

    private static void writeCommand(BufferedWriter writer, String... parts) throws IOException {
        writer.write("*" + parts.length + "\r\n");
        for (String part : parts) {
            byte[] bytes = part.getBytes(StandardCharsets.UTF_8);
            writer.write("$" + bytes.length + "\r\n");
            writer.write(part);
            writer.write("\r\n");
        }
        writer.flush();
    }
}
