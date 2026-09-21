"""Versioned, deterministic definitions for the company library's base metrics.

Company-specific accounting mappings belong to reviewed source metadata, not
formula code. Industry operating KPIs and forward estimates are outside v2.
"""

VERSION = 'derived_financials.v2'
CONCEPTS = {
    # Total reported revenues can include items outside customer contracts
    # (for example energy hedges). A contract-revenue subtotal is not total.
    'revenue': ('Revenues', 'Revenue', 'NetSales', 'RevenueFromContractWithCustomerExcludingAssessedTax'),
    'cost': ('CostOfRevenue', 'CostOfGoodsAndServicesSold', 'CostOfSales'),
    'gross': ('GrossProfit',),
    'operating': ('OperatingIncomeLoss', 'OperatingProfit', 'ProfitLossFromOperatingActivities'),
    'profit': ('ProfitLoss', 'ProfitForPeriod', 'NetIncomeLoss'),
    'parent_profit': ('NetIncomeLoss', 'ProfitLossAttributableToOwnersOfParent', 'ProfitOwners'),
    'current_assets': ('AssetsCurrent', 'CurrentAssets'),
    'current_liabilities': ('LiabilitiesCurrent', 'CurrentLiabilities'),
    'noncurrent_assets': ('AssetsNoncurrent', 'NoncurrentAssets'),
    'noncurrent_liabilities': ('LiabilitiesNoncurrent', 'NoncurrentLiabilities'),
    'assets': ('Assets', 'TotalAssets'),
    'liabilities': ('Liabilities', 'TotalLiabilities'),
    'equity': ('StockholdersEquity', 'EquityAttributableToOwnersOfParent', 'EquityOwners'),
    'total_equity': ('StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest', 'Equity', 'TotalEquity'),
    'cash': ('CashAndCashEquivalentsAtCarryingValue', 'CashAndCashEquivalents'),
    'inventory': ('InventoryNet', 'Inventories'),
    'receivables': ('AccountsReceivableNetCurrent', 'CurrentTradeReceivables', 'TradeReceivables', 'AccountsReceivable'),
    'cfo': ('NetCashProvidedByUsedInOperatingActivities', 'CashFlowsFromUsedInOperatingActivities'),
    'capex': ('PaymentsToAcquirePropertyPlantAndEquipment', 'PurchaseOfPropertyPlantAndEquipment', 'PurchaseOfPPE'),
    'capex_extended': ('CashPurchasePrepaymentsPPEConstructionInvestmentProperty',),
    'eps': ('EarningsPerShareDiluted', 'DilutedEarningsLossPerShare', 'DilutedEPS'),
    'shares': ('EntityCommonStockSharesOutstanding', 'CommonStockSharesOutstanding', 'OrdinarySharesOutstanding'),
}

# ID, label, left role, right role, expression, unit, denominator/sign policy.
FORMULAS = [
    ('gross_margin','毛利率','gross','revenue','a / b * 100','%','positive_denominator'),
    ('operating_margin','经营利润率','operating','revenue','a / b * 100','%','positive_denominator'),
    ('net_margin','净利率（期间净利润口径）','profit','revenue','a / b * 100','%','positive_denominator'),
    ('parent_net_margin','归母净利率','parent_profit','revenue','a / b * 100','%','positive_denominator'),
    ('operating_cash_margin','经营现金流收入比','cfo','revenue','a / b * 100','%','positive_denominator'),
    ('capex_to_revenue','现金购建固定资产／收入','capex','revenue','a / b * 100','%','nonnegative_numerator'),
    ('cash_conversion','经营现金流／期间净利润','cfo','profit','a / b','倍','positive_denominator'),
    ('current_ratio','流动比率','current_assets','current_liabilities','a / b','倍','positive_denominator'),
    ('cash_ratio','现金及现金等价物／流动负债','cash','current_liabilities','a / b','倍','positive_denominator'),
    ('liabilities_to_assets','资产负债率','liabilities','assets','a / b * 100','%','positive_denominator'),
    ('liabilities_to_equity','总负债／归母权益','liabilities','equity','a / b','倍','positive_denominator'),
    ('fcf_cash_ppe','自由现金流（经营现金流减现金购建固定资产）','cfo','capex','a - b','source_currency','cash_capex'),
    ('fcf_extended_property','自由现金流（扣除固定资产、在建工程及投资物业购买／预付款）','cfo','capex_extended','a - b','source_currency','cash_capex'),
]

METHOD_SOURCES = [
    'https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/financial-analysis-techniques',
    'https://www.sec.gov/rules-regulations/staff-guidance/corporation-finance-interpretations/non-gaap-financial-measures',
]
