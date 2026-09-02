[CmdletBinding()]
param(
    [switch]$PreflightOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$expectedRepositoryRoot = 'D:\FIN_Insight_Agent'
$resolvedRepositoryRoot = (Resolve-Path -LiteralPath (
    Join-Path $PSScriptRoot '..\..'
)).Path
if ($resolvedRepositoryRoot -ne $expectedRepositoryRoot) {
    throw 'This run authority is bound to D:\FIN_Insight_Agent.'
}

$pythonPath = Join-Path $expectedRepositoryRoot '.venv\Scripts\python.exe'
$runnerPath = Join-Path (
    $expectedRepositoryRoot
) 'scripts\research\run_dell_reference_vertical.py'
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw 'Bound repository Python runtime is unavailable.'
}
if (-not (Test-Path -LiteralPath $runnerPath -PathType Leaf)) {
    throw 'Bound DELL vertical runner is unavailable.'
}

$runArguments = @(
    $runnerPath,
    'start',
    '--repository-root', $expectedRepositoryRoot,
    '--state-root', 'Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\runtime',
    '--attempt-id', '20260902-dell-reference-vertical-structured-a01',
    '--run-id', 'dell-reference-vertical-structured-run-a01',
    '--case-id', 'DELL_AI_INFRA_REFERENCE_VERTICAL',
    '--snapshot-id', '20260902-dell-structured-rag-s2-successor-candidate',
    '--research-as-of', '2026-09-02T23:59:59+08:00',
    '--research-question', (
        '截至 2026 年 9 月 2 日，Dell 的 AI 基础设施业务增长到底有多大、多可持续、' +
        '能否转化为收入利润和现金流；架构迭代、GPU 与内存供给、价格数量组合、' +
        '客户需求及对华出口管制分别怎样影响兑现，最强反证和后续验证指标是什么？'
    ),
    '--foundation-path', (
        'D:\FIN_Insight_Agent\configs\research\' +
        'fin_ia_0_1_3_dell_reference_vertical_foundation_v1_0.json'
    ),
    '--foundation-sha256', 'bf214a085916c296428f51e77c8518f2905b5d451290535fea54040fb2d96d47',
    '--deepseek-config-path', (
        'D:\FIN_Insight_Agent\configs\research\' +
        'fin_ia_0_1_3_dell_reference_vertical_deepseek_structured_agents_v1_0.json'
    ),
    '--deepseek-config-sha256', '03115289a715fb65aa72e9d2c9b5463cc459c4c927a0e81fd54d6da9b1216fc8',
    '--knowledge-bridge-result-path', (
        'Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\knowledge_bridge\' +
        'combined_a02_e0_attempt_20260902_01\result.json'
    ),
    '--knowledge-bridge-result-sha256', '5d2014ebf6a0561e3f3ea0b6e76e4b5d838b5db7bb097ff086a452ececba9bf2',
    '--knowledge-records-path', (
        'Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\knowledge_bridge\' +
        'combined_a02_e0_attempt_20260902_01\records.jsonl'
    ),
    '--knowledge-records-sha256', '47d518b937390a446444dd27893a297b97d2aa297a06ac382e13fba9fd26bef9',
    '--knowledge-record-count', '597',
    '--structured-rag-result-path', (
        'Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\rag_mature_stack\' +
        'retrieval_qualification\dell_rag_full_stack_preview_attempt_20260902_03\result.json'
    ),
    '--structured-rag-result-sha256', '2ad27d586a64ad7018e460ca836ca689f84615772a561f6b5ebaba196a28191c',
    '--structured-rag-nodes-path', (
        'Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\rag_mature_stack\' +
        'retrieval_qualification\dell_rag_full_stack_preview_attempt_20260902_03\retrieval_nodes.jsonl'
    ),
    '--structured-rag-nodes-sha256', 'f7fbf9f43a68933bad52146c3a8aa3c9a1b52bba81e4e804c2b05a0aff9d0817',
    '--structured-rag-node-count', '1025',
    '--allow-engineering-preview-candidate-runtime',
    '--s2-result-path', (
        'Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\s2\' +
        's2_exact_period_contract_successor_20260902_r1\company_financial_fact_mart_result.json'
    ),
    '--s2-result-sha256', 'dd2c92400de777867545de2c41b975d1f07ca6060f4ed431075b7081ab16ed82',
    '--s2-mart-path', (
        'Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\s2\' +
        's2_exact_period_contract_successor_20260902_r1\company_financial_facts.sqlite'
    ),
    '--s2-mart-sha256', '363780c076d0f8766c0ceaafdb8b93d308d339636504b2a263127bb6ca365ac4',
    '--reviewed-evidence-root', 'D:\FIN_Insight_Agent\data\workbench_private',
    '--workbench-private-root', 'D:\FIN_Insight_Agent\data\workbench_private',
    '--reviewed-evidence-projection-digest', '2d4e3d572494e6fc7b7537b567a644a894cdf1e82143d325812860c4cc84eccd',
    '--reviewed-evidence-overlay-projection-path', (
        'Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\evidence_overlay\attempts\' +
        '20260902T051005+0800-dell-fy27q2-sec-ex99-review-a01\' +
        'reviewed-evidence-case-projection.json'
    ),
    '--reviewed-evidence-overlay-projection-sha256', '1479e49f0cde7166fe6474a74b666dfb646b31a5291f1317689aaa6bc8391eb9',
    '--reviewed-evidence-overlay-receipt-path', (
        'Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\evidence_overlay\attempts\' +
        '20260902T051005+0800-dell-fy27q2-sec-ex99-review-a01\receipt.json'
    ),
    '--reviewed-evidence-overlay-receipt-sha256', 'e846fc5d85defa9909779d0ef12f6a1e0c5b00a99ef1eb2d1fffa6ed16492d70',
    '--api-key-env', 'DEEPSEEK_API_KEY'
)
if ($PreflightOnly) {
    $runArguments += '--preflight-only'
}

& $pythonPath @runArguments
exit $LASTEXITCODE
