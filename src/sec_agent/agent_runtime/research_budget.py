"""Host-owned binding of one research root to role budgets; no model authority."""
from .model_dispatch_guard import ModelDispatchGuard, TokenPrices
from sec_agent.adapters.model_dispatch_store import DispatchBlocked, ModelDispatchStore


class ResearchBudget:
    def __init__(self, store, *, owner, budget, prices, roles):
        self.store, self.owner, self.budget = store, owner, budget
        self.prices, self.roles = dict(prices), dict(roles)

    def guard(self, role, profile):
        policy = self.roles.get(role)
        prices = self.prices.get(profile.model)
        if not isinstance(policy, dict) or prices is None:
            raise DispatchBlocked('research_role_budget_not_authorized')
        if set(policy) != {'reservation_micros', 'reservation_basis', 'delivery'} or type(policy['delivery']) is not bool:
            raise DispatchBlocked('research_role_budget_policy_invalid')
        return ModelDispatchGuard(self.store, owner=self.owner, budget=self.budget, prices=prices, **policy)


def budget_from_host(settings, *, thread_id, metadata, environment):
    """Only mounted host settings bind thread/owner/root. Native input cannot mint money.

    Budgets must already exist in PostgreSQL. Enabling bindings makes missing or
    mismatching threads fail closed; there is no local-pilot owner fallback.
    """
    bindings = settings.get('model_budget_bindings')
    if bindings is None:
        return None
    binding = bindings.get(thread_id) if isinstance(bindings, dict) else None
    if not isinstance(binding, dict) or not metadata.get('owner_id') or binding.get('owner_id') != metadata['owner_id']:
        raise DispatchBlocked('research_budget_owner_binding_missing')
    dsn = environment.get('FIN_MODEL_BUDGET_POSTGRES_URI')
    if not dsn:
        raise DispatchBlocked('dedicated_model_budget_database_required')
    store = ModelDispatchStore(dsn)
    store.require_runtime_role()
    snapshot = store.snapshot(binding['owner_id'], binding['budget_id'])
    prices = {row['model']: TokenPrices(**row) for row in binding['prices']}
    if not prices or any(price.currency != snapshot['currency'] for price in prices.values()):
        raise DispatchBlocked('research_budget_price_currency_mismatch')
    return ResearchBudget(store, owner=binding['owner_id'], budget=binding['budget_id'],
                          prices=prices, roles=binding['roles'])
