package io.finsight.business;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.validation.annotation.Validated;
import java.util.*;
import static io.finsight.business.TaskStore.*;

@RestController
@RequestMapping("/v1/tasks")
@Validated
class ResearchTasks {
    record Execution(@NotNull @Pattern(regexp="standard|auto|selected|single") String mode,
        @NotNull @Pattern(regexp="default|deepseek-v4-flash|deepseek-v4-pro") String model,
        @NotNull @Size(max=24) List<@NotBlank @Size(max=120) String> branch_ids) {}
    record CreateTask(@NotNull UUID project_id, @NotBlank @Size(max=120) String title,
        @NotBlank @Size(min=10,max=16000) String question, @Size(max=12) List<@NotBlank @Size(max=160) String> document_ids,
        UUID sec_version, @Valid Execution execution) {}
    private final TaskStore store;
    private final PythonIntake python;
    private final ObjectMapper json;
    ResearchTasks(TaskStore store, PythonIntake python, ObjectMapper json) { this.store = store; this.python = python; this.json = json; }
    private String owner(HttpServletRequest request) { return (String)request.getAttribute("owner"); }
    private Task authorized(String owner, UUID id) {
        Task task = store.owned(owner, id); python.authorize(owner, task.project()); return task;
    }
    private ObjectNode document(Task task) {
        var result = json.createObjectNode();
        result.put("id", task.id().toString()).put("project_id", task.project().toString()).put("title", task.title())
            .put("question", task.question()).put("created_at", task.created()).put("submission_key", task.key().toString());
        result.set("binding", task.binding());
        var prepare = store.command(task.id(), "prepare");
        var start = store.command(task.id(), "start");
        try {
            var session = json.readTree(prepare.request()).path("session");
            result.set("research_options", session);
        } catch (java.io.IOException e) { throw new IllegalStateException("invalid_saved_research_request", e); }
        for (var c : List.of(prepare, start)) {
            var value = result.putObject(c.phase());
            // A process crash during dispatch is indistinguishable from a lost response.
            value.put("status", c.status().equals("dispatching") ? "unknown" : c.status()).put("operation_id", c.operation().toString());
            if (c.response() != null) value.set("result", c.response());
        }
        if (prepare.status().equals("received")) result.put("thread_id", task.id().toString());
        return result;
    }
    @GetMapping
    Object list(HttpServletRequest request, @RequestParam UUID project_id, @RequestParam(defaultValue="0") @Min(0) @Max(100000) int offset) {
        String owner = owner(request); python.authorize(owner, project_id);
        var tasks = store.list(owner, project_id, offset);
        var result = json.createObjectNode();
        result.set("items", json.valueToTree(tasks.stream().limit(50).map(this::document).toList()));
        if (tasks.size() > 50) result.put("next_offset", offset + 50); else result.putNull("next_offset");
        return result;
    }
    @GetMapping("/{id}")
    Object get(HttpServletRequest request, @PathVariable UUID id) { return document(authorized(owner(request), id)); }

    @PostMapping
    Object create(HttpServletRequest request, @RequestHeader("Idempotency-Key") UUID key, @Valid @RequestBody CreateTask input) {
        String owner = owner(request);
        python.authorize(owner, input.project_id());
        String fingerprint = Delegation.digest((byte[])request.getAttribute("originalBody"));
        Task task = store.byKey(owner, key);
        if (task == null) {
            if (input.document_ids() != null && new HashSet<>(input.document_ids()).size() != input.document_ids().size())
                throw new ApiFailure(422, "不能重复选择同一份资料");
            var response = python.request(owner, "GET", "projects/" + input.project_id() + "/binding", null, null);
            if (response.status() != 200) throw new IntakeUnavailable();
            JsonNode binding = response.body();
            if (!binding.path("snapshot_ref").asText().startsWith("sha256:") || binding.path("research_as_of").asText().isBlank()) throw new IntakeUnavailable();
            UUID id = UUID.randomUUID();
            var session = json.createObjectNode().put("title", input.title()).put("question", input.question()).put("mode", "research").put("defer_start", true);
            if (input.execution() != null) session.set("execution", json.valueToTree(input.execution()));
            if ((input.document_ids() != null && !input.document_ids().isEmpty()) || input.sec_version() != null) {
                var materials = session.putObject("project_materials").put("project_id", input.project_id().toString());
                materials.set("document_ids", json.valueToTree(input.document_ids() == null ? List.of() : input.document_ids()));
                if (input.sec_version() != null) materials.put("sec_version", input.sec_version().toString());
            }
            var prepare = json.createObjectNode().put("contract_version", "research_intake.v1").put("task_id", id.toString()).put("project_id", input.project_id().toString());
            prepare.set("binding", binding); prepare.set("session", session);
            var start = json.createObjectNode().put("task_id", id.toString()).put("project_id", input.project_id().toString()).put("thread_id", id.toString());
            task = store.insert(new Task(id, owner, input.project_id(), key, fingerprint, input.title(), input.question(), binding, null), prepare.toString(), start.toString());
        }
        if (!task.fingerprint().equals(fingerprint)) throw new ApiFailure(409, "此提交凭证已用于其他内容，请核对原任务");
        dispatch(task, "prepare");
        return document(task);
    }
    @PostMapping("/{id}/start")
    Object start(HttpServletRequest request, @PathVariable UUID id) {
        Task task = authorized(owner(request), id);
        if (!store.command(id, "prepare").status().equals("received")) throw new ApiFailure(409, "原草稿尚未确认准备完成，请先核对");
        dispatch(task, "start");
        return document(task);
    }
    @PostMapping("/{id}/prepare")
    Object prepare(HttpServletRequest request, @PathVariable UUID id) {
        Task task = authorized(owner(request), id);
        dispatch(task, "prepare");
        return document(task);
    }
    private boolean belongs(Task task, String phase, JsonNode result) {
        if (result == null || !task.id().toString().equals(result.path("task_id").asText())
            || !task.project().toString().equals(result.path("project_id").asText())
            || !task.id().toString().equals(result.path("thread_id").asText())) return false;
        if (phase.equals("prepare")) return task.binding().equals(result.path("binding")) && "draft".equals(result.path("status").asText());
        try { UUID.fromString(result.path("run_id").asText()); return true; } catch (IllegalArgumentException e) { return false; }
    }
    private void accept(Task task, Command command, int status, JsonNode result) {
        if (status >= 200 && status < 300 && belongs(task, command.phase(), result)) store.complete(command, "received", result);
        else if (status == 409 && result != null && "unknown".equals(result.path("submission_status").asText())) store.complete(command, "unknown", null);
        else if (status >= 400 && status < 500) store.complete(command, "rejected", result);
        else store.complete(command, "unknown", null);
    }
    private void dispatch(Task task, String phase) {
        var command = store.command(task.id(), phase);
        if (!store.claim(command)) return; // Database CAS across workers; never redispatch unknown.
        try {
            var reply = python.request(task.owner(), "POST", phase, command.request(), command.operation());
            accept(task, command, reply.status(), reply.body());
        } catch (IntakeUnavailable e) { store.complete(command, "unknown", null); }
    }
    @PostMapping("/{id}/reconcile")
    Object reconcile(HttpServletRequest request, @PathVariable UUID id) {
        Task task = authorized(owner(request), id);
        for (String phase : List.of("prepare", "start")) {
            var command = store.command(id, phase);
            if (!Set.of("unknown", "dispatching").contains(command.status())) continue;
            String query = "?project_id=" + task.project() + "&task_id=" + id;
            var receipt = python.request(task.owner(), "GET", "receipts/" + command.operation() + query, null, null);
            if (receipt.status() == 200 && "received".equals(receipt.body().path("status").asText())) {
                accept(task, command, receipt.body().path("http_status").asInt(), receipt.body().path("body"));
                continue;
            }
            // Only exact deterministic IDs and operation tags count as proof.
            var state = python.request(task.owner(), "GET", "tasks/" + id + "/state?project_id=" + task.project(), null, null);
            if (state.status() != 200 || !id.toString().equals(state.body().path("task_id").asText())
                || !task.project().toString().equals(state.body().path("project_id").asText())
                || !task.binding().equals(state.body().path("binding"))) continue;
            var result = json.createObjectNode().put("task_id", id.toString()).put("project_id", task.project().toString()).put("thread_id", id.toString());
            if (phase.equals("prepare") && state.body().path("prepared").asBoolean()
                && command.operation().toString().equals(state.body().path("prepare_operation_id").asText())) {
                result.put("status", "draft").set("binding", task.binding());
                accept(task, command, 200, result);
            } else if (phase.equals("start")) {
                List<JsonNode> matches = new ArrayList<>();
                state.body().path("runs").forEach(run -> { if (command.operation().toString().equals(run.path("operation_id").asText())) matches.add(run); });
                if (matches.size() == 1) {
                    result.put("run_id", matches.getFirst().path("run_id").asText()).put("status", matches.getFirst().path("status").asText());
                    accept(task, command, 200, result);
                }
            }
        }
        return document(task);
    }
}
