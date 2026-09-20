"""Shared navigation semantics; categories never confer factual authority."""

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
    return "CASE WHEN taxonomy='ffd' THEN 'offering' WHEN taxonomy='ecd' THEN 'compensation' WHEN lower(taxonomy) LIKE '%fred%' THEN 'macro' WHEN taxonomy IN ('us-gaap','ifrs-full','DART-IFRS') THEN 'operating' ELSE 'other' END"


def financial_identity(row):
    raw = row.get('label')
    row['raw_label'] = raw
    row['label'] = str(raw).strip() if raw and str(raw).strip() else f"{row['taxonomy']}:{row['concept']}"
    row['label_status'] = 'source_label' if raw and str(raw).strip() else 'runtime_compatibility_parse:original_concept_fallback'
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
