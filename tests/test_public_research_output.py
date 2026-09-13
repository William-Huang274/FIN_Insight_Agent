import json
from sec_agent.agent_runtime.public_research_output import submitted_prose




def test_complete_prose_retained_without_character_truncation():
    text = "Detailed research output with limitation. " * 800
    assert submitted_prose("submit_case_report", {"report": {"narrative_markdown": text}}) == text
