package io.finsight.business;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

/** Explicit disposable PostgreSQL only. Real command SQL, mocked outer grant. */
@EnabledIfEnvironmentVariable(named="FINSIGHT_TASK_DB_TEST_URL",matches=".+")
class TaskCommandDatabaseTest {
    final ObjectMapper json=new ObjectMapper();
    JdbcTemplate db; DriverManagerDataSource source; String schema;
    OrganizationExecutionBindings bindings; OrganizationTaskCommands controller;
    UUID root=UUID.randomUUID(),parentRun=UUID.randomUUID(),cp=UUID.randomUUID();
    final String manifest="sha256:"+"a".repeat(64);
    @BeforeEach void setup() {
        String url=System.getenv("FINSIGHT_TASK_DB_TEST_URL");
        schema="task_test_"+UUID.randomUUID().toString().replace("-","");
        var admin=new DriverManagerDataSource(url,"postgres",System.getenv("FINSIGHT_TASK_DB_TEST_PASSWORD"));
        new JdbcTemplate(admin).execute("CREATE SCHEMA "+schema);
        source=new DriverManagerDataSource(url+(url.contains("?")?"&":"?")+"currentSchema="+schema,
            "postgres",System.getenv("FINSIGHT_TASK_DB_TEST_PASSWORD")); db=new JdbcTemplate(source);
        db.execute("CREATE TABLE organization_research_draft(id uuid primary key,organization_id uuid)");
        db.execute("CREATE TABLE organization_execution_binding(id uuid primary key,principal text,draft_id uuid)");
        db.execute("CREATE TABLE organization_native_start(execution_id uuid,run_id uuid)");
        db.execute("CREATE TABLE organization_native_continuation(execution_id uuid,run_id uuid)");
        db.update("INSERT INTO organization_research_draft VALUES(?,?)",root,UUID.randomUUID());
        db.update("INSERT INTO organization_execution_binding VALUES(?,?,?)",root,"alice",root);
        db.update("INSERT INTO organization_native_start VALUES(?,?)",root,parentRun);
        new ResourceDatabasePopulator(new ClassPathResource("db/migration/V11__organization_report_commands.sql")).execute(source);
        // A pre-migration report must keep its identity and serial constraint.
        db.update("INSERT INTO organization_report_command(id,execution_id,operation_id,principal,fingerprint,checkpoint_id,request_body) VALUES(?,?,?,'alice','hash',?,'{}')",
            UUID.randomUUID(),root,UUID.randomUUID(),cp);
        new ResourceDatabasePopulator(new ClassPathResource("db/migration/V12__research_task_command_scope.sql")).execute(source);
        new ResourceDatabasePopulator(new ClassPathResource("db/migration/V13__continuous_root_commands.sql")).execute(source);
        bindings=mock(OrganizationExecutionBindings.class);
        controller=new OrganizationTaskCommands(db,json,bindings,new DataSourceTransactionManager(source),true);
    }
    @AfterEach void cleanup() { if(db!=null)db.execute("DROP SCHEMA "+schema+" CASCADE"); }
    OrganizationTaskCommands.Claim create(UUID child) {
        ObjectNode task=json.createObjectNode().put("delivery_intent","workpaper");
        ObjectNode c=json.createObjectNode().put("command_id",UUID.randomUUID().toString())
            .put("execution_id",root.toString()).put("parent_thread_id",root.toString())
            .put("parent_run_id",parentRun.toString()).put("parent_checkpoint_id",cp.toString())
            .put("child_thread_id",child.toString()).put("action","create")
            .put("root_budget_id","root-budget").put("manifest_digest",manifest).put("message","");
        c.set("task",task);c.putNull("checkpoint_id");
        ObjectNode fixed=json.createObjectNode().put("source_thread",root.toString()).put("checkpoint_id",cp.toString())
            .put("root_budget_id","root-budget").put("manifest_digest",manifest).put("input_digest","b".repeat(64));
        fixed.set("task",task);return new OrganizationTaskCommands.Claim(c,fixed);
    }
    @SuppressWarnings("unchecked") Map<String,Object> claim(OrganizationTaskCommands.Claim input) {
        return (Map<String,Object>)controller.claim(root,input);
    }
    OrganizationTaskCommands.Claim action(OrganizationTaskCommands.Claim first,String action,UUID checkpoint) {
        ObjectNode c=((ObjectNode)first.command()).deepCopy().put("command_id",UUID.randomUUID().toString())
            .put("action",action).put("checkpoint_id",checkpoint.toString()).put("message",action.equals("continue")?"Continue this same task":"");
        c.putNull("task");return new OrganizationTaskCommands.Claim(c,null);
    }
    @Test void twoChildrenShareParentCheckpointButNotCommandsAndUnknownDoesNotReissue() {
        UUID child=UUID.randomUUID();var input=create(child);var a=claim(input);
        assertEquals(true,a.get("dispatch_allowed"));assertEquals(false,claim(input).get("dispatch_allowed"));
        assertEquals(a.get("operation_id"),claim(input).get("operation_id"));
        assertEquals(true,claim(create(UUID.randomUUID())).get("dispatch_allowed"));
        assertThrows(ApiFailure.class,()->claim(create(child)));
        assertThrows(ApiFailure.class,()->claim(action(input,"continue",UUID.randomUUID())));
        var changed=new OrganizationTaskCommands.Claim(input.command(),input.fixed_input().deepCopy());
        ((ObjectNode)changed.fixed_input()).put("extra","different");
        assertThrows(ApiFailure.class,()->claim(changed));
        assertEquals(1,db.queryForObject("SELECT count(*) FROM organization_report_command WHERE command_kind='report'",Integer.class));
        assertThrows(org.springframework.dao.DataIntegrityViolationException.class,()->db.update(
            "INSERT INTO organization_report_command(id,execution_id,operation_id,principal,fingerprint,checkpoint_id,request_body) VALUES(?,?,?,'alice','hash',?,'{}')",
            UUID.randomUUID(),root,UUID.randomUUID(),cp));
    }
    @Test void rootContinuationKeepsCheckpointUniquenessAcrossOldAndNewContracts() {
        assertThrows(org.springframework.dao.DataIntegrityViolationException.class,()->db.update(
            "INSERT INTO organization_report_command(id,execution_id,operation_id,principal,fingerprint,checkpoint_id,request_body,command_kind) VALUES(?,?,?,'alice','hash',?,'{}','root_task')",
            UUID.randomUUID(),root,UUID.randomUUID(),cp));
        UUID next=UUID.randomUUID();
        db.update("INSERT INTO organization_report_command(id,execution_id,operation_id,principal,fingerprint,checkpoint_id,request_body,command_kind) VALUES(?,?,?,'alice','hash',?,'{}','root_task')",
            UUID.randomUUID(),root,UUID.randomUUID(),next);
        assertEquals(1,db.queryForObject("SELECT count(*) FROM organization_report_command WHERE command_kind='root_task'",Integer.class));
        assertThrows(org.springframework.dao.DataIntegrityViolationException.class,()->db.update(
            "UPDATE organization_report_command SET child_thread_id=? WHERE command_kind='root_task'",UUID.randomUUID()));
        assertEquals(true,claim(create(UUID.randomUUID())).get("dispatch_allowed"));
    }
    @Test void cancellationWinsOverLateAcceptanceAndDoesNotEraseResults() {
        UUID child=UUID.randomUUID(),run=UUID.randomUUID();var first=create(child);var saved=claim(first);
        UUID id=(UUID)saved.get("command_id");
        controller.admit(root,new OrganizationTaskCommands.Lookup(manifest,child,id,run,null));
        claim(action(first,"cancel",UUID.randomUUID()));
        var catalog=(List<?>)controller.catalog(root,new OrganizationTaskCommands.Catalog(manifest));
        assertEquals(1,catalog.size());
        assertEquals("cancel",((Map<?,?>)catalog.getFirst()).get("task_action"));
        assertEquals(id,((Map<?,?>)catalog.getFirst()).get("create_command_id"));
        var receipt=json.createObjectNode().put("thread_id",child.toString()).put("run_id",run.toString()).put("status","pending");
        controller.accept(root,new OrganizationTaskCommands.Lookup(manifest,child,id,null,receipt));
        var wrongReceipt=receipt.deepCopy().put("run_id",UUID.randomUUID().toString());
        assertThrows(ApiFailure.class,()->controller.accept(root,new OrganizationTaskCommands.Lookup(manifest,child,id,null,wrongReceipt)));
        assertThrows(ApiFailure.class,()->controller.admit(root,new OrganizationTaskCommands.Lookup(manifest,child,id,run,null)));
        var read=(Map<?,?>)controller.read(root,new OrganizationTaskCommands.Lookup(manifest,child,id,null,null));
        assertEquals(true,read.get("cancel_requested"));assertEquals(run,read.get("run_id"));
        assertThrows(ApiFailure.class,()->controller.read(root,new OrganizationTaskCommands.Lookup(manifest,UUID.randomUUID(),id,null,null)));
        doThrow(new ApiFailure(404,"revoked")).when(bindings).access(eq(root),any());
        assertThrows(ApiFailure.class,()->controller.read(root,new OrganizationTaskCommands.Lookup(manifest,child,id,null,null)));
    }
    @Test void resumeSharesRootAndCannotRebindRunOrReuseCheckpoint() {
        UUID child=UUID.randomUUID(),run=UUID.randomUUID();var first=create(child);var saved=claim(first);
        UUID id=(UUID)saved.get("command_id");
        controller.admit(root,new OrganizationTaskCommands.Lookup(manifest,child,id,run,null));
        assertThrows(ApiFailure.class,()->controller.admit(root,new OrganizationTaskCommands.Lookup(manifest,child,id,UUID.randomUUID(),null)));
        var receipt=json.createObjectNode().put("thread_id",child.toString()).put("run_id",run.toString()).put("status","success");
        controller.accept(root,new OrganizationTaskCommands.Lookup(manifest,child,id,null,receipt));
        UUID checkpoint=UUID.randomUUID();claim(action(first,"continue",checkpoint));
        assertThrows(ApiFailure.class,()->claim(action(first,"continue",checkpoint)));
        var wrong=action(first,"continue",UUID.randomUUID());((ObjectNode)wrong.command()).put("root_budget_id","new-budget");
        assertThrows(ApiFailure.class,()->claim(wrong));
    }
}
