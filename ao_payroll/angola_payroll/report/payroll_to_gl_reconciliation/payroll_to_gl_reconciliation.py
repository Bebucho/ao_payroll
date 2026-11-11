import frappe
from ao_payroll.payroll.settings import get_payroll_settings
from frappe import _
from frappe.utils import flt, getdate


TOLERANCE = 0.01


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)

    settings = get_payroll_settings(
        company=filters.company,
        reference_date=filters.to_date,
    )

    data = []

    for payroll_entry in get_payroll_entries(filters):
        row = reconcile_payroll_entry(
            payroll_entry,
            settings,
        )

        if (
            filters.show == "Mismatches Only"
            and row["status"] == "OK"
        ):
            continue

        data.append(row)

    return get_columns(), data


def validate_filters(filters):
    if not filters.company:
        frappe.throw(_("Company is required."))

    if not filters.from_date:
        frappe.throw(_("From Date is required."))

    if not filters.to_date:
        frappe.throw(_("To Date is required."))

    if getdate(filters.from_date) > getdate(filters.to_date):
        frappe.throw(
            _("From Date cannot be after To Date.")
        )


def get_payroll_entries(filters):
    conditions = [
        "company = %(company)s",
        "docstatus = 1",
        "posting_date >= %(from_date)s",
        "posting_date <= %(to_date)s",
    ]

    values = {
        "company": filters.company,
        "from_date": filters.from_date,
        "to_date": filters.to_date,
    }

    if filters.payroll_entry:
        conditions.append(
            "name = %(payroll_entry)s"
        )

        values["payroll_entry"] = (
            filters.payroll_entry
        )

    return frappe.db.sql(
        f"""
        SELECT
            name,
            company,
            posting_date,
            start_date,
            end_date,
            number_of_employees,
            payroll_payable_account,
            currency
        FROM
            `tabPayroll Entry`
        WHERE
            {" AND ".join(conditions)}
        ORDER BY
            posting_date DESC,
            name DESC
        """,
        values,
        as_dict=True,
    )


def reconcile_payroll_entry(
    payroll_entry,
    settings,
):
    slips = frappe.get_all(
        "Salary Slip",
        filters={
            "payroll_entry":
                payroll_entry.name,
            "docstatus": 1,
        },
        fields=[
            "name",
            "employee",
            "gross_pay",
            "total_deduction",
            "net_pay",
            "journal_entry",
        ],
    )

    if not slips:
        return empty_row(
            payroll_entry,
            "NO SLIPS",
        )

    slip_names = [
        row.name
        for row in slips
    ]

    journal_entries = sorted({
        row.journal_entry
        for row in slips
        if row.journal_entry
    })

    payroll_gross = sum(
        flt(row.gross_pay)
        for row in slips
    )

    payroll_deductions = sum(
        flt(row.total_deduction)
        for row in slips
    )

    payroll_net = sum(
        flt(row.net_pay)
        for row in slips
    )

    components = get_component_totals(
        slip_names
    )

    employee_inss = component_value(
        components,
        settings.inss_salary_component
        or "Seguranca Social",
    )

    irt = component_value(
        components,
        settings.irt_salary_component
        or (
            "Imposto Sobre o "
            "Rendimento do Trabalho"
        ),
    )

    holiday = (
        component_value(
            components,
            settings.holyday_allowance_salary_component
            or "Subsidio de Ferias",
        )
        + component_value(
            components,
            "Proporcional Subsidio Ferias",
        )
    )

    christmas = (
        component_value(
            components,
            settings.christmas_allowance_salary_component
            or "Subsidio de Natal",
        )
        + component_value(
            components,
            "Proporcional Subsidio Natal",
        )
    )

    other_deductions = (
        payroll_deductions
        - employee_inss
        - irt
    )

    if not journal_entries:
        row = base_row(
            payroll_entry,
            slips,
            journal_entries,
        )

        row.update({
            "payroll_gross":
                payroll_gross,
            "payroll_deductions":
                payroll_deductions,
            "payroll_net":
                payroll_net,
            "employee_inss":
                employee_inss,
            "irt":
                irt,
            "other_deductions":
                other_deductions,
            "holiday_allowance":
                holiday,
            "christmas_allowance":
                christmas,
            "status":
                "NO GL",
        })

        return row

    gl_entries = frappe.get_all(
        "GL Entry",
        filters={
            "voucher_type":
                "Journal Entry",
            "voucher_no": [
                "in",
                journal_entries,
            ],
            "company":
                payroll_entry.company,
            "is_cancelled": 0,
        },
        fields=[
            "voucher_no",
            "account",
            "party_type",
            "party",
            "debit",
            "credit",
        ],
    )

    if not gl_entries:
        row = base_row(
            payroll_entry,
            slips,
            journal_entries,
        )

        row.update({
            "payroll_gross":
                payroll_gross,
            "payroll_deductions":
                payroll_deductions,
            "payroll_net":
                payroll_net,
            "employee_inss":
                employee_inss,
            "irt":
                irt,
            "other_deductions":
                other_deductions,
            "holiday_allowance":
                holiday,
            "christmas_allowance":
                christmas,
            "status":
                "NO GL",
        })

        return row

    gl_total_debit = sum(
        flt(row.debit)
        for row in gl_entries
    )

    gl_total_credit = sum(
        flt(row.credit)
        for row in gl_entries
    )

    employer_inss = account_net_debit(
        gl_entries,
        settings.custom_inss_employer_expense_account,
    )

    gl_inss_liability = account_net_credit(
        gl_entries,
        settings.custom_inss_liability_account,
    )

    gl_irt = party_net_credit(
        gl_entries,
        party_type="Estado",
        party="IRT",
    )

    gl_payroll_payable = account_net_credit(
        gl_entries,
        payroll_entry.payroll_payable_account,
    )

    gl_holiday = account_net_debit(
        gl_entries,
        settings.custom_holiday_accrual_liability_account,
    )

    gl_christmas = account_net_debit(
        gl_entries,
        settings.custom_christmas_accrual_liability_account,
    )

    #
    # Total employee deductions represented in GL:
    #
    # total credits
    # - salary payable
    # - employer INSS liability contribution
    #
    gl_employee_deductions = (
        gl_total_credit
        - gl_payroll_payable
        - employer_inss
    )

    gl_other_deductions = (
        gl_employee_deductions
        - employee_inss
        - irt
    )

    #
    # Gross payroll represented by GL:
    #
    # total debits
    # - employer INSS expense
    #
    gl_gross = (
        gl_total_debit
        - employer_inss
    )

    gross_difference = (
        gl_gross
        - payroll_gross
    )

    deductions_difference = (
        gl_employee_deductions
        - payroll_deductions
    )

    net_difference = (
        gl_payroll_payable
        - payroll_net
    )

    employee_inss_gl = (
        gl_inss_liability
        - employer_inss
    )

    employee_inss_difference = (
        employee_inss_gl
        - employee_inss
    )

    employer_inss_difference = (
        gl_inss_liability
        - employee_inss
        - employer_inss
    )

    irt_difference = (
        gl_irt
        - irt
    )

    holiday_difference = (
        gl_holiday
        - holiday
    )

    christmas_difference = (
        gl_christmas
        - christmas
    )

    gl_balance_difference = (
        gl_total_debit
        - gl_total_credit
    )

    #
    # Sum of absolute discrepancies gives one control number.
    # Zero means every independent control reconciled.
    #
    control_difference = sum(
        abs(flt(value))
        for value in [
            gross_difference,
            deductions_difference,
            net_difference,
            employee_inss_difference,
            employer_inss_difference,
            irt_difference,
            holiday_difference,
            christmas_difference,
            gl_balance_difference,
        ]
    )

    status = (
        "OK"
        if control_difference <= TOLERANCE
        else "MISMATCH"
    )

    row = base_row(
        payroll_entry,
        slips,
        journal_entries,
    )

    row.update({
        "payroll_gross":
            payroll_gross,

        "gl_gross":
            gl_gross,

        "gross_difference":
            gross_difference,

        "payroll_deductions":
            payroll_deductions,

        "gl_employee_deductions":
            gl_employee_deductions,

        "deductions_difference":
            deductions_difference,

        "payroll_net":
            payroll_net,

        "gl_payroll_payable":
            gl_payroll_payable,

        "net_difference":
            net_difference,

        "employee_inss":
            employee_inss,

        "employee_inss_gl":
            employee_inss_gl,

        "employee_inss_difference":
            employee_inss_difference,

        "employer_inss":
            employer_inss,

        "gl_inss_liability":
            gl_inss_liability,

        "employer_inss_difference":
            employer_inss_difference,

        "irt":
            irt,

        "gl_irt":
            gl_irt,

        "irt_difference":
            irt_difference,

        "other_deductions":
            other_deductions,

        "gl_other_deductions":
            gl_other_deductions,

        "holiday_allowance":
            holiday,

        "gl_holiday_liability":
            gl_holiday,

        "holiday_difference":
            holiday_difference,

        "christmas_allowance":
            christmas,

        "gl_christmas_liability":
            gl_christmas,

        "christmas_difference":
            christmas_difference,

        "gl_total_debit":
            gl_total_debit,

        "gl_total_credit":
            gl_total_credit,

        "gl_balance_difference":
            gl_balance_difference,

        "control_difference":
            control_difference,

        "status":
            status,
    })

    return row


def get_component_totals(slip_names):
    rows = frappe.get_all(
        "Salary Detail",
        filters={
            "parent": ["in", slip_names],
            "parenttype": "Salary Slip",
        },
        fields=[
            "salary_component",
            "amount",
        ],
    )

    result = {}

    for row in rows:
        result[row.salary_component] = (
            result.get(
                row.salary_component,
                0,
            )
            + flt(row.amount)
        )

    return result


def component_value(
    components,
    component,
):
    if not component:
        return 0.0

    return flt(
        components.get(
            component,
            0,
        )
    )


def account_net_debit(
    gl_entries,
    account,
):
    if not account:
        return 0.0

    return sum(
        flt(row.debit)
        - flt(row.credit)
        for row in gl_entries
        if row.account == account
    )


def account_net_credit(
    gl_entries,
    account,
):
    if not account:
        return 0.0

    return sum(
        flt(row.credit)
        - flt(row.debit)
        for row in gl_entries
        if row.account == account
    )


def party_net_credit(
    gl_entries,
    party_type,
    party,
):
    return sum(
        flt(row.credit)
        - flt(row.debit)
        for row in gl_entries
        if (
            row.party_type == party_type
            and row.party == party
        )
    )


def base_row(
    payroll_entry,
    slips,
    journal_entries,
):
    return {
        "posting_date":
            payroll_entry.posting_date,

        "start_date":
            payroll_entry.start_date,

        "end_date":
            payroll_entry.end_date,

        "payroll_entry":
            payroll_entry.name,

        "employee_count":
            len(slips),

        "journal_entries":
            ", ".join(journal_entries),
    }


def empty_row(
    payroll_entry,
    status,
):
    row = base_row(
        payroll_entry,
        [],
        [],
    )

    row["status"] = status

    return row


def get_columns():
    return [
        {
            "label": _("Posting Date"),
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": _("Period Start"),
            "fieldname": "start_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": _("Period End"),
            "fieldname": "end_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": _("Payroll Entry"),
            "fieldname": "payroll_entry",
            "fieldtype": "Link",
            "options": "Payroll Entry",
            "width": 170,
        },
        {
            "label": _("Employees"),
            "fieldname": "employee_count",
            "fieldtype": "Int",
            "width": 80,
        },

        {
            "label": _("Payroll Gross"),
            "fieldname": "payroll_gross",
            "fieldtype": "Currency",
            "width": 125,
        },
        {
            "label": _("GL Gross"),
            "fieldname": "gl_gross",
            "fieldtype": "Currency",
            "width": 125,
        },
        {
            "label": _("Gross Difference"),
            "fieldname": "gross_difference",
            "fieldtype": "Currency",
            "width": 125,
        },

        {
            "label": _("Payroll Deductions"),
            "fieldname": "payroll_deductions",
            "fieldtype": "Currency",
            "width": 135,
        },
        {
            "label": _("GL Deductions"),
            "fieldname": "gl_employee_deductions",
            "fieldtype": "Currency",
            "width": 125,
        },
        {
            "label": _("Deduction Difference"),
            "fieldname": "deductions_difference",
            "fieldtype": "Currency",
            "width": 135,
        },

        {
            "label": _("Payroll Net"),
            "fieldname": "payroll_net",
            "fieldtype": "Currency",
            "width": 125,
        },
        {
            "label": _("GL Salary Payable"),
            "fieldname": "gl_payroll_payable",
            "fieldtype": "Currency",
            "width": 135,
        },
        {
            "label": _("Net Difference"),
            "fieldname": "net_difference",
            "fieldtype": "Currency",
            "width": 120,
        },

        {
            "label": _("Employee INSS"),
            "fieldname": "employee_inss",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": _("Employee INSS GL"),
            "fieldname": "employee_inss_gl",
            "fieldtype": "Currency",
            "width": 125,
        },
        {
            "label": _("Employee INSS Δ"),
            "fieldname": "employee_inss_difference",
            "fieldtype": "Currency",
            "width": 120,
        },

        {
            "label": _("Employer INSS"),
            "fieldname": "employer_inss",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": _("Total INSS Liability"),
            "fieldname": "gl_inss_liability",
            "fieldtype": "Currency",
            "width": 135,
        },
        {
            "label": _("INSS Difference"),
            "fieldname": "employer_inss_difference",
            "fieldtype": "Currency",
            "width": 120,
        },

        {
            "label": _("Payroll IRT"),
            "fieldname": "irt",
            "fieldtype": "Currency",
            "width": 115,
        },
        {
            "label": _("GL IRT"),
            "fieldname": "gl_irt",
            "fieldtype": "Currency",
            "width": 115,
        },
        {
            "label": _("IRT Difference"),
            "fieldname": "irt_difference",
            "fieldtype": "Currency",
            "width": 115,
        },

        {
            "label": _("Other Deductions"),
            "fieldname": "other_deductions",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": _("GL Other Deductions"),
            "fieldname": "gl_other_deductions",
            "fieldtype": "Currency",
            "width": 135,
        },

        {
            "label": _("Holiday Allowance"),
            "fieldname": "holiday_allowance",
            "fieldtype": "Currency",
            "width": 125,
        },
        {
            "label": _("GL Holiday Liability"),
            "fieldname": "gl_holiday_liability",
            "fieldtype": "Currency",
            "width": 135,
        },
        {
            "label": _("Holiday Difference"),
            "fieldname": "holiday_difference",
            "fieldtype": "Currency",
            "width": 125,
        },

        {
            "label": _("Christmas Allowance"),
            "fieldname": "christmas_allowance",
            "fieldtype": "Currency",
            "width": 135,
        },
        {
            "label": _("GL Christmas Liability"),
            "fieldname": "gl_christmas_liability",
            "fieldtype": "Currency",
            "width": 145,
        },
        {
            "label": _("Christmas Difference"),
            "fieldname": "christmas_difference",
            "fieldtype": "Currency",
            "width": 135,
        },

        {
            "label": _("GL Debit"),
            "fieldname": "gl_total_debit",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": _("GL Credit"),
            "fieldname": "gl_total_credit",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": _("GL Balance Δ"),
            "fieldname": "gl_balance_difference",
            "fieldtype": "Currency",
            "width": 110,
        },

        {
            "label": _("Control Difference"),
            "fieldname": "control_difference",
            "fieldtype": "Currency",
            "width": 125,
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "label": _("Journal Entries"),
            "fieldname": "journal_entries",
            "fieldtype": "Data",
            "width": 160,
        },
    ]
