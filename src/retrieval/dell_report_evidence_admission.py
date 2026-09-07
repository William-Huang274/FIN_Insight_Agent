from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from .query_plan import canonical_digest


PROGRAM_SCHEMA_VERSION = "fin_ia_dell_report_evidence_admission_program_v1_1"
PRIVATE_PACKET_SCHEMA_VERSION = (
    "fin_ia_dell_report_evidence_admission_private_packet_v1_1"
)
PUBLIC_MANIFEST_SCHEMA_VERSION = (
    "fin_ia_dell_report_evidence_admission_public_manifest_v1_1"
)

EXPECTED_INPUT_BINDINGS = {
    "G1_independent_audit": {
        "ref": "configs/audits/fin_ia_0_1_3_commit_7ba8bb2a_dell_rsq_r3_fresh_final_audit_pass_v1_0.json",
        "sha256": "9429d75f101097da5e48815e8a0fab8ffb8966a38c4f5dd499eb5df1c4b27189",
        "digest_field": "result_digest",
        "digest": "4f28008ea1a15a9813ec0ac22ec5e8219519de9c3195cf6b6928d0c6c1542dd4",
    },
    "G1_crosswalk_public": {
        "ref": "configs/research/evals/fin_ia_0_1_3_dell_report_gap_crosswalk_result_v1_2.json",
        "sha256": "990972fc1acb62696f0bebbc12713e100597271ec562424296cf8d220ff577f5",
        "digest_field": "result_digest",
        "digest": "afc37e760cd88c107365e727d10b53694b299f93c4245cf90110775ec22676e2",
    },
    "current_readiness_public": {
        "ref": "configs/retrieval/fin_ia_0_1_3_s1_dell_current_product_readiness_result_v1_7.json",
        "sha256": "67a65f8efbde97bef20e2cc2ff8439e30eb3fac4ddeb2680c369d67f1361b19b",
        "digest_field": "result_digest",
        "digest": "bd6d652cc4b9551fc3d046724702d57b62beb56bfd76f6131c4513a4c805e40f",
    },
    "current_readiness_private": {
        "ref": "data/workbench_private/fin_0_1_3_s1_current_product_readiness/dell-r9/full_result.json",
        "sha256": "c6af46811dd9f85487eface3c2e49aaafd22a4b7b2c7fa2960b75c9670b0db42",
        "digest_field": "result_digest",
        "digest": "2f09b9832d09ce1600f5ef403499e25fbb83ab5cf40079681be42aaa2e2c7665",
    },
    "R17_private_report": {
        "ref": "data/workbench_private/fin_0_1_3_s3_current_dynamic_multi_agent/dell-R10-protected-writer-reversal-gate-r17/full_result.json",
        "sha256": "433b2c486f8753d4f0b2468aa66f21c0ef2ff0e4bcc7d9347233e239b30ec0e8",
        "digest_field": "full_result_digest",
        "digest": "3be5a5453c8cf18cf5a14f7b7de7535b8d8c64367275e2f509dc0849db587743",
    },
    "immutable_execution_program": {
        "ref": "docs/architecture/research/FIN_0_1_3_DELL_SOURCE_CLOSURE_MODEL_AND_REPORT_QUALITY_EXECUTION_PROGRAM_20260825.zh-CN.md",
        "sha256": "5bbb52691fd183bae5c61c6d6dd1b119544e76ffa2625a42dcb1297bd1ae4f0d",
    },
    "R1_failed_audit": {
        "ref": "configs/audits/fin_ia_0_1_3_commit_581c1d6e_dell_02a_03a_fresh_audit_fail_v1_0.json",
        "sha256": "892e11be5ac74ae1191e19a6012a41b6f44cb66103836e3a4d10e7edd03260e4",
        "digest_field": "result_digest",
        "digest": "061cd35cbf624e8a7f84b379466396e0870f122799627107afc6ae9541d4a3ea",
    },
    "R1_admission_program": {
        "ref": "configs/retrieval/fin_ia_0_1_3_s1_dell_report_evidence_admission_program_v1_0.json",
        "sha256": "4ebebcd60ca276d0d188013cc6d1ceec41e83585348365e5b61861a5f9cf02ee",
        "digest_field": "program_digest",
        "digest": "60fd30e57fa588837fd72025aa74ca96e96e5f468e5649fb18c211df08b0776b",
    },
    "R1_admission_public": {
        "ref": "configs/retrieval/fin_ia_0_1_3_s1_dell_report_evidence_admission_manifest_v1_0.json",
        "sha256": "5af6e9b4028c0ba02642733330db9a8f6ff564073e9d116b984710ba8b3f7306",
        "digest_field": "result_digest",
        "digest": "199b5d56e7ea419268a56deb333e66fa8c06f46000d3e53c5cab1e10340edcb2",
    },
    "R1_admission_private": {
        "ref": "data/workbench_private/fin_0_1_3_dell_report_evidence_admission/dell-r1/full_result.json",
        "sha256": "895d340ebdd9e79f4aa8b46344aaf925ed83ead5aa50c3310d946f07cd7ef0f7",
        "digest_field": "full_result_digest",
        "digest": "d5494b4ea30653792f3d7daf6efab00c0b9dbbcdee09a32f6040c553e9e9950a",
    },
}

EXPECTED_REVIEW_ITEM_INVENTORY_BY_REQUEST = {
    "REQ::fb06661b946711fc3b334146": {
        "CANDOBJ::224717EF1BE75160C9B8551C": (
            "e03184947dc71c8a679cf4cb3a30a80506ca00f0395882b0b15c81bf8929d002",
            False,
        ),
        "CANDOBJ::0381BE87C0EE31414BA6EA4E": (
            "0bd1c306dbd895bfc7eac7bfe1a457c986e9ce18b5771e6ae48bb416a7110f22",
            True,
        ),
        "CANDOBJ::D7A996F5F40E35C760851932": (
            "b594920f4f80823c725aa0cdb99e15df69d28ac6c7278650ebe134c525c626a4",
            True,
        ),
    },
    "REQ::eb2e808dd2e48b4fe7474223": {
        "CANDOBJ::C65DFBE229D71DEFB12E15E9": (
            "bd4680084c81cd600dbe8ed86d60098789f2266ca010993150ce900d83c8569b",
            False,
        ),
        "CANDOBJ::040A820BE15FD0CEAF83C0AD": (
            "ebc02f66b559e1631f29488e3a5e237da4939fba2ef3a28309c4764678ee2feb",
            True,
        ),
        "CANDOBJ::E9A0B4076252D3978B8DAB73": (
            "5a83aa396988f3d2a14f2a1ef3e7d3fa80c12bce6e69f61d1f027a7cd11f1688",
            True,
        ),
    },
    "REQ::e17c40f93e25438950673210": {
        "CANDOBJ::E591113506AF79306D11D8AD": (
            "3674c9ed006637a3771df271f067358530f50e00fc34af67a5a293a809e0b0a2",
            True,
        ),
        "CANDOBJ::8EDA130D7FDA0F0B66BA53B5": (
            "ae21569fc5bd4876aa286f45f4a37465293497bd30dffedda98bc27b515f5f3c",
            True,
        ),
    },
    "REQ::081c06389f9dcb8487886b57": {
        "CANDOBJ::51BFECDF1794E6CE42A7B2CE": (
            "09cddcda4bfdd2c53889d6b9cea118818b665f11483f47582849e406c3260e69",
            True,
        ),
        "CANDOBJ::C20F9F784D691747A36DADC3": (
            "85c4d56d66c0c5e5f44f1444380a866ce96f9f26550312b9d40a6a9d0a067df6",
            True,
        ),
    },
    "REQ::273bf40c53d28f49de438b41": {
        "CANDOBJ::6E0870ECD8935A2BE7A6110F": (
            "e2d5cf130dcacf1dac526c0b44846178797978a965d4bb01c997c3262348df89",
            True,
        ),
        "CANDOBJ::E56F86F06307372B2F18FA97": (
            "8fa6a5bea5271cf7827728c61d5915a000ac54c84d90e825fcaadf10d3b467ef",
            True,
        ),
    },
    "REQ::c21c10d6e8f13263cf69ffa5": {
        "CANDOBJ::27FD9953E64ED8DF1F3B2428": (
            "a2364d9afdff35d1c050708366560561cf11f9bd4bf77c485589bbe5bf4c4dd7",
            True,
        ),
        "CANDOBJ::9A29D551F01388C5C785FF82": (
            "5a368493e2e560911847346d3c724773af7601f3735040a03feb07f3d8433763",
            True,
        ),
    },
    "REQ::07e898259cfe6b2e12d7f82c": {
        "CANDOBJ::0B13DC6BFDAF674340B451BC": (
            "b813c1005b5854dc1422dcdc1ceef128403320ef0fea5539272761cb6a2b06cd",
            True,
        ),
        "CANDOBJ::884E327B61E2F4DCB0788D95": (
            "5e5a3316586074463b1b35322a22980a1cfcf58c5879e650acbde88e33319b48",
            True,
        ),
    },
    "REQ::39d61ebcc0dad17a756c1cac": {
        "CANDOBJ::D7769F8FD29DE6807D0B57F6": (
            "6f5e8565ef221147685cd6b6bd9d715a75ffb45a053726e3b0bab3f017c7396a",
            True,
        ),
        "CANDOBJ::C250AD7345231BD7C1DF0CBB": (
            "f25a6f642033764f55d601441f0468a3e47a8ece8ab7b3f69042a748fb495293",
            True,
        ),
    },
}

EXPECTED_CLAIM_USE_SEMANTICS_BY_REF = {
    "CANDOBJ::0381BE87C0EE31414BA6EA4E": {
        "review_recommendation": "consider_bounded_context",
        "material_use_class": "historical_same_company_timing_context",
        "report_claim_refs": (
            "WPCLAIM::653D7E95ECA46E262391",
            "WPCLAIM::DFDFF241544B90012DA1",
        ),
        "report_surface_paths": ("trusted_report.sections[0].clauses[3]",),
        "source_owner_ticker": "DELL",
        "source_type": "10-Q",
        "source_period_end": "2025-10-31",
        "period_relationship": "historical_interim_context_not_current_quarter_fact",
        "basis_alignment": "issuer_timing_nonlinearity_context_only",
        "duplicate_of_review_item_ref": None,
    },
    "CANDOBJ::D7A996F5F40E35C760851932": {
        "review_recommendation": "recommend_reject_no_current_material_report_use",
        "material_use_class": "no_current_material_report_use",
        "report_claim_refs": (),
        "report_surface_paths": (),
        "source_owner_ticker": "DELL",
        "source_type": "10-Q",
        "source_period_end": "2025-10-31",
        "period_relationship": "historical_interim_unrelated_to_customer_conversion",
        "basis_alignment": "supplier_purchase_order_timing_not_customer_order_conversion",
        "duplicate_of_review_item_ref": None,
    },
    "CANDOBJ::040A820BE15FD0CEAF83C0AD": {
        "review_recommendation": "recommend_rebind_duplicate_to_canonical_candidate",
        "material_use_class": "duplicate_source_no_separate_report_citation",
        "report_claim_refs": (),
        "report_surface_paths": (),
        "source_owner_ticker": "DELL",
        "source_type": "10-K",
        "source_period_end": "2026-01-30",
        "period_relationship": "as_of_valid_risk_disclosure_duplicate",
        "basis_alignment": "exact_duplicate_source_reserved_for_canonical_counterevidence_item",
        "duplicate_of_review_item_ref": "CANDOBJ::0B13DC6BFDAF674340B451BC",
    },
    "CANDOBJ::E9A0B4076252D3978B8DAB73": {
        "review_recommendation": "consider_bounded_context",
        "material_use_class": "historical_same_company_backlog_context",
        "report_claim_refs": ("WPCLAIM::653D7E95ECA46E262391",),
        "report_surface_paths": ("trusted_report.sections[0].clauses[3]",),
        "source_owner_ticker": "DELL",
        "source_type": "10-K",
        "source_period_end": "2026-01-30",
        "period_relationship": "historical_annual_context_not_current_quarter_order_fact",
        "basis_alignment": "issuer_backlog_history_context_without_conversion_inference",
        "duplicate_of_review_item_ref": None,
    },
    "CANDOBJ::E591113506AF79306D11D8AD": {
        "review_recommendation": "consider_bounded_context",
        "material_use_class": "historical_same_company_mix_context",
        "report_claim_refs": ("WPCLAIM::2339C903BA4B36F0C033",),
        "report_surface_paths": ("trusted_report.sections[2].clauses[0]",),
        "source_owner_ticker": "DELL",
        "source_type": "10-Q",
        "source_period_end": "2025-10-31",
        "period_relationship": "historical_interim_mix_context_not_current_quarter_bridge",
        "basis_alignment": "issuer_mix_explanation_not_ASP_units_PVM_or_product_profit",
        "duplicate_of_review_item_ref": None,
    },
    "CANDOBJ::8EDA130D7FDA0F0B66BA53B5": {
        "review_recommendation": "recommend_reject_no_current_material_report_use",
        "material_use_class": "no_current_material_report_use",
        "report_claim_refs": (),
        "report_surface_paths": (),
        "source_owner_ticker": "DELL",
        "source_type": "10-K",
        "source_period_end": "2026-01-30",
        "period_relationship": "annual_segment_row_not_current_quarter_company_or_product_fact",
        "basis_alignment": "reportable_segment_operating_income_not_company_bridge_or_AI_product_profit",
        "duplicate_of_review_item_ref": None,
    },
    "CANDOBJ::51BFECDF1794E6CE42A7B2CE": {
        "review_recommendation": "recommend_reject_no_current_material_report_use",
        "material_use_class": "no_current_material_report_use",
        "report_claim_refs": (),
        "report_surface_paths": (),
        "source_owner_ticker": "DELL",
        "source_type": "10-K",
        "source_period_end": "2026-01-30",
        "period_relationship": "annual_consolidated_row_not_current_quarter_fact",
        "basis_alignment": "annual_company_results_do_not_support_Q1_FY2027_claims_or_product_attribution",
        "duplicate_of_review_item_ref": None,
    },
    "CANDOBJ::C20F9F784D691747A36DADC3": {
        "review_recommendation": "recommend_reject_no_current_material_report_use",
        "material_use_class": "no_current_material_report_use",
        "report_claim_refs": (),
        "report_surface_paths": (),
        "source_owner_ticker": "DELL",
        "source_type": "10-K",
        "source_period_end": "2026-01-30",
        "period_relationship": "annual_non_GAAP_row_not_current_quarter_GAAP_bridge",
        "basis_alignment": "non_GAAP_annual_gross_margin_not_Q1_FY2027_GAAP_signed_bridge",
        "duplicate_of_review_item_ref": None,
    },
    "CANDOBJ::6E0870ECD8935A2BE7A6110F": {
        "review_recommendation": "consider_definition_boundary",
        "material_use_class": "same_issuer_non_GAAP_definition_boundary",
        "report_claim_refs": ("WPCLAIM::B9FB00649A060D443976",),
        "report_surface_paths": ("trusted_report.sections[3].clauses[0]",),
        "source_owner_ticker": "DELL",
        "source_type": "10-K",
        "source_period_end": "2026-01-30",
        "period_relationship": "as_of_valid_definition_not_numeric_period_fact",
        "basis_alignment": "FCF_non_GAAP_definition_boundary_only",
        "duplicate_of_review_item_ref": None,
    },
    "CANDOBJ::E56F86F06307372B2F18FA97": {
        "review_recommendation": "recommend_reject_no_current_material_report_use",
        "material_use_class": "wrong_cash_flow_row_no_current_material_report_use",
        "report_claim_refs": (),
        "report_surface_paths": (),
        "source_owner_ticker": "DELL",
        "source_type": "10-K",
        "source_period_end": "2026-01-30",
        "period_relationship": "annual_financing_cash_flow_row_not_current_quarter_OCF_or_FCF",
        "basis_alignment": "financing_cash_flow_cannot_support_operating_cash_flow_free_cash_flow_or_product_cash_conversion",
        "duplicate_of_review_item_ref": None,
    },
    "CANDOBJ::27FD9953E64ED8DF1F3B2428": {
        "review_recommendation": "recommend_reject_no_current_material_report_use",
        "material_use_class": "generic_accounting_policy_no_current_material_report_use",
        "report_claim_refs": (),
        "report_surface_paths": (),
        "source_owner_ticker": "DELL",
        "source_type": "10-K",
        "source_period_end": "2026-01-30",
        "period_relationship": "as_of_valid_policy_without_measured_current_period_change",
        "basis_alignment": "generic_ECL_policy_not_credit_deterioration_working_capital_or_AI_attribution",
        "duplicate_of_review_item_ref": None,
    },
    "CANDOBJ::9A29D551F01388C5C785FF82": {
        "review_recommendation": "recommend_reject_no_current_material_report_use",
        "material_use_class": "stale_period_row_no_current_material_report_use",
        "report_claim_refs": (),
        "report_surface_paths": (),
        "source_owner_ticker": "DELL",
        "source_type": "10-Q",
        "source_period_end": "2025-10-31",
        "period_relationship": "nine_month_prior_period_row_not_May_2026_quarter_working_capital",
        "basis_alignment": "single_receivables_cash_flow_row_not_current_quarter_complete_working_capital_bridge",
        "duplicate_of_review_item_ref": None,
    },
    "CANDOBJ::0B13DC6BFDAF674340B451BC": {
        "review_recommendation": "consider_risk_counterevidence",
        "material_use_class": "same_issuer_as_of_valid_risk_counterevidence",
        "report_claim_refs": (
            "WPCLAIM::B1BDD811CE1DF55EE55E",
            "WPCLAIM::E3BFD59CC60F05B1BD7C",
            "WPCLAIM::FC2C8B1EA97D7EF82311",
        ),
        "report_surface_paths": ("trusted_report.sections[4].clauses[0]",),
        "source_owner_ticker": "DELL",
        "source_type": "10-K",
        "source_period_end": "2026-01-30",
        "period_relationship": "as_of_valid_risk_disclosure_not_realized_loss",
        "basis_alignment": "issuer_AI_order_working_capital_cancellation_inventory_risk_counterevidence",
        "duplicate_of_review_item_ref": None,
    },
    "CANDOBJ::884E327B61E2F4DCB0788D95": {
        "review_recommendation": "recommend_reject_no_current_material_report_use",
        "material_use_class": "generic_strategy_risk_no_current_material_report_use",
        "report_claim_refs": (),
        "report_surface_paths": (),
        "source_owner_ticker": "DELL",
        "source_type": "10-K",
        "source_period_end": "2026-01-30",
        "period_relationship": "generic_as_of_risk_without_AI_event_or_threshold",
        "basis_alignment": "generic_inventory_management_language_not_AI_impairment_cancellation_or_realized_loss",
        "duplicate_of_review_item_ref": None,
    },
    "CANDOBJ::D7769F8FD29DE6807D0B57F6": {
        "review_recommendation": "recommend_reject_no_current_material_report_use",
        "material_use_class": "unbridged_cross_company_context_no_current_material_report_use",
        "report_claim_refs": (),
        "report_surface_paths": (),
        "source_owner_ticker": "MSFT",
        "source_type": "10-Q",
        "source_period_end": "2026-03-31",
        "period_relationship": "other_company_current_period_without_Dell_relationship_bridge",
        "basis_alignment": "Microsoft_component_risk_not_NVIDIA_export_control_hyperscaler_or_Dell_fact",
        "duplicate_of_review_item_ref": None,
    },
    "CANDOBJ::C250AD7345231BD7C1DF0CBB": {
        "review_recommendation": "recommend_reject_no_current_material_report_use",
        "material_use_class": "unbridged_cross_company_context_no_current_material_report_use",
        "report_claim_refs": (),
        "report_surface_paths": (),
        "source_owner_ticker": "MU",
        "source_type": "10-Q",
        "source_period_end": "2026-05-28",
        "period_relationship": "other_company_current_period_without_Dell_relationship_bridge",
        "basis_alignment": "Micron_equipment_supplier_dependency_not_Dell_HBM_allocation_delivery_or_NVIDIA_claim",
        "duplicate_of_review_item_ref": None,
    },
}

EXPECTED_BLOCKED_REQUEST_IDS = {
    "REQ::e17c40f93e25438950673210",
    "REQ::081c06389f9dcb8487886b57",
    "REQ::273bf40c53d28f49de438b41",
    "REQ::c21c10d6e8f13263cf69ffa5",
}

EXPECTED_SUCCESSOR_LINEAGE = {
    "program_id": "DELL-RSQ-02A-R2",
    "predecessor_attempt": "DELL-RSQ-02A-R1",
    "predecessor_commit": "581c1d6e89f27981298d8fd9379bf53b40dc488c",
    "predecessor_verdict": "FAIL",
    "predecessor_audit_digest": "061cd35cbf624e8a7f84b379466396e0870f122799627107afc6ae9541d4a3ea",
    "same_stage_root_cause_ids": [
        "RC-S1-066-DELL-02A-nested-population-not-recounted",
        "RC-S1-067-DELL-02A-report-claim-use-semantic-padding",
    ],
    "predecessor_overwrite_forbidden": True,
    "qualified_human_decisions_carried_forward": 0,
}


class DellReportEvidenceAdmissionError(ValueError):
    """Raised when the DELL report-use admission packet loses identity or scope."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DellReportEvidenceAdmissionError(code)


def _mapping(value: Any, code: str) -> dict[str, Any]:
    _require(isinstance(value, Mapping), code)
    return dict(value)


def _sequence(value: Any, code: str) -> list[Any]:
    _require(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes)),
        code,
    )
    return list(value)


def _unique_by(
    rows: Iterable[Mapping[str, Any]], field: str, *, code: str
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        key = str(row.get(field) or "")
        _require(key and key not in indexed, code)
        indexed[key] = row
    return indexed


def _validate_self_digest(payload: Mapping[str, Any], field: str, code: str) -> None:
    body = {key: value for key, value in payload.items() if key != field}
    _require(canonical_digest(body) == payload.get(field), code)


def validate_dell_report_evidence_admission_program(
    program: Mapping[str, Any],
) -> dict[str, Any]:
    parsed = dict(program)
    _require(
        parsed.get("schema_version") == PROGRAM_SCHEMA_VERSION,
        "dell_report_admission_program_schema_invalid",
    )
    _validate_self_digest(
        parsed,
        "program_digest",
        "dell_report_admission_program_digest_invalid",
    )
    expected = _mapping(
        parsed.get("expected_scope"),
        "dell_report_admission_expected_scope_missing",
    )
    _require(
        expected
        == {
            "request_count": 8,
            "candidate_review_item_count": 18,
            "all_human_required_item_count": 16,
            "blocked_request_count": 4,
            "blocked_request_human_item_count": 8,
        },
        "dell_report_admission_expected_scope_invalid",
    )
    _require(
        parsed.get("input_bindings") == EXPECTED_INPUT_BINDINGS,
        "dell_report_admission_input_binding_contract_drift",
    )
    _require(
        parsed.get("successor_lineage") == EXPECTED_SUCCESSOR_LINEAGE,
        "dell_report_admission_successor_lineage_drift",
    )
    blocked = _sequence(
        parsed.get("readiness_blocker_request_ids"),
        "dell_report_admission_blocker_requests_invalid",
    )
    _require(
        {str(item) for item in blocked} == EXPECTED_BLOCKED_REQUEST_IDS
        and len(blocked) == len(EXPECTED_BLOCKED_REQUEST_IDS),
        "dell_report_admission_blocker_request_set_invalid",
    )
    raw_inventory = _mapping(
        parsed.get("expected_review_item_inventory_by_request"),
        "dell_report_admission_expected_review_inventory_missing",
    )
    normalized_inventory: dict[str, dict[str, tuple[str, bool]]] = {}
    for request_id, raw_items in raw_inventory.items():
        items = _mapping(
            raw_items,
            f"dell_report_admission_expected_review_inventory_request_invalid:{request_id}",
        )
        normalized_inventory[str(request_id)] = {}
        for ref, raw_contract in items.items():
            contract = _sequence(
                raw_contract,
                f"dell_report_admission_expected_review_inventory_item_invalid:{ref}",
            )
            _require(
                len(contract) == 2 and isinstance(contract[1], bool),
                f"dell_report_admission_expected_review_inventory_item_invalid:{ref}",
            )
            normalized_inventory[str(request_id)][str(ref)] = (
                str(contract[0]),
                contract[1],
            )
    _require(
        normalized_inventory == EXPECTED_REVIEW_ITEM_INVENTORY_BY_REQUEST,
        "dell_report_admission_expected_review_inventory_drift",
    )
    policies = _sequence(
        parsed.get("item_claim_use_policies"),
        "dell_report_admission_claim_use_policies_invalid",
    )
    policy_by_ref = _unique_by(
        (_mapping(row, "dell_report_admission_claim_use_policy_invalid") for row in policies),
        "review_item_ref",
        code="dell_report_admission_claim_use_policy_duplicate",
    )
    _require(
        len(policy_by_ref) == 16,
        "dell_report_admission_claim_use_policy_count_invalid",
    )
    for ref, policy in policy_by_ref.items():
        expected_semantics = EXPECTED_CLAIM_USE_SEMANTICS_BY_REF.get(ref)
        _require(
            expected_semantics is not None,
            f"dell_report_admission_policy_item_not_frozen:{ref}",
        )
        _require(
            len(str(policy.get("review_item_digest") or "")) == 64,
            f"dell_report_admission_policy_item_digest_invalid:{ref}",
        )
        inventory_contract = next(
            (
                contract
                for items in EXPECTED_REVIEW_ITEM_INVENTORY_BY_REQUEST.values()
                for item_ref, contract in items.items()
                if item_ref == ref
            ),
            None,
        )
        _require(
            inventory_contract is not None
            and inventory_contract[1] is True
            and policy.get("review_item_digest") == inventory_contract[0],
            f"dell_report_admission_policy_item_identity_not_frozen:{ref}",
        )
        claim_refs = tuple(str(item) for item in policy.get("report_claim_refs") or [])
        surface_paths = tuple(
            str(item) for item in policy.get("report_surface_paths") or []
        )
        actual_semantics = {
            "review_recommendation": policy.get("review_recommendation"),
            "material_use_class": policy.get("material_use_class"),
            "report_claim_refs": claim_refs,
            "report_surface_paths": surface_paths,
            "source_owner_ticker": policy.get("source_owner_ticker"),
            "source_type": policy.get("source_type"),
            "source_period_end": policy.get("source_period_end"),
            "period_relationship": policy.get("period_relationship"),
            "basis_alignment": policy.get("basis_alignment"),
            "duplicate_of_review_item_ref": policy.get(
                "duplicate_of_review_item_ref"
            ),
        }
        _require(
            actual_semantics == expected_semantics,
            f"dell_report_admission_policy_semantics_drift:{ref}",
        )
        _require(
            len(claim_refs) == len(set(claim_refs))
            and len(surface_paths) == len(set(surface_paths)),
            f"dell_report_admission_policy_claim_surface_duplicate:{ref}",
        )
        no_direct_use = policy.get("review_recommendation") in {
            "recommend_reject_no_current_material_report_use",
            "recommend_rebind_duplicate_to_canonical_candidate",
        }
        _require(
            (not claim_refs and not surface_paths)
            if no_direct_use
            else (bool(claim_refs) and bool(surface_paths)),
            f"dell_report_admission_policy_claim_surface_cardinality_invalid:{ref}",
        )
        _require(
            bool(str(policy.get("alignment_hypothesis") or "").strip())
            and bool(str(policy.get("forbidden_inference") or "").strip()),
            f"dell_report_admission_policy_quality_fields_missing:{ref}",
        )
    return parsed


def _validate_input_bindings(
    *,
    program: Mapping[str, Any],
    payloads: Mapping[str, Mapping[str, Any]],
    sha256_by_ref: Mapping[str, str],
) -> None:
    bindings = _mapping(
        program.get("input_bindings"),
        "dell_report_admission_input_bindings_missing",
    )
    required = set(EXPECTED_INPUT_BINDINGS)
    _require(
        set(bindings) == required,
        "dell_report_admission_input_binding_set_invalid",
    )
    for name, raw_binding in bindings.items():
        binding = _mapping(
            raw_binding,
            f"dell_report_admission_input_binding_invalid:{name}",
        )
        ref = str(binding.get("ref") or "")
        _require(
            sha256_by_ref.get(ref) == binding.get("sha256"),
            f"dell_report_admission_input_sha256_mismatch:{name}",
        )
        digest_field = binding.get("digest_field")
        if digest_field is None:
            continue
        payload = _mapping(
            payloads.get(name),
            f"dell_report_admission_input_payload_missing:{name}",
        )
        _require(
            payload.get(str(digest_field)) == binding.get("digest"),
            f"dell_report_admission_input_digest_mismatch:{name}",
        )
        _validate_self_digest(
            payload,
            str(digest_field),
            f"dell_report_admission_input_self_digest_invalid:{name}",
        )

    failed_audit = _mapping(
        payloads.get("R1_failed_audit"),
        "dell_report_admission_R1_failed_audit_missing",
    )
    _require(
        failed_audit.get("status")
        == "fail_material_findings_preserved_successor_required"
        and failed_audit.get("severity_counts")
        == {"P0": 1, "P1": 2, "P2": 1, "P3": 0}
        and _mapping(
            failed_audit.get("reviewed_identity"),
            "dell_report_admission_R1_failed_identity_missing",
        ).get("commit")
        == "581c1d6e89f27981298d8fd9379bf53b40dc488c",
        "dell_report_admission_R1_failure_lineage_invalid",
    )


def _collect_report_claim_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == "source_claim_refs":
                if isinstance(item, str):
                    refs.add(item)
                elif isinstance(item, Sequence):
                    refs.update(str(ref) for ref in item if str(ref))
            else:
                refs.update(_collect_report_claim_refs(item))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            refs.update(_collect_report_claim_refs(item))
    return refs


def _collect_report_claim_surfaces(
    value: Any,
    *,
    path: str,
) -> dict[str, set[str]]:
    surfaces: dict[str, set[str]] = {}
    if isinstance(value, Mapping):
        if "source_claim_refs" in value:
            raw_refs = value.get("source_claim_refs")
            refs = (
                {str(raw_refs)}
                if isinstance(raw_refs, str)
                else {
                    str(ref)
                    for ref in _sequence(
                        raw_refs,
                        f"dell_report_admission_R17_surface_claims_invalid:{path}",
                    )
                    if str(ref)
                }
            )
            _require(
                bool(refs),
                f"dell_report_admission_R17_surface_claims_empty:{path}",
            )
            surfaces[path] = refs
        for key, item in value.items():
            surfaces.update(
                _collect_report_claim_surfaces(
                    item,
                    path=f"{path}.{key}",
                )
            )
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            surfaces.update(
                _collect_report_claim_surfaces(
                    item,
                    path=f"{path}[{index}]",
                )
            )
    return surfaces


def _validate_predecessor_review_population(
    *,
    readiness_public: Mapping[str, Any],
    readiness_private: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
]:
    public_request_by_id = _unique_by(
        (
            _mapping(row, "dell_report_admission_public_request_invalid")
            for row in _sequence(
                readiness_public.get("requests"),
                "dell_report_admission_public_requests_invalid",
            )
        ),
        "request_id",
        code="dell_report_admission_public_request_duplicate",
    )
    private_readiness = _mapping(
        readiness_private.get("pack_readiness"),
        "dell_report_admission_private_readiness_missing",
    )
    private_readiness_request_by_id = _unique_by(
        (
            _mapping(
                row,
                "dell_report_admission_private_readiness_request_invalid",
            )
            for row in _sequence(
                private_readiness.get("requests"),
                "dell_report_admission_private_readiness_requests_invalid",
            )
        ),
        "request_id",
        code="dell_report_admission_private_readiness_request_duplicate",
    )
    packet = _mapping(
        readiness_private.get("candidate_review_packet"),
        "dell_report_admission_predecessor_packet_missing",
    )
    packet_request_by_id = _unique_by(
        (
            _mapping(row, "dell_report_admission_private_request_invalid")
            for row in _sequence(
                packet.get("requests"),
                "dell_report_admission_private_requests_invalid",
            )
        ),
        "request_id",
        code="dell_report_admission_private_request_duplicate",
    )
    exact_request_ids = set(EXPECTED_REVIEW_ITEM_INVENTORY_BY_REQUEST)
    _require(
        set(public_request_by_id)
        == set(private_readiness_request_by_id)
        == set(packet_request_by_id)
        == exact_request_ids,
        "dell_report_admission_request_sets_differ",
    )
    _require(
        packet.get("request_count")
        == len(packet_request_by_id)
        == expected["request_count"],
        "dell_report_admission_predecessor_request_count_invalid",
    )

    actual_review_item_count = 0
    actual_human_count = 0
    actual_issue_class_counts: dict[str, int] = {}
    global_refs: set[str] = set()
    global_digests: set[str] = set()
    human_item_by_ref: dict[str, dict[str, Any]] = {}
    inventory_rows: list[dict[str, Any]] = []

    for request_id in sorted(packet_request_by_id):
        public_request = public_request_by_id[request_id]
        private_readiness_request = private_readiness_request_by_id[request_id]
        request = packet_request_by_id[request_id]
        _require(
            all(
                request.get(field)
                == public_request.get(field)
                == private_readiness_request.get(field)
                for field in (
                    "slot_id",
                    "facet_id",
                    "business_question_zh",
                )
            )
            and public_request.get("readiness_state")
            == private_readiness_request.get("readiness_state"),
            f"dell_report_admission_request_identity_mismatch:{request_id}",
        )
        review_items = _sequence(
            request.get("review_items"),
            f"dell_report_admission_review_items_invalid:{request_id}",
        )
        item_by_ref = _unique_by(
            (
                _mapping(item, "dell_report_admission_review_item_invalid")
                for item in review_items
            ),
            "review_item_ref",
            code=f"dell_report_admission_review_item_ref_duplicate:{request_id}",
        )
        _require(
            request.get("review_item_count") == len(item_by_ref),
            f"dell_report_admission_request_item_count_invalid:{request_id}",
        )
        expected_items = EXPECTED_REVIEW_ITEM_INVENTORY_BY_REQUEST[request_id]
        _require(
            set(item_by_ref) == set(expected_items),
            f"dell_report_admission_request_item_set_drift:{request_id}",
        )

        request_human_count = 0
        request_issue_class_counts: dict[str, int] = {}
        for ref, item in item_by_ref.items():
            _require(
                item.get("request_id") == request_id,
                f"dell_report_admission_item_request_mismatch:{ref}",
            )
            _validate_self_digest(
                item,
                "review_item_digest",
                f"dell_report_admission_predecessor_item_digest_invalid:{ref}",
            )
            human_required = item.get("human_review_required")
            _require(
                isinstance(human_required, bool),
                f"dell_report_admission_item_human_flag_invalid:{ref}",
            )
            expected_digest, expected_human = expected_items[ref]
            _require(
                item.get("review_item_digest") == expected_digest
                and human_required is expected_human,
                f"dell_report_admission_item_inventory_contract_drift:{ref}",
            )
            digest = str(item["review_item_digest"])
            _require(
                ref not in global_refs and digest not in global_digests,
                f"dell_report_admission_item_identity_duplicate:{ref}",
            )
            global_refs.add(ref)
            global_digests.add(digest)
            request_human_count += int(human_required)
            if human_required:
                human_item_by_ref[ref] = item
            issue_classes = [
                str(value)
                for value in _sequence(
                    item.get("issue_classes"),
                    f"dell_report_admission_item_issue_classes_invalid:{ref}",
                )
            ]
            _require(
                all(issue_classes)
                and len(issue_classes) == len(set(issue_classes)),
                f"dell_report_admission_item_issue_classes_duplicate:{ref}",
            )
            for issue_class in issue_classes:
                request_issue_class_counts[issue_class] = (
                    request_issue_class_counts.get(issue_class, 0) + 1
                )
                actual_issue_class_counts[issue_class] = (
                    actual_issue_class_counts.get(issue_class, 0) + 1
                )
            inventory_rows.append(
                {
                    "request_id": request_id,
                    "review_item_ref": ref,
                    "review_item_digest": digest,
                    "human_review_required": human_required,
                }
            )
        _require(
            request.get("human_review_required_count") == request_human_count,
            f"dell_report_admission_request_human_count_invalid:{request_id}",
        )
        _require(
            request.get("issue_class_counts") == request_issue_class_counts,
            f"dell_report_admission_request_issue_counts_invalid:{request_id}",
        )
        _validate_self_digest(
            request,
            "request_review_digest",
            f"dell_report_admission_predecessor_request_digest_invalid:{request_id}",
        )
        actual_review_item_count += len(item_by_ref)
        actual_human_count += request_human_count

    _require(
        len(global_refs)
        == len(global_digests)
        == actual_review_item_count
        == expected["candidate_review_item_count"],
        "dell_report_admission_all_review_item_count_invalid",
    )
    _require(
        actual_human_count == expected["all_human_required_item_count"],
        "dell_report_admission_all_human_item_count_invalid",
    )
    _require(
        packet.get("review_item_count") == actual_review_item_count
        and packet.get("human_review_required_count") == actual_human_count
        and packet.get("issue_class_counts") == actual_issue_class_counts,
        "dell_report_admission_predecessor_scope_counts_invalid",
    )
    _validate_self_digest(
        packet,
        "review_packet_digest",
        "dell_report_admission_predecessor_packet_digest_invalid",
    )
    public_summary = _mapping(
        readiness_public.get("candidate_review_packet_summary"),
        "dell_report_admission_public_packet_summary_missing",
    )
    _require(
        all(
            public_summary.get(field) == packet.get(field)
            for field in (
                "schema_version",
                "status",
                "review_item_count",
                "human_review_required_count",
                "issue_class_counts",
                "review_packet_digest",
            )
        )
        and public_summary.get(
            "private_packet_required_for_bounded_excerpt_projection"
        )
        is True,
        "dell_report_admission_public_private_packet_summary_mismatch",
    )
    return (
        public_request_by_id,
        packet_request_by_id,
        human_item_by_ref,
        sorted(
            inventory_rows,
            key=lambda row: (row["request_id"], row["review_item_ref"]),
        ),
    )


def _citation_right(source: Mapping[str, Any]) -> dict[str, Any]:
    license_scope = str(source.get("license_scope") or "")
    _require(
        license_scope.startswith("public"),
        "dell_report_admission_source_license_not_public",
    )
    redistributable = bool(source.get("redistributable"))
    return {
        "license_scope": license_scope,
        "citation_locator_allowed": True,
        "bounded_quote_review_allowed": True,
        "full_text_redistribution_allowed": redistributable,
        "public_artifact_excerpt_allowed": False,
        "required_publication_surface": [
            "publisher_or_owner",
            "title_or_source_type",
            "publication_date",
            "period",
            "section_or_table",
            "locator",
        ],
    }


def _compile_item(
    *,
    item: Mapping[str, Any],
    request: Mapping[str, Any],
    policy: Mapping[str, Any],
    readiness_state: str,
    in_blocker_subset: bool,
) -> dict[str, Any]:
    ref = str(item.get("review_item_ref") or "")
    expected_semantics = EXPECTED_CLAIM_USE_SEMANTICS_BY_REF[ref]
    _validate_self_digest(
        item,
        "review_item_digest",
        f"dell_report_admission_predecessor_item_digest_invalid:{ref}",
    )
    _require(
        item.get("review_item_digest") == policy.get("review_item_digest"),
        f"dell_report_admission_policy_item_digest_mismatch:{ref}",
    )
    _require(
        item.get("human_review_required") is True
        and item.get("decision_state") == "needs_human_review",
        f"dell_report_admission_item_not_human_pending:{ref}",
    )
    _require(
        item.get("candidate_is_not_evidence") is True
        and item.get("candidate_text_promoted") is False
        and item.get("new_evidence_created") is False,
        f"dell_report_admission_candidate_authority_invalid:{ref}",
    )
    role = _mapping(
        item.get("advisory_evidence_role"),
        f"dell_report_admission_advisory_role_missing:{ref}",
    )
    _require(
        role.get("advisory_only") is True,
        f"dell_report_admission_model_role_not_advisory:{ref}",
    )
    source = _mapping(
        item.get("source"),
        f"dell_report_admission_source_missing:{ref}",
    )
    _require(
        item.get("evidence_owner_ticker")
        == expected_semantics["source_owner_ticker"]
        and item.get("subject_ticker") == "DELL"
        and source.get("source_type") == expected_semantics["source_type"]
        and source.get("period_end") == expected_semantics["source_period_end"],
        f"dell_report_admission_source_semantic_identity_drift:{ref}",
    )
    excerpt = " ".join(str(source.get("bounded_excerpt") or "").split())
    _require(
        bool(excerpt) and len(excerpt) <= 1200,
        f"dell_report_admission_excerpt_invalid:{ref}",
    )
    _require(
        str(source.get("source_url") or "").startswith(("https://", "http://")),
        f"dell_report_admission_source_url_invalid:{ref}",
    )
    requirement_alignment = {
        "request_id": request["request_id"],
        "slot_id": request["slot_id"],
        "facet_id": request["facet_id"],
        "business_question_zh": request["business_question_zh"],
        "predecessor_requirement_contexts": list(
            item.get("requirement_contexts") or []
        ),
        "alignment_state": "qualified_human_validation_pending",
        "alignment_hypothesis": policy["alignment_hypothesis"],
        "forbidden_inference": policy["forbidden_inference"],
    }
    report_claim_use = {
        "review_recommendation": policy["review_recommendation"],
        "recommendation_is_not_qualified_human_decision": True,
        "material_use_class": policy["material_use_class"],
        "report_claim_refs": sorted(str(ref) for ref in policy["report_claim_refs"]),
        "report_surface_paths": list(policy["report_surface_paths"]),
        "period_relationship": policy["period_relationship"],
        "basis_alignment": policy["basis_alignment"],
        "duplicate_of_review_item_ref": policy[
            "duplicate_of_review_item_ref"
        ],
        "material_report_use_required_for_acceptance_or_rebind": True,
        "empty_claim_set_means_no_current_report_citation": not bool(
            policy["report_claim_refs"]
        ),
        "citation_padding_forbidden": True,
        "qualified_human_may_reject_or_rebind": True,
        "decision_authority": "qualified_human_only",
    }
    source_identity = {
        "source_record_id": item["source_record_id"],
        "compiled_object_id": item["compiled_object_id"],
        "source_lineage_digest": item["source_lineage_digest"],
        "surface_digest": source["surface_digest"],
        "source_owner_ticker": item["evidence_owner_ticker"],
        "research_subject_ticker": item["subject_ticker"],
        "company": source.get("company"),
        "source_type": source.get("source_type"),
        "source_tier": source.get("source_tier"),
        "publication_date": source.get("publication_date"),
        "reporting_period_end": source.get("period_end"),
        "section": source.get("section"),
        "subsection": source.get("subsection"),
        "source_url": source.get("source_url"),
    }
    body: dict[str, Any] = {
        "review_item_ref": ref,
        "predecessor_review_item_digest": item["review_item_digest"],
        "request_id": request["request_id"],
        "readiness_state": readiness_state,
        "scope_membership": {
            "all_human_required_decision_set": True,
            "four_request_readiness_blocker_subset": in_blocker_subset,
        },
        "candidate_state": "candidate_not_evidence_qualified_human_pending",
        "source_identity": source_identity,
        "bounded_excerpt_private_review_only": excerpt,
        "citation_and_redistribution_rights": _citation_right(source),
        "retrieval_route": {
            "route_membership": sorted(str(route) for route in item.get("route_membership") or []),
            "rank_trace_advisory_only": dict(item.get("rank_trace") or {}),
            "rank_or_embedding_score_is_admission_reason": False,
        },
        "advisory_evidence_role": role,
        "requirement_alignment": requirement_alignment,
        "report_claim_use": report_claim_use,
        "numeric_authority": False,
        "evidence_promotion_authorized": False,
        "decision_prefilled": False,
    }
    return {**body, "packet_item_digest": canonical_digest(body)}


def compile_dell_report_evidence_admission_packet(
    *,
    program: Mapping[str, Any],
    input_payloads: Mapping[str, Mapping[str, Any]],
    input_sha256_by_ref: Mapping[str, str],
    private_output_ref: str,
    recorded_at: str,
    prepared_from_commit: str,
) -> dict[str, dict[str, Any]]:
    """Freeze DELL's sixteen human decisions without issuing any decision."""

    parsed_program = validate_dell_report_evidence_admission_program(program)
    _validate_input_bindings(
        program=parsed_program,
        payloads=input_payloads,
        sha256_by_ref=input_sha256_by_ref,
    )
    audit = _mapping(
        input_payloads.get("G1_independent_audit"),
        "dell_report_admission_G1_audit_missing",
    )
    _require(
        bool(_mapping(audit.get("verdicts"), "dell_report_admission_G1_verdicts_missing").get("G1_crosswalk_pass"))
        and bool(_mapping(audit.get("authority"), "dell_report_admission_G1_authority_missing").get("independent_crosswalk_G1_pass")),
        "dell_report_admission_G1_not_passed",
    )
    readiness_public = _mapping(
        input_payloads.get("current_readiness_public"),
        "dell_report_admission_readiness_public_missing",
    )
    readiness_private = _mapping(
        input_payloads.get("current_readiness_private"),
        "dell_report_admission_readiness_private_missing",
    )
    expected = parsed_program["expected_scope"]
    (
        public_request_by_id,
        private_request_by_id,
        human_item_by_ref,
        predecessor_inventory,
    ) = _validate_predecessor_review_population(
        readiness_public=readiness_public,
        readiness_private=readiness_private,
        expected=expected,
    )
    predecessor_inventory_digest = canonical_digest(
        {
            "request_count": len(private_request_by_id),
            "review_item_count": len(predecessor_inventory),
            "human_review_required_count": len(human_item_by_ref),
            "items": predecessor_inventory,
        }
    )
    _require(
        len(predecessor_inventory) == expected["candidate_review_item_count"]
        and len(human_item_by_ref)
        == expected["all_human_required_item_count"],
        "dell_report_admission_predecessor_inventory_count_invalid",
    )
    blocked_ids = set(
        str(item) for item in parsed_program["readiness_blocker_request_ids"]
    )
    actual_blocked = {
        request_id
        for request_id, request in public_request_by_id.items()
        if request.get("readiness_state") == "blocked_by_evidence_admission"
    }
    _require(
        actual_blocked == blocked_ids == EXPECTED_BLOCKED_REQUEST_IDS,
        "dell_report_admission_blocker_request_set_mismatch",
    )
    policy_by_ref = _unique_by(
        parsed_program["item_claim_use_policies"],
        "review_item_ref",
        code="dell_report_admission_claim_use_policy_duplicate",
    )
    r17 = _mapping(
        input_payloads.get("R17_private_report"),
        "dell_report_admission_R17_missing",
    )
    trusted_report = _mapping(
        r17.get("trusted_report"),
        "dell_report_admission_R17_trusted_report_missing",
    )
    report_claim_surfaces = _collect_report_claim_surfaces(
        trusted_report,
        path="trusted_report",
    )
    report_claim_refs = {
        claim_ref
        for claim_refs in report_claim_surfaces.values()
        for claim_ref in claim_refs
    }
    _require(report_claim_refs, "dell_report_admission_R17_claim_refs_missing")
    for ref, policy in policy_by_ref.items():
        policy_claims = set(str(value) for value in policy["report_claim_refs"])
        surface_paths = [str(value) for value in policy["report_surface_paths"]]
        _require(
            all(path in report_claim_surfaces for path in surface_paths),
            f"dell_report_admission_unknown_R17_surface_path:{ref}",
        )
        surface_claims = {
            claim_ref
            for path in surface_paths
            for claim_ref in report_claim_surfaces[path]
        }
        _require(
            policy_claims.issubset(report_claim_refs)
            and policy_claims.issubset(surface_claims),
            f"dell_report_admission_unknown_or_misplaced_R17_claim_ref:{ref}",
        )

    for ref, policy in policy_by_ref.items():
        duplicate_ref = policy.get("duplicate_of_review_item_ref")
        if duplicate_ref is None:
            continue
        item = human_item_by_ref[ref]
        canonical_item = human_item_by_ref[str(duplicate_ref)]
        item_source = _mapping(
            item.get("source"),
            f"dell_report_admission_source_missing:{ref}",
        )
        canonical_source = _mapping(
            canonical_item.get("source"),
            f"dell_report_admission_source_missing:{duplicate_ref}",
        )
        _require(
            all(
                item.get(field) == canonical_item.get(field)
                for field in (
                    "source_record_id",
                    "compiled_object_id",
                    "source_lineage_digest",
                )
            )
            and item_source.get("surface_digest")
            == canonical_source.get("surface_digest"),
            f"dell_report_admission_duplicate_source_identity_mismatch:{ref}",
        )

    requests: list[dict[str, Any]] = []
    all_refs: set[str] = set()
    all_digests: set[str] = set()
    blocker_item_count = 0
    for request_id in sorted(private_request_by_id):
        request = private_request_by_id[request_id]
        readiness_state = str(public_request_by_id[request_id].get("readiness_state") or "")
        in_blocker_subset = request_id in blocked_ids
        human_items = [
            human_item_by_ref[ref]
            for ref, (_, human_required) in sorted(
                EXPECTED_REVIEW_ITEM_INVENTORY_BY_REQUEST[request_id].items()
            )
            if human_required
        ]
        compiled_items: list[dict[str, Any]] = []
        for item in human_items:
            ref = str(item.get("review_item_ref") or "")
            _require(
                ref not in all_refs and item.get("review_item_digest") not in all_digests,
                f"dell_report_admission_item_identity_duplicate:{ref}",
            )
            _require(
                ref in policy_by_ref,
                f"dell_report_admission_claim_use_policy_missing:{ref}",
            )
            compiled_items.append(
                _compile_item(
                    item=item,
                    request=request,
                    policy=policy_by_ref[ref],
                    readiness_state=readiness_state,
                    in_blocker_subset=in_blocker_subset,
                )
            )
            all_refs.add(ref)
            all_digests.add(str(item["review_item_digest"]))
        if in_blocker_subset:
            blocker_item_count += len(compiled_items)
        request_body: dict[str, Any] = {
            "request_id": request_id,
            "readiness_state": readiness_state,
            "business_question_zh": request["business_question_zh"],
            "slot_id": request["slot_id"],
            "facet_id": request["facet_id"],
            "all_human_required_decision_set": True,
            "four_request_readiness_blocker_subset": in_blocker_subset,
            "predecessor_review_item_count": request["review_item_count"],
            "predecessor_non_human_item_count": (
                request["review_item_count"] - len(compiled_items)
            ),
            "human_item_count": len(compiled_items),
            "items": sorted(compiled_items, key=lambda row: row["review_item_ref"]),
        }
        requests.append(
            {**request_body, "request_packet_digest": canonical_digest(request_body)}
        )
    _require(
        len(all_refs) == expected["all_human_required_item_count"],
        "dell_report_admission_all_human_item_count_invalid",
    )
    _require(
        set(policy_by_ref) == all_refs,
        "dell_report_admission_policy_item_set_mismatch",
    )
    _require(
        blocker_item_count == expected["blocked_request_human_item_count"],
        "dell_report_admission_blocker_item_count_invalid",
    )
    recommendation_counts = {
        "bounded_or_direct_material_use_candidate_count": sum(
            bool(policy["report_claim_refs"]) for policy in policy_by_ref.values()
        ),
        "recommend_reject_no_current_material_report_use_count": sum(
            policy["review_recommendation"]
            == "recommend_reject_no_current_material_report_use"
            for policy in policy_by_ref.values()
        ),
        "recommend_rebind_duplicate_to_canonical_candidate_count": sum(
            policy["review_recommendation"]
            == "recommend_rebind_duplicate_to_canonical_candidate"
            for policy in policy_by_ref.values()
        ),
    }
    _require(
        recommendation_counts
        == {
            "bounded_or_direct_material_use_candidate_count": 5,
            "recommend_reject_no_current_material_report_use_count": 10,
            "recommend_rebind_duplicate_to_canonical_candidate_count": 1,
        },
        "dell_report_admission_recommendation_partition_invalid",
    )

    decision_schema = {
        "decision_authority": "qualified_human_only",
        "author_recommendations_are_not_decisions": True,
        "allowed_decisions": [
            "accept_existing",
            "rebind",
            "accept_new",
            "reject",
            "defer",
        ],
        "required_fields": [
            "review_item_ref",
            "predecessor_review_item_digest",
            "decision",
            "reason",
            "evidence_role",
            "report_claim_use",
            "period",
            "polarity",
            "authority",
            "license_and_citation_right",
            "reviewer_identity",
            "reviewed_at",
        ],
        "accept_new_requires_exact_source_passage_and_evidence_gate": True,
        "defer_remains_blocking": True,
        "model_or_harness_generated_decision_forbidden": True,
    }
    scope_reconciliation = {
        "frozen_program_wording": "four_requests_sixteen_human_items",
        "actual_predecessor_scope": {
            "all_human_required_decision_set": {
                "request_count": 8,
                "candidate_review_item_count": 18,
                "human_item_count": 16,
                "required_for_G2": True,
            },
            "four_request_readiness_blocker_subset": {
                "request_count": 4,
                "human_item_count": 8,
                "request_ids": sorted(blocked_ids),
                "changes_four_blocked_readiness_states": True,
            },
        },
        "false_interpretation_rejected": "four_requests_each_with_four_human_items",
        "immutable_execution_program_rewritten": False,
    }
    packet_content: dict[str, Any] = {
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "successor_lineage": {
            "predecessor_attempt": "DELL-RSQ-02A-R1",
            "predecessor_verdict": "FAIL",
            "predecessor_audit_ref": EXPECTED_INPUT_BINDINGS["R1_failed_audit"][
                "ref"
            ],
            "predecessor_audit_digest": EXPECTED_INPUT_BINDINGS[
                "R1_failed_audit"
            ]["digest"],
            "successor_attempt": "DELL-RSQ-02A-R2",
            "same_stage_root_cause_ids": [
                "RC-S1-066-DELL-02A-nested-population-not-recounted",
                "RC-S1-067-DELL-02A-report-claim-use-semantic-padding",
            ],
            "predecessor_overwritten": False,
        },
        "scope_reconciliation": scope_reconciliation,
        "predecessor_review_inventory": {
            "request_count": len(private_request_by_id),
            "review_item_count": len(predecessor_inventory),
            "human_review_required_count": len(human_item_by_ref),
            "inventory_digest": predecessor_inventory_digest,
            "items": predecessor_inventory,
        },
        "claim_use_recommendation_counts": recommendation_counts,
        "qualified_human_decision_schema": decision_schema,
        "requests": requests,
    }
    admission_packet_digest = canonical_digest(packet_content)
    full_body: dict[str, Any] = {
        "schema_version": PRIVATE_PACKET_SCHEMA_VERSION,
        "status": "packet_frozen_qualified_human_decisions_pending",
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "program_digest": parsed_program["program_digest"],
        "input_bindings": parsed_program["input_bindings"],
        **packet_content,
        "admission_packet_digest": admission_packet_digest,
        "counts": {
            "request_count": len(requests),
            "candidate_review_item_count": len(predecessor_inventory),
            "all_human_required_item_count": len(all_refs),
            "blocked_request_count": len(blocked_ids),
            "blocked_request_human_item_count": blocker_item_count,
            **recommendation_counts,
            "qualified_human_decision_count": 0,
        },
        "execution": {
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "embedding_calls": 0,
            "reranker_calls": 0,
            "candidate_promotions": 0,
            "evidence_promotions": 0,
        },
        "authority": {
            "qualified_human_decisions_complete": False,
            "G2_pass": False,
            "S1_pass": False,
            "S2_pass": False,
            "S3_pass": False,
            "report_quality_pass": False,
            "product_acceptance": False,
            "publication": False,
            "release_ready": False,
        },
        "known_boundary": (
            "This successor freezes review recommendations only. Five candidates "
            "have a bounded possible R17 use, ten are recommended for rejection "
            "because no current material report use is demonstrated, and one is "
            "recommended for duplicate rebind. None is a decision. Every one of "
            "the sixteen human-required items still needs an authorized "
            "qualified-human decision; the eight-item blocker subset does not "
            "replace the full G2 decision set."
        ),
    }
    full = {**full_body, "full_result_digest": canonical_digest(full_body)}
    public_items: list[dict[str, Any]] = []
    for request in requests:
        for item in request["items"]:
            public_items.append(
                {
                    "review_item_ref": item["review_item_ref"],
                    "predecessor_review_item_digest": item[
                        "predecessor_review_item_digest"
                    ],
                    "request_id": item["request_id"],
                    "four_request_readiness_blocker_subset": item[
                        "scope_membership"
                    ]["four_request_readiness_blocker_subset"],
                    "source_identity_digest": canonical_digest(
                        item["source_identity"]
                    ),
                    "report_claim_use": item["report_claim_use"],
                    "packet_item_digest": item["packet_item_digest"],
                    "decision_state": "qualified_human_pending",
                }
            )
    public_body: dict[str, Any] = {
        "schema_version": PUBLIC_MANIFEST_SCHEMA_VERSION,
        "status": "packet_frozen_qualified_human_decisions_pending",
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "program_digest": parsed_program["program_digest"],
        "successor_lineage": packet_content["successor_lineage"],
        "scope_reconciliation": scope_reconciliation,
        "predecessor_review_inventory_summary": {
            "request_count": len(private_request_by_id),
            "review_item_count": len(predecessor_inventory),
            "human_review_required_count": len(human_item_by_ref),
            "inventory_digest": predecessor_inventory_digest,
        },
        "claim_use_recommendation_counts": recommendation_counts,
        "counts": full["counts"],
        "items": sorted(public_items, key=lambda row: row["review_item_ref"]),
        "admission_packet_digest": admission_packet_digest,
        "private_full_result_ref": private_output_ref,
        "execution": full["execution"],
        "authority": full["authority"],
        "known_boundary": full["known_boundary"],
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    serialized_public = str(public).casefold()
    _require(
        "bounded_excerpt_private_review_only" not in serialized_public
        and "source_url" not in serialized_public,
        "dell_report_admission_public_projection_leaks_private_source",
    )
    return {"private": full, "public": public}


__all__ = [
    "DellReportEvidenceAdmissionError",
    "EXPECTED_BLOCKED_REQUEST_IDS",
    "EXPECTED_CLAIM_USE_SEMANTICS_BY_REF",
    "EXPECTED_REVIEW_ITEM_INVENTORY_BY_REQUEST",
    "PRIVATE_PACKET_SCHEMA_VERSION",
    "PROGRAM_SCHEMA_VERSION",
    "PUBLIC_MANIFEST_SCHEMA_VERSION",
    "compile_dell_report_evidence_admission_packet",
    "validate_dell_report_evidence_admission_program",
]
