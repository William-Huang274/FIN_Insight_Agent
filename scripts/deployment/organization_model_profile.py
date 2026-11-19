"""Generate, fund and verify the optional organization Sol/Flash execution profile."""
import argparse
from copy import deepcopy
from sec_agent.agent_runtime.model_execution_policy import file_sha256
import json
import os
from pathlib import Path
from uuid import UUID

from sec_agent.adapters.model_dispatch_store import ModelDispatchStore, amount
from sec_agent.agent_runtime.model_dispatch_guard import TokenPrices
from sec_agent.agent_runtime.organization_model_profiles import execution_profile
from sec_agent.agent_runtime.research_budget import budget_from_host

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def prepare(args):
    settings = read(args.settings)
    executable = args.binary.resolve(strict=True)
    if file_sha256(executable) != args.binary_sha256:
        raise ValueError("harness_release_checksum_mismatch")
    if not args.task_scope.strip() or not args.price_version.strip():
        raise ValueError("task_scope_and_dated_price_source_required")
    source = read(args.roles)["nodes"]
    template = {}
    prices = []
    for role, model, window, rates in [
        ("lead", "gpt-6.2-sol", args.lead_window, args.lead_prices),
        ("specialist", "deepseek-flash", args.investigator_window, args.investigator_prices),
    ]:
        basis = deepcopy(source[role]["budget"])
        basis["reasoning_profile"] = "agentic_message_history_thinking_enabled"
        basis["comparable_run_evidence"] = (
            "Operator-selected continuous research profile using the shipped research role contract. "
            "Model capacity and pricing come from deployment inputs. Cross-model output quality requires separate acceptance."
        )
        output = basis["max_output_tokens"]
        if not isinstance(output, int) or not 0 < output < window or not 0 < args.summary_tokens < window:
            raise ValueError("invalid_profile_capacity")
        config = dict(token_budget_basis=basis, context_window=window, output_tokens=output, summary_tokens=args.summary_tokens)
        if role == "lead":
            template.update(config, binary=str(executable), binary_sha256=args.binary_sha256)
        else:
            config.update(reservation_micros=amount(args.investigator_reservation, positive=True),
                reservation_basis="Pre-authorized single investigator request under the shared execution budget.")
            template["research_delegate"] = config
        price = TokenPrices(args.price_version, model, args.currency, *rates)
        prices.append(vars(price))
    profiles = settings.setdefault("organization_model_profiles", {})
    if "sol-high-flash" in profiles and profiles["sol-high-flash"] != template:
        raise ValueError("existing_profile_differs_create_a_separate_settings_revision")
    profiles["sol-high-flash"] = template
    tid = str(args.execution)
    binding = dict(organization_id=str(args.organization), project_id=str(args.project),
        draft_id=str(args.draft), manifest_digest=args.manifest)
    import re
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", args.manifest):
        raise ValueError("invalid_manifest_digest")
    budget = dict(owner_id="organization:" + str(args.organization), budget_id=tid,
        roles={"lead": dict(reservation_basis=args.task_scope, reservation_micros=amount(args.lead_reservation, positive=True), delivery=False)},
        prices=prices)
    for table, entry in [("model_budget_bindings", budget), ("organization_profile_bindings", binding)]:
        bindings = settings.setdefault(table, {})
        if tid in bindings and bindings[tid] != entry:
            raise ValueError("existing_execution_binding_differs")
        bindings[tid] = entry
    if tid in settings.get("harness_execution_bindings", {}):
        raise ValueError("execution_already_has_a_private_harness_binding")
    # Explicit output path. Never replace a live settings file or expose owner material.
    with open(args.out, "x", encoding="utf8", opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
        stream.write(json.dumps(settings, ensure_ascii=False, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    configure = commands.add_parser("prepare", help="Write settings to a new private file. No DB or model access.")
    fund = commands.add_parser("fund", help="Explicitly authorize a budget in the provisioner database. No provider call.")
    check = commands.add_parser("check", help="Run production profile and runtime-role budget checks. No provider call.")
    for entry in [configure, fund, check]:
        entry.add_argument("--settings", type=Path, required=True)
        entry.add_argument("--execution", type=UUID, required=True)
    configure.add_argument("--out", type=Path, required=True)
    configure.add_argument("--roles", type=Path, default=ROOT / "configs/research/runtime/research_session.json")
    configure.add_argument("--binary", type=Path, required=True)
    configure.add_argument("--binary-sha256", required=True)
    for name in ("organization", "project", "draft"):
        configure.add_argument("--" + name, type=UUID, required=True)
    for name in ("manifest", "task-scope", "price-version", "currency"):
        configure.add_argument("--" + name, required=True)
    for name in ("lead-window", "investigator-window", "summary-tokens", "lead-reservation", "investigator-reservation"):
        configure.add_argument("--" + name, type=int, required=True)
    for name in ("lead-prices", "investigator-prices"):
        configure.add_argument("--" + name, type=int, nargs=3, metavar=("INPUT_MISS", "INPUT_HIT", "OUTPUT"), required=True)
    fund.add_argument("--authorized-micros", type=int, required=True)
    fund.add_argument("--delivery-floor-micros", type=int, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args)
        print("Private settings prepared.")
        return
    settings = read(args.settings)
    tid = str(args.execution)
    scope = settings["organization_profile_bindings"][tid]
    reference, _, _ = execution_profile(settings, os.environ, scope, tid)
    budget = settings["model_budget_bindings"][tid]
    if args.command == "fund":
        store = ModelDispatchStore(os.environ["FIN_MODEL_BUDGET_PROVISIONER_URI"])
        store.create_budget(budget["owner_id"], budget["budget_id"], budget["prices"][0]["currency"],
            args.authorized_micros, args.delivery_floor_micros)
        print("Execution budget authorized.")
    else:
        budget_from_host(settings, thread_id=tid, metadata={"owner_id": budget["owner_id"]}, environment=os.environ)
        print(json.dumps({"execution_id": tid, "runtime_profile": reference}))


if __name__ == "__main__":
    main()
