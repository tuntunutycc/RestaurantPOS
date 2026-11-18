"""How much of a paid order was taken by each payment method.

One set of SQL expressions shared by every report (per cashier, dashboard
breakdown, period report) so they cannot disagree with each other.

Stored amounts win. Rows from before the amount columns existed fall back to
`payment_method` + `total_amount`. See specs/feature-payment-kpay-mmqr.
"""

from __future__ import annotations

from sqlalchemy import case, func

from models import Order


def _method():
    return func.lower(Order.payment_method)


def cash_part():
    return case(
        (Order.cash_amount.isnot(None), Order.cash_amount),
        (_method() == "cash", Order.total_amount),
        else_=0.0,
    )


def kpay_part():
    return case(
        (Order.kpay_amount.isnot(None), Order.kpay_amount),
        (_method() == "kpay", Order.total_amount),
        else_=0.0,
    )


def mmqr_part():
    return case(
        (Order.mmqr_amount.isnot(None), Order.mmqr_amount),
        (_method() == "mmqr", Order.total_amount),
        else_=0.0,
    )


def mobile_part():
    """All mobile money: KPay + MMQR + mobile money recorded before they were told apart."""
    return case(
        (Order.mobile_money_amount.isnot(None), Order.mobile_money_amount),
        (
            Order.kpay_amount.isnot(None) | Order.mmqr_amount.isnot(None),
            func.coalesce(Order.kpay_amount, 0.0) + func.coalesce(Order.mmqr_amount, 0.0),
        ),
        (_method().in_(("mobile_money", "kpay", "mmqr")), Order.total_amount),
        else_=0.0,
    )


def summed(expr):
    return func.coalesce(func.sum(expr), 0.0)


def mobile_unspecified(mobile: float, kpay: float, mmqr: float) -> float:
    """Mobile money that is neither KPay nor MMQR (sales from before this feature)."""
    return max(round(float(mobile or 0.0) - float(kpay or 0.0) - float(mmqr or 0.0), 2), 0.0)
