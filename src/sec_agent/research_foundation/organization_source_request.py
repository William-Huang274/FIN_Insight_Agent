"""Capability view of the shared source protocol for fixed organization inputs.

Archived neutral fields remain readable; the model sees only usable parameters.
No source-space aliasing or authority broadening is performed.
"""
from typing import ClassVar, Literal
from pydantic import Field, model_validator

from .source_document_navigation import SourceDocumentToolRequest


class OrganizationSourceRequest(SourceDocumentToolRequest):
    source_space: Literal['organization'] = Field(default='organization',
        description='The execution-bound organization publications, including its fixed retrieval scope. No local, public-library, upload or web route is available through this tool.')
    operation: Literal['catalog', 'outline', 'search', 'read'] = Field(
        description='catalog discovers documents by company/ticker; outline lists sections of a returned document; search finds candidate passages; read retrieves citable original windows. Copy returned document/node IDs and readback parameters.')
    query: str = Field(default='', max_length=600,
        description='Catalog: company name/ticker or empty. Search: research keywords. Use returned organization metadata for explicit source filters; do not invent document IDs.')
    offset: int = Field(default=0, ge=0, description='Result-row pagination. Copy the returned next request.')
    character_offset: int | None = Field(default=None, ge=0,
        description='Character window inside a returned node for read; copy readback/next_readback. A window need not contain the complete table.')
    graph_depth: Literal[1] = 1
    public_fields: ClassVar[frozenset[str]] = frozenset({
        'source_space', 'operation', 'query', 'document_id', 'node_id', 'offset', 'character_offset',
        'limit', 'max_characters', 'organization_filter', 'organization_metadata_policy',
        'organization_query_planning', 'entity_id', 'graph_depth', 'graph_predicates',
        'graph_direction', 'graph_review'})

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        schema = handler(core_schema)
        schema['properties'] = {k:v for k,v in schema['properties'].items() if k in cls.public_fields}
        schema['required'] = [k for k in schema.get('required', []) if k in cls.public_fields]
        return schema

    @model_validator(mode='after')
    def reject_unavailable_parameters(self):
        # Full legacy readback dictionaries contain neutral default fields. Keep
        # these compatible, but never silently discard an active unsupported filter.
        for name, info in type(self).model_fields.items():
            if name not in self.public_fields and getattr(self, name) != info.get_default(call_default_factory=True):
                raise ValueError('organization_parameter_not_available:' + name)
        return self
