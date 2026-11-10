import json
import pytest
from langchain_core.tools import ToolException
from sec_agent.agent_runtime.organization_work_session import select_observed_sources


@pytest.mark.parametrize('key,reader,arguments', [
    ('WEB::'+'a'*64, 'read_public_source', {'operation':'read','document_id':'WEB::'+'a'*64}),
    ('fin-tool-180aa910-826d-4c55-9f66-896efcbd9f29', 'read_saved_result', {'tool_call_id':'fin-tool-180aa910-826d-4c55-9f66-896efcbd9f29'}),
    ('PASSAGE::unknown', 'browse_context', {'region':'sources'}),
])
def test_selection_feedback_routes_without_accepting_unobserved_source(key, reader, arguments):
    with pytest.raises(ToolException) as failure:
        select_observed_sources({'messages':[]}, source_ids=[key])
    result=json.loads(str(failure.value))
    assert result['requested_source_id']==key
    assert result['readback']=={'tool':reader,'arguments':arguments}
    assert result['code']=='source_not_observed_read_current_source_catalog'
