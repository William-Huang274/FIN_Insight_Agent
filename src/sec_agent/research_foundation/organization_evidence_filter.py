"""Business scope supplied by a caller, never an authorization grant."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class OrganizationEvidenceFilter(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    reporting_entity: tuple[str, ...] = Field(default=(), max_length=8,
        description='Exact reporting entity names from original table headings, not the filing issuer by assumption. OR within this field.')
    statement_type: tuple[Literal['balance_sheet','cash_flow','income_statement'], ...] = ()
    statement_role: tuple[Literal['primary','supplemental','reconciliation'], ...] = ()
    consolidation: tuple[Literal['consolidated'], ...] = ()
    event_type: tuple[Literal['earnings_release','financing'], ...] = ()
    unknown_policy: Literal['exclude','retain'] = Field(default='exclude',
        description='exclude requires a verified match; retain permits unresolved originals for exploration. Known conflicts are excluded in both. No matches is not proof of absent disclosure.')

    @model_validator(mode='after')
    def nonempty(self):
        if not any((self.reporting_entity,self.statement_type,self.statement_role,self.consolidation,self.event_type)):
            raise ValueError('organization_evidence_filter_requires_constraint')
        if any(not n.strip() or len(n)>180 for n in self.reporting_entity):
            raise ValueError('organization_evidence_entity_name_invalid')
        return self
