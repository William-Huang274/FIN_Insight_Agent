package io.finsight.business;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import java.util.UUID;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class TaskCommandTest {
    final ObjectMapper json=new ObjectMapper();
    final JdbcTemplate db=mock(JdbcTemplate.class);
    final OrganizationExecutionBindings bindings=mock(OrganizationExecutionBindings.class);
    final PlatformTransactionManager manager=mock(PlatformTransactionManager.class);

    @Test void disabledActionNeverUsesParentAuthorityOrDatabase() {
        var controller=new OrganizationTaskCommands(db,json,bindings,manager,false);
        assertThrows(ApiFailure.class,()->controller.claim(UUID.randomUUID(),
            new OrganizationTaskCommands.Claim(json.createObjectNode(),null)));
        verifyNoInteractions(db,bindings,manager);
    }
    @Test void malformedTaskCannotBorrowAnOldReportCommand() {
        var controller=new OrganizationTaskCommands(db,json,bindings,manager,true);
        ObjectNode command=json.createObjectNode().put("action","create");
        assertThrows(ApiFailure.class,()->controller.claim(UUID.randomUUID(),new OrganizationTaskCommands.Claim(command,null)));
        verifyNoInteractions(db,bindings,manager);
    }
}
