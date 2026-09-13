"""Canonical financial definitions; execution remains in the existing fact mart.

These are domain formulas, not natural-language classification rules. Existing
snapshots stay immutable: the runtime advertises definitions whose inputs exist.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DerivedMetric:
    title: str
    inputs: tuple[str, str]
    operation: str
    formula: str
    unit_family: str
    comparison: str = "same_period"
    boundary: str = "计算值不单独证明经营原因或持续性。"


DERIVED_METRICS = {
    "gross_margin": DerivedMetric("毛利率", ("gross_profit", "revenue"), "divide_percent", "gross_profit / revenue * 100", "percentage"),
    "operating_margin": DerivedMetric("营业利润率", ("operating_income", "revenue"), "divide_percent", "operating_income / revenue * 100", "percentage"),
    "net_margin": DerivedMetric("净利率", ("net_income", "revenue"), "divide_percent", "net_income / revenue * 100", "percentage"),
    "free_cash_flow": DerivedMetric("自由现金流（经营现金流减资本开支）", ("operating_cash_flow", "capital_expenditures"), "subtract", "operating_cash_flow - capital_expenditures", "currency", boundary="资本开支按正支出；不等同公司调整后或净资本开支口径FCF。"),
    "capex_to_revenue": DerivedMetric("资本开支占收入比例", ("capital_expenditures", "revenue"), "divide_percent", "capital_expenditures / revenue * 100", "percentage"),
    "operating_cash_flow_to_net_income": DerivedMetric("经营现金流与净利润之比", ("operating_cash_flow", "net_income"), "divide_ratio", "operating_cash_flow / net_income", "ratio", boundary="净利润须为正；不是客户回款率，不单独证明盈利质量或营运资本因果。"),
    "free_cash_flow_margin": DerivedMetric("自由现金流占收入比例", ("free_cash_flow", "revenue"), "divide_percent", "free_cash_flow / revenue * 100", "percentage"),
}

for _metric, _title in {
    "revenue": "收入", "operating_income": "营业利润", "net_income": "净利润",
    "operating_cash_flow": "经营活动现金流", "free_cash_flow": "自由现金流",
    "capital_expenditures": "资本开支",
}.items():
    for _comparison, _label in (("yoy", "同比"), ("qoq", "环比")):
        for _suffix, _operation, _family, _formula, _name in (
            ("change", "subtract", "currency", "current - prior", "变化额"),
            ("growth", "growth_percent", "percentage", "(current / prior - 1) * 100", "变化率"),
        ):
            DERIVED_METRICS[f"{_metric}_{_comparison}_{_suffix}"] = DerivedMetric(
                _title + _label + _name, (_metric, _metric), _operation, _formula,
                _family, _comparison,
                "两期同口径；变化率仅用于两期均为正的数值，盈亏转换或零/负基期请引用变化额和两期原值。",
            )
for _metric, _title in (("gross_margin", "毛利率"), ("operating_margin", "营业利润率"), ("net_margin", "净利率")):
    for _comparison, _label in (("yoy", "同比"), ("qoq", "环比")):
        DERIVED_METRICS[f"{_metric}_{_comparison}_pp"] = DerivedMetric(
            _title + _label + "百分点变化", (_metric, _metric), "subtract_pp",
            "current_percent - prior_percent", "percentage_point", _comparison,
            "单位是百分点，不是百分比增速。",
        )


def available_derived_metrics(base_metric_ids):
    """Return only definitions with reachable inputs, never claim row coverage."""
    available = set(base_metric_ids)
    result = {}
    for key, metric in DERIVED_METRICS.items():
        if set(metric.inputs) <= available:
            result[key] = metric
            available.add(key)
    return result


def derived_metric_catalog(base_metric_ids):
    return [{"metric_id": key, "title": value.title, "formula": value.formula,
             "inputs": list(value.inputs), "unit_family": value.unit_family,
             "comparison": value.comparison, "interpretation_boundary": value.boundary,
             "definition_version": 1, "availability": "derived_at_query_time"}
            for key, value in available_derived_metrics(base_metric_ids).items()]
