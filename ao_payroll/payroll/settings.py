import frappe
from frappe.utils import getdate


FIELD_ALIASES = {
    "inss_salary_component": "inss",
    "irt_salary_component": "irt",
    "irt_base_salary_component": "irt_base",
    "overtime_salary_component": "overtime",
    "gross_salary_component": "gross_salary",
    "net_salary_component": "net_salary",
    "holyday_allowance_salary_component": "holiday_allowance",
    "christmas_allowance_salary_component": "christmas_allowance",
    "christmas_allowance_rate": "rate",
    "holiday_allowance_rate": "holidays_rate",
    "custom_christmas_allowance_payment_mode": "payment_mode",
    "custom_christmas_allowance_payment_month": "payment_month",
    "custom_christmas_allowance_payment_blocks": "christmas_allowance_payment_blocks",
    "custom_holiday_allowance_payment_mode": "holidays_payment_mode",
    "custom_holiday_allowance_block_method": "holidays_payment_block_method",
    "custom_holiday_allowance_fixed_month": "holidays_payment_month",
    "custom_holiday_allowance_prorate_service": "prorate_for_partial_year_service",
    "custom_inss_employer_expense_account": "inss_employer_account",
    "custom_inss_liability_account": "inss_liability_account",
    "custom_christmas_accrual_liability_account": "christmas_accrual_liability_account",
    "custom_christmas_accrual_expense_account": "christmas_accrual_expense_account",
    "custom_holiday_accrual_liability_account": "holiday_accrual_liability_account",
    "custom_holiday_accrual_expense_account": "holiday_accrual_expense_account",
}


def _get_company(company=None, employee=None):
    if company:
        return company

    if employee:
        company = frappe.db.get_value(
            "Employee",
            employee,
            "company",
        )
        if company:
            return company

    frappe.throw(
        "Company is required to load Settings Angola Payroll."
    )


def _get_fiscal_year(year=None, reference_date=None):
    if year and frappe.db.exists(
        "Fiscal Year",
        str(year),
    ):
        return str(year)

    if reference_date:
        date_value = getdate(reference_date)

    elif year:
        try:
            date_value = getdate(
                f"{int(year)}-12-31"
            )
        except (TypeError, ValueError):
            frappe.throw(
                f"Invalid payroll year: {year}"
            )

    else:
        frappe.throw(
            "Fiscal Year or payroll reference date "
            "is required to load Settings Angola Payroll."
        )

    fiscal_year = frappe.db.get_value(
        "Fiscal Year",
        {
            "year_start_date": ["<=", date_value],
            "year_end_date": [">=", date_value],
        },
        "name",
        order_by="year_start_date desc",
    )

    if not fiscal_year:
        frappe.throw(
            f"No Fiscal Year found for {date_value}."
        )

    return fiscal_year


def get_payroll_settings(
    company=None,
    year=None,
    reference_date=None,
    employee=None,
):
    company = _get_company(
        company=company,
        employee=employee,
    )

    fiscal_year = _get_fiscal_year(
        year=year,
        reference_date=reference_date,
    )

    names = frappe.get_all(
        "Settings Angola Payroll",
        filters={
            "company": company,
            "year": fiscal_year,
        },
        pluck="name",
        limit=2,
    )

    if not names:
        frappe.throw(
            f"No Settings Angola Payroll found for "
            f"{company} / {fiscal_year}."
        )

    if len(names) > 1:
        frappe.throw(
            f"More than one Settings Angola Payroll exists for "
            f"{company} / {fiscal_year}. "
            f"Keep only one configuration."
        )

    settings = frappe.get_doc(
        "Settings Angola Payroll",
        names[0],
    )

    for old_field, new_field in FIELD_ALIASES.items():
        setattr(
            settings,
            old_field,
            getattr(
                settings,
                new_field,
                None,
            ),
        )

    return settings
