"""Normalize redundant tool identity, never model-selected research parameters."""
from copy import deepcopy


def complete_action_tag(model, arguments):
    """The registered tool must uniquely declare a string action constant.

    Only absence is recoverable. Explicit null, conflicting values, unknown
    tools and non-object arguments retain their normal validation errors.
    """
    if model is None or not isinstance(arguments, dict) or 'action' in arguments:
        return arguments, []
    field = model.model_json_schema().get('properties', {}).get('action', {})
    value = field.get('const')
    if field.get('type') != 'string' or not isinstance(value, str):
        return arguments, []
    return {**deepcopy(arguments), 'action': value}, [{
        'field': 'action', 'value': value, 'reason': 'missing_unique_tool_action_constant',
        'tool_name': model.__name__, 'original_arguments_preserved': True}]
