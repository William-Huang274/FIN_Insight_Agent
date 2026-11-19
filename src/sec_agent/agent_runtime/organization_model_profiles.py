"""Bind an opt-in organization harness profile to one already funded execution."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from uuid import UUID

from .research_budget import budget_from_host


class ProfileUnavailable(ValueError):
    pass


def host_settings(environment):
    path = environment.get("FINSIGHT_REPORT_SESSION_SETTINGS")
    return json.loads(Path(path).read_text(encoding="utf8")) if path else {}


def execution_profile(settings, environment, scope, tid, *, load_keys=False):
    binding = settings.get("organization_profile_bindings", {}).get(tid)
    if not binding:
        raise ProfileUnavailable("organization_profile_binding_missing")
    identity = {k: scope[k] for k in ("organization_id", "project_id", "draft_id", "manifest_digest")}
    if binding != identity or tid in settings.get("harness_execution_bindings", {}):
        raise ProfileUnavailable("organization_profile_scope_mismatch")
    org = str(UUID(identity["organization_id"]))
    owner = "organization:" + org
    budget = settings.get("model_budget_bindings", {}).get(tid) or {}
    template = deepcopy(settings.get("organization_model_profiles", {}).get("sol-high-flash", {}))
    common = {"token_budget_basis", "context_window", "output_tokens", "summary_tokens"}
    root_fields = common | {"binary", "binary_sha256", "research_delegate"}
    worker_fields = common | {"reservation_basis", "reservation_micros"}
    if (set(template) != root_fields or set(template["research_delegate"]) != worker_fields
            or budget.get("owner_id") != owner
            or not {"gpt-6.2-sol", "deepseek-flash"} <= {p["model"] for p in budget.get("prices", [])}):
        raise ProfileUnavailable("organization_profile_contract_incomplete")
    from .deepseek_structured_agents import TokenBudgetBasis
    from sec_agent.adapters.model_dispatch_store import amount
    for role in (template, template["research_delegate"]):
        TokenBudgetBasis.model_validate_json(json.dumps(role["token_budget_basis"]))
        if not all(type(role[k]) is int and 0 < role[k] < role["context_window"]
                   for k in ("output_tokens", "summary_tokens")):
            raise ProfileUnavailable("organization_profile_model_limits_invalid")
    for reservation in (budget["roles"]["lead"], template["research_delegate"]):
        amount(reservation["reservation_micros"], positive=True)
        if not reservation["reservation_basis"]:
            raise ProfileUnavailable("organization_profile_reservation_basis_required")
    fingerprint = json.dumps([tid, binding, template, budget], sort_keys=True, separators=(",", ":")).encode()
    reference = "sol-high-flash@" + sha256(fingerprint).hexdigest()
    if sha256(Path(template["binary"]).read_bytes()).hexdigest() != template["binary_sha256"]:
        raise ProfileUnavailable("organization_profile_binary_mismatch")
    directory = Path(environment["FINSIGHT_ORGANIZATION_MODEL_KEYS"]) / org
    keys = {"FINSIGHT_TASK_OPENAI_KEY": directory / "openai.key",
            "FINSIGHT_TASK_DEEPSEEK_KEY": directory / "deepseek.key"}
    if not all(path.is_file() and path.stat().st_size > 0 for path in keys.values()):
        raise ProfileUnavailable("organization_model_credentials_unavailable")
    template.update(model="gpt-6.2-sol", reasoning="high", protocol="openai_responses", provider="fin-openai",
        provider_endpoint="https://api.openai.com/v1/responses", provider_key_env="FINSIGHT_TASK_OPENAI_KEY",
        default_model_profile={"model": "gpt-6.2-sol", "reasoning": "high"}, manifest_digest=binding["manifest_digest"],
        allow_agent_consultation=True)
    template["research_delegate"].update(model="deepseek-flash", reasoning="high", protocol="deepseek_messages",
        provider="deepseek-official", provider_endpoint="https://api.deepseek.com/anthropic/v1/messages", provider_key_env="FINSIGHT_TASK_DEEPSEEK_KEY")
    credentials = {name: path.read_text(encoding="ascii").strip() for name, path in keys.items()} if load_keys else {}
    if load_keys and not all(credentials.values()):
        raise ProfileUnavailable("organization_model_credentials_unavailable")
    return reference, template, credentials


def available_profiles(settings, environment, scope):
    rows = []
    for tid, binding in settings.get("organization_profile_bindings", {}).items():
        if not all(binding.get(key) == value for key, value in scope.items()):
            continue
        try:
            ref, _, _ = execution_profile(settings, environment, scope, tid)
            budget_from_host(settings, thread_id=tid, metadata={"owner_id": "organization:" + scope["organization_id"]},
                environment=environment)
        except Exception:
            # No secret paths, database errors or unrelated budget identities enter the catalogue.
            continue
        rows.append({"execution_id": tid, "runtime_profile": ref})
    return rows
