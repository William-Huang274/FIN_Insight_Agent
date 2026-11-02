"""Typed record inventory for retained native objects, not financial inference."""
import json
from lxml import etree


def describe(document):
    route=document['route']; result=dict(route=route,chapter_applicability='not_applicable',quality_pass=False)
    if route=='structured_xml':
        root=etree.fromstring(document['structured_xml'].encode(),etree.XMLParser(resolve_entities=False,no_network=True))
        name=etree.QName(root).localname
        if root.tag=='rss':
            items=root.findall('./channel/item')
            result.update(kind='news_discovery_feed',records=[dict(locator=root.getroottree().getpath(e),
                title=e.findtext('title'),url=e.findtext('link'),published=e.findtext('pubDate'),description=e.findtext('description')) for e in items],
                content_scope='feed_entries_not_full_articles')
        elif name=='informationTable' and root.tag.startswith('{http://www.sec.gov/edgar/document/thirteenf/informationtable}'):
            records=[]
            for e in root:
                if etree.QName(e).localname!='infoTable':continue
                records.append(dict(locator=root.getroottree().getpath(e),fields=[dict(name=c.tag,text=c.text,
                    xml=etree.tostring(c,encoding='unicode',with_tail=False)) for c in e]))
            result.update(kind='sec_13f_information_table',records=records,content_scope='reported_holdings_not_cover_summary',numeric_coercion=False)
        elif name=='edgarSubmission':
            result.update(kind='sec_submission_form',content_scope='form_not_holdings_detail',records=[])
        else:result.update(kind='unknown_xml_schema',content_scope='raw_xml_only',records=[])
    else:
        value=document['structured_object']; keys=set(value) if isinstance(value,dict) else set()
        if {'cik','entityName','facts'}<=keys:
            collections=[]
            for taxonomy,concepts in value['facts'].items():
                for concept,definition in concepts.items():
                    for unit,rows in definition.get('units',{}).items():
                        escape=lambda s:str(s).replace('~','~0').replace('/','~1')
                        collections.append(dict(locator='/facts/'+escape(taxonomy)+'/'+escape(concept)+'/units/'+escape(unit),
                            taxonomy=taxonomy,concept=concept,unit=unit,record_count=len(rows)))
            result.update(kind='sec_companyfacts',collections=collections,record_count=sum(c['record_count'] for c in collections),
                content_scope='reported_facts_require_period_dimension_revision_validation',numeric_coercion=False)
        elif {'cik','filings'}<=keys:
            recent=value['filings'].get('recent',{});counts={k:len(v) for k,v in recent.items() if isinstance(v,list)}
            result.update(kind='sec_submission_catalog',record_count=counts.get('accessionNumber',0),
                recent_column_counts=counts,column_lengths_consistent=len(set(counts.values()))<=1,
                content_scope='filing_metadata_not_filing_body')
        elif isinstance(value,list):result.update(kind='unresolved_record_array',record_count=len(value),content_scope='schema_review_required')
        elif 'chart' in keys:result.update(kind='chart_response',content_scope='chart_schema_requires_time_series_contract')
        elif {'data','msg','status'}<=keys:result.update(kind='api_response_envelope',content_scope='status_and_payload_schema_require_review')
        else:result.update(kind='unknown_json_schema',content_scope='raw_object_only')
    return result
