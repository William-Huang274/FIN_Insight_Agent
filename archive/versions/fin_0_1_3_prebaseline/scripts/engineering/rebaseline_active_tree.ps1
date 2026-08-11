param(
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$ArchiveVersionsRoot = Join-Path $RepositoryRoot "archive/versions"
$IndexPath = Join-Path $ArchiveVersionsRoot "FIN_0_1_3_REBASELINE_REDIRECT_INDEX.jsonl"

function Assert-WithinRepository([string]$PathValue) {
    $resolved = [System.IO.Path]::GetFullPath($PathValue)
    $rootPrefix = $RepositoryRoot.TrimEnd('\') + '\'
    if ($resolved -ne $RepositoryRoot -and -not $resolved.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "path_escape:$resolved"
    }
    return $resolved
}

function Normalize-Relative([string]$Value) {
    return $Value.Replace('\', '/').TrimStart('/')
}

function Infer-Version([string]$RelativePath) {
    $lower = $RelativePath.ToLowerInvariant()
    if ($lower.Contains('fin_0_1_1')) { return 'fin_0_1_1' }
    if ($lower.Contains('fin_0_1_2')) { return 'fin_0_1_2' }
    if ($lower.Contains('fin_0_1_3')) { return 'fin_0_1_3_prebaseline' }
    if ($lower.Contains('r53_r60') -or $lower.Contains('p36') -or $lower.Contains('point01') -or $lower.Contains('point02') -or $lower.Contains('point03')) {
        return 'pre_fin_0_1_3'
    }
    return 'pre_fin_0_1_3/unpromoted_active_tree'
}

function Classify([string]$RelativePath) {
    if ($RelativePath.StartsWith('src/') -or $RelativePath.StartsWith('apps/')) {
        return @('unpromoted_or_superseded_code', 'current FIN 0.1.3 active import graph', 'not_runtime_evidence')
    }
    if ($RelativePath.StartsWith('scripts/')) {
        return @('release_attempt_or_unadmitted_tooling', 'admitted data-build scripts and active baseline verifier', 'reproducible_historical_tool')
    }
    if ($RelativePath.StartsWith('tests/')) {
        return @('historical_or_unadmitted_capability_test', 'FIN 0.1.3 current baseline suite', 'reproducible_historical_test')
    }
    if ($RelativePath.StartsWith('configs/')) {
        return @('historical_contract_release_or_attempt_record', 'current runtime registry and repository governance manifests', 'immutable_historical_contract_or_result')
    }
    if ($RelativePath.StartsWith('docs/')) {
        return @('historical_design_execution_or_handoff_record', 'current PRD TECH Project OS and code map', 'immutable_historical_document')
    }
    if ($RelativePath.StartsWith('data/') -or $RelativePath.StartsWith('reports/') -or $RelativePath.StartsWith('eval_sets/')) {
        return @('historical_fixture_eval_or_model_run', 'current reviewed three-case product resources', 'immutable_historical_evidence')
    }
    return @('diagnostic_or_experimental_asset', 'current FIN 0.1.3 baseline', 'reproducible_historical_asset')
}

$VerifierOutput = & python (Join-Path $RepositoryRoot 'scripts/engineering/verify_active_baseline.py')
if ($LASTEXITCODE -ne 0) {
    throw 'active_import_graph_must_pass_before_archive'
}
$Graph = $VerifierOutput | ConvertFrom-Json
$Keep = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
foreach ($path in @($Graph.python_import_graph) + @($Graph.frontend_import_graph) + @($Graph.runtime_detector_refs) + @($Graph.runtime_resource_refs)) {
    [void]$Keep.Add((Normalize-Relative ([string]$path)))
}

$ExactKeep = @(
    'apps/__init__.py',
    'apps/workbench/__init__.py',
    'apps/workbench/README.md',
    'apps/workbench/backend/__init__.py',
    'apps/workbench/backend/api/__init__.py',
    'apps/workbench/backend/api/v1/__init__.py',
    'apps/workbench/backend/application/__init__.py',
    'apps/workbench/frontend/index.html',
    'apps/workbench/frontend/package-lock.json',
    'apps/workbench/frontend/package.json',
    'apps/workbench/frontend/playwright.config.ts',
    'apps/workbench/frontend/tsconfig.json',
    'apps/workbench/frontend/vite.config.ts',
    'apps/workbench/frontend/vite/index.html',
    'src/__init__.py',
    'src/indexing/__init__.py',
    'src/retrieval/__init__.py',
    'src/sec_agent/__init__.py',
    'src/sec_agent/research/__init__.py',
    'src/sec_agent/runtime_bridge/__init__.py',
    'src/sec_agent/workbench/__init__.py',
    'scripts/README.md',
    'scripts/engineering/rebaseline_active_tree.ps1',
    'tests/contract/test_fin_0_1_3_workbench_current_research_evidence_pack_projection.py',
    'tests/test_build_evidence_store_streaming.py',
    'tests/test_current_data_build_catalog.py',
    'tests/test_current_runtime_registry.py',
    'tests/test_current_workbench_baseline.py',
    'tests/test_industry_source_snapshot.py',
    'tests/test_sec_20f_section_splitter.py',
    'tests/test_sec_40f_annual_package.py',
    'tests/test_sec_chunk_id_uniqueness.py',
    'tests/test_workbench_artifacts.py',
    'tests/test_workbench_profiles.py',
    'configs/industry_data_api_contracts_v0_2.yaml',
    'configs/sec_tech_8k_earnings_pilot_2026_2027.yaml',
    'configs/sec_tech_universe.yaml',
    'configs/runtime/fin_ia_0_1_3_clean_baseline_runtime_resource_registry_v1_0.json',
    'docs/README.md',
    'docs/architecture/repository/README.md',
    'docs/architecture/repository/FIN_0_1_3_CURRENT_BASELINE_CODE_MAP_20260811.zh-CN.md',
    'docs/architecture/repository/FIN_0_1_3_STRICT_MAINLINE_REBASELINE_ACCEPTANCE_AND_MIGRATION_PROGRAM_20260811.zh-CN.md',
    'docs/eval/FIN_0_1_3_CODEX_VS_DEEPSEEK_THREE_CASE_RESEARCH_PROTOCOL_20260806.zh-CN.md',
    'docs/eval/FIN_0_1_3_EXPANDED_PRODUCT_PERFORMANCE_CASE_AND_ADVERSARIAL_TEST_PLAN_20260805.zh-CN.md',
    'docs/eval/FIN_0_1_3_RESEARCH_CONTENT_OUTPUT_QUALITY_RUBRIC_20260806.zh-CN.md',
    'docs/product/README.md',
    'docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md',
    'docs/product/PRODUCT_20260628_finsight_tob_toc_positioning_and_product_line.zh-CN.md',
    'docs/product/PRODUCT_20260717_release_ladder_and_cadence.zh-CN.md',
    'docs/product/FIN_0_1_3_CURRENT_BASELINE_AND_S0_TO_S5_CLOSEOUT_PLAN_20260812.zh-CN.md',
    'docs/product/FIN_0_1_3_CODEX_GOLD_RESEARCH_BENCHMARK_SCOPE_20260806.zh-CN.md',
    'docs/product/FIN_PRD_FULL_ABSORPTION_AND_RELEASE_ALLOCATION_MATRIX_20260719.zh-CN.md',
    'docs/project_os/README.md',
    'docs/project_os/agent_engineering_pattern_extraction_ledger.jsonl',
    'docs/project_os/agent_engineering_pattern_learning_ledger.jsonl',
    'docs/project_os/capability_status_ledger.jsonl',
    'docs/project_os/current_context_pack.zh-CN.md',
    'docs/project_os/done_definition_l4_scope_pass.zh-CN.md',
    'docs/project_os/external_pattern_registry.jsonl',
    'docs/project_os/financial_research_method_extraction_ledger.jsonl',
    'docs/project_os/financial_research_method_learning_ledger.jsonl',
    'docs/project_os/financial_research_method_registry.jsonl',
    'docs/project_os/full_chain_preflight_checklist.json',
    'docs/project_os/full_chain_run_policy.zh-CN.md',
    'docs/project_os/root_cause_issue_ledger.jsonl',
    'docs/project_os/senior_assistant_collaboration_policy.zh-CN.md',
    'docs/project_os/STRICT_SCHEMA_TRANSPORT_API_HANDOFF.zh-CN.md',
    'docs/project_os/token_budget_policy.zh-CN.md'
)
foreach ($path in $ExactKeep) { [void]$Keep.Add($path) }

$KeepPrefixes = @(
    'configs/repository/',
    'docs/research/'
)
function Is-Kept([string]$RelativePath) {
    if ($Keep.Contains($RelativePath)) { return $true }
    foreach ($prefix in $KeepPrefixes) {
        if ($RelativePath.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
}

$ScopedPrefixes = @('apps/', 'src/', 'scripts/', 'tests/', 'configs/', 'docs/', 'data/', 'reports/', 'eval_sets/', 'experiments/', 'deploy/')
$Tracked = @(& git -C $RepositoryRoot ls-files)
if ($LASTEXITCODE -ne 0) { throw 'git_ls_files_failed' }
$Candidates = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
foreach ($raw in $Tracked) {
    $path = Normalize-Relative $raw
    if ($path.StartsWith('archive/')) { continue }
    if ($ScopedPrefixes | Where-Object { $path.StartsWith($_, [System.StringComparison]::OrdinalIgnoreCase) }) {
        if (-not (Is-Kept $path)) { [void]$Candidates.Add($path) }
    }
}
foreach ($path in @(
    'src/sec_agent/workbench/native_checkpoint_inspection.py'
)) {
    if ((Test-Path -LiteralPath (Join-Path $RepositoryRoot $path)) -and -not (Is-Kept $path)) {
        [void]$Candidates.Add($path)
    }
}

$Ordered = @($Candidates | Sort-Object)
if (-not $Apply) {
    [PSCustomObject]@{
        mode = 'dry_run'
        candidate_count = $Ordered.Count
        keep_count = $Keep.Count
        sample = @($Ordered | Select-Object -First 30)
    } | ConvertTo-Json -Depth 4
    exit 0
}

[void](New-Item -ItemType Directory -Force -Path (Assert-WithinRepository $ArchiveVersionsRoot))
$Rows = [System.Collections.Generic.List[object]]::new()
foreach ($relative in $Ordered) {
    $source = Assert-WithinRepository (Join-Path $RepositoryRoot $relative)
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { continue }
    $version = Infer-Version $relative
    $archiveRelative = Normalize-Relative ("archive/versions/$version/$relative")
    $target = Assert-WithinRepository (Join-Path $RepositoryRoot $archiveRelative)
    if (Test-Path -LiteralPath $target) { throw "archive_target_exists:$archiveRelative" }
    [void](New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target))
    Move-Item -LiteralPath $source -Destination $target
    $classification = Classify $relative
    $Rows.Add([ordered]@{
        source_path = $relative
        archive_path = $archiveRelative
        origin_version = $version
        reason = $classification[0]
        replacement = $classification[1]
        evidence_classification = $classification[2]
        active_imports_allowed = $false
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()
    })
}

$ExistingMoved = @(
    @('apps/workbench/backend/app.py', 'archive/versions/pre_fin_0_1_3/apps/workbench/backend/app.py'),
    @('apps/workbench/backend/api/operations.py', 'archive/versions/pre_fin_0_1_3/apps/workbench/backend/api/operations_legacy_full_bridge.py'),
    @('apps/workbench/frontend/vite/src/main.tsx', 'archive/versions/pre_fin_0_1_3/apps/workbench/frontend/vite/src/main.tsx'),
    @('apps/workbench/frontend/vite/src/workbench.css', 'archive/versions/pre_fin_0_1_3/apps/workbench/frontend/vite/src/workbench.css')
)
foreach ($pair in $ExistingMoved) {
    $target = Assert-WithinRepository (Join-Path $RepositoryRoot $pair[1])
    if (-not (Test-Path -LiteralPath $target -PathType Leaf)) { continue }
    $Rows.Add([ordered]@{
        source_path = $pair[0]
        archive_path = $pair[1]
        origin_version = 'pre_fin_0_1_3'
        reason = 'superseded_workbench_consumer'
        replacement = 'current FIN 0.1.3 workspace and operations surface'
        evidence_classification = 'reproducible_historical_code'
        active_imports_allowed = $false
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()
    })
}

$IndexBuilder = Join-Path $RepositoryRoot 'scripts/engineering/build_archive_redirect_index.py'
& python $IndexBuilder
if ($LASTEXITCODE -ne 0) { throw 'archive_redirect_index_build_failed' }
[PSCustomObject]@{
    mode = 'applied'
    moved_count = $Rows.Count
    index_path = Normalize-Relative $IndexPath.Substring($RepositoryRoot.Length)
} | ConvertTo-Json
