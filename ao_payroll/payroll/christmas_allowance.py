import calendar

import frappe
from frappe.utils import flt, getdate

from ao_payroll.payroll import calculator


MONTHS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}


def _complete_calendar_months(
    start_date,
    end_date,
):
    start_date = getdate(start_date)
    end_date = getdate(end_date)

    if end_date < start_date:
        return 0

    count = 0
    year = start_date.year
    month = start_date.month

    while (
        year < end_date.year
        or (
            year == end_date.year
            and month <= end_date.month
        )
    ):
        first = getdate(
            f"{year}-{month:02d}-01"
        )

        last_day = calendar.monthrange(
            year,
            month,
        )[1]

        last = getdate(
            f"{year}-{month:02d}-{last_day:02d}"
        )

        if (
            start_date <= first
            and end_date >= last
        ):
            count += 1

        if month == 12:
            year += 1
            month = 1
        else:
            month += 1

    return count


def _service_period(
    employee,
    year,
    end_date=None,
):
    employee_doc = frappe.get_doc(
        "Employee",
        employee,
    )

    year_start = getdate(
        f"{year}-01-01"
    )

    year_end = getdate(
        f"{year}-12-31"
    )

    start = max(
        getdate(
            employee_doc.date_of_joining
        ),
        year_start,
    )

    if end_date:
        end = min(
            getdate(end_date),
            year_end,
        )
    else:
        end = year_end

    if employee_doc.relieving_date:
        end = min(
            end,
            getdate(
                employee_doc.relieving_date
            ),
        )

    return start, end


def calculate_annual_entitlement(
    employee,
    year,
    base_salary,
):
    settings = frappe.get_single(
        "Angola Payroll Settings"
    )

    rate = (
        flt(
            settings.christmas_allowance_rate
        )
        / 100
    )

    start, end = _service_period(
        employee=employee,
        year=year,
    )

    months = _complete_calendar_months(
        start,
        end,
    )

    amount = (
        flt(base_salary)
        * rate
        * months
        / 12
    )

    return {
        "service_months": months,
        "annual_entitlement": flt(
            amount,
            2,
        ),
    }


def calculate_earned_to_date(
    employee,
    year,
    base_salary,
    payroll_date,
):
    settings = frappe.get_single(
        "Angola Payroll Settings"
    )

    rate = (
        flt(
            settings.christmas_allowance_rate
        )
        / 100
    )

    start, end = _service_period(
        employee=employee,
        year=year,
        end_date=payroll_date,
    )

    months = _complete_calendar_months(
        start,
        end,
    )

    return flt(
        flt(base_salary)
        * rate
        * months
        / 12,
        2,
    )


def _month_number(value):
    if not value:
        return None

    value = str(value).strip()

    if value.isdigit():
        return int(value)

    return MONTHS.get(value)


def calculate_salary_slip_christmas_allowance(
    employee,
    base_salary,
    payroll_start_date,
    payroll_end_date,
):
    payroll_start_date = getdate(
        payroll_start_date
    )

    payroll_end_date = getdate(
        payroll_end_date
    )

    settings = frappe.get_single(
        "Angola Payroll Settings"
    )

    mode = getattr(
        settings,
        "custom_christmas_allowance_payment_mode",
        None,
    ) or "Fixed Month"

    year = payroll_end_date.year

    annual = calculate_annual_entitlement(
        employee=employee,
        year=year,
        base_salary=base_salary,
    )

    annual_entitlement = flt(
        annual["annual_entitlement"]
    )

    paid = (
        calculator.get_christmas_allowance_paid(
            employee=employee,
            year=year,
        )
    )

    remaining = max(
        0,
        annual_entitlement - flt(paid),
    )

    result = {
        "payment_mode": mode,
        "annual_entitlement":
            flt(annual_entitlement, 2),
        "paid":
            flt(paid, 2),
        "remaining":
            flt(remaining, 2),
        "amount": 0.0,
    }

    if remaining <= 0:
        return result

    if mode == "Fixed Month":
        configured_month = getattr(
            settings,
            "custom_christmas_allowance_payment_month",
            None,
        )

        payment_month = _month_number(
            configured_month
        )

        if not payment_month:
            frappe.throw(
                "Christmas Allowance Payment Month "
                "is not configured."
            )

        if payroll_end_date.month == payment_month:
            result["amount"] = flt(
                remaining,
                2,
            )

        return result

    if mode == "Monthly Duodecimos":
        earned = calculate_earned_to_date(
            employee=employee,
            year=year,
            base_salary=base_salary,
            payroll_date=payroll_end_date,
        )

        payable = max(
            0,
            flt(earned) - flt(paid),
        )

        result["earned_to_date"] = flt(
            earned,
            2,
        )

        result["amount"] = flt(
            min(
                payable,
                remaining,
            ),
            2,
        )

        return result

    if mode == "Payment Blocks":
        blocks = (
            settings
            .custom_christmas_allowance_payment_blocks
            or []
        )

        total_percentage = sum(
            flt(row.percentage)
            for row in blocks
        )

        if abs(total_percentage - 100) > 0.01:
            frappe.throw(
                "Christmas Allowance Payment Blocks "
                f"must total 100%. Current total: "
                f"{flt(total_percentage, 2)}%."
            )

        month_percentage = sum(
            flt(row.percentage)
            for row in blocks
            if (
                _month_number(row.month)
                == payroll_end_date.month
            )
        )

        if month_percentage <= 0:
            return result

        block_amount = (
            annual_entitlement
            * month_percentage
            / 100
        )

        result["block_percentage"] = flt(
            month_percentage,
            2,
        )

        result["amount"] = flt(
            min(
                block_amount,
                remaining,
            ),
            2,
        )

        return result

    frappe.throw(
        f"Invalid Christmas Allowance "
        f"Payment Mode: {mode}"
    )
