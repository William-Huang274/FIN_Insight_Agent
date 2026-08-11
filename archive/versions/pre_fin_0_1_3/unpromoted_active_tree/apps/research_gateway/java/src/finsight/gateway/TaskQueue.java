package finsight.gateway;

import java.io.IOException;

interface TaskQueue {
    void publish(String taskId, String payloadJson) throws IOException;
}
