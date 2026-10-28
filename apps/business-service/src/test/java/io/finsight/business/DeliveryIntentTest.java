package io.finsight.business;

import com.fasterxml.jackson.databind.*;
import jakarta.servlet.http.HttpServletRequest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import java.util.UUID;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

/** Contract/admission tests only: no PostgreSQL, Docker, native service or model. */
class DeliveryIntentTest {
    final ObjectMapper json = new ObjectMapper().disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES);
    final String base = "\"mode\":\"standard\",\"model\":\"default\",\"branch_ids\":[]";

    ResearchTasks.Execution options(String extra) throws Exception {
        return json.readValue("{" + base + extra + "}", ResearchTasks.Execution.class);
    }

    @Test void omissionAndExplicitReportRemainDifferent() throws Exception {
        var omitted = options("");
        var explicit = options(",\"delivery_intent\":\"report\"");
        omitted.requireReportWorkflow(); explicit.requireReportWorkflow();
        assertFalse(json.valueToTree(omitted).has("delivery_intent"));
        assertEquals("report", json.valueToTree(explicit).path("delivery_intent").asText());
        for (var value : new ResearchTasks.Execution[]{omitted, explicit}) {
            var saved = json.writeValueAsString(value);
            assertEquals(saved, json.writeValueAsString(json.readValue(saved, ResearchTasks.Execution.class)));
        }
        assertNotEquals(Delegation.digest(json.writeValueAsBytes(omitted)), Delegation.digest(json.writeValueAsBytes(explicit)));
    }

    @ParameterizedTest @ValueSource(strings={"null", "true", "0", "[]", "{}", "\"memo\"", "\"\""})
    void invalidIntentCannotBecomeDefault(String value) {
        assertThrows(JsonMappingException.class, () -> options(",\"delivery_intent\":" + value));
    }

    @Test void unknownOptionCannotBeSilentlyDiscarded() {
        assertThrows(JsonMappingException.class, () -> options(",\"delivery_intnets\":\"answer\""));
    }

    @ParameterizedTest @ValueSource(strings={"answer", "workpaper"})
    void unsupportedIntentIsRejectedBeforeBusinessOrNativeWork(String intent) throws Exception {
        var execution = options(",\"delivery_intent\":\"" + intent + "\"");
        assertEquals(intent, json.valueToTree(execution).path("delivery_intent").asText());
        var store = mock(TaskStore.class); var python = mock(PythonIntake.class);
        var request = mock(HttpServletRequest.class);
        var tasks = new ResearchTasks(store, python, json);
        var failure = assertThrows(ApiFailure.class, () -> tasks.create(request, UUID.randomUUID(),
            new ResearchTasks.CreateTask(UUID.randomUUID(), "Title", "Question to research", null, null, execution)));
        assertEquals(422, failure.status);
        assertEquals("delivery_intent_not_supported_by_report_workflow:" + intent, failure.getMessage());
        var db = mock(JdbcTemplate.class); var bindings = mock(OrganizationExecutionBindings.class);
        var manager = mock(PlatformTransactionManager.class);
        var drafts = new OrganizationNativeDrafts(db, bindings, python, json, manager);
        var organizationFailure = assertThrows(ApiFailure.class, () -> drafts.prepare(request, UUID.randomUUID(),
            UUID.randomUUID(), new OrganizationNativeDrafts.Prepare(execution)));
        assertEquals(422, organizationFailure.status);
        verifyNoInteractions(store, python, db, bindings, manager, request);
    }
}
