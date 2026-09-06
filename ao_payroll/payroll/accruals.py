import calendar
from datetime import date

import frappe
from frappe.utils import flt, getdate

from ao_payroll.payroll import calculator


ACCRUAL_REMARK_PREFIX = "AO Payroll Accrual |"


def _complete_calendar_months(
    start_date,
    end_date,
    year,
):
    start_date = getdate(start_date)
    end_date = getdate(end_date)

    months = 0

    for month in range(1, 13):
        month_start = date(
            year,
            month,
            1,
        )

        month_end = date(
            year,
            month,
            calendar.monthrange(
                year,
                month,
            )[1],
        )

        if (
            start_date <= month_start
            and end_date >= month_end
        ):
            months += 1

    return months


def _get_salary_base(
    employee,
    reference_date,
):
    """
    Return Salary Structure Assignment base in KZ.

    USD assignments use the latest Currency Exchange rate
    on or before the reference date.
    """

    reference_date = getdate(
        reference_date
    )

    assignment = frappe.db.get_value(
        "Salary Structure Assignment",
        {
            "employee": employee,
            "docstatus": 1,
            "from_date": [
                "<=",
                reference_date,
            ],
        },
        [
            "name",
            "base",
            "moeda_usd",
        ],
        order_by="from_date desc, creation desc",
        as_dict=True,
    )

    if not assignment:
        return None

    base = flt(
        assignment.base
    )

    if int(
        assignment.get("moeda_usd")
        or 0
    ):
        exchange_rate = frappe.db.get_value(
            "Currency Exchange",
            {
                "from_currency": "USD",
                "to_currency": "KZ",
                "date": [
                    "<=",
                    reference_date,
                ],
            },
            "exchange_rate",
            order_by="date desc, creation desc",
        )

        if not exchange_rate:
            frappe.throw(
                f"No USD -> KZ Currency Exchange rate "
                f"found for {employee} on or before "
                f"{reference_date}."
            )

        base *= flt(
            exchange_rate
        )

    return {
        "assignment": assignment.name,
        "base": flt(
            base,
            2,
        ),
    }


def calculate_employee_accrual(
    employee,
    posting_date,
):
    """
    Calculate cumulative Férias and Natal liabilities
    earned by one employee up to posting_date.

    This calculates target liability only.
    """

    posting_date = getdate(
        posting_date
    )

    year = posting_date.year
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    employee_doc = frappe.get_doc(
        "Employee",
        employee,
    )

    joining_date = getdate(
        employee_doc.date_of_joining
    )

    if joining_date > posting_date:
        return None

    relieving_date = (
        getdate(employee_doc.relieving_date)
        if employee_doc.relieving_date
        else None
    )

    service_start = max(
        joining_date,
        year_start,
    )

    service_end_for_year = min(
        relieving_date or year_end,
        year_end,
    )

    service_end_to_date = min(
        relieving_date or posting_date,
        posting_date,
    )

    if service_end_to_date < service_start:
        return None

    salary = _get_salary_base(
        employee,
        service_end_to_date,
    )

    if not salary:
        return None

    base_salary = flt(
        salary["base"]
    )

    settings = frappe.get_single(
        "Angola Payroll Settings"
    )

    # -----------------------------------------------------
    # Total service months in the entitlement year
    # -----------------------------------------------------

    total_service_months = (
        _complete_calendar_months(
            service_start,
            service_end_for_year,
            year,
        )
    )

    earned_service_months = (
        _complete_calendar_months(
            service_start,
            service_end_to_date,
            year,
        )
    )

    # -----------------------------------------------------
    # Férias
    #
    # Reuse annual entitlement logic, then recognize only
    # the portion earned up to posting date.
    # -----------------------------------------------------

    holiday = (
        calculator
        .calculate_holiday_allowance_entitlement(
            employee=employee,
            year=year,
            base_salary=base_salary,
        )
    )

    annual_holiday = flt(
        holiday["annual_entitlement"]
    )

    if total_service_months:
        holiday_earned = (
            annual_holiday
            * earned_service_months
            / total_service_months
        )
    else:
        holiday_earned = 0

    holiday_paid = (
        calculator.get_holiday_allowance_paid(
            employee=employee,
            year=year,
        )
    )

    holiday_target = max(
        0,
        flt(holiday_earned)
        - flt(holiday_paid),
    )

    # -----------------------------------------------------
    # Natal
    #
    # Annual configured percentage accrued by complete
    # months of service / 12.
    # -----------------------------------------------------

    christmas_rate = (
        flt(
            settings.christmas_allowance_rate
        )
        / 100
    )

    christmas_earned = (
        base_salary
        * christmas_rate
        * earned_service_months
        / 12
    )

    christmas_paid = (
        calculator.get_christmas_allowance_paid(
            employee=employee,
            year=year,
        )
    )

    christmas_target = max(
        0,
        flt(christmas_earned)
        - flt(christmas_paid),
    )

    return {
        "employee": employee,
        "salary_structure_assignment":
            salary["assignment"],
        "base_salary": flt(
            base_salary,
            2,
        ),
        "earned_service_months":
            earned_service_months,
        "total_service_months":
            total_service_months,
        "holiday_earned": flt(
            holiday_earned,
            2,
        ),
        "holiday_paid": flt(
            holiday_paid,
            2,
        ),
        "holiday_target": flt(
            holiday_target,
            2,
        ),
        "christmas_earned": flt(
            christmas_earned,
            2,
        ),
        "christmas_paid": flt(
            christmas_paid,
            2,
        ),
        "christmas_target": flt(
            christmas_target,
            2,
        ),
    }


def get_liability_gl_balance(
    company,
    account,
    posting_date,
):
    """
    Return actual liability account balance as of posting_date.

    Credit increases the liability.
    Debit reduces the liability.

    This intentionally sees both:
    - accrual Journal Entries
    - payroll debits when the allowance is paid
    """

    posting_date = getdate(
        posting_date
    )

    value = frappe.db.sql(
        """
        SELECT COALESCE(
            SUM(credit - debit),
            0
        )
        FROM `tabGL Entry`
        WHERE
            company = %(company)s
            AND account = %(account)s
            AND posting_date <= %(posting_date)s
            AND is_cancelled = 0
        """,
        {
            "company": company,
            "account": account,
            "posting_date": posting_date,
        },
    )[0][0]

    return flt(
        value,
        2,
    )



def calculate_monthly_accrual(
    company,
    posting_date,
):
    """
    Calculate company cumulative liability and current
    month movement.

    No Journal Entry is created here.
    """

    posting_date = getdate(
        posting_date
    )

    settings = frappe.get_single(
        "Angola Payroll Settings"
    )

    employees = frappe.get_all(
        "Employee",
        filters={
            "company": company,
            "date_of_joining": [
                "<=",
                posting_date,
            ],
        },
        fields=[
            "name",
            "relieving_date",
        ],
    )

    schedule = []

    for row in employees:
        if (
            row.relieving_date
            and getdate(row.relieving_date)
            < date(
                posting_date.year,
                1,
                1,
            )
        ):
            continue

        result = (
            calculate_employee_accrual(
                employee=row.name,
                posting_date=posting_date,
            )
        )

        if result:
            schedule.append(
                result
            )

    holiday_target = sum(
        flt(row["holiday_target"])
        for row in schedule
    )

    christmas_target = sum(
        flt(row["christmas_target"])
        for row in schedule
    )

    holiday_gl_balance = (
        get_liability_gl_balance(
            company=company,
            account=(
                settings
                .custom_holiday_accrual_liability_account
            ),
            posting_date=posting_date,
        )
    )

    christmas_gl_balance = (
        get_liability_gl_balance(
            company=company,
            account=(
                settings
                .custom_christmas_accrual_liability_account
            ),
            posting_date=posting_date,
        )
    )

    return {
        "company": company,
        "posting_date": posting_date,
        "employees": schedule,

        "holiday_target": flt(
            holiday_target,
            2,
        ),
        "holiday_gl_balance": flt(
            holiday_gl_balance,
            2,
        ),
        "holiday_movement": flt(
            holiday_target
            - holiday_gl_balance,
            2,
        ),

        "christmas_target": flt(
            christmas_target,
            2,
        ),
        "christmas_gl_balance": flt(
            christmas_gl_balance,
            2,
        ),
        "christmas_movement": flt(
            christmas_target
            - christmas_gl_balance,
            2,
        ),
    }


def create_monthly_accrual_journal_entry(
    company,
    posting_date,
):
    """
    Create one submitted monthly accrual JE.

    Positive movement:
        Dr expense
        Cr liability

    Negative movement:
        Dr liability
        Cr expense
    """

    posting_date = getdate(
        posting_date
    )

    settings = frappe.get_single(
        "Angola Payroll Settings"
    )

    remark = (
        f"{ACCRUAL_REMARK_PREFIX}"
        f"{posting_date.strftime('%Y-%m')}"
    )

    existing = frappe.db.get_value(
        "Journal Entry",
        {
            "company": company,
            "docstatus": ["!=", 2],
            "user_remark": remark,
        },
        "name",
    )

    if existing:
        frappe.throw(
            f"Payroll accrual for "
            f"{posting_date.strftime('%Y-%m')} "
            f"already exists: {existing}"
        )

    result = calculate_monthly_accrual(
        company=company,
        posting_date=posting_date,
    )

    accounts = []

    def add_movement(
        expense_account,
        liability_account,
        movement,
    ):
        movement = flt(
            movement,
            2,
        )

        if not movement:
            return

        if movement > 0:
            accounts.append({
                "account": expense_account,
                "debit_in_account_currency":
                    movement,
                "credit_in_account_currency":
                    0,
            })

            accounts.append({
                "account": liability_account,
                "debit_in_account_currency":
                    0,
                "credit_in_account_currency":
                    movement,
            })

        else:
            amount = abs(
                movement
            )

            accounts.append({
                "account": liability_account,
                "debit_in_account_currency":
                    amount,
                "credit_in_account_currency":
                    0,
            })

            accounts.append({
                "account": expense_account,
                "debit_in_account_currency":
                    0,
                "credit_in_account_currency":
                    amount,
            })

    add_movement(
        settings
        .custom_holiday_accrual_expense_account,
        settings
        .custom_holiday_accrual_liability_account,
        result["holiday_movement"],
    )

    add_movement(
        settings
        .custom_christmas_accrual_expense_account,
        settings
        .custom_christmas_accrual_liability_account,
        result["christmas_movement"],
    )

    if not accounts:
        return {
            **result,
            "journal_entry": None,
            "created": False,
        }

    je = frappe.new_doc(
        "Journal Entry"
    )

    je.voucher_type = "Journal Entry"
    je.company = company
    je.posting_date = posting_date
    je.user_remark = remark

    for account in accounts:
        je.append(
            "accounts",
            account,
        )

    je.insert()
    je.submit()

    return {
        **result,
        "journal_entry": je.name,
        "created": True,
    }


def create_reversal_journal_entry(
    journal_entry,
    posting_date,
    payroll_accrual=None,
):
    """
    Reverse a submitted accrual Journal Entry.

    Debit/credit values are swapped line by line.
    Intended for automatic reversal on the first day
    of the following month.
    """

    posting_date = getdate(posting_date)

    source = frappe.get_doc(
        "Journal Entry",
        journal_entry,
    )

    if source.docstatus != 1:
        frappe.throw(
            f"Journal Entry {journal_entry} is not submitted."
        )

    remark = (
        f"AO Payroll Accrual Reversal | "
        f"{payroll_accrual or journal_entry}"
    )

    existing = frappe.db.get_value(
        "Journal Entry",
        {
            "company": source.company,
            "posting_date": posting_date,
            "user_remark": remark,
            "docstatus": 1,
        },
        "name",
    )

    if existing:
        return {
            "journal_entry": existing,
            "created": False,
        }

    reverse = frappe.new_doc(
        "Journal Entry"
    )

    reverse.company = source.company
    reverse.posting_date = posting_date
    reverse.voucher_type = "Journal Entry"
    reverse.user_remark = remark

    for row in source.accounts:
        reverse.append(
            "accounts",
            {
                "account": row.account,
                "party_type": row.party_type,
                "party": row.party,
                "cost_center": row.cost_center,
                "project": row.project,

                "debit_in_account_currency":
                    flt(
                        row.credit_in_account_currency,
                        2,
                    ),

                "credit_in_account_currency":
                    flt(
                        row.debit_in_account_currency,
                        2,
                    ),

                "exchange_rate":
                    row.exchange_rate or 1,

                "reference_type":
                    row.reference_type,

                "reference_name":
                    row.reference_name,
            },
        )

    reverse.insert(
        ignore_permissions=True
    )

    reverse.submit()

    return {
        "journal_entry": reverse.name,
        "created": True,
    }
