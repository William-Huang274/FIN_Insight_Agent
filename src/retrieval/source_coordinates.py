"""Keep complete-document and imported-node coordinate spaces distinct."""

VERIFIED = {'verified_original_coordinates','verified_original_node_coordinates'}


def origin_bounds(origin):
    if 'source_char_start' in origin:
        start,end=origin.get('source_char_start'),origin.get('source_char_end')
        space=None  # Caller additionally binds the immutable document/digest.
    else:
        start,end=origin.get('char_start'),origin.get('char_end')
        space=origin.get('original_node_id')
        if not space:raise ValueError('source_coordinate_space_missing')
    if type(start) is not int or type(end) is not int or not 0<=start<end:
        raise ValueError('source_coordinate_interval_invalid')
    return space,start,end


def verified_bounds(row):
    structure=row.get('source_structure',{})
    if structure.get('status') not in VERIFIED:raise ValueError('source_coordinates_not_verified')
    space,start,end=origin_bounds(row['original_source'])
    if structure['status']=='verified_original_node_coordinates':
        if not space or structure.get('coordinate_space',{}).get('original_node_id')!=space:
            raise ValueError('source_coordinate_node_identity_mismatch')
    elif space is not None:
        raise ValueError('source_coordinate_document_identity_mismatch')
    return space,start,end
