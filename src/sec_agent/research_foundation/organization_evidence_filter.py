"""Business scope supplied by a caller, never an authorization grant."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator


class OrganizationEvidenceFilter(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    reporting_entity: tuple[str, ...] = Field(default=(), max_length=8,
        description='Exact reporting entity names from original table headings, not the filing issuer by assumption. OR within this field.')
    statement_type: tuple[Literal['balance_sheet','cash_flow','income_statement'], ...] = ()
    statement_role: tuple[Literal['primary','supplemental','reconciliation'], ...] = ()
    consolidation: tuple[Literal['consolidated'], ...] = ()
    event_type: tuple[Literal['earnings_release','financing'], ...] = ()
    asset_scope: tuple[Literal['pension_plan','postretirement_plan','nuclear_decommissioning_trust','investment_fund'], ...] = ()
    table_topic: tuple[Literal['fair_value_measurements','asset_allocation'], ...] = ()
    exhibit_role: tuple[Literal['press_release','certification','interactive_data','debt_agreement','acquisition_agreement'], ...] = ()
    transaction_id: tuple[str,...] = Field(default=(), max_length=8,
        description='Explicit original security identifier, CUSIP:<9 characters> or ISIN:<12 characters>; no guessed issue identity.')
    unknown_policy: Literal['exclude','retain'] = Field(default='exclude',
        description='exclude requires a verified match; retain permits unresolved originals for exploration. Known conflicts are excluded in both. No matches is not proof of absent disclosure.')

    @model_validator(mode='after')
    def nonempty(self):
        if not any((self.reporting_entity,self.statement_type,self.statement_role,self.consolidation,
                    self.event_type,self.asset_scope,self.table_topic,self.exhibit_role,self.transaction_id)):
            raise ValueError('organization_evidence_filter_requires_constraint')
        if any(not n.strip() or len(n)>180 for n in self.reporting_entity):
            raise ValueError('organization_evidence_entity_name_invalid')
        return self

    @field_validator('transaction_id')
    @classmethod
    def identifier_shape(cls,values):
        import re
        if any(not re.fullmatch(r'(?:CUSIP:[A-Z0-9]{9}|ISIN:[A-Z0-9]{12})',v) for v in values):
            raise ValueError('organization_transaction_identifier_requires_original_labeled_id')
        return values
