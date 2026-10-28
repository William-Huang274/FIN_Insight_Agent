"""Explicit source metadata constraints, separate from graph counterparties.

Only original metadata is consumed. Titles, publication dates and parent filing
forms cannot silently stand in for issuer, fiscal period or exhibit identity.
"""
from datetime import date
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, model_serializer


class OrganizationSourceFilter(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    issuer_id: str | None = Field(default=None, min_length=1, max_length=200)
    company_name: str | None = Field(default=None, min_length=1, max_length=300)
    form: str | None = Field(default=None, min_length=1, max_length=40)
    period_end: date | None = None
    publication_date: date | None = None
    published_from: date | None = None
    published_through: date | None = None

    @model_serializer(mode='wrap')
    def preserve_original_filter(self, handler):
        body=handler(self)
        for key in ('publication_date','published_from','published_through'):
            if key not in self.model_fields_set:
                body.pop(key,None)
        return body

    @field_validator('period_end','publication_date','published_from','published_through', mode='before')
    @classmethod
    def exact_date(cls, value):
        if value is None or type(value) is date:
            return value
        if not isinstance(value, str) or len(value) != 10:
            raise ValueError('organization_period_end_requires_iso_date')
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError('organization_period_end_requires_iso_date')
        return parsed

    @field_validator('issuer_id', 'company_name', 'form')
    @classmethod
    def normalize(cls, value, info):
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError('organization_filter_value_empty')
        return value.upper() if info.field_name == 'form' else value

    @model_validator(mode='after')
    def nonempty(self):
        if self.published_from and self.published_through and self.published_from>self.published_through:
            raise ValueError('organization_publication_range_invalid')
        if all(v is None for v in self.model_dump().values()):
            raise ValueError('organization_filter_requires_constraint')
        return self


class OrganizationSourceFilterReceipt(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    filter: OrganizationSourceFilter
    scope_sources: int = Field(ge=0)
    matched_sources: int = Field(ge=0)
    unknown_sources: int = Field(ge=0)
    mismatched_sources: int = Field(ge=0)
    metadata_missing_is_not_source_absence: Literal[True] = True
    metadata_policy: Literal['original.v1', 'sec_cover.v2'] = 'original.v1'


def original_source_metadata(bundle):
    """A small descriptor derived from the already verified source bundle."""
    metadata = json.loads(bundle['source']['metadata']) if bundle else {}
    def text(key):
        value = metadata.get(key)
        return value.strip() if isinstance(value, str) and value.strip() else None
    period = text('period_end')
    try:
        normalized = date.fromisoformat(period).isoformat() if period and len(period) == 10 else None
        period = period if normalized == period else None
    except ValueError:
        period = None
    form = text('form')
    result={'issuer_id': text('entity_id'), 'company_name': text('company'),
            'form': form.upper() if form else None, 'period_end': period}
    # Publication remains a separate observation; never substitute period_end.
    published=bundle['source'].get('published_at') if bundle else None
    if isinstance(published,str):
        try:
            value=date.fromisoformat(published)
            if value.isoformat()==published:result['publication_date']=published
        except ValueError:pass
    return result


def source_metadata_details(bundle):
    """Resolve only an explicit original cover, retaining conflicts as unknown."""
    descriptor = original_source_metadata(bundle)
    proof = None
    if bundle:
        from retrieval.catalog_company_identity import cover_names
        recovered_names = cover_names(bundle.get('text', ''))
        if len(recovered_names) == 1:
            descriptor['verified_company_names'] = recovered_names
        elif recovered_names:
            descriptor['company_name_resolution'] = 'joint_registrants_not_a_unique_owner'
        from .sec_cover_metadata import cover_form, calendar_annual_year
        from retrieval.filing_document_identity import original_filing_key
        if key := original_filing_key(bundle['source'].get('url')):
            descriptor['original_filing_key'] = key
        metadata = json.loads(bundle['source']['metadata'])
        cik = metadata.get('cik')
        if (not recovered_names or len(recovered_names)==1) and isinstance(cik,(str,int)) and not isinstance(cik,bool):
            digits=str(cik).strip()
            if digits.isascii() and digits.isdigit() and 0<len(digits)<=10 and int(digits)>0:
                descriptor['fact_entity_identifiers']=[{'scheme':'http://www.sec.gov/CIK',
                    'identifier':str(int(digits)), 'basis':'original_source_metadata_cik'}]
        # A discovery catalogue is a known evidence role, not an unknown
        # filing form. Keep this original marker; never infer it from a title
        # or from absence of an article body in an arbitrary document.
        if metadata.get('evidence_role') == 'discovery_metadata_only':
            descriptor['evidence_role'] = 'discovery_metadata_only'
        evidence = cover_form(bundle, metadata)
        if evidence:
            previous = descriptor['form']
            conflict = previous is not None and previous != evidence['form']
            descriptor['form'] = None if conflict else evidence['form']
            proof = {**evidence, 'metadata_form': previous,
                'status': 'conflict' if conflict else 'confirmed' if previous else 'recovered'}
            annual = calendar_annual_year(bundle, descriptor, evidence)
            if annual is not None:
                descriptor['calendar_annual_year'] = annual['year']
                proof['calendar_annual_year'] = annual
    from retrieval.catalog_company_identity import with_original_registrant_identity
    return with_original_registrant_identity(descriptor), proof


def source_metadata(bundle):
    return source_metadata_details(bundle)[0]


def select_documents(metadata, constraint):
    """Conjunction over exact original fields; unknown stays explicitly unknown."""
    wanted = constraint.model_dump(mode='json', exclude_none=True)
    matches, unknown = set(), 0
    from retrieval.catalog_company_identity import aliases_for, name_key
    for document, actual in metadata.items():
        verified_names = [n for n in [actual.get('company_name'), *(actual.get('verified_company_names') or [])] if n]
        def field_matches(key,value):
            if key=='company_name':
                return name_key(value) in {name_key(a) for n in verified_names for a in aliases_for({'company_name':n})}
            if key=='published_from':return actual['publication_date']>=value
            if key=='published_through':return actual['publication_date']<=value
            return actual[key]==value
        if any((not verified_names if key == 'company_name' else actual.get(
                'publication_date' if key in {'published_from','published_through'} else key) is None) for key in wanted):
            unknown += 1
            continue
        if all(field_matches(key,value) for key,value in wanted.items()):
            matches.add(document)
    return matches, {'filter': wanted, 'scope_sources': len(metadata),
                     'matched_sources': len(matches), 'unknown_sources': unknown,
                     'mismatched_sources': len(metadata) - len(matches) - unknown,
                     'metadata_missing_is_not_source_absence': True}


def filter_notice(receipt):
    return (' Organization source filter: ' + json.dumps(receipt, ensure_ascii=False, sort_keys=True)
            + '. Unknown metadata is excluded, not evidence that the requested disclosure does not exist.')
