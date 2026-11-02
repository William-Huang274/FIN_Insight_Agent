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
        elif isinstance(value,list):
            def matches(fields):
                return bool(value) and all(isinstance(r,dict) and fields<=set(r) for r in value)
            if matches({'id','full_name','owner','html_url','default_branch'}) and all(
                    isinstance(r['id'],int) and isinstance(r['full_name'],str) and
                    isinstance(r['owner'],dict) and isinstance(r['owner'].get('login'),str) for r in value):
                result.update(kind='github_repository_catalog',content_scope='repository_metadata_not_readme_or_source_code',
                    records=[dict(locator='/'+str(i),id=r['id'],full_name=r['full_name'],owner=r['owner']['login'],
                                  url=r['html_url'],default_branch=r['default_branch']) for i,r in enumerate(value)])
            elif matches({'id','number','title','body','repository_url','state','user'}) and all(
                    isinstance(r['id'],int) and isinstance(r['number'],int) and isinstance(r['repository_url'],str)
                    and isinstance(r['title'],str) and (r['body'] is None or isinstance(r['body'],str)) for r in value):
                result.update(kind='github_issue_pull_request_records',content_scope='saved_issue_or_pull_request_body_not_complete_discussion',
                    records=[dict(locator='/'+str(i),id=r['id'],number=r['number'],repository_url=r['repository_url'],
                                  record_role='pull_request' if isinstance(r.get('pull_request'),dict) else 'issue',
                                  body_locator='/'+str(i)+'/body') for i,r in enumerate(value)])
            elif matches({'id','modelId','sha','siblings','tags','author'}) and all(
                    isinstance(r['id'],str) and r['id']==r['modelId'] and isinstance(r['sha'],str)
                    and isinstance(r['siblings'],list) and isinstance(r['tags'],list) for r in value):
                result.update(kind='huggingface_model_catalog',content_scope='model_revision_and_file_metadata_not_model_card_or_weights',
                    records=[dict(locator='/'+str(i),model_id=r['id'],revision=r['sha'],files_locator='/'+str(i)+'/siblings')
                             for i,r in enumerate(value)])
            else:result.update(kind='unresolved_record_array',content_scope='schema_review_required')
            result.update(record_count=len(value),numeric_coercion=False)
        elif 'chart' in keys:result.update(kind='chart_response',content_scope='chart_schema_requires_time_series_contract')
        elif {'data','msg','status'}<=keys:result.update(kind='api_response_envelope',content_scope='status_and_payload_schema_require_review')
        elif {'cik','name','addresses'}<=keys:
            result.update(kind='sec_entity_profile',record_count=1,entity_identity={'cik':value['cik'],'name':value['name']},
                          content_scope='entity_registration_not_filing_body',numeric_coercion=False)
        elif {'metadata','observations'}<=keys and isinstance(value['metadata'],dict) and isinstance(value['observations'],list):
            result.update(kind='macro_observation_series',record_count=len(value['observations']),
                          series_identity=value['metadata'].get('id'),unit=value['metadata'].get('units'),
                          content_scope='saved_observations_not_historical_vintage_proof',numeric_coercion=False)
        elif {'data_table','filed_at','period_end','rows'}<=keys and isinstance(value['rows'],int):
            result.update(kind='sql_table_reference',record_count=0,declared_rows=value['rows'],
                          target_table=value['data_table'],filed_at=value['filed_at'],period_end=value['period_end'],
                          content_scope='reference_only_requires_sql_readback',numeric_coercion=False)
        elif {'indicators','meta','timestamp'}<=keys and isinstance(value['timestamp'],list):
            counts={'timestamp':len(value['timestamp'])}
            for group,items in value['indicators'].items():
                for i,item in enumerate(items):
                    for field,column in item.items():
                        if isinstance(column,list):counts[f'{group}/{i}/{field}']=len(column)
            result.update(kind='market_price_series',record_count=len(value['timestamp']),column_counts=counts,
                          column_lengths_consistent=len(set(counts.values()))<=1,
                          content_scope='saved_prices_require_currency_adjustment_and_timezone_validation',numeric_coercion=False)
        elif {'meta','splits','requested_range','reviewed_through'}<=keys and isinstance(value['splits'],dict):
            result.update(kind='split_event_review',record_count=len(value['splits']),
                          reviewed_through=value['reviewed_through'],content_scope='reviewed_range_not_all_corporate_actions',numeric_coercion=False)
        elif {'list','message','status'}<=keys and isinstance(value['list'],list):
            result.update(kind='financial_statement_api_response',record_count=len(value['list']),
                          provider_status=value['status'],success=value['status']=='000',
                          content_scope='accounts_require_receipt_period_unit_and_revision_validation',numeric_coercion=False)
        else:result.update(kind='unknown_json_schema',content_scope='raw_object_only')
    return result
