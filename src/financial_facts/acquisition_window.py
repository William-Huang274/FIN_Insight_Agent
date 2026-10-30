"""Separate financial observation periods from the filing catalogue window."""
from datetime import date


def financial_period_floor(plan):
    # Legacy plans retain their explicit historical coverage. New plans can
    # include comparative facts without expanding the filing catalogue.
    value=plan.get('financial_period_since',plan['filings_since'])
    date.fromisoformat(value)
    if value>plan['as_of']:
        raise ValueError('financial_period_window_after_as_of')
    return value


def within_financial_window(value, plan):
    end=value.get('end');filed=value.get('filed')
    if not end or not filed:return False
    date.fromisoformat(end);date.fromisoformat(filed)
    return financial_period_floor(plan)<=end<=plan['as_of'] and filed<=plan['as_of']
