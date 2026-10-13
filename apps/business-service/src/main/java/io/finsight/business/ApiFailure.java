package io.finsight.business;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import java.util.Map;

class ApiFailure extends RuntimeException {
    final int status;
    ApiFailure(int status, String message) { super(message); this.status = status; }
    static ApiFailure missing() { return new ApiFailure(404, "任务或项目不存在于当前工作区"); }
}
class IntakeUnavailable extends ApiFailure {
    IntakeUnavailable() { super(503, "研究接入暂不可用；请核对原任务，不要重复创建"); }
}
@RestControllerAdvice
class ApiErrors {
    @ExceptionHandler(ApiFailure.class)
    ResponseEntity<?> failure(ApiFailure e) { return ResponseEntity.status(e.status).body(Map.of("detail", e.getMessage())); }
}
