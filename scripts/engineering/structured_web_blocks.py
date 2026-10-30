"""Normalize extracted XML elements, including meaningful text in their tails.

An element serialized with its tail is an XML fragment, not an XML document.
Retain that text separately rather than dropping it to make parsing succeed.
"""
import re
from xml.etree import ElementTree as ET


def normalize_web(output):
    blocks=[]
    for row in output['blocks']:
        wrapper=ET.fromstring('<fragment>'+row['xml']+'</fragment>')
        if len(wrapper)!=1:raise ValueError('expected_one_extracted_element')
        element=wrapper[0];kind=row['kind']
        if kind=='head':
            match=re.fullmatch(r'h([1-6])',element.get('rend',''))
            blocks.append({'kind':'heading','text':row['text'],'level':int(match[1]) if match else None,
                           'heading_basis':'trafilatura_rend' if match else 'unknown_level'})
        elif kind=='table':
            rows=[]
            for tr in element.iter('row'):
                rows.append([{'text':''.join(c.itertext()),'rowspan':c.get('rowspan'),
                              'colspan':c.get('colspan')} for c in tr])
            blocks.append({'kind':'table','text':row['text'],'rows':rows,'headers':[],
                           'structure_gap':'xml_table_spans_not_guaranteed'})
        else:blocks.append({'kind':'text','text':row['text']})
        if element.tail and element.tail.strip():
            blocks.append({'kind':'text','text':element.tail,'basis':'extracted_xml_element_tail'})
    return blocks
