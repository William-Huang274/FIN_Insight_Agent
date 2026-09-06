"""Small source-bound chart contract; plotting belongs to the renderer."""
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .source_bound_calculator import CalculationOperand, SourceBoundCalculation, calculate_from_sources


class ChartPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=90)
    series: str = Field(default="", max_length=80)
    source: CalculationOperand


class ReportChart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=160)
    kind: Literal["bar", "line"] = "bar"
    unit: str = Field(min_length=1, max_length=80)
    scale_divisor: Literal[1, 1000, 1000000, 1000000000] = 1
    points: list[ChartPoint] = Field(min_length=2, max_length=36)
    interpretation: str = Field(min_length=10, max_length=1200,
        description="Explain the relationship, comparison periods and relevant caveat; no unsupported causal claim.")


def bind_report_charts(charts, source_lookup):
    bound = []
    for chart in charts:
        if len({(p.label, p.series) for p in chart.points}) != len(chart.points):
            raise ValueError("chart_duplicate_label_series_would_hide_values")
        points = []
        for point in chart.points:
            if not point.source.source_id or point.source.assumption_note:
                raise ValueError("chart_points_require_observed_sources_not_unsourced_values")
            item = source_lookup(point.source.source_id)
            if item.get("arithmetic_verified") is True and item.get("result_state") == "non_authoritative_metric":
                value = Decimal(item["value_decimal"])
                provenance = {"calculation": item}
            else:
                result = calculate_from_sources(SourceBoundCalculation(expression="v", operands={"v": point.source},
                    result_unit=chart.unit, rationale="Read source value for chart; labels and comparability require independent review"), source_lookup)
                value = Decimal(result["value_decimal"])
                provenance = result["operands"]["v"]
            points.append({"label": point.label, "series": point.series, "value": float(value / chart.scale_divisor),
                "source_id": point.source.source_id, "provenance": provenance})
        bound.append({**chart.model_dump(mode="json", exclude={"points"}), "points": points,
            "numeric_fact_authority": False, "notice": "图示依据已观察来源，缩放和算术不代表财务可比性已获独立验证。"})
    return bound
