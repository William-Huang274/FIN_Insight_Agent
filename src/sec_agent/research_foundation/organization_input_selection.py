"""Separate focal documents from the frozen searchable dependency set.

Every candidate remains a current-ACL dependency. This contract does not grant
implicit access to a team space, follow latest versions, or filter away denial.
"""
from uuid import UUID

MAX_RETRIEVAL_RESOURCES = 2048


def validate_input_selection(manifest):
    ids = [str(UUID(item['resource_id'])) for item in manifest['inputs']]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate_frozen_input')
    selection = manifest.get('input_selection')
    if 'input_selection' not in manifest:
        if not 1 <= len(ids) <= 12:
            raise ValueError('legacy_input_count')
        return ids
    if (not isinstance(selection, dict) or set(selection) != {
            'contract_version', 'selected_resource_ids', 'retrieval_resource_ids'}
            or selection['contract_version'] != 'organization_input_selection.v1'):
        raise ValueError('input_selection_contract')
    selected, searchable = selection['selected_resource_ids'], selection['retrieval_resource_ids']
    if not isinstance(selected, list) or not isinstance(searchable, list):
        raise ValueError('input_selection_lists')
    if (not 1 <= len(selected) <= 12 or not 1 <= len(searchable) <= MAX_RETRIEVAL_RESOURCES
            or len(set(selected)) != len(selected) or len(set(searchable)) != len(searchable)
            or not set(selected) <= set(searchable) or set(searchable) != set(ids)
            or any(str(UUID(value)) != value for value in selected + searchable)):
        raise ValueError('input_selection_scope')
    return selected
