from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.runtime_resource_registry import (
    RuntimeResourceRegistryError,
    read_registered_runtime_json,
)


FACT_CANDIDATE_POOL_PLAN_REF = "fin01.s4.fact_candidate_pool_plan:v1"
FACT_CANDIDATE_POOL_PROFILE_REF = "fin01.s4.fact_candidate_pool_profile:v1"
FACT_CANDIDATE_PROFILE_SET_RELATIVE_PATH = (
    "configs/releases/"
    "fin_ia_0_1_s4_fact_candidate_pool_profiles_v1_0.json"
)
FACT_CANDIDATE_PROFILE_SET_RESOURCE_ID = "s4.fact_candidate_pool_profiles"
FIN_0_1_2_S3_FACT_CANDIDATE_PROFILE_SET_RELATIVE_PATH = (
    "configs/runtime/"
    "fin_ia_0_1_2_s3_nvda_fact_candidate_pool_profiles_v1_0.json"
)
FIN_0_1_2_S4_T05_FACT_CANDIDATE_PROFILE_SET_RELATIVE_PATH = (
    "configs/runtime/"
    "fin_ia_0_1_2_s4_t05_current_evidence_fact_candidate_pool_profiles_v1_0.json"
)
FACT_CANDIDATE_POOL_MAXIMUM = 6


class FactCandidatePoolPlannerError(ValueError):
    """Typed, content-free pre-Provider candidate-planning failure."""

    def __init__(
        self,
        failure_code: str,
        *,
        research_profile_ref: str,
        program_cell_id: str,
        profile_digest: str = "",
        eligible_support_count: int = 0,
        mapped_support_count: int = 0,
        audit_only_support_count: int = 0,
        coverage_slot_count: int = 0,
    ) -> None:
        super().__init__(failure_code)
        self.failure_code = failure_code
        self.telemetry = {
            "candidate_pool_contract_ref": FACT_CANDIDATE_POOL_PLAN_REF,
            "candidate_profile_contract_ref": (
                FACT_CANDIDATE_POOL_PROFILE_REF
            ),
            "failure_phase": "pre_provider_fact_candidate_pool_planning",
            "failure_code": failure_code,
            "research_profile_ref": research_profile_ref,
            "program_cell_id": program_cell_id,
            "profile_digest": profile_digest,
            "eligible_support_count": eligible_support_count,
            "mapped_support_count": mapped_support_count,
            "audit_only_support_count": audit_only_support_count,
            "coverage_slot_count": coverage_slot_count,
            "provider_calls": 0,
            "raw_fact_text_persisted": False,
            "raw_numeric_value_persisted": False,
            "private_reasoning_persisted": False,
        }


@dataclass(frozen=True)
class FactCandidatePoolPlan:
    contract_ref: str
    profile_contract_ref: str
    research_profile_ref: str
    program_cell_id: str
    profile_set_digest: str
    profile_digest: str
    eligible_catalog_digest: str
    candidate_pool_digest: str
    eligible_support_count: int
    candidate_pool_count: int
    omitted_eligible_support_count: int
    audit_only_support_count: int
    candidate_rows: tuple[dict[str, str], ...]
    slot_counts: tuple[dict[str, Any], ...]
    audit_only_reason_counts: tuple[dict[str, Any], ...]

    def safe_receipt(self) -> dict[str, Any]:
        return {
            "contract_ref": self.contract_ref,
            "profile_contract_ref": self.profile_contract_ref,
            "research_profile_ref": self.research_profile_ref,
            "program_cell_id": self.program_cell_id,
            "profile_set_digest": self.profile_set_digest,
            "profile_digest": self.profile_digest,
            "eligible_catalog_digest": self.eligible_catalog_digest,
            "candidate_pool_digest": self.candidate_pool_digest,
            "eligible_support_count": self.eligible_support_count,
            "candidate_pool_count": self.candidate_pool_count,
            "omitted_eligible_support_count": (
                self.omitted_eligible_support_count
            ),
            "audit_only_support_count": self.audit_only_support_count,
            "slot_counts": [dict(row) for row in self.slot_counts],
            "audit_only_reason_counts": [
                dict(row) for row in self.audit_only_reason_counts
            ],
            "raw_fact_text_persisted": False,
            "raw_numeric_value_persisted": False,
            "private_reasoning_persisted": False,
        }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


@lru_cache(maxsize=4)
def _load_profile_set(path_text: str) -> dict[str, Any]:
    path = Path(path_text)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("s4_fact_candidate_profile_set_unreadable") from exc
    return _validate_profile_set_payload(payload)


def _validate_profile_set_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("s4_fact_candidate_profile_set_invalid")
    expected_keys = {
        "schema_version",
        "contract_ref",
        "profile_set_id",
        "profile_set_digest",
        "profiles",
    }
    if (
        set(payload) != expected_keys
        or payload.get("contract_ref")
        != FACT_CANDIDATE_POOL_PROFILE_REF
        or not isinstance(payload.get("profiles"), list)
        or not payload["profiles"]
    ):
        raise ValueError("s4_fact_candidate_profile_set_invalid")
    digest_payload = {
        key: payload[key]
        for key in (
            "schema_version",
            "contract_ref",
            "profile_set_id",
            "profiles",
        )
    }
    if payload.get("profile_set_digest") != canonical_digest(
        digest_payload
    ):
        raise ValueError("s4_fact_candidate_profile_set_digest_mismatch")
    return payload


class FactCandidatePoolPlanner:
    """Build a stable, typed, at-most-six Fact alias pool locally."""

    def __init__(
        self,
        *,
        research_profile_ref: str,
        program_cell_id: str,
        profile_payload: Mapping[str, Any],
        profile_set_digest: str,
        allow_unmapped_audit_only: bool = False,
    ) -> None:
        self.research_profile_ref = str(research_profile_ref).strip()
        self.program_cell_id = str(program_cell_id).strip()
        self.profile_payload = dict(profile_payload)
        self.profile_set_digest = str(profile_set_digest).strip()
        self.allow_unmapped_audit_only = bool(
            allow_unmapped_audit_only
        )
        self._validate_profile()
        self.profile_digest = canonical_digest(
            {
                "profile_payload": self.profile_payload,
                "allow_unmapped_audit_only": True,
            }
            if self.allow_unmapped_audit_only
            else self.profile_payload
        )

    @classmethod
    def from_registry(
        cls,
        *,
        research_profile_ref: str,
        program_cell_id: str,
        registry_path: str | Path | None = None,
        allow_unmapped_audit_only: bool = False,
    ) -> FactCandidatePoolPlanner:
        if registry_path is not None:
            profile_set = _load_profile_set(str(Path(registry_path).resolve()))
        elif research_profile_ref.startswith(
            "fin_0_1_2.s4.t05.research_profile."
        ):
            profile_set = _load_profile_set(
                str(
                    (
                        _repo_root()
                        / FIN_0_1_2_S4_T05_FACT_CANDIDATE_PROFILE_SET_RELATIVE_PATH
                    ).resolve()
                )
            )
        else:
            try:
                profile_set = _validate_profile_set_payload(
                    read_registered_runtime_json(
                        _repo_root(),
                        FACT_CANDIDATE_PROFILE_SET_RESOURCE_ID,
                    )
                )
            except RuntimeResourceRegistryError as exc:
                raise ValueError(
                    "s4_fact_candidate_profile_set_unreadable"
                ) from exc
        matches = [
            row
            for row in profile_set["profiles"]
            if isinstance(row, Mapping)
            and row.get("research_profile_ref") == research_profile_ref
            and row.get("program_cell_id") == program_cell_id
        ]
        if len(matches) != 1:
            raise FactCandidatePoolPlannerError(
                "s4_fact_candidate_profile_resolution_invalid",
                research_profile_ref=research_profile_ref,
                program_cell_id=program_cell_id,
            )
        return cls(
            research_profile_ref=research_profile_ref,
            program_cell_id=program_cell_id,
            profile_payload=matches[0],
            profile_set_digest=str(profile_set["profile_set_digest"]),
            allow_unmapped_audit_only=allow_unmapped_audit_only,
        )

    def _fail(
        self,
        code: str,
        *,
        eligible_support_count: int = 0,
        mapped_support_count: int = 0,
        audit_only_support_count: int = 0,
    ) -> None:
        raise FactCandidatePoolPlannerError(
            code,
            research_profile_ref=self.research_profile_ref,
            program_cell_id=self.program_cell_id,
            profile_digest=getattr(self, "profile_digest", ""),
            eligible_support_count=eligible_support_count,
            mapped_support_count=mapped_support_count,
            audit_only_support_count=audit_only_support_count,
            coverage_slot_count=len(
                self.profile_payload.get("coverage_slots") or ()
            ),
        )

    def _validate_profile(self) -> None:
        expected = {
            "profile_contract_ref",
            "research_profile_ref",
            "program_cell_id",
            "coverage_slots",
            "audit_only_rules",
        }
        if (
            set(self.profile_payload) != expected
            or self.profile_payload.get("profile_contract_ref")
            != FACT_CANDIDATE_POOL_PROFILE_REF
            or self.profile_payload.get("research_profile_ref")
            != self.research_profile_ref
            or self.profile_payload.get("program_cell_id")
            != self.program_cell_id
        ):
            self._fail("s4_fact_candidate_profile_scope_mismatch")
        slots = self.profile_payload.get("coverage_slots")
        rules = self.profile_payload.get("audit_only_rules")
        if (
            not isinstance(slots, list)
            or not 1 <= len(slots) <= FACT_CANDIDATE_POOL_MAXIMUM
            or not isinstance(rules, list)
        ):
            self._fail("s4_fact_candidate_profile_shape_invalid")
        slot_ids: set[str] = set()
        minimum_total = 0
        for slot in slots:
            if not isinstance(slot, Mapping):
                self._fail("s4_fact_candidate_profile_shape_invalid")
            if set(slot) != {
                "coverage_slot_id",
                "coverage_slot_priority",
                "eligible_support_kinds",
                "eligible_semantic_roles",
                "authority_preference",
                "scope_preference",
                "minimum_coverage",
                "maximum_selected_from_slot",
            }:
                self._fail("s4_fact_candidate_profile_shape_invalid")
            slot_id = str(slot.get("coverage_slot_id") or "").strip()
            kinds = slot.get("eligible_support_kinds")
            roles = slot.get("eligible_semantic_roles")
            authority = slot.get("authority_preference")
            scope = slot.get("scope_preference")
            if (
                not slot_id
                or slot_id in slot_ids
                or not isinstance(slot.get("coverage_slot_priority"), int)
                or not isinstance(kinds, list)
                or not kinds
                or any(kind not in {"Evidence", "Numeric"} for kind in kinds)
                or not isinstance(roles, list)
                or not roles
                or any(
                    not isinstance(role, str) or not role.strip()
                    for role in roles
                )
                or not isinstance(authority, list)
                or not authority
                or not isinstance(scope, list)
                or not scope
            ):
                self._fail("s4_fact_candidate_profile_shape_invalid")
            minimum = slot.get("minimum_coverage")
            maximum = slot.get("maximum_selected_from_slot")
            if (
                not isinstance(minimum, int)
                or not isinstance(maximum, int)
                or minimum < 0
                or maximum < 1
                or minimum > maximum
                or maximum > FACT_CANDIDATE_POOL_MAXIMUM
            ):
                self._fail("s4_fact_candidate_profile_shape_invalid")
            minimum_total += minimum
            slot_ids.add(slot_id)
        if minimum_total > FACT_CANDIDATE_POOL_MAXIMUM:
            self._fail("s4_fact_candidate_profile_minimum_over_capacity")

    @staticmethod
    def _normalized_row(raw: Mapping[str, Any]) -> dict[str, str]:
        expected = {
            "alias",
            "authority_ref",
            "statement",
            "boundary",
            "role",
            "support_kind",
            "authority_kind",
            "scope_kind",
            "canonical_support_digest",
        }
        if set(raw) != expected:
            raise ValueError("s4_fact_candidate_catalog_row_shape_invalid")
        row = {key: str(raw.get(key) or "").strip() for key in expected}
        if (
            not all(row.values())
            or row["support_kind"] not in {"Evidence", "Numeric"}
            or len(row["canonical_support_digest"]) != 64
        ):
            raise ValueError("s4_fact_candidate_catalog_row_shape_invalid")
        return row

    @staticmethod
    def _preference_rank(value: str, preferences: Sequence[Any]) -> int:
        normalized = [str(item) for item in preferences]
        try:
            return normalized.index(value)
        except ValueError:
            return len(normalized)

    def _row_rank(
        self,
        row: Mapping[str, str],
        slot: Mapping[str, Any],
    ) -> tuple[Any, ...]:
        return (
            int(slot["coverage_slot_priority"]),
            self._preference_rank(
                row["authority_kind"],
                slot["authority_preference"],
            ),
            self._preference_rank(
                row["scope_kind"],
                slot["scope_preference"],
            ),
            0 if row["support_kind"] == "Numeric" else 1,
            0 if row["authority_kind"] == "Numeric" else 1,
            row["canonical_support_digest"],
            row["alias"],
        )

    def plan(
        self,
        catalog: Sequence[Mapping[str, Any]],
    ) -> FactCandidatePoolPlan:
        try:
            rows = [self._normalized_row(row) for row in catalog]
        except ValueError:
            self._fail(
                "s4_fact_candidate_catalog_row_shape_invalid",
                eligible_support_count=len(catalog),
            )
        aliases = [row["alias"] for row in rows]
        digests = [row["canonical_support_digest"] for row in rows]
        if len(set(aliases)) != len(aliases) or len(set(digests)) != len(
            digests
        ):
            self._fail(
                "s4_fact_candidate_catalog_duplicate",
                eligible_support_count=len(rows),
            )

        slots = [
            dict(slot) for slot in self.profile_payload["coverage_slots"]
        ]
        audit_rules = [
            dict(rule) for rule in self.profile_payload["audit_only_rules"]
        ]
        mapped: dict[str, list[dict[str, str]]] = {
            str(slot["coverage_slot_id"]): [] for slot in slots
        }
        audit_only: list[tuple[dict[str, str], str]] = []
        for row in rows:
            matches = [
                slot
                for slot in slots
                if row["support_kind"] in slot["eligible_support_kinds"]
                and row["role"] in slot["eligible_semantic_roles"]
            ]
            if len(matches) > 1:
                self._fail(
                    "s4_fact_candidate_profile_overlapping_slot_mapping",
                    eligible_support_count=len(rows),
                    mapped_support_count=sum(map(len, mapped.values())),
                    audit_only_support_count=len(audit_only),
                )
            if len(matches) == 1:
                mapped[str(matches[0]["coverage_slot_id"])].append(row)
                continue
            audit_matches = [
                rule
                for rule in audit_rules
                if isinstance(rule, Mapping)
                and set(rule)
                == {
                    "support_kind",
                    "semantic_role",
                    "audit_only_reason",
                }
                and rule.get("support_kind") == row["support_kind"]
                and rule.get("semantic_role") == row["role"]
                and str(rule.get("audit_only_reason") or "").strip()
            ]
            if len(audit_matches) != 1:
                if self.allow_unmapped_audit_only and not audit_matches:
                    audit_only.append(
                        (row, "production_profile_unmapped_audit_only")
                    )
                    continue
                self._fail(
                    "s4_fact_candidate_profile_unmapped_semantic_role",
                    eligible_support_count=len(rows),
                    mapped_support_count=sum(map(len, mapped.values())),
                    audit_only_support_count=len(audit_only),
                )
            audit_only.append(
                (row, str(audit_matches[0]["audit_only_reason"]))
            )

        eligible_count = sum(map(len, mapped.values()))
        if eligible_count == 0:
            self._fail(
                "s4_fact_candidate_pool_empty",
                eligible_support_count=0,
                audit_only_support_count=len(audit_only),
            )

        ordered_by_slot: dict[str, list[dict[str, str]]] = {}
        selected: list[dict[str, str]] = []
        selected_aliases: set[str] = set()
        for slot in sorted(
            slots,
            key=lambda item: (
                int(item["coverage_slot_priority"]),
                str(item["coverage_slot_id"]),
            ),
        ):
            slot_id = str(slot["coverage_slot_id"])
            ordered = sorted(
                mapped[slot_id],
                key=lambda row: self._row_rank(row, slot),
            )
            ordered_by_slot[slot_id] = ordered
            minimum = int(slot["minimum_coverage"])
            if len(ordered) < minimum:
                self._fail(
                    "s4_fact_candidate_profile_minimum_unmet",
                    eligible_support_count=eligible_count,
                    mapped_support_count=eligible_count,
                    audit_only_support_count=len(audit_only),
                )
            for row in ordered[:minimum]:
                selected.append(row)
                selected_aliases.add(row["alias"])

        target = min(eligible_count, FACT_CANDIDATE_POOL_MAXIMUM)
        if eligible_count <= FACT_CANDIDATE_POOL_MAXIMUM:
            selected = [
                row
                for slot in sorted(
                    slots,
                    key=lambda item: (
                        int(item["coverage_slot_priority"]),
                        str(item["coverage_slot_id"]),
                    ),
                )
                for row in ordered_by_slot[
                    str(slot["coverage_slot_id"])
                ]
            ]
            selected_aliases = {row["alias"] for row in selected}
        remaining: list[
            tuple[tuple[Any, ...], str, dict[str, str]]
        ] = []
        for slot in slots:
            slot_id = str(slot["coverage_slot_id"])
            maximum = int(slot["maximum_selected_from_slot"])
            already = sum(
                1
                for row in selected
                if row in ordered_by_slot[slot_id]
            )
            capacity = maximum - already
            if capacity <= 0:
                continue
            for row in ordered_by_slot[slot_id]:
                if row["alias"] not in selected_aliases:
                    remaining.append(
                        (self._row_rank(row, slot), slot_id, row)
                    )
        for _, slot_id, row in sorted(remaining, key=lambda item: item[0]):
            if len(selected) >= target:
                break
            slot = next(
                item
                for item in slots
                if item["coverage_slot_id"] == slot_id
            )
            current = sum(
                1
                for item in selected
                if item in ordered_by_slot[slot_id]
            )
            if current >= int(slot["maximum_selected_from_slot"]):
                continue
            selected.append(row)
            selected_aliases.add(row["alias"])
        if len(selected) != target:
            self._fail(
                "s4_fact_candidate_profile_capacity_insufficient",
                eligible_support_count=eligible_count,
                mapped_support_count=eligible_count,
                audit_only_support_count=len(audit_only),
            )

        selected = sorted(
            selected,
            key=lambda row: next(
                self._row_rank(row, slot)
                for slot in slots
                if row in ordered_by_slot[str(slot["coverage_slot_id"])]
            ),
        )
        catalog_digest = canonical_digest(
            sorted(row["canonical_support_digest"] for row in rows)
        )
        pool_digest = canonical_digest(
            [
                {
                    "alias": row["alias"],
                    "support_kind": row["support_kind"],
                    "semantic_role": row["role"],
                    "canonical_support_digest": (
                        row["canonical_support_digest"]
                    ),
                }
                for row in selected
            ]
        )
        slot_counts = []
        for slot in sorted(
            slots,
            key=lambda item: (
                int(item["coverage_slot_priority"]),
                str(item["coverage_slot_id"]),
            ),
        ):
            slot_id = str(slot["coverage_slot_id"])
            slot_rows = ordered_by_slot[slot_id]
            selected_count = sum(
                1 for row in selected if row in slot_rows
            )
            slot_counts.append(
                {
                    "coverage_slot_id": slot_id,
                    "eligible_count": len(slot_rows),
                    "selected_count": selected_count,
                    "omitted_count": len(slot_rows) - selected_count,
                }
            )
        reason_counts: dict[str, int] = {}
        for _, reason in audit_only:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        return FactCandidatePoolPlan(
            contract_ref=FACT_CANDIDATE_POOL_PLAN_REF,
            profile_contract_ref=FACT_CANDIDATE_POOL_PROFILE_REF,
            research_profile_ref=self.research_profile_ref,
            program_cell_id=self.program_cell_id,
            profile_set_digest=self.profile_set_digest,
            profile_digest=self.profile_digest,
            eligible_catalog_digest=catalog_digest,
            candidate_pool_digest=pool_digest,
            eligible_support_count=eligible_count,
            candidate_pool_count=len(selected),
            omitted_eligible_support_count=(
                eligible_count - len(selected)
            ),
            audit_only_support_count=len(audit_only),
            candidate_rows=tuple(dict(row) for row in selected),
            slot_counts=tuple(slot_counts),
            audit_only_reason_counts=tuple(
                {
                    "audit_only_reason": reason,
                    "support_count": count,
                }
                for reason, count in sorted(reason_counts.items())
            ),
        )
