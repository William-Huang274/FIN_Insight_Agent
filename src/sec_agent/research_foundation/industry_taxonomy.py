"""Shared navigation semantics; categories never confer factual authority."""
import re

# Navigation translations, not cross-taxonomy accounting equivalences. Keep the
# SEC concept and raw source label alongside them. ECD/FFD definitions and
# regulatory references are published in xbrl.sec.gov/{ecd,ffd}/2026 schemas.
METRIC_NAMES = {
    'ecd:CoSelectedMeasureAmt':'公司选定的绩效指标值',
    'ecd:NonPeoNeoAvgCompActuallyPaidAmt':'其他具名高管平均实际支付薪酬（SEC口径）',
    'ecd:NonPeoNeoAvgTotalCompAmt':'其他具名高管平均薪酬总额',
    'ecd:PeerGroupTotalShareholderRtnAmt':'同业组股东总回报值',
    'ecd:PeoActuallyPaidCompAmt':'首席执行官实际支付薪酬（SEC口径）',
    'ecd:PeoTotalCompAmt':'首席执行官薪酬总额',
    'ecd:TotalShareholderRtnAmt':'股东总回报值',
    'ffd:NetFeeAmt':'应缴注册费净额',
    'ffd:NrrtvMaxAggtOfferingPric':'最大发行总价（披露口径）',
    'ffd:TtlFeeAmt':'注册费总额','ffd:TtlOfferingAmt':'发行总金额',
    'ffd:TtlOffsetAmt':'抵扣总额','ffd:TtlPrevslyPdAmt':'此前已支付总额',
}

MATERIAL_GROUPS = {
    'disclosures': ('公司披露', {'filing','annual_report','annual_report_mirror','official_report','filing_exhibit','earnings_release','legacy_10-K','legacy_10-Q','legacy_8-K','company_profile','sec_submissions','filing_directory'}),
    'products': ('业务与产品', {'model_product','product_platform','industry_ecosystem','model_card','model_catalogue','community_repository','repository_readme','product_specification'}),
    'transactions': ('交易与合作', {'relationship_announcement','financing_announcement','power_contract','infrastructure_project'}),
    'capital': ('机构持仓与资本数据', {'institutional_positions','institutional_notice'}),
    'market': ('财务与行情数据', {'financial_api','market_api'}),
    'policy': ('政策与宏观', {'policy_regulation','policy_current_rule','macro_series','macro_release'}),
    'feedback': ('新闻与外部反馈', {'news_discovery','news_article','community_feedback','official_social_post'}),
    'other': ('其他资料', set()),
}
FINANCIAL_GROUPS = {'operating':'经营财务', 'offering':'发行与注册费用',
                    'compensation':'薪酬与治理', 'macro':'宏观数据', 'other':'其他原始指标'}


def material_group(category):
    return next((key for key, (_, values) in MATERIAL_GROUPS.items() if category in values), 'other')


def profile(row, card):
    """Older snapshots remain readable without pretending classification is done."""
    kind = card.get('profile_type', 'macro_collection' if row['entity_id']=='INSTITUTION::macro' else 'company')
    return {'type':kind, 'roles':card.get('roles', ['company'] if kind=='company' else []),
            'institution_type':card.get('institution_type'), 'country':row.get('country'),
            'jurisdiction':card.get('jurisdiction'), 'identity_basis':card.get('identity_basis'),
            'registration_country':card.get('registration_country'),
            'classification_status':card.get('classification_status','legacy_navigation_only')}


def financial_group_sql():
    # SEC taxonomy namespaces separate filing fees and executive compensation
    # from operating financial statements; no metric meaning is inferred here.
    return "CASE WHEN taxonomy='ffd' THEN 'offering' WHEN taxonomy='ecd' THEN 'compensation' WHEN lower(taxonomy) LIKE '%fred%' THEN 'macro' WHEN taxonomy IN ('us-gaap','ifrs-full','DART-IFRS','issuer-reported') THEN 'operating' ELSE 'other' END"


def financial_identity(row):
    raw = row.get('label')
    row['raw_label'] = raw
    row['label'] = str(raw).strip() if raw and str(raw).strip() else f"{row['taxonomy']}:{row['concept']}"
    row['label_status'] = 'source_label' if raw and str(raw).strip() else 'runtime_compatibility_parse:original_concept_fallback'
    code=f"{row['taxonomy']}:{row['concept']}"
    row['display_label']=METRIC_NAMES.get(code) or (row['label'] if row['label']!=code else re.sub(r'(?<=[a-z0-9])(?=[A-Z])',' ',row['concept']))
    row['display_label_basis']='reviewed_navigation_translation' if code in METRIC_NAMES else row['label_status']
    row['metric_identity']=code
    row['comparison_status']='source_metric_not_cross_company_equivalence'
    return row


def source_navigation(source):
    meta = source['metadata']
    source['material_group'] = material_group(source['category'])
    source['material_group_label'] = MATERIAL_GROUPS[source['material_group']][0]
    source['relevance_status'] = meta.get('relevance_review', {}).get('status',
        'needs_review' if source['category']=='policy_regulation' else 'not_screened')
    if source['category']=='policy_regulation':
        group={'needs_review':('policy_review','政策 · 适用性待核实'), 'out_of_scope':('policy_excluded','政策 · 当前主题不适用')}.get(source['relevance_status'])
        if group:source['material_group'],source['material_group_label']=group
    source['publisher_names'] = [a.get('name') or a.get('raw_name') for a in meta.get('agencies', []) if a.get('name') or a.get('raw_name')]
    return source
