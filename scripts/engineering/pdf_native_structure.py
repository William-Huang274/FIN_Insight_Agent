"""Consume local PDF text geometry and table candidates without OCR/models."""
from collections import Counter
import inspect
import math

from ingestion.pdf_panel_candidates import source_panel_candidates


def describe_page(page):
    # TEXTFLAGS_TEXT excludes embedded image bytes; image locations are separate.
    import pymupdf
    from pymupdf.table import find_tables
    native=page.get_text('dict',flags=pymupdf.TEXTFLAGS_TEXT,sort=False)
    blocks=native.get('blocks',[])
    directions=Counter()
    for b in blocks:
        for line in b.get('lines',[]):
            direction=line.get('dir',(1,0));angle=round(math.degrees(math.atan2(direction[1],direction[0])))%360
            directions[str(angle)]+=sum(len(s.get('text','')) for s in line.get('spans',[]))
    panels=source_panel_candidates(page)
    tables=[];errors=[]
    try:
        options={'strategy':'lines'}
        if 'use_layout' in inspect.signature(find_tables).parameters:
            options['use_layout']=False
        elif getattr(pymupdf,'_get_layout',None) is not None:
            raise RuntimeError('active_layout_hook_cannot_be_disabled_for_this_table_api')
        found=page.find_tables(**options)
        for i,t in enumerate(found.tables):
            tables.append(dict(index=i,bbox=list(t.bbox),cells=[list(c) if c is not None else None for c in t.cells],
                rows=t.extract(),row_count=t.row_count,column_count=t.col_count,
                header=dict(names=t.header.names,bbox=list(t.header.bbox),external=t.header.external),
                role='ruled_table_candidate_not_financial_fact',method='pymupdf_native_lines'))
    except Exception as exc:errors.append(dict(stage='native_ruled_tables',error=type(exc).__name__,detail=str(exc)))
    images=[dict(bbox=list(x['bbox']),width=x.get('width'),height=x.get('height')) for x in page.get_image_info()]
    return dict(page=page.number+1,width=page.cropbox.width,height=page.cropbox.height,rotation=page.rotation,
        visible_page_rect=list(page.rect),cropbox=list(page.cropbox),rotation_matrix=list(page.rotation_matrix),
        derotation_matrix=list(page.derotation_matrix),
        coordinate_namespace='original_pdf_page_unrotated_native_coordinates',text_blocks=blocks,
        line_direction_character_counts=dict(directions),panels=panels,tables=tables,images=images,errors=errors,
        limitations=['heading_hierarchy_unreviewed','global_reading_order_unreviewed','unruled_tables_require_supplement',
                     'table_header_footnote_relations_unreviewed','image_text_not_ocr_processed'],
        quality_pass=False,ocr_calls=0,model_calls=0,table_layout_model_enabled=False)
