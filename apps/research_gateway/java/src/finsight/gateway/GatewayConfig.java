package finsight.gateway;

import java.nio.file.Path;

final class GatewayConfig {
    final String host;
    final int port;
    final String storeMode;
    final Path stateDir;
    final String queueMode;
    final Path queueDir;
    final String redisHost;
    final int redisPort;
    final String redisQueueKey;
    final String jdbcUrl;
    final String jdbcUser;
    final String jdbcPassword;
    final String workerToken;

    private GatewayConfig() {
        this.host = env("FINSIGHT_GATEWAY_HOST", "127.0.0.1");
        this.port = intEnv("FINSIGHT_GATEWAY_PORT", 8780);
        this.storeMode = env("FINSIGHT_GATEWAY_STORE_MODE", "file").trim().toLowerCase();
        this.stateDir = Path.of(env("FINSIGHT_GATEWAY_STATE_DIR", "data/runtime_bridge/java_gateway")).toAbsolutePath().normalize();
        this.queueMode = env("FINSIGHT_GATEWAY_QUEUE_MODE", "file").trim().toLowerCase();
        this.queueDir = Path.of(env("FINSIGHT_GATEWAY_QUEUE_DIR", stateDir.resolve("queue").toString())).toAbsolutePath().normalize();
        this.redisHost = env("FINSIGHT_REDIS_HOST", "127.0.0.1");
        this.redisPort = intEnv("FINSIGHT_REDIS_PORT", 6379);
        this.redisQueueKey = env("FINSIGHT_REDIS_QUEUE_KEY", "finsight:research_tasks");
        this.jdbcUrl = env("FINSIGHT_JDBC_URL", "");
        this.jdbcUser = env("FINSIGHT_JDBC_USER", "");
        this.jdbcPassword = env("FINSIGHT_JDBC_PASSWORD", "");
        this.workerToken = env("FINSIGHT_WORKER_TOKEN", "");
    }

    static GatewayConfig fromEnv() {
        return new GatewayConfig();
    }

    TaskStore createTaskStore() {
        if ("jdbc".equals(storeMode) || "mysql".equals(storeMode) || "postgres".equals(storeMode)) {
            if (jdbcUrl.isBlank()) {
                throw new IllegalArgumentException("FINSIGHT_JDBC_URL is required when FINSIGHT_GATEWAY_STORE_MODE=" + storeMode);
            }
            return new JdbcTaskStore(jdbcUrl, jdbcUser, jdbcPassword);
        }
        if (!"file".equals(storeMode)) {
            throw new IllegalArgumentException("unsupported_store_mode: " + storeMode);
        }
        return new FileTaskStore(stateDir.resolve("tasks"));
    }

    TaskQueue createTaskQueue() {
        if ("redis".equals(queueMode)) {
            return new RedisTaskQueue(redisHost, redisPort, redisQueueKey);
        }
        if (!"file".equals(queueMode)) {
            throw new IllegalArgumentException("unsupported_queue_mode: " + queueMode);
        }
        return new FileTaskQueue(queueDir);
    }

    private static String env(String key, String defaultValue) {
        String value = System.getenv(key);
        return value == null || value.isBlank() ? defaultValue : value;
    }

    private static int intEnv(String key, int defaultValue) {
        String value = System.getenv(key);
        if (value == null || value.isBlank()) {
            return defaultValue;
        }
        try {
            return Integer.parseInt(value.trim());
        } catch (NumberFormatException exc) {
            throw new IllegalArgumentException("invalid integer env " + key + ": " + value, exc);
        }
    }
}
