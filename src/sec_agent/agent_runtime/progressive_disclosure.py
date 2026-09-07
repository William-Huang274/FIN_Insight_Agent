"""Fail-closed progressive disclosure for the Dell agentic vertical.

This module is deliberately a small domain policy layer.  It does not read a
file, call MCP, invoke a model, or confer financial-research authority.  It
only decides whether an already catalogued, content-addressed resource may be
made visible on the *next* model turn and emits an immutable receipt.

The provider-facing request is intentionally separate from
``DisclosureRuntimeContext``.  Case/session identity, role, task authority and
budget are sealed runtime inputs and therefore cannot be overridden through a
tool call.  Operator diagnostics use a different, non-provider API and never
enter this module's model-visible manifest.
"""

from __future__ import annotations

from typing import Any, Literal, Mapping, Protocol, Sequence

from pydantic import Field, model_validator

from sec_agent.canonical_runtime.contracts_v1_2 import (
    CanonicalEventLedgerSnapshot,
    CanonicalSessionEventV1_2,
    StrictFrozenModel,
    canonical_json_sha256,
    validate_session_event_sequence,
)

from .dell_agentic_contracts import (
    AvailableNextAction,
    ModelVisibleContextManifest,
    RuntimePolicySnapshot,
    RuntimeScope,
    RuntimeScopeAuthorizationRecord,
    research_objective_digest,
    validate_runtime_scope_authorization,
)


DISCLOSURE_CONTRACT_VERSION = "1.2"

Digest = str
DisclosureKind = Literal[
    "capability",
    "data",
    "skill",
    "evidence",
    "fact",
    "artifact",
    "diagnostic",
]
ProviderDisclosureKind = Literal[
    "capability",
    "data",
    "skill",
    "evidence",
    "fact",
    "artifact",
]
DisclosureDepth = Literal[
    "contract",              # L1
    "resource_index",        # L2
    "content",               # L3
    "restricted_diagnostic", # L4
]
ProviderDisclosureDepth = Literal["contract", "resource_index", "content"]
DisclosureLevel = Literal["L0", "L1", "L2", "L3", "L4"]
DisclosureStatus = Literal["granted", "denied"]

_HEX_DIGEST_PATTERN = r"^[0-9a-f]{64}$"
_REF_PATTERN = r"^[a-z][a-z0-9_-]{1,31}:[A-Za-z0-9][A-Za-z0-9._:/-]{0,238}$"
_DEPTH_TO_LEVEL: dict[str, str] = {
    "contract": "L1",
    "resource_index": "L2",
    "content": "L3",
    "restricted_diagnostic": "L4",
}
_LEVEL_NUMBER = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4}
_HOST_RUNTIME_EVENT_ACTOR_ID = "runtime"
_DISCLOSURE_REQUEST_REF_PREFIX = "disclosure-request://sha256/"
_DISCLOSURE_RECEIPT_REF_PREFIX = "disclosure-receipt://sha256/"
_DISCLOSURE_RESOURCE_REF_PREFIX = "disclosure-resource://sha256/"
_DISCLOSURE_RESOURCE_BINDING_REF_PREFIX = (
    "disclosure-resource-binding://sha256/"
)


class _FrozenContract(StrictFrozenModel):
    """Disclosure contracts use the canonical runtime's one strict base."""


def canonical_digest(value: Any) -> str:
    """Return the repository's canonical lowercase, bare SHA-256 digest."""
    return canonical_json_sha256(value)


class CapabilityDescriptor(_FrozenContract):
    """Answer-free L0 description; it describes but never grants authority."""

    contract_version: Literal["1.2"] = DISCLOSURE_CONTRACT_VERSION
    capability_ref: str = Field(pattern=_REF_PATTERN)
    kind: DisclosureKind
    name: str = Field(min_length=1, max_length=120)
    purpose: str = Field(min_length=1, max_length=600)
    authority_summary: str = Field(min_length=1, max_length=320)
    cost_tier: Literal["none", "low", "medium", "high", "unknown"]
    latency_tier: Literal["local", "short", "medium", "long", "unknown"]
    maximum_disclosure_level: DisclosureLevel
    action_names: tuple[str, ...] = Field(default=(), max_length=32)
    answer_free: Literal[True] = True
    grants_tool_authority: Literal[False] = False
    grants_evidence_authority: Literal[False] = False
    grants_policy_authority: Literal[False] = False


class DisclosureResource(_FrozenContract):
    """Content-addressed metadata for one ref at one disclosure level."""

    contract_version: Literal["1.2"] = DISCLOSURE_CONTRACT_VERSION
    ref: str = Field(pattern=_REF_PATTERN)
    kind: DisclosureKind
    level: Literal["L1", "L2", "L3", "L4"]
    resource_uri: str = Field(min_length=1, max_length=1000)
    resource_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)
    estimated_context_tokens: int = Field(ge=1, le=10_000_000)
    parent_ref: str | None = Field(default=None, pattern=_REF_PATTERN)
    operator_only: bool = False
    answer_free: bool
    grants_tool_authority: Literal[False] = False
    grants_evidence_authority: Literal[False] = False
    grants_policy_authority: Literal[False] = False

    @model_validator(mode="after")
    def validate_level_and_kind(self) -> "DisclosureResource":
        if self.level == "L4" and not self.operator_only:
            raise ValueError("l4_resource_must_be_operator_only")
        if self.level != "L4" and self.operator_only:
            raise ValueError("operator_only_resource_must_be_l4")
        if self.kind == "diagnostic" and self.level != "L4":
            raise ValueError("diagnostic_resource_must_be_l4")
        if self.kind == "skill" and not self.answer_free:
            raise ValueError("skill_resource_must_be_answer_free")
        if self.level == "L1" and not self.answer_free:
            raise ValueError("l1_resource_must_be_answer_free")
        return self


class DisclosureCatalogSnapshot(_FrozenContract):
    """Immutable L0 catalog plus deeper resource metadata."""

    contract_version: Literal["1.2"] = DISCLOSURE_CONTRACT_VERSION
    snapshot_id: str = Field(min_length=1, max_length=240)
    inventory_snapshot_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)
    capabilities: tuple[CapabilityDescriptor, ...] = Field(min_length=1)
    resources: tuple[DisclosureResource, ...] = Field(default=())
    catalog_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_catalog(self) -> "DisclosureCatalogSnapshot":
        capability_refs = [item.capability_ref for item in self.capabilities]
        if len(capability_refs) != len(set(capability_refs)):
            raise ValueError("duplicate_capability_ref")

        resource_keys = [(item.ref, item.level) for item in self.resources]
        if len(resource_keys) != len(set(resource_keys)):
            raise ValueError("duplicate_disclosure_resource")

        capability_map = {item.capability_ref: item for item in self.capabilities}
        known_refs = set(capability_refs).union(item.ref for item in self.resources)
        for resource in self.resources:
            if resource.parent_ref is not None and resource.parent_ref not in known_refs:
                raise ValueError("disclosure_parent_ref_unknown")
            chain: list[str] = [resource.ref]
            cursor = resource
            seen = {cursor.ref}
            while cursor.parent_ref is not None:
                if cursor.parent_ref in seen:
                    raise ValueError("disclosure_reference_chain_cycle")
                seen.add(cursor.parent_ref)
                chain.append(cursor.parent_ref)
                parents = [item for item in self.resources if item.ref == cursor.parent_ref]
                if not parents:
                    break
                parent_refs = {item.parent_ref for item in parents}
                if len(parent_refs) != 1:
                    raise ValueError("disclosure_reference_chain_ambiguous")
                cursor = parents[0]
            anchors = [capability_map[ref] for ref in chain if ref in capability_map]
            if len({item.capability_ref for item in anchors}) != 1:
                raise ValueError("disclosure_resource_capability_anchor_invalid")
            capability = anchors[0]
            if resource.ref == capability.capability_ref and resource.kind != capability.kind:
                raise ValueError("disclosure_same_ref_kind_changed")
            if resource.kind == "skill" and capability.kind != "skill":
                raise ValueError("skill_resource_capability_kind_mismatch")
            if _LEVEL_NUMBER[resource.level] > _LEVEL_NUMBER[capability.maximum_disclosure_level]:
                raise ValueError("disclosure_resource_exceeds_capability_maximum")
            if resource.level == "L1" and resource.parent_ref is not None:
                raise ValueError("l1_resource_parent_forbidden")
            if resource.level != "L1":
                previous_level = f"L{_LEVEL_NUMBER[resource.level] - 1}"
                previous_refs = {resource.ref}
                if resource.parent_ref is not None:
                    previous_refs.add(resource.parent_ref)
                previous = [
                    item
                    for item in self.resources
                    if item.level == previous_level and item.ref in previous_refs
                ]
                if not previous or any(item.kind != resource.kind for item in previous):
                    raise ValueError("disclosure_resource_preceding_level_missing")

        unsigned = self.model_dump(mode="json", exclude={"catalog_digest"})
        if canonical_digest(unsigned) != self.catalog_digest:
            raise ValueError("disclosure_catalog_digest_mismatch")
        return self


class DisclosureAuthorityRule(_FrozenContract):
    """Server-side policy; catalog/Skill prose cannot replace this rule."""

    ref: str = Field(pattern=_REF_PATTERN)
    allowed_roles: tuple[str, ...] = Field(min_length=1)
    allowed_task_kinds: tuple[str, ...] = Field(min_length=1)
    maximum_level: Literal["L1", "L2", "L3", "L4"]
    allow_recursive_children: bool = False


class DisclosurePolicySnapshot(_FrozenContract):
    contract_version: Literal["1.2"] = DISCLOSURE_CONTRACT_VERSION
    policy_snapshot_id: str = Field(min_length=1, max_length=240)
    rules: tuple[DisclosureAuthorityRule, ...] = Field(min_length=1)
    maximum_tokens_per_receipt: int = Field(ge=1, le=10_000_000)
    maximum_tokens_per_task: int = Field(ge=1, le=100_000_000)
    maximum_recursive_depth: int = Field(ge=0, le=32)
    policy_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_policy(self) -> "DisclosurePolicySnapshot":
        refs = [rule.ref for rule in self.rules]
        if len(refs) != len(set(refs)):
            raise ValueError("duplicate_disclosure_authority_rule")
        if self.maximum_tokens_per_receipt > self.maximum_tokens_per_task:
            raise ValueError("per_receipt_budget_exceeds_task_budget")
        unsigned = self.model_dump(mode="json", exclude={"policy_digest"})
        if canonical_digest(unsigned) != self.policy_digest:
            raise ValueError("disclosure_policy_digest_mismatch")
        return self


class DisclosureRequest(_FrozenContract):
    """The complete provider-visible ``request_disclosure`` input."""

    contract_version: Literal["1.2"] = DISCLOSURE_CONTRACT_VERSION
    catalog_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)
    inventory_snapshot_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)
    policy_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)
    kind: ProviderDisclosureKind
    ref: str = Field(pattern=_REF_PATTERN)
    depth: ProviderDisclosureDepth
    reason: str = Field(min_length=1, max_length=1000)
    expected_use: str = Field(min_length=1, max_length=1000)
    parent_receipt_digest: Digest | None = Field(
        default=None,
        pattern=_HEX_DIGEST_PATTERN,
    )


class DisclosureGrantLedgerView(_FrozenContract):
    """Host-derived receipt membership projected from the canonical event ledger.

    This is not a provider object and does not create a grant.  It lets the
    policy layer reject a structurally valid, self-resigned receipt that was
    never durably recorded for this exact ActionAttempt.
    """

    contract_version: Literal["1.2"] = DISCLOSURE_CONTRACT_VERSION
    ledger_view_id: str = Field(pattern=_REF_PATTERN)
    runtime_scope_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)
    session_id: str = Field(pattern=_REF_PATTERN)
    research_run_id: str = Field(pattern=_REF_PATTERN)
    run_invocation_id: str = Field(pattern=_REF_PATTERN)
    action_attempt_id: str = Field(pattern=_REF_PATTERN)
    canonical_event_ledger_snapshot_digest: Digest = Field(
        pattern=_HEX_DIGEST_PATTERN
    )
    runtime_scope_authorization_record_digest: Digest = Field(
        pattern=_HEX_DIGEST_PATTERN
    )
    canonical_event_ledger_tip_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)
    canonical_event_ledger_store_revision: int = Field(ge=1)
    source_scope_authority_event_digest: Digest = Field(
        pattern=_HEX_DIGEST_PATTERN
    )
    source_request_event_digests: tuple[Digest, ...] = Field(default=())
    source_grant_event_digests: tuple[Digest, ...] = Field(default=())
    verified_receipt_digests: tuple[Digest, ...] = Field(default=())
    ledger_view_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_ledger_view(self) -> "DisclosureGrantLedgerView":
        if len(self.verified_receipt_digests) != len(set(self.verified_receipt_digests)):
            raise ValueError("disclosure_ledger_receipt_digest_duplicate")
        if len(self.source_grant_event_digests) != len(
            set(self.source_grant_event_digests)
        ):
            raise ValueError("disclosure_ledger_event_digest_duplicate")
        if len(self.source_request_event_digests) != len(
            set(self.source_request_event_digests)
        ):
            raise ValueError("disclosure_ledger_request_event_digest_duplicate")
        if not (
            len(self.source_request_event_digests)
            == len(self.source_grant_event_digests)
            == len(self.verified_receipt_digests)
        ):
            raise ValueError("disclosure_ledger_provenance_cardinality_mismatch")
        unsigned = self.model_dump(mode="json", exclude={"ledger_view_digest"})
        if canonical_digest(unsigned) != self.ledger_view_digest:
            raise ValueError("disclosure_grant_ledger_view_digest_mismatch")
        return self


class DisclosureRuntimeContext(_FrozenContract):
    """Sealed host context.  This object must never enter a provider payload."""

    runtime_scope: RuntimeScope
    scope_authorization_record: RuntimeScopeAuthorizationRecord
    role: str = Field(min_length=1, max_length=120)
    task_kind: str = Field(min_length=1, max_length=120)
    consumed_disclosure_tokens: int = Field(ge=0, le=100_000_000)
    grants: tuple["DisclosureReceipt", ...] = Field(default=())
    grant_ledger_view: DisclosureGrantLedgerView
    sealed: Literal[True] = True

    @model_validator(mode="after")
    def validate_receipt_bindings(self) -> "DisclosureRuntimeContext":
        scope = self.runtime_scope
        validate_runtime_scope_authorization(
            runtime_scope=scope,
            authorization_record=self.scope_authorization_record,
        )
        ledger = self.grant_ledger_view
        if self.role != scope.agent_role or self.task_kind != scope.task_kind:
            raise ValueError("runtime_context_role_or_task_not_scope_bound")
        ledger_binding = (
            (ledger.runtime_scope_digest, scope.scope_digest),
            (ledger.session_id, scope.session_id),
            (ledger.research_run_id, scope.research_run_id),
            (ledger.run_invocation_id, scope.run_invocation_id),
            (ledger.action_attempt_id, scope.action_attempt_id),
            (
                ledger.runtime_scope_authorization_record_digest,
                self.scope_authorization_record.authorization_record_digest,
            ),
            (
                ledger.canonical_event_ledger_snapshot_digest,
                self.scope_authorization_record.canonical_event_ledger_snapshot_digest,
            ),
        )
        if any(actual != wanted for actual, wanted in ledger_binding):
            raise ValueError("runtime_context_disclosure_ledger_scope_mismatch")
        receipt_digests = tuple(receipt.receipt_digest for receipt in self.grants)
        if len(receipt_digests) != len(set(receipt_digests)):
            raise ValueError("runtime_context_duplicate_disclosure_receipt")
        if set(receipt_digests) != set(ledger.verified_receipt_digests):
            raise ValueError("runtime_context_disclosure_receipt_not_in_ledger")
        for receipt in self.grants:
            if receipt.status != "granted":
                raise ValueError("runtime_context_denied_disclosure_forbidden")
            expected = (
                (receipt.runtime_scope_digest, scope.scope_digest),
                (receipt.session_id, scope.session_id),
                (receipt.research_run_id, scope.research_run_id),
                (receipt.run_invocation_id, scope.run_invocation_id),
                (receipt.action_attempt_id, scope.action_attempt_id),
                (receipt.agent_id, scope.agent_id),
                (receipt.task_id, scope.task_id),
                (receipt.role, self.role),
                (receipt.task_kind, self.task_kind),
                (receipt.inventory_snapshot_digest, scope.data_snapshot_digest),
                (receipt.policy_digest, scope.disclosure_policy_digest),
            )
            if any(actual != wanted for actual, wanted in expected):
                raise ValueError("runtime_context_disclosure_scope_mismatch")
            if receipt.granted_level == "L4" or receipt.kind == "diagnostic":
                raise ValueError("runtime_context_operator_disclosure_forbidden")
        derived_tokens = sum(receipt.estimated_context_tokens for receipt in self.grants)
        if self.consumed_disclosure_tokens != derived_tokens:
            raise ValueError("runtime_context_disclosure_token_total_mismatch")
        return self

    def validate_current_grant_view(
        self,
        *,
        ledger_reader: "CanonicalEventLedgerReader",
        authority_resolver: "RuntimeScopeAuthorityResolver",
    ) -> "DisclosureRuntimeContext":
        """Rebuild this context's grant view from current host-owned state."""

        validated = DisclosureRuntimeContext.model_validate(
            self.model_dump(mode="python")
        )
        _validate_current_disclosure_grant_view(
            context=validated,
            ledger_reader=ledger_reader,
            authority_resolver=authority_resolver,
        )
        return validated


class DisclosureReceipt(_FrozenContract):
    """Immutable decision receipt.  A denial always carries a legal remedy."""

    contract_version: Literal["1.2"] = DISCLOSURE_CONTRACT_VERSION
    status: DisclosureStatus
    request_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)
    catalog_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)
    inventory_snapshot_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)
    policy_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)
    runtime_scope_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)
    session_id: str = Field(pattern=_REF_PATTERN)
    research_run_id: str = Field(pattern=_REF_PATTERN)
    run_invocation_id: str = Field(pattern=_REF_PATTERN)
    action_attempt_id: str = Field(pattern=_REF_PATTERN)
    agent_id: str = Field(pattern=_REF_PATTERN)
    task_id: str = Field(pattern=_REF_PATTERN)
    role: str = Field(min_length=1, max_length=120)
    task_kind: str = Field(min_length=1, max_length=120)
    ref: str = Field(pattern=_REF_PATTERN)
    kind: DisclosureKind
    requested_depth: DisclosureDepth
    granted_level: Literal["L1", "L2", "L3", "L4"] | None = None
    resource_uri: str | None = Field(default=None, max_length=1000)
    resource_digest: Digest | None = Field(
        default=None,
        pattern=_HEX_DIGEST_PATTERN,
    )
    estimated_context_tokens: int = Field(ge=0, le=10_000_000)
    error_code: str | None = Field(default=None, max_length=160)
    decision_reason: str = Field(min_length=1, max_length=1000)
    parent_receipt_digest: Digest | None = Field(
        default=None,
        pattern=_HEX_DIGEST_PATTERN,
    )
    available_next_actions: tuple[AvailableNextAction, ...] = Field(min_length=1)
    receipt_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_decision_and_digest(self) -> "DisclosureReceipt":
        if self.status == "granted":
            if self.granted_level is None or self.resource_uri is None:
                raise ValueError("granted_disclosure_resource_required")
            if self.resource_digest is None or self.estimated_context_tokens < 1:
                raise ValueError("granted_disclosure_digest_and_tokens_required")
            if self.error_code is not None:
                raise ValueError("granted_disclosure_error_forbidden")
        else:
            if self.error_code is None:
                raise ValueError("denied_disclosure_error_required")
            if any(
                value is not None
                for value in (
                    self.granted_level,
                    self.resource_uri,
                    self.resource_digest,
                )
            ):
                raise ValueError("denied_disclosure_must_not_leak_resource")
            if self.estimated_context_tokens != 0:
                raise ValueError("denied_disclosure_tokens_must_be_zero")

        unsigned = self.model_dump(mode="json", exclude={"receipt_digest"})
        if canonical_digest(unsigned) != self.receipt_digest:
            raise ValueError("disclosure_receipt_digest_mismatch")
        return self


def current_model_context_state_digest(
    *,
    context_snapshot_id: str,
    resolver_ref: str,
    store_revision: int,
    session_id: str,
    research_run_id: str,
    run_invocation_id: str,
    action_attempt_id: str,
    task_id: str,
    latest_plan_delta_refs: Sequence[str],
    observation_refs: Sequence[str],
    unresolved_feedback_refs: Sequence[str],
    available_next_actions: Sequence[AvailableNextAction],
    budget_status: str,
    stop_status: str,
    intervention_status: str,
    context_checkpoint_ref: str | None,
) -> str:
    """Digest current model-visible state before sealing its RuntimeScope."""

    actions = tuple(
        AvailableNextAction.model_validate(action.model_dump(mode="python"))
        for action in available_next_actions
    )
    state = {
        "contract_version": DISCLOSURE_CONTRACT_VERSION,
        "context_snapshot_id": context_snapshot_id,
        "resolver_ref": resolver_ref,
        "store_revision": store_revision,
        "session_id": session_id,
        "research_run_id": research_run_id,
        "run_invocation_id": run_invocation_id,
        "action_attempt_id": action_attempt_id,
        "task_id": task_id,
        "latest_plan_delta_refs": tuple(latest_plan_delta_refs),
        "observation_refs": tuple(observation_refs),
        "unresolved_feedback_refs": tuple(unresolved_feedback_refs),
        "available_next_actions": tuple(
            action.model_dump(mode="json") for action in actions
        ),
        "budget_status": budget_status,
        "stop_status": stop_status,
        "intervention_status": intervention_status,
        "context_checkpoint_ref": context_checkpoint_ref,
    }
    return canonical_digest(state)


class CurrentModelContextSnapshot(_FrozenContract):
    """Host-owned current state projected into one model turn."""

    contract_version: Literal["1.2"] = DISCLOSURE_CONTRACT_VERSION
    context_snapshot_id: str = Field(pattern=_REF_PATTERN)
    resolver_ref: str = Field(pattern=_REF_PATTERN)
    store_revision: int = Field(ge=1)
    runtime_scope_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)
    scope_authorization_record_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)
    session_id: str = Field(pattern=_REF_PATTERN)
    research_run_id: str = Field(pattern=_REF_PATTERN)
    run_invocation_id: str = Field(pattern=_REF_PATTERN)
    action_attempt_id: str = Field(pattern=_REF_PATTERN)
    task_id: str = Field(pattern=_REF_PATTERN)
    accepted_plan_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)
    research_graph_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)
    canonical_event_ledger_snapshot_digest: Digest = Field(
        pattern=_HEX_DIGEST_PATTERN
    )
    canonical_event_ledger_tip_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)
    canonical_event_ledger_store_revision: int = Field(ge=1)
    runtime_policy_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)
    disclosure_policy_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)
    governance_summary_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)
    current_state_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)
    latest_plan_delta_refs: tuple[str, ...] = Field(default=(), max_length=32)
    observation_refs: tuple[str, ...] = Field(default=(), max_length=256)
    unresolved_feedback_refs: tuple[str, ...] = Field(default=(), max_length=128)
    available_next_actions: tuple[AvailableNextAction, ...] = Field(
        min_length=1,
        max_length=32,
    )
    budget_status: Literal[
        "within_budget",
        "approaching_limit",
        "exhausted",
        "not_applicable",
    ]
    stop_status: Literal[
        "continue",
        "pause_required",
        "human_required",
        "stop_sufficient",
    ]
    intervention_status: Literal["none", "pending", "applied"]
    context_checkpoint_ref: str | None = Field(default=None, pattern=_REF_PATTERN)
    issued_by: Literal["host_current_model_context_resolver"] = (
        "host_current_model_context_resolver"
    )
    context_snapshot_digest: Digest = Field(pattern=_HEX_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_current_context(self) -> "CurrentModelContextSnapshot":
        for name in (
            "latest_plan_delta_refs",
            "observation_refs",
            "unresolved_feedback_refs",
        ):
            refs = tuple(getattr(self, name))
            if len(refs) != len(set(refs)):
                raise ValueError(f"current_model_context_{name}_duplicate")
        action_kinds = tuple(item.action for item in self.available_next_actions)
        if len(action_kinds) != len(set(action_kinds)):
            raise ValueError("current_model_context_next_action_duplicate")
        if self.budget_status == "exhausted" and self.stop_status == "continue":
            raise ValueError("current_model_context_exhausted_budget_continue_invalid")
        if self.stop_status == "human_required" and not any(
            item.action == "request_human_review"
            for item in self.available_next_actions
        ):
            raise ValueError("current_model_context_human_action_required")
        if self.current_state_digest != current_model_context_state_digest(
            context_snapshot_id=self.context_snapshot_id,
            resolver_ref=self.resolver_ref,
            store_revision=self.store_revision,
            session_id=self.session_id,
            research_run_id=self.research_run_id,
            run_invocation_id=self.run_invocation_id,
            action_attempt_id=self.action_attempt_id,
            task_id=self.task_id,
            latest_plan_delta_refs=self.latest_plan_delta_refs,
            observation_refs=self.observation_refs,
            unresolved_feedback_refs=self.unresolved_feedback_refs,
            available_next_actions=self.available_next_actions,
            budget_status=self.budget_status,
            stop_status=self.stop_status,
            intervention_status=self.intervention_status,
            context_checkpoint_ref=self.context_checkpoint_ref,
        ):
            raise ValueError("current_model_context_state_digest_mismatch")
        unsigned = self.model_dump(mode="json", exclude={"context_snapshot_digest"})
        if canonical_digest(unsigned) != self.context_snapshot_digest:
            raise ValueError("current_model_context_snapshot_digest_mismatch")
        return self


DisclosureRuntimeContext.model_rebuild()


class CanonicalEventLedgerReader(Protocol):
    """Host port returning the current durable snapshot for one session."""

    def read_current_session_ledger(
        self,
        session_id: str,
    ) -> CanonicalEventLedgerSnapshot | None: ...


class DisclosureCatalogResolver(Protocol):
    """Host port resolving the current catalog authorized for one runtime scope."""

    def resolve_current_catalog(
        self,
        *,
        runtime_scope_digest: str,
    ) -> DisclosureCatalogSnapshot | None: ...


class RuntimeScopeAuthorityResolver(Protocol):
    """Host port resolving a scope from accepted task/action authority state."""

    def resolve_current_scope_authorization(
        self,
        runtime_scope_digest: str,
    ) -> RuntimeScopeAuthorizationRecord | None: ...


class CurrentModelContextResolver(Protocol):
    """Host port; request/model payloads cannot submit current runtime state."""

    def resolve_current_model_context(
        self,
        *,
        runtime_scope_digest: str,
    ) -> CurrentModelContextSnapshot | None: ...


def _resolve_current_scope_authorization(
    *,
    runtime_scope: RuntimeScope,
    authority_resolver: RuntimeScopeAuthorityResolver | None,
) -> RuntimeScopeAuthorizationRecord:
    if authority_resolver is None:
        raise ValueError("runtime_scope_authority_resolver_required")
    record = authority_resolver.resolve_current_scope_authorization(
        runtime_scope.scope_digest
    )
    if record is None:
        raise ValueError("runtime_scope_absent_from_authoritative_store")
    return validate_runtime_scope_authorization(
        runtime_scope=runtime_scope,
        authorization_record=record,
    )


def _resolve_current_disclosure_catalog(
    *,
    catalog: DisclosureCatalogSnapshot,
    runtime_scope: RuntimeScope,
    catalog_resolver: DisclosureCatalogResolver | None,
) -> DisclosureCatalogSnapshot:
    """Reject stale or caller-authored catalogs before any resource is consumed."""

    catalog = DisclosureCatalogSnapshot.model_validate(
        catalog.model_dump(mode="python")
    )
    if catalog_resolver is None:
        raise ValueError("disclosure_catalog_resolver_required")
    current = catalog_resolver.resolve_current_catalog(
        runtime_scope_digest=runtime_scope.scope_digest,
    )
    if current is None:
        raise ValueError("disclosure_catalog_absent_from_authoritative_store")
    if not isinstance(current, DisclosureCatalogSnapshot):
        raise ValueError("disclosure_catalog_resolver_model_required")
    current = DisclosureCatalogSnapshot.model_validate(
        current.model_dump(mode="python")
    )

    supplied_unsigned = catalog.model_dump(mode="json", exclude={"catalog_digest"})
    if canonical_digest(supplied_unsigned) != catalog.catalog_digest:
        raise ValueError("disclosure_catalog_supplied_digest_invalid")
    current_unsigned = current.model_dump(mode="json", exclude={"catalog_digest"})
    if canonical_digest(current_unsigned) != current.catalog_digest:
        raise ValueError("disclosure_catalog_current_digest_invalid")
    if current.inventory_snapshot_digest != runtime_scope.data_snapshot_digest:
        raise ValueError("disclosure_catalog_current_runtime_snapshot_mismatch")
    if current != catalog:
        raise ValueError("disclosure_catalog_stale_or_self_signed")
    return current


def _scope_authority_binding_refs(
    *,
    runtime_scope: RuntimeScope,
    authority_record: RuntimeScopeAuthorizationRecord,
) -> tuple[str, ...]:
    """Exact refs a canonical action-intent event must bind before disclosure."""

    return (
        f"runtime-scope://sha256/{runtime_scope.scope_digest}",
        f"action-attempt://sha256/{authority_record.action_attempt_digest}",
        f"accepted-plan://sha256/{authority_record.accepted_plan_digest}",
        f"research-graph://sha256/{authority_record.research_graph_digest}",
        f"objective://sha256/{authority_record.objective_digest}",
        f"task-assignment://sha256/{authority_record.task_assignment_digest}",
        f"runtime-policy://sha256/{authority_record.policy_digest}",
        (
            "disclosure-policy://sha256/"
            f"{authority_record.disclosure_policy_digest}"
        ),
        f"authority-matrix://sha256/{authority_record.authority_matrix_digest}",
    )


def _disclosure_resource_binding_ref(receipt: DisclosureReceipt) -> str:
    """Bind the semantic resource identity, URI and content digest together."""

    binding = {
        "ref": receipt.ref,
        "kind": receipt.kind,
        "granted_level": receipt.granted_level,
        "resource_uri": receipt.resource_uri,
        "resource_digest": receipt.resource_digest,
    }
    return _DISCLOSURE_RESOURCE_BINDING_REF_PREFIX + canonical_digest(binding)


def build_disclosure_grant_ledger_view(
    *,
    ledger_view_id: str,
    runtime_scope: RuntimeScope,
    ledger_reader: CanonicalEventLedgerReader | None,
    authority_resolver: RuntimeScopeAuthorityResolver | None,
    verified_receipts: Sequence[DisclosureReceipt],
) -> DisclosureGrantLedgerView:
    """Build the immutable view after a host ledger resolver verified membership."""

    runtime_scope = RuntimeScope.model_validate(
        runtime_scope.model_dump(mode="python")
    )
    verified_receipts = tuple(
        DisclosureReceipt.model_validate(receipt.model_dump(mode="python"))
        for receipt in verified_receipts
    )
    authority_record = _resolve_current_scope_authorization(
        runtime_scope=runtime_scope,
        authority_resolver=authority_resolver,
    )
    if ledger_reader is None:
        raise ValueError("canonical_event_ledger_reader_required")
    ledger_snapshot = ledger_reader.read_current_session_ledger(
        runtime_scope.session_id
    )
    if ledger_snapshot is None:
        raise ValueError("canonical_event_ledger_snapshot_missing")
    if not isinstance(ledger_snapshot, CanonicalEventLedgerSnapshot):
        raise ValueError("canonical_event_ledger_snapshot_model_required")
    ledger_snapshot = CanonicalEventLedgerSnapshot.model_validate(
        ledger_snapshot.model_dump(mode="python")
    )
    if (
        ledger_snapshot.session_id != runtime_scope.session_id
        or ledger_snapshot.ledger_snapshot_digest
        != authority_record.canonical_event_ledger_snapshot_digest
        or ledger_snapshot.store_revision
        != authority_record.authority_store_revision
    ):
        raise ValueError("disclosure_canonical_ledger_snapshot_stale_or_unbound")
    events = validate_session_event_sequence(
        ledger_snapshot.events,
        expected_session_id=runtime_scope.session_id,
    )
    if not events:
        raise ValueError("disclosure_grant_event_ledger_empty")
    if ledger_snapshot.canonical_tip_digest != events[-1].event_digest:
        raise ValueError("disclosure_canonical_ledger_tip_stale")

    scoped_events = [
        event
        for event in events
        if event.run_id == runtime_scope.research_run_id
        and event.run_invocation_id == runtime_scope.run_invocation_id
        and event.action_attempt_id == runtime_scope.action_attempt_id
    ]
    scope_authority_candidates = [
        event
        for event in scoped_events
        if event.event_type == "action_intent_committed"
        and any(
            ref
            == f"runtime-scope://sha256/{runtime_scope.scope_digest}"
            for ref in event.output_refs
        )
    ]
    if not scope_authority_candidates:
        raise ValueError("disclosure_scope_authority_event_missing")
    if len(scope_authority_candidates) != 1:
        raise ValueError("disclosure_scope_authority_event_ambiguous")
    scope_authority_event = scope_authority_candidates[0]
    if scope_authority_event.actor_id != _HOST_RUNTIME_EVENT_ACTOR_ID:
        raise ValueError("disclosure_scope_authority_event_issuer_invalid")
    if set(scope_authority_event.output_refs) != set(
        _scope_authority_binding_refs(
            runtime_scope=runtime_scope,
            authority_record=authority_record,
        )
    ):
        raise ValueError("disclosure_scope_authority_binding_mismatch")

    grant_events = [
        event
        for event in scoped_events
        if event.event_type == "disclosure_granted"
    ]
    event_by_receipt_digest: dict[str, CanonicalSessionEventV1_2] = {}
    for event in grant_events:
        if event.actor_id != _HOST_RUNTIME_EVENT_ACTOR_ID:
            raise ValueError("disclosure_grant_event_issuer_invalid")
        receipt_refs = [
            output_ref.removeprefix(_DISCLOSURE_RECEIPT_REF_PREFIX)
            for output_ref in event.output_refs
            if output_ref.startswith(_DISCLOSURE_RECEIPT_REF_PREFIX)
        ]
        if len(receipt_refs) != 1:
            raise ValueError("disclosure_grant_receipt_binding_invalid")
        receipt_digest = receipt_refs[0]
        if receipt_digest in event_by_receipt_digest:
            raise ValueError("disclosure_grant_receipt_event_duplicate")
        event_by_receipt_digest[receipt_digest] = event
    receipt_digests = tuple(sorted(receipt.receipt_digest for receipt in verified_receipts))
    if len(receipt_digests) != len(set(receipt_digests)):
        raise ValueError("disclosure_verified_receipt_duplicate")
    if any(receipt.status != "granted" for receipt in verified_receipts):
        raise ValueError("disclosure_verified_receipt_not_granted")
    if any(digest not in event_by_receipt_digest for digest in receipt_digests):
        raise ValueError("disclosure_receipt_absent_from_canonical_event_ledger")

    request_events_by_digest: dict[str, list[CanonicalSessionEventV1_2]] = {}
    request_events = [
        event
        for event in scoped_events
        if event.event_type == "disclosure_requested"
    ]
    for event in request_events:
        if event.actor_id != _HOST_RUNTIME_EVENT_ACTOR_ID:
            raise ValueError("disclosure_request_event_issuer_invalid")
        request_refs = [
            input_ref.removeprefix(_DISCLOSURE_REQUEST_REF_PREFIX)
            for input_ref in event.input_refs
            if input_ref.startswith(_DISCLOSURE_REQUEST_REF_PREFIX)
        ]
        if len(request_refs) != 1:
            raise ValueError("disclosure_request_event_binding_invalid")
        request_events_by_digest.setdefault(request_refs[0], []).append(event)

    request_event_by_receipt_digest: dict[str, CanonicalSessionEventV1_2] = {}
    for receipt in verified_receipts:
        grant_event = event_by_receipt_digest[receipt.receipt_digest]
        matching_requests = request_events_by_digest.get(receipt.request_digest, [])
        if not matching_requests:
            raise ValueError("disclosure_grant_missing_canonical_request_event")
        if len(matching_requests) != 1:
            raise ValueError("disclosure_canonical_request_event_duplicate")
        request_event = matching_requests[0]
        if (
            request_event.session_sequence >= grant_event.session_sequence
            or request_event.occurred_at >= grant_event.occurred_at
        ):
            raise ValueError("disclosure_canonical_request_not_before_grant")
        if scope_authority_event.session_sequence >= request_event.session_sequence:
            raise ValueError("disclosure_scope_authority_not_before_request")
        expected_request_ref = (
            _DISCLOSURE_REQUEST_REF_PREFIX + receipt.request_digest
        )
        if expected_request_ref not in grant_event.input_refs:
            raise ValueError("disclosure_grant_request_binding_missing")
        expected_resource_refs = {
            _DISCLOSURE_RESOURCE_REF_PREFIX + str(receipt.resource_digest),
            _disclosure_resource_binding_ref(receipt),
        }
        actual_resource_refs = {
            output_ref
            for output_ref in grant_event.output_refs
            if output_ref.startswith(_DISCLOSURE_RESOURCE_REF_PREFIX)
            or output_ref.startswith(_DISCLOSURE_RESOURCE_BINDING_REF_PREFIX)
        }
        if actual_resource_refs != expected_resource_refs:
            raise ValueError("disclosure_grant_resource_binding_missing")
        request_event_by_receipt_digest[receipt.receipt_digest] = request_event
    body: dict[str, Any] = {
        "contract_version": DISCLOSURE_CONTRACT_VERSION,
        "ledger_view_id": ledger_view_id,
        "runtime_scope_digest": runtime_scope.scope_digest,
        "session_id": runtime_scope.session_id,
        "research_run_id": runtime_scope.research_run_id,
        "run_invocation_id": runtime_scope.run_invocation_id,
        "action_attempt_id": runtime_scope.action_attempt_id,
        "canonical_event_ledger_snapshot_digest": ledger_snapshot.ledger_snapshot_digest,
        "runtime_scope_authorization_record_digest": (
            authority_record.authorization_record_digest
        ),
        "canonical_event_ledger_tip_digest": ledger_snapshot.canonical_tip_digest,
        "canonical_event_ledger_store_revision": ledger_snapshot.store_revision,
        "source_scope_authority_event_digest": scope_authority_event.event_digest,
        "source_request_event_digests": tuple(
            request_event_by_receipt_digest[digest].event_digest
            for digest in receipt_digests
        ),
        "source_grant_event_digests": tuple(
            event_by_receipt_digest[digest].event_digest for digest in receipt_digests
        ),
        "verified_receipt_digests": receipt_digests,
    }
    return DisclosureGrantLedgerView(
        **body,
        ledger_view_digest=canonical_digest(body),
    )


def _validate_current_disclosure_grant_view(
    *,
    context: DisclosureRuntimeContext,
    ledger_reader: CanonicalEventLedgerReader,
    authority_resolver: RuntimeScopeAuthorityResolver,
) -> DisclosureGrantLedgerView:
    """Reject a stale or caller-authored view before any grant is consumed."""

    rebuilt = build_disclosure_grant_ledger_view(
        ledger_view_id=context.grant_ledger_view.ledger_view_id,
        runtime_scope=context.runtime_scope,
        ledger_reader=ledger_reader,
        authority_resolver=authority_resolver,
        verified_receipts=context.grants,
    )
    if rebuilt != context.grant_ledger_view:
        raise ValueError(
            "runtime_context_disclosure_ledger_view_stale_or_self_signed"
        )
    return rebuilt


def build_disclosure_catalog(
    *,
    snapshot_id: str,
    inventory_snapshot_digest: str,
    capabilities: Sequence[CapabilityDescriptor],
    resources: Sequence[DisclosureResource],
) -> DisclosureCatalogSnapshot:
    """Build rather than hand-author a content-addressed catalog."""

    digest_body = {
        "contract_version": DISCLOSURE_CONTRACT_VERSION,
        "snapshot_id": snapshot_id,
        "inventory_snapshot_digest": inventory_snapshot_digest,
        "capabilities": tuple(item.model_dump(mode="json") for item in capabilities),
        "resources": tuple(item.model_dump(mode="json") for item in resources),
    }
    return DisclosureCatalogSnapshot(
        contract_version=DISCLOSURE_CONTRACT_VERSION,
        snapshot_id=snapshot_id,
        inventory_snapshot_digest=inventory_snapshot_digest,
        capabilities=tuple(capabilities),
        resources=tuple(resources),
        catalog_digest=canonical_digest(digest_body),
    )


def build_disclosure_policy(
    *,
    policy_snapshot_id: str,
    rules: Sequence[DisclosureAuthorityRule],
    maximum_tokens_per_receipt: int,
    maximum_tokens_per_task: int,
    maximum_recursive_depth: int,
) -> DisclosurePolicySnapshot:
    digest_body = {
        "contract_version": DISCLOSURE_CONTRACT_VERSION,
        "policy_snapshot_id": policy_snapshot_id,
        "rules": tuple(item.model_dump(mode="json") for item in rules),
        "maximum_tokens_per_receipt": maximum_tokens_per_receipt,
        "maximum_tokens_per_task": maximum_tokens_per_task,
        "maximum_recursive_depth": maximum_recursive_depth,
    }
    return DisclosurePolicySnapshot(
        contract_version=DISCLOSURE_CONTRACT_VERSION,
        policy_snapshot_id=policy_snapshot_id,
        rules=tuple(rules),
        maximum_tokens_per_receipt=maximum_tokens_per_receipt,
        maximum_tokens_per_task=maximum_tokens_per_task,
        maximum_recursive_depth=maximum_recursive_depth,
        policy_digest=canonical_digest(digest_body),
    )


def _find_resource(
    catalog: DisclosureCatalogSnapshot,
    *,
    ref: str,
    level: str,
) -> DisclosureResource | None:
    return next(
        (item for item in catalog.resources if item.ref == ref and item.level == level),
        None,
    )


def _resource_parent_chain(
    catalog: DisclosureCatalogSnapshot,
    resource: DisclosureResource,
) -> tuple[str, ...] | None:
    """Return ancestors, or ``None`` for a cycle/ambiguous parent chain."""

    chain: list[str] = []
    current = resource
    seen = {resource.ref}
    while current.parent_ref is not None:
        parent_ref = current.parent_ref
        if parent_ref in seen:
            return None
        seen.add(parent_ref)
        chain.append(parent_ref)
        parents = [item for item in catalog.resources if item.ref == parent_ref]
        if not parents:
            return None
        # A ref can have several levels but its semantic parent must be stable.
        parent_refs = {item.parent_ref for item in parents}
        if len(parent_refs) != 1:
            return None
        current = parents[0]
    return tuple(chain)


def _resolve_rule(
    *,
    resource: DisclosureResource,
    chain: tuple[str, ...],
    policy: DisclosurePolicySnapshot,
) -> DisclosureAuthorityRule | None:
    exact = next((rule for rule in policy.rules if rule.ref == resource.ref), None)
    if exact is not None:
        return exact
    for ancestor in chain:
        rule = next((item for item in policy.rules if item.ref == ancestor), None)
        if rule is not None:
            return rule if rule.allow_recursive_children else None
    return None


def _grant_index(
    context: DisclosureRuntimeContext,
) -> dict[str, DisclosureReceipt]:
    return {grant.receipt_digest: grant for grant in context.grants}


def _receipt(
    *,
    request: DisclosureRequest,
    context: DisclosureRuntimeContext,
    status: DisclosureStatus,
    decision_reason: str,
    actions: tuple[AvailableNextAction, ...],
    error_code: str | None = None,
    resource: DisclosureResource | None = None,
) -> DisclosureReceipt:
    scope = context.runtime_scope
    body: dict[str, Any] = {
        "contract_version": DISCLOSURE_CONTRACT_VERSION,
        "status": status,
        "request_digest": canonical_digest(request),
        "catalog_digest": request.catalog_digest,
        "inventory_snapshot_digest": request.inventory_snapshot_digest,
        "policy_digest": request.policy_digest,
        "runtime_scope_digest": scope.scope_digest,
        "session_id": scope.session_id,
        "research_run_id": scope.research_run_id,
        "run_invocation_id": scope.run_invocation_id,
        "action_attempt_id": scope.action_attempt_id,
        "agent_id": scope.agent_id,
        "task_id": scope.task_id,
        "role": context.role,
        "task_kind": context.task_kind,
        "ref": request.ref,
        "kind": request.kind,
        "requested_depth": request.depth,
        "granted_level": resource.level if resource is not None else None,
        "resource_uri": resource.resource_uri if resource is not None else None,
        "resource_digest": resource.resource_digest if resource is not None else None,
        "estimated_context_tokens": (
            resource.estimated_context_tokens if resource is not None else 0
        ),
        "error_code": error_code,
        "decision_reason": decision_reason,
        "parent_receipt_digest": request.parent_receipt_digest,
        "available_next_actions": actions,
    }
    return DisclosureReceipt(**body, receipt_digest=canonical_digest(body))


def _action(
    action: str,
    reason: str,
    *,
    target_ref: str | None = None,
    capability_ref: str | None = None,
    requires_human: bool = False,
) -> AvailableNextAction:
    values: dict[str, Any] = {
        "action": action,
        "reason": reason,
        "requires_human": requires_human,
    }
    if target_ref is not None:
        values["target_ref"] = target_ref
    if capability_ref is not None:
        values["capability_ref"] = capability_ref
    return AvailableNextAction(**values)


def _deny(
    request: DisclosureRequest,
    *,
    context: DisclosureRuntimeContext,
    code: str,
    reason: str,
    actions: tuple[AvailableNextAction, ...],
) -> DisclosureReceipt:
    if not actions:
        raise ValueError("disclosure_denial_requires_legal_remedy")
    return _receipt(
        request=request,
        context=context,
        status="denied",
        error_code=code,
        decision_reason=reason,
        actions=actions,
    )


def decide_disclosure(
    *,
    request: DisclosureRequest,
    catalog: DisclosureCatalogSnapshot,
    policy: DisclosurePolicySnapshot,
    context: DisclosureRuntimeContext,
    ledger_reader: CanonicalEventLedgerReader,
    catalog_resolver: DisclosureCatalogResolver | None,
    authority_resolver: RuntimeScopeAuthorityResolver,
) -> DisclosureReceipt:
    """Evaluate a provider request against sealed, current runtime state.

    Rejections are ordinary typed receipts, not exceptions.  Structural model
    validation still raises before this boundary, while every policy/runtime
    rejection includes at least one presently legal next action.
    """

    request = DisclosureRequest.model_validate(request.model_dump(mode="python"))
    policy = DisclosurePolicySnapshot.model_validate(
        policy.model_dump(mode="python")
    )
    context = DisclosureRuntimeContext.model_validate(
        context.model_dump(mode="python")
    )
    current_authorization = _resolve_current_scope_authorization(
        runtime_scope=context.runtime_scope,
        authority_resolver=authority_resolver,
    )
    if current_authorization != context.scope_authorization_record:
        raise ValueError("runtime_scope_authorization_record_stale")
    context = context.validate_current_grant_view(
        ledger_reader=ledger_reader,
        authority_resolver=authority_resolver,
    )
    _resolve_current_disclosure_catalog(
        catalog=catalog,
        runtime_scope=context.runtime_scope,
        catalog_resolver=catalog_resolver,
    )
    if request.catalog_digest != catalog.catalog_digest:
        return _deny(
            request,
            context=context,
            code="stale_catalog_digest",
            reason="The requested catalog is not the active immutable catalog.",
            actions=(
                _action(
                    "request_data_inventory",
                    "Refresh the compact L0 catalog before requesting a resource.",
                ),
            ),
        )
    if context.runtime_scope.data_snapshot_digest != catalog.inventory_snapshot_digest:
        return _deny(
            request,
            context=context,
            code="runtime_inventory_snapshot_mismatch",
            reason="The sealed runtime scope is bound to a different data snapshot.",
            actions=(
                _action(
                    "request_human_review",
                    "Ask the runtime to create a correctly snapshot-bound action attempt.",
                    requires_human=True,
                ),
            ),
        )
    if request.inventory_snapshot_digest != catalog.inventory_snapshot_digest:
        return _deny(
            request,
            context=context,
            code="stale_inventory_snapshot_digest",
            reason="The request was planned against a different data snapshot.",
            actions=(
                _action(
                    "request_data_inventory",
                    "Refresh the L0 inventory coverage and re-plan against it.",
                ),
            ),
        )
    if request.policy_digest != policy.policy_digest:
        return _deny(
            request,
            context=context,
            code="stale_policy_digest",
            reason="The authority policy changed after this request was prepared.",
            actions=(
                _action(
                    "request_human_review",
                    "Ask the runtime operator for a fresh policy-bound action menu.",
                    requires_human=True,
                ),
            ),
        )
    if context.runtime_scope.disclosure_policy_digest != policy.policy_digest:
        return _deny(
            request,
            context=context,
            code="runtime_policy_snapshot_mismatch",
            reason="The sealed runtime scope is bound to a different policy snapshot.",
            actions=(
                _action(
                    "request_human_review",
                    "Ask the runtime to create a correctly policy-bound action attempt.",
                    requires_human=True,
                ),
            ),
        )

    level = _DEPTH_TO_LEVEL[request.depth]
    resource = _find_resource(catalog, ref=request.ref, level=level)
    if resource is None or resource.kind != request.kind:
        return _deny(
            request,
            context=context,
            code="disclosure_ref_or_depth_unavailable",
            reason="The active catalog has no matching kind/ref/depth resource.",
            actions=(
                _action(
                    "request_data_inventory",
                    "Choose a ref and depth present in the current L0 catalog.",
                ),
            ),
        )

    chain = _resource_parent_chain(catalog, resource)
    if chain is None:
        return _deny(
            request,
            context=context,
            code="disclosure_reference_chain_invalid",
            reason="The resource ancestry is cyclic, missing, or ambiguous.",
            actions=(
                _action(
                    "request_human_review",
                    "Ask an operator to repair the immutable catalog snapshot.",
                    target_ref=request.ref,
                    requires_human=True,
                ),
            ),
        )
    if len(chain) > policy.maximum_recursive_depth:
        return _deny(
            request,
            context=context,
            code="disclosure_recursive_depth_exceeded",
            reason="The resource exceeds the policy's bounded recursion depth.",
            actions=(
                _action(
                    "submit_plan_delta",
                    "Select a shallower resource or an alternative qualified route.",
                    target_ref=request.ref,
                ),
                _action(
                    "request_human_review",
                    "Request an operator decision if the deep resource is material.",
                    target_ref=request.ref,
                    requires_human=True,
                ),
            ),
        )

    rule = _resolve_rule(resource=resource, chain=chain, policy=policy)
    if rule is None:
        return _deny(
            request,
            context=context,
            code="disclosure_authority_rule_missing",
            reason="No current server-side rule authorizes this resource.",
            actions=(
                _action(
                    "choose_qualified_alternative_route",
                    "Use a capability already present in the legal action menu.",
                ),
                _action(
                    "request_human_review",
                    "Ask an operator to review a material missing authority rule.",
                    target_ref=request.ref,
                    requires_human=True,
                ),
            ),
        )
    if context.role not in rule.allowed_roles or context.task_kind not in rule.allowed_task_kinds:
        return _deny(
            request,
            context=context,
            code="disclosure_role_or_task_not_authorized",
            reason="The sealed role/task authority does not permit this disclosure.",
            actions=(
                _action(
                    "submit_plan_delta",
                    "Route the need to an already-authorized task owner.",
                    target_ref=request.ref,
                ),
                _action(
                    "request_human_review",
                    "Ask a human to change task assignment, not model authority.",
                    target_ref=request.ref,
                    requires_human=True,
                ),
            ),
        )
    if _LEVEL_NUMBER[level] > _LEVEL_NUMBER[rule.maximum_level]:
        return _deny(
            request,
            context=context,
            code="disclosure_depth_not_authorized",
            reason="The requested depth exceeds the server-side authority rule.",
            actions=(
                _action(
                    "request_disclosure",
                    "Request the deepest level allowed by the current action menu.",
                    capability_ref=request.ref,
                ),
            ),
        )
    grants = _grant_index(context)
    if level != "L1":
        parent = (
            grants.get(request.parent_receipt_digest)
            if request.parent_receipt_digest is not None
            else None
        )
        prior_level = f"L{_LEVEL_NUMBER[level] - 1}"
        allowed_parent_refs = {request.ref}
        if resource.parent_ref is not None:
            allowed_parent_refs.add(resource.parent_ref)
        parent_current = (
            parent is not None
            and parent.status == "granted"
            and parent.catalog_digest == catalog.catalog_digest
            and parent.inventory_snapshot_digest == catalog.inventory_snapshot_digest
            and parent.policy_digest == policy.policy_digest
            and parent.runtime_scope_digest == context.runtime_scope.scope_digest
        )
        if (
            not parent_current
            or parent.granted_level != prior_level
            or parent.ref not in allowed_parent_refs
            or parent.kind != resource.kind
        ):
            return _deny(
                request,
                context=context,
                code="disclosure_depth_escalation_required",
                reason="Deeper content requires a current receipt for the preceding level.",
                actions=(
                    _action(
                        "request_disclosure",
                        f"Request {prior_level} for this ref or its declared parent first.",
                        capability_ref=resource.parent_ref or request.ref,
                    ),
                ),
            )
    elif request.parent_receipt_digest is not None:
        return _deny(
            request,
            context=context,
            code="l1_parent_receipt_forbidden",
            reason="L1 starts a disclosure chain and must not claim a parent grant.",
            actions=(
                _action(
                    "request_disclosure",
                    "Retry the L1 contract request without a parent receipt.",
                    target_ref=request.ref,
                ),
            ),
        )

    remaining = policy.maximum_tokens_per_task - context.consumed_disclosure_tokens
    if (
        resource.estimated_context_tokens > policy.maximum_tokens_per_receipt
        or resource.estimated_context_tokens > remaining
    ):
        return _deny(
            request,
            context=context,
            code="disclosure_token_budget_exceeded",
            reason="This pack does not fit the current per-receipt or task budget.",
            actions=(
                _action(
                    "request_deeper_inventory",
                    "Request a smaller content-addressed excerpt or metadata view.",
                    target_ref=request.ref,
                ),
                _action(
                    "submit_plan_delta",
                    "Reprioritize the research route instead of silently truncating.",
                    target_ref=request.ref,
                ),
                _action(
                    "request_human_review",
                    "Escalate a material budget conflict; do not call it complete.",
                    target_ref=request.ref,
                    requires_human=True,
                ),
            ),
        )

    next_actions = (
        _action(
            "submit_plan_delta",
            "Use the disclosed pack only for the stated task and preserve its digest in the next plan revision.",
            target_ref=request.ref,
        ),
        _action(
            "request_deeper_inventory",
            "Request the next bounded layer only if this pack is insufficient.",
            target_ref=request.ref,
        ),
    )
    return _receipt(
        request=request,
        context=context,
        status="granted",
        decision_reason="The current policy, authority, depth, recursion, and budget gates passed.",
        actions=next_actions,
        resource=resource,
    )


def derive_runtime_governance_summary(policy: RuntimePolicySnapshot) -> str:
    """Derive the answer-free L0 governance text from the bound runtime policy."""

    policy = RuntimePolicySnapshot.model_validate(policy.model_dump(mode="python"))
    return (
        "Runtime governance: paid model execution is not authorized; Evidence "
        "promotion requires a qualified reviewer; S2 writes are not authorized; "
        "a public-information gap requires a GapEligibilityReceipt; research "
        f"as-of is {policy.research_as_of}; allowed branch scopes="
        f"{len(policy.allowed_branch_refs)}; allowed authority classes="
        f"{len(policy.allowed_authority_class_refs)}."
    )


def _governance_summary_digest(policy: RuntimePolicySnapshot) -> str:
    summary = derive_runtime_governance_summary(policy)
    return canonical_digest(
        {
            "runtime_policy_digest": policy.policy_digest,
            "governance_summary": summary,
        }
    )


def build_current_model_context_snapshot(
    *,
    runtime_policy: RuntimePolicySnapshot,
    **fields: Any,
) -> CurrentModelContextSnapshot:
    """Build one host snapshot; current-state fields never come from a request."""

    runtime_policy = RuntimePolicySnapshot.model_validate(
        runtime_policy.model_dump(mode="python")
    )
    forbidden = {
        "contract_version",
        "runtime_policy_digest",
        "governance_summary_digest",
        "current_state_digest",
        "issued_by",
        "context_snapshot_digest",
    }.intersection(fields)
    if forbidden:
        raise ValueError("current_model_context_derived_fields_forbidden")
    body = {
        "contract_version": DISCLOSURE_CONTRACT_VERSION,
        **fields,
        "runtime_policy_digest": runtime_policy.policy_digest,
        "governance_summary_digest": _governance_summary_digest(runtime_policy),
        "current_state_digest": current_model_context_state_digest(
            context_snapshot_id=fields["context_snapshot_id"],
            resolver_ref=fields["resolver_ref"],
            store_revision=fields["store_revision"],
            session_id=fields["session_id"],
            research_run_id=fields["research_run_id"],
            run_invocation_id=fields["run_invocation_id"],
            action_attempt_id=fields["action_attempt_id"],
            task_id=fields["task_id"],
            latest_plan_delta_refs=fields.get("latest_plan_delta_refs", ()),
            observation_refs=fields.get("observation_refs", ()),
            unresolved_feedback_refs=fields.get("unresolved_feedback_refs", ()),
            available_next_actions=fields["available_next_actions"],
            budget_status=fields["budget_status"],
            stop_status=fields["stop_status"],
            intervention_status=fields["intervention_status"],
            context_checkpoint_ref=fields.get("context_checkpoint_ref"),
        ),
        "issued_by": "host_current_model_context_resolver",
    }
    return CurrentModelContextSnapshot(
        **body,
        context_snapshot_digest=canonical_digest(body),
    )


def _resolve_current_model_context_snapshot(
    *,
    runtime_policy: RuntimePolicySnapshot,
    disclosure_policy: DisclosurePolicySnapshot,
    context: DisclosureRuntimeContext,
    current_authorization: RuntimeScopeAuthorizationRecord,
    ledger_reader: CanonicalEventLedgerReader,
    model_context_resolver: CurrentModelContextResolver | None,
) -> CurrentModelContextSnapshot:
    if model_context_resolver is None:
        raise ValueError("current_model_context_resolver_required")
    current = model_context_resolver.resolve_current_model_context(
        runtime_scope_digest=context.runtime_scope.scope_digest,
    )
    if current is None:
        raise ValueError("current_model_context_snapshot_missing")
    if not isinstance(current, CurrentModelContextSnapshot):
        raise ValueError("current_model_context_snapshot_model_required")
    current = CurrentModelContextSnapshot.model_validate(
        current.model_dump(mode="python")
    )
    if context.runtime_scope.model_context_state_digest is None:
        raise ValueError("runtime_scope_model_context_state_unbound")
    if ledger_reader is None:
        raise ValueError("canonical_event_ledger_reader_required")
    ledger = ledger_reader.read_current_session_ledger(
        context.runtime_scope.session_id
    )
    if ledger is None:
        raise ValueError("canonical_event_ledger_snapshot_missing")
    if not isinstance(ledger, CanonicalEventLedgerSnapshot):
        raise ValueError("canonical_event_ledger_snapshot_model_required")
    ledger = CanonicalEventLedgerSnapshot.model_validate(
        ledger.model_dump(mode="python")
    )
    expected = {
        "runtime_scope_digest": context.runtime_scope.scope_digest,
        "scope_authorization_record_digest": (
            current_authorization.authorization_record_digest
        ),
        "session_id": context.runtime_scope.session_id,
        "research_run_id": context.runtime_scope.research_run_id,
        "run_invocation_id": context.runtime_scope.run_invocation_id,
        "action_attempt_id": context.runtime_scope.action_attempt_id,
        "task_id": context.runtime_scope.task_id,
        "accepted_plan_digest": current_authorization.accepted_plan_digest,
        "research_graph_digest": current_authorization.research_graph_digest,
        "canonical_event_ledger_snapshot_digest": ledger.ledger_snapshot_digest,
        "canonical_event_ledger_tip_digest": ledger.canonical_tip_digest,
        "canonical_event_ledger_store_revision": ledger.store_revision,
        "runtime_policy_digest": runtime_policy.policy_digest,
        "disclosure_policy_digest": disclosure_policy.policy_digest,
        "governance_summary_digest": _governance_summary_digest(runtime_policy),
        "current_state_digest": context.runtime_scope.model_context_state_digest,
    }
    for name, expected_value in expected.items():
        if getattr(current, name) != expected_value:
            raise ValueError(f"current_model_context_binding_stale:{name}")
    if (
        ledger.session_id != context.runtime_scope.session_id
        or ledger.ledger_snapshot_digest
        != current_authorization.canonical_event_ledger_snapshot_digest
        or ledger.store_revision != current_authorization.authority_store_revision
    ):
        raise ValueError("current_model_context_ledger_or_authority_stale")
    return current


def assemble_model_visible_manifest(
    *,
    manifest_id: str,
    objective: str,
    runtime_policy: RuntimePolicySnapshot,
    catalog: DisclosureCatalogSnapshot,
    policy: DisclosurePolicySnapshot,
    context: DisclosureRuntimeContext,
    ledger_reader: CanonicalEventLedgerReader,
    catalog_resolver: DisclosureCatalogResolver | None,
    authority_resolver: RuntimeScopeAuthorityResolver,
    model_context_resolver: CurrentModelContextResolver | None,
    granted_receipts: Sequence[DisclosureReceipt],
) -> ModelVisibleContextManifest:
    """Assemble an allowlisted manifest without sealed scope or raw resource text."""

    runtime_policy = RuntimePolicySnapshot.model_validate(
        runtime_policy.model_dump(mode="python")
    )
    policy = DisclosurePolicySnapshot.model_validate(
        policy.model_dump(mode="python")
    )
    context = DisclosureRuntimeContext.model_validate(
        context.model_dump(mode="python")
    )
    granted_receipts = tuple(
        DisclosureReceipt.model_validate(receipt.model_dump(mode="python"))
        for receipt in granted_receipts
    )
    current_authorization = _resolve_current_scope_authorization(
        runtime_scope=context.runtime_scope,
        authority_resolver=authority_resolver,
    )
    if current_authorization != context.scope_authorization_record:
        raise ValueError("runtime_scope_authorization_record_stale")
    objective_digest = research_objective_digest(objective)
    if objective_digest != current_authorization.objective_digest:
        raise ValueError("manifest_objective_not_current_task_assignment")
    if runtime_policy.policy_digest != current_authorization.policy_digest:
        raise ValueError("manifest_runtime_policy_not_current")
    if runtime_policy.policy_digest != context.runtime_scope.policy_digest:
        raise ValueError("manifest_runtime_policy_scope_mismatch")
    if (
        runtime_policy.case_id != context.runtime_scope.case_id
        or runtime_policy.case_version != context.runtime_scope.case_version
        or runtime_policy.research_as_of != context.runtime_scope.research_as_of
        or runtime_policy.data_snapshot_digest
        != context.runtime_scope.data_snapshot_digest
    ):
        raise ValueError("manifest_runtime_policy_identity_or_snapshot_mismatch")
    if not set(context.runtime_scope.branch_scope_refs).issubset(
        runtime_policy.allowed_branch_refs
    ):
        raise ValueError("manifest_runtime_policy_branch_scope_not_allowed")
    if not set(context.runtime_scope.permission_refs).issubset(
        runtime_policy.allowed_authority_class_refs
    ):
        raise ValueError("manifest_runtime_policy_permission_not_allowed")
    if policy.policy_digest != context.runtime_scope.disclosure_policy_digest:
        raise ValueError("manifest_disclosure_policy_scope_mismatch")
    if catalog.inventory_snapshot_digest != context.runtime_scope.data_snapshot_digest:
        raise ValueError("manifest_inventory_scope_mismatch")
    context = context.validate_current_grant_view(
        ledger_reader=ledger_reader,
        authority_resolver=authority_resolver,
    )
    _resolve_current_disclosure_catalog(
        catalog=catalog,
        runtime_scope=context.runtime_scope,
        catalog_resolver=catalog_resolver,
    )
    if runtime_policy.catalog_digest != catalog.catalog_digest:
        raise ValueError("manifest_runtime_policy_catalog_mismatch")
    if runtime_policy.disclosure_policy_digest != policy.policy_digest:
        raise ValueError("manifest_runtime_policy_disclosure_policy_mismatch")
    current_model_context = _resolve_current_model_context_snapshot(
        runtime_policy=runtime_policy,
        disclosure_policy=policy,
        context=context,
        current_authorization=current_authorization,
        ledger_reader=ledger_reader,
        model_context_resolver=model_context_resolver,
    )
    invalid = [receipt.receipt_digest for receipt in granted_receipts if receipt.status != "granted"]
    if invalid:
        raise ValueError("denied_disclosure_receipt_cannot_enter_manifest")
    stale = [
        receipt.receipt_digest
        for receipt in granted_receipts
        if receipt.catalog_digest != catalog.catalog_digest
        or receipt.inventory_snapshot_digest != catalog.inventory_snapshot_digest
        or receipt.policy_digest != policy.policy_digest
        or receipt.runtime_scope_digest != context.runtime_scope.scope_digest
        or receipt.session_id != context.runtime_scope.session_id
        or receipt.research_run_id != context.runtime_scope.research_run_id
        or receipt.run_invocation_id != context.runtime_scope.run_invocation_id
        or receipt.action_attempt_id != context.runtime_scope.action_attempt_id
        or receipt.agent_id != context.runtime_scope.agent_id
        or receipt.task_id != context.runtime_scope.task_id
        or receipt.role != context.role
        or receipt.task_kind != context.task_kind
    ]
    if stale:
        raise ValueError("stale_disclosure_receipt_cannot_enter_manifest")
    if any(
        receipt.granted_level == "L4" or receipt.kind == "diagnostic"
        for receipt in granted_receipts
    ):
        raise ValueError("operator_l4_disclosure_cannot_enter_model_manifest")
    context_receipt_digests = {receipt.receipt_digest for receipt in context.grants}
    if any(
        receipt.receipt_digest not in context_receipt_digests
        for receipt in granted_receipts
    ):
        raise ValueError("unbound_disclosure_receipt_cannot_enter_manifest")
    body: dict[str, Any] = {
        "contract_version": DISCLOSURE_CONTRACT_VERSION,
        "manifest_id": manifest_id,
        "task_id": context.runtime_scope.task_id,
        "objective": objective,
        "objective_digest": objective_digest,
        "task_assignment_digest": current_authorization.task_assignment_digest,
        "governance_summary": derive_runtime_governance_summary(runtime_policy),
        "runtime_policy_digest": runtime_policy.policy_digest,
        "disclosure_policy_digest": policy.policy_digest,
        "authority_matrix_digest": current_authorization.authority_matrix_digest,
        "plan_digest": current_authorization.accepted_plan_digest,
        "research_graph_digest": current_authorization.research_graph_digest,
        "latest_plan_delta_refs": current_model_context.latest_plan_delta_refs,
        "observation_refs": current_model_context.observation_refs,
        "unresolved_feedback_refs": current_model_context.unresolved_feedback_refs,
        "l0_catalog_digest": catalog.catalog_digest,
        "l0_capability_refs": tuple(item.capability_ref for item in catalog.capabilities),
        "granted_disclosure_receipt_refs": tuple(
            receipt.receipt_digest for receipt in granted_receipts
        ),
        "available_next_actions": current_model_context.available_next_actions,
        "budget_status": current_model_context.budget_status,
        "stop_status": current_model_context.stop_status,
        "intervention_status": current_model_context.intervention_status,
        "context_checkpoint_ref": current_model_context.context_checkpoint_ref,
        "current_model_context_snapshot_digest": (
            current_model_context.context_snapshot_digest
        ),
        "public_content_only": True,
    }
    return ModelVisibleContextManifest(
        **body,
        manifest_digest=canonical_digest(body),
    )


def provider_visible_disclosure_schema() -> Mapping[str, Any]:
    """Return only the semantic request schema; sealed context is unreachable."""

    return DisclosureRequest.model_json_schema(mode="validation")


__all__ = [
    "DISCLOSURE_CONTRACT_VERSION",
    "CapabilityDescriptor",
    "CanonicalEventLedgerReader",
    "CurrentModelContextResolver",
    "CurrentModelContextSnapshot",
    "DisclosureCatalogResolver",
    "DisclosureAuthorityRule",
    "DisclosureCatalogSnapshot",
    "DisclosureGrantLedgerView",
    "DisclosurePolicySnapshot",
    "DisclosureRequest",
    "DisclosureResource",
    "DisclosureReceipt",
    "DisclosureRuntimeContext",
    "RuntimeScopeAuthorityResolver",
    "assemble_model_visible_manifest",
    "build_current_model_context_snapshot",
    "build_disclosure_catalog",
    "build_disclosure_grant_ledger_view",
    "build_disclosure_policy",
    "canonical_digest",
    "current_model_context_state_digest",
    "decide_disclosure",
    "derive_runtime_governance_summary",
    "provider_visible_disclosure_schema",
]
