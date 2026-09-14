"""One bounded, known-source E3 comparison; opt-in only, never a blind eval."""
import copy
import hashlib
import os
from pathlib import Path

import pytest

from test_native_server_runtime import native
from test_project_materials_live import configuration, run_real_project_materials
from sec_agent.research_foundation.research_methods import get_research_method


def method_configuration():
    config, profile, old_basis = configuration()
    basis = old_basis.model_copy(update={
        'node_purpose': 'Known-source E3 comparison: no role-method body, directly supplied finance method, dynamically selected method',
        'input_scale': 'Same saved official HTML and task; 23649 parsed characters; up to 180000 UTF8 payload bytes including native tool schemas, complete method and exact source/tool history',
        'required_outputs': (*old_basis.required_outputs,
            'Distinguish reporting segment, product and cross-segment metrics; verify relevant table before asserting non-disclosure'),
        'comparable_run_evidence': '012/013 each needed five calls without method reads; allow two catalog/method turns plus three table/calculation/repair turns: ten calls total, twenty tool actions. Historical largest payload113596 bytes;180000 allows full finance method, another source chunk and three extra exact tool turns without dropping original required work. Four-thousand output tokens previously completed the same short workpaper; no thinking tokens are hidden in this ceiling.',
        'max_input_characters': 180000,
    })
    return config.model_copy(update={'token_budget_basis': {**config.token_budget_basis, 'specialist': basis}}), profile, basis


@pytest.mark.paid_model
@pytest.mark.local_data_integration
@pytest.mark.skipif(os.getenv('FIN_NATIVE_QUALIFICATION') != '1' or os.getenv('FIN_PAID_METHOD_COMPARISON') != '1',
                    reason='explicit bounded three-arm E3 comparison only')
@pytest.mark.parametrize('arm', ['unavailable', 'direct', 'dynamic'])
def test_real_method_comparison(native, monkeypatch, arm):
    probe = copy.copy(native)
    probe.output = native.output / arm
    probe.output.mkdir(exist_ok=False)
    method = get_research_method('finance')
    options = {'role_method': method} if arm == 'direct' else {}
    if arm == 'unavailable':
        options['role_method_reader'] = lambda method_id='': {
            'method_id': method_id, 'available': False, 'answer_free': True, 'grants_authority': False,
            'reason': 'No role-method content is available in this qualification arm. Continue the actual task with the provided source and tools.'}
    comparison = {
        'arm': arm, 'baseline': 'same-attempt/unavailable; historical012/013 are contextual evidence only',
        'changed_variable': 'Role-method availability/delivery only; same shared prompt, question, saved source, model/settings and ceilings in all arms',
        'qualification_code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'method_content_sha256': hashlib.sha256(method['content'].encode()).hexdigest(),
        'review': 'All narrative, claims, counterevidence and gaps: quarter/unit/margin/citations; segment-product membership, unsupported attribution and negative disclosure claims. Method reads alone are not acceptance.',
        'limits': 'One known development source, one run per arm, no statistical/causal/generalization claim. Unavailable arm retains general system instructions and tools; it is not a prompt-free baseline.',
    }
    run_real_project_materials(probe, monkeypatch, config_bundle=method_configuration(), method_options=options,
        max_calls=10, max_bytes=180000, max_tool_actions=20, comparison=comparison, tariff_multiplier=1)
