"""Reviewed navigation of reporting concepts, not an accounting consolidation.

A concept may be disclosed in several statements/notes. This menu describes its
economic subject; it does not recreate the issuer's presentation linkbase or sum
its children. Unknown extensions remain visible and cannot enter calculations.
"""
VERSION = 'financial_accounts.v2'
LABELS = {
    'balance':'资产负债表', 'balance/assets':'资产',
    'balance/assets/current':'流动资产', 'balance/assets/noncurrent':'非流动资产',
    'balance/assets/total':'资产合计', 'balance/liabilities':'负债',
    'balance/liabilities/current':'流动负债', 'balance/liabilities/noncurrent':'非流动负债',
    'balance/liabilities/total':'负债合计', 'balance/equity':'所有者权益',
    'balance/equity/capital':'股本及资本公积', 'balance/equity/retained':'留存收益与其他综合收益',
    'balance/equity/total':'权益及负债权益合计',
    'income':'利润表', 'income/revenue':'收入与成本', 'income/revenue/sales':'营业收入',
    'income/revenue/cost':'营业成本', 'income/revenue/gross':'毛利',
    'income/expenses':'费用与损益', 'income/expenses/operating':'经营费用',
    'income/expenses/nonoperating':'非经营损益', 'income/expenses/tax':'所得税',
    'income/profit':'利润与每股收益', 'income/profit/operating':'经营利润',
    'income/profit/pretax':'税前利润', 'income/profit/net':'净利润',
    'income/profit/eps':'每股收益及加权股数',
    'cashflow':'现金流量表', 'cashflow/operating':'经营活动',
    'cashflow/operating/net':'经营现金流净额', 'cashflow/operating/adjustments':'非现金调整及营运资本',
    'cashflow/investing':'投资活动', 'cashflow/investing/net':'投资现金流净额',
    'cashflow/investing/capex':'购建长期资产支出', 'cashflow/investing/other':'投资与处置',
    'cashflow/financing':'筹资活动', 'cashflow/financing/net':'筹资现金流净额',
    'cashflow/financing/capital':'融资、回购与分配',
    'cashflow/reconciliation':'现金变动与调节', 'cashflow/reconciliation/change':'现金变动',
    'unclassified':'待归类及其他披露',
}

# Exact concepts only. Similar words in an extension never establish equivalence.
GROUPS = {
 'balance/assets/current': 'AssetsCurrent CurrentAssets CashAndCashEquivalentsAtCarryingValue CashAndCashEquivalents CashCashEquivalentsAndShortTermInvestments ShortTermInvestments MarketableSecuritiesCurrent AccountsReceivableNetCurrent TradeAndOtherCurrentReceivables InventoryNet Inventories PrepaidExpenseCurrent OtherAssetsCurrent',
 'balance/assets/noncurrent': 'AssetsNoncurrent NoncurrentAssets PropertyPlantAndEquipmentNet PropertyPlantAndEquipment InvestmentProperty Goodwill IntangibleAssetsNetExcludingGoodwill IntangibleAssetsOtherThanGoodwill OperatingLeaseRightOfUseAsset LongTermInvestments OtherAssetsNoncurrent DeferredIncomeTaxAssetsNet',
 'balance/assets/total': 'Assets TotalAssets',
 'balance/liabilities/current': 'LiabilitiesCurrent CurrentLiabilities AccountsPayableCurrent TradeAndOtherCurrentPayables AccruedLiabilitiesCurrent OtherLiabilitiesCurrent LongTermDebtCurrent ShortTermBorrowings OperatingLeaseLiabilityCurrent EmployeeRelatedLiabilitiesCurrent ContractWithCustomerLiabilityCurrent IncomeTaxesPayableCurrent',
 'balance/liabilities/noncurrent': 'LiabilitiesNoncurrent NoncurrentLiabilities LongTermDebtNoncurrent LongTermDebtAndCapitalLeaseObligations OperatingLeaseLiabilityNoncurrent OtherLiabilitiesNoncurrent DeferredIncomeTaxLiabilitiesNet ContractWithCustomerLiabilityNoncurrent',
 'balance/liabilities/total': 'Liabilities TotalLiabilities',
 'balance/equity/capital': 'CommonStockValue CommonStocksIncludingAdditionalPaidInCapital AdditionalPaidInCapital CommonStockSharesOutstanding CommonStockSharesIssued CommonStockSharesAuthorized CommonStockParOrStatedValuePerShare IssuedCapital SharePremium',
 'balance/equity/retained': 'RetainedEarningsAccumulatedDeficit RetainedEarnings AccumulatedOtherComprehensiveIncomeLossNetOfTax TreasuryStockValue',
 'balance/equity/total': 'StockholdersEquity StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest Equity EquityAttributableToOwnersOfParent TotalEquity LiabilitiesAndStockholdersEquity EquityAndLiabilities MinorityInterest',
 'income/revenue/sales': 'Revenue RevenueFromContractWithCustomerExcludingAssessedTax RevenueFromContractWithCustomerIncludingAssessedTax Revenues SalesRevenueNet SalesRevenueGoodsNet SalesRevenueServicesNet NetSales',
 'income/revenue/cost': 'CostOfRevenue CostOfGoodsAndServicesSold CostOfGoodsSold CostOfSales',
 'income/revenue/gross': 'GrossProfit',
 'income/expenses/operating': 'OperatingExpenses ResearchAndDevelopmentExpense ResearchAndDevelopmentExpenses SellingGeneralAndAdministrativeExpense GeneralAndAdministrativeExpense SellingAndMarketingExpense SellingExpense OperatingLeaseCost',
 'income/expenses/nonoperating': 'OtherNonoperatingIncomeExpense NonoperatingIncomeExpense InterestExpense InterestIncomeExpenseNet FinanceCosts FinanceIncome InvestmentGain',
 'income/expenses/tax': 'IncomeTaxExpenseBenefit IncomeTaxExpenseContinuingOperations EffectiveIncomeTaxRateContinuingOperations',
 'income/profit/operating': 'OperatingIncomeLoss OperatingProfit OperatingProfitLoss ProfitLossFromOperatingActivities',
 'income/profit/pretax': 'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest ProfitLossBeforeTax ProfitBeforeTax',
 'income/profit/net': 'NetIncomeLoss ProfitLoss ProfitForPeriod ProfitOwners ProfitLossAttributableToOwnersOfParent NetIncomeLossAvailableToCommonStockholdersBasic NetIncomeLossAttributableToParent',
 'income/profit/eps': 'EarningsPerShareBasic EarningsPerShareDiluted BasicEarningsLossPerShare DilutedEarningsLossPerShare WeightedAverageNumberOfSharesOutstandingBasic WeightedAverageNumberOfDilutedSharesOutstanding WeightedAverageNumberOfOrdinarySharesOutstanding WeightedAverageNumberOfDilutedOrdinarySharesOutstanding',
 'cashflow/operating/net': 'NetCashProvidedByUsedInOperatingActivities CashFlowsFromUsedInOperatingActivities',
 'cashflow/operating/adjustments': 'Depreciation DepreciationDepletionAndAmortization DepreciationDepletionAndAmortizationPropertyPlantAndEquipment AmortizationOfIntangibleAssets ShareBasedCompensation IncreaseDecreaseInAccountsReceivable IncreaseDecreaseInInventories IncreaseDecreaseInAccountsPayable',
 'cashflow/investing/net': 'NetCashProvidedByUsedInInvestingActivities CashFlowsFromUsedInInvestingActivities',
 'cashflow/investing/capex': 'PaymentsToAcquirePropertyPlantAndEquipment PurchaseOfPropertyPlantAndEquipment PaymentsToAcquireProductiveAssets',
 'cashflow/investing/other': 'PaymentsToAcquireBusinessesNetOfCashAcquired PaymentsToAcquireInvestments ProceedsFromSaleMaturityAndCollectionsOfInvestments PaymentsToAcquireAvailableForSaleSecuritiesDebt ProceedsFromMaturitiesPrepaymentsAndCallsOfAvailableForSaleSecurities ProceedsFromSaleOfAvailableForSaleSecuritiesDebt',
 'cashflow/financing/net': 'NetCashProvidedByUsedInFinancingActivities CashFlowsFromUsedInFinancingActivities',
 'cashflow/financing/capital': 'PaymentsForRepurchaseOfCommonStock PaymentsOfDividends PaymentsOfDividendsCommonStock ProceedsFromIssuanceOfCommonStock ProceedsFromStockOptionsExercised ProceedsFromPaymentsForOtherFinancingActivities ProceedsFromIssuanceOfLongTermDebt RepaymentsOfLongTermDebt',
 'cashflow/reconciliation/change': 'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect CashAndCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect IncreaseDecreaseInCashAndCashEquivalents EffectOfExchangeRateOnCashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
}
CONCEPTS = {concept:path for path,names in GROUPS.items() for concept in names.split()}
SUPPORTED = {'us-gaap','ifrs-full','DART-IFRS','issuer-reported'}


def account_path(taxonomy, concept):
    if taxonomy=='DART-IFRS':
        raw,_,statement=concept.partition(':')
        # DART preserves its statement code in the wire identity. Only the
        # standard IFRS namespace may reuse an exact IFRS subject mapping.
        if raw.startswith('ifrs-full_') and raw[10:] in CONCEPTS:
            return CONCEPTS[raw[10:]]
        return {'BS':'balance','IS':'income','CIS':'income','CF':'cashflow'}.get(statement,'unclassified')
    if taxonomy.startswith('FinMind:'):
        if concept in CONCEPTS:return CONCEPTS[concept]
        return {'FinMind:TaiwanStockBalanceSheet':'balance','FinMind:TaiwanStockCashFlowsStatement':'cashflow','FinMind:TaiwanStockFinancialStatements':'income'}.get(taxonomy,'unclassified')
    if taxonomy=='dei' and concept=='EntityCommonStockSharesOutstanding':return 'balance/equity/capital'
    if concept=='LongTermDebtAndCapitalLeaseObligations':return 'unclassified'
    return CONCEPTS.get(concept,'unclassified') if taxonomy in SUPPORTED else 'unclassified'


def annotate(row):
    path=row.get('payload',{}).get('account_path') or account_path(row['taxonomy'],row['concept'])
    if path not in LABELS:path='unclassified'
    row['account_path']=path
    row['account_labels']=[LABELS['/'.join(path.split('/')[:i])] for i in range(1,len(path.split('/'))+1)]
    row['account_mapping_version']=VERSION
    return row


def tree(db, entity_id):
    totals={}
    for taxonomy,concept,override,count in db.execute("SELECT taxonomy,concept,json_extract(payload,'$.account_path'),count(*) FROM financial_points WHERE entity_id=? GROUP BY taxonomy,concept,3",(entity_id,)):
        path=override if override in LABELS else account_path(taxonomy,concept)
        for i in range(1,len(path.split('/'))+1):
            parent='/'.join(path.split('/')[:i]);totals[parent]=totals.get(parent,0)+count
    return [{'path':path,'label':label,'count':totals[path]} for path,label in LABELS.items() if totals.get(path)]
