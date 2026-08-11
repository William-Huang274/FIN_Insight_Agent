from __future__ import annotations

from typing import Any

from .facade import MissingDependency, RuntimeFacade
from .models import CommandEnvelope, ResultEnvelope


class CheckpointArtifactService:
    """M5.3 checkpoint/artifact lifecycle over the canonical temporary store.

    This service owns immutable checkpoint versions and exact recovery reads. It
    neither creates a worker nor retains unbounded graph/context history.
    """

    def __init__(self, facade: RuntimeFacade):
        self.facade = facade

    def write(self, command: CommandEnvelope) -> ResultEnvelope:
        return self.facade.create_checkpoint_version(command)

    def read_exact(self, *, case_id: str, checkpoint_ref: str) -> dict[str, Any]:
        return self.facade.get_checkpoint_version(case_id=case_id, checkpoint_ref=checkpoint_ref)

    def recovery_view(self, *, case_id: str) -> dict[str, Any]:
        versions = [
            row
            for row in self.facade.store.list_versions("canonical_artifact_versions", case_id=case_id)
            if row.get("artifact_type") == "runtime_checkpoint"
        ]
        versions.sort(key=lambda row: (str(row.get("artifact_id") or ""), int(row.get("artifact_version") or 0)))
        latest_by_id = {
            str(row["artifact_id"]): int(row["artifact_version"])
            for row in versions
        }
        records = [
            {
                "checkpoint_ref": row["artifact_version_id"],
                "checkpoint_id": row["artifact_id"],
                "checkpoint_version": row["artifact_version"],
                "supersedes_version_id": row.get("supersedes_version_id"),
                "producer_attempt_id": row["producer_attempt_id"],
                "checkpoint_schema_ref": row.get("checkpoint_schema_ref"),
                "checkpoint_state_digest": row.get("checkpoint_state_digest"),
                "is_latest": int(row["artifact_version"]) == latest_by_id[str(row["artifact_id"])],
            }
            for row in versions
        ]
        return {
            "scope": "Point01_M5_3_checkpoint_artifact_versioning_control_plane_only",
            "case_id": case_id,
            "checkpoint_count": len(records),
            "records": records,
            "worker_started": False,
            "model_call_count": 0,
            "external_call_count": 0,
        }

    def require_exact_checkpoint(self, *, case_id: str, checkpoint_ref: str) -> dict[str, Any]:
        """A named read boundary for future recovery callers; latest-only reads fail closed."""
        if ":v" not in checkpoint_ref:
            raise MissingDependency("checkpoint_exact_version_required")
        return self.read_exact(case_id=case_id, checkpoint_ref=checkpoint_ref)
