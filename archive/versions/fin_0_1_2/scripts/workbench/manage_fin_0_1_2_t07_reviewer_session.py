from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.fin_0_1_2_s4_t06_current_product_projection import (  # noqa: E402
    CurrentProductProjectionService,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t06_current_review_control import (  # noqa: E402
    CurrentProductReviewControlService,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t07_reviewer_packet import (  # noqa: E402
    CurrentProductReviewerPacketService,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t07_reviewer_session import (  # noqa: E402
    CurrentProductReviewerSessionService,
)
from sec_agent.workbench import default_store_path  # noqa: E402


def _service(db_path: Path) -> CurrentProductReviewerSessionService:
    projection = CurrentProductProjectionService.from_repository(ROOT)
    control = CurrentProductReviewControlService.from_repository(
        ROOT, projection, db_path
    )
    packet = CurrentProductReviewerPacketService.from_repository(
        ROOT, projection, control
    )
    return CurrentProductReviewerSessionService.from_repository(
        ROOT, packet, db_path
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Offline-only FIN 0.1.2 T07 reviewer session issuance/revocation. "
            "Never redirect issuance output into logs or tracked files."
        )
    )
    parser.add_argument(
        "--db-path", type=Path, default=default_store_path(ROOT)
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    issue = subparsers.add_parser("issue")
    issue.add_argument("--admin-actor", required=True)
    issue.add_argument("--reviewer-ref", required=True)
    issue.add_argument("--reviewer-role", required=True)
    issue.add_argument("--ttl-seconds", required=True, type=int)
    revoke = subparsers.add_parser("revoke")
    revoke.add_argument("--admin-actor", required=True)
    revoke.add_argument("--session-id", required=True)
    args = parser.parse_args()
    service = _service(args.db_path.resolve())
    if args.command == "revoke":
        service.revoke_session(
            admin_actor_ref=args.admin_actor, session_id=args.session_id
        )
        print("reviewer_session_revoked")
        return 0
    issued = service.issue_session(
        admin_actor_ref=args.admin_actor,
        reviewer_ref=args.reviewer_ref,
        reviewer_role=args.reviewer_role,
        ttl_seconds=args.ttl_seconds,
    )
    print("Store this credential in a password manager now; it is shown once.", file=sys.stderr)
    print(issued.credential)
    print(f"session_id={issued.session_id}", file=sys.stderr)
    print(f"expires_at={issued.expires_at}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
