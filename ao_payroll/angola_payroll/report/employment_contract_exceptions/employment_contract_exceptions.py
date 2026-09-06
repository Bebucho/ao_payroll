import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate


FIXED_TERM = "Contrato por Tempo Determinado"
INDEFINITE = "Contrato por Tempo Indeterminado"


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)

    employees = get_employees(filters)

    data = []

    for employee in employees:
        data.extend(
            evaluate_employee(
                employee,
                filters,
            )
        )

    data = [
        row
        for row in data
        if row_matches_filters(
            row,
            filters,
        )
    ]

    data.sort(
        key=lambda row: (
            severity_order(
                row["severity"]
            ),
            row.get("contract_end_date")
            or getdate("9999-12-31"),
            row.get("employee") or "",
        )
    )

    return get_columns(), data


def validate_filters(filters):
    if not filters.company:
        frappe.throw(
            _("Company is required.")
        )

    if not filters.as_of_date:
        frappe.throw(
            _("As Of Date is required.")
        )

    if (
        filters.expiry_warning_days is not None
        and cint(filters.expiry_warning_days) < 0
    ):
        frappe.throw(
            _(
                "Expiry Warning Days cannot "
                "be negative."
            )
        )


def get_employees(filters):
    conditions = [
        "company = %(company)s",
    ]

    values = {
        "company": filters.company,
    }

    if filters.employee:
        conditions.append(
            "name = %(employee)s"
        )
        values["employee"] = (
            filters.employee
        )

    return frappe.db.sql(
        f"""
        SELECT
            name,
            employee_name,
            status,
            employment_type,
            date_of_joining,
            contract_end_date,
            scheduled_confirmation_date,
            final_confirmation_date,
            relieving_date,
            notice_number_of_days,
            custom_contract_type,
            custom_contract_form,
            custom_fixed_term_reason,
            custom_contract_renewal_number,
            custom_last_contract_renewal_date
        FROM
            `tabEmployee`
        WHERE
            {" AND ".join(conditions)}
        ORDER BY
            employee_name,
            name
        """,
        values,
        as_dict=True,
    )


def evaluate_employee(
    employee,
    filters,
):
    rows = []

    as_of_date = getdate(
        filters.as_of_date
    )

    warning_days = cint(
        filters.expiry_warning_days or 30
    )

    warning_limit = add_days(
        as_of_date,
        warning_days,
    )

    contract_type = (
        employee.custom_contract_type
        or ""
    )

    contract_form = (
        employee.custom_contract_form
        or ""
    )

    fixed_term_reason = (
        employee.custom_fixed_term_reason
        or ""
    ).strip()

    renewal_number = cint(
        employee.custom_contract_renewal_number
        or 0
    )

    renewal_date = (
        employee.custom_last_contract_renewal_date
    )

    end_date = (
        getdate(employee.contract_end_date)
        if employee.contract_end_date
        else None
    )

    scheduled_confirmation = (
        getdate(
            employee.scheduled_confirmation_date
        )
        if employee.scheduled_confirmation_date
        else None
    )

    final_confirmation = (
        getdate(
            employee.final_confirmation_date
        )
        if employee.final_confirmation_date
        else None
    )

    #
    # Missing classification
    #
    if not contract_type:
        rows.append(
            make_row(
                employee=employee,
                severity="INFO",
                exception_type=
                    "Missing Contract Classification",
                description=(
                    "Employee has no Angola "
                    "Contract Type defined."
                ),
            )
        )

    #
    # Fixed-term controls
    #
    if contract_type == FIXED_TERM:

        if not end_date:
            rows.append(
                make_row(
                    employee=employee,
                    severity="CRITICAL",
                    exception_type=
                        "Fixed-Term Without End Date",
                    description=(
                        "Fixed-term contract has "
                        "no Contract End Date."
                    ),
                )
            )

        if not fixed_term_reason:
            rows.append(
                make_row(
                    employee=employee,
                    severity="CRITICAL",
                    exception_type=
                        "Fixed-Term Without Legal Reason",
                    description=(
                        "Fixed-term contract has "
                        "no recorded legal reason."
                    ),
                )
            )

        if contract_form == "Verbal":
            rows.append(
                make_row(
                    employee=employee,
                    severity="WARNING",
                    exception_type=
                        "Fixed-Term Verbal Contract",
                    description=(
                        "Fixed-term contract is "
                        "recorded as verbal. Verify "
                        "that a legal exception applies."
                    ),
                )
            )

        if end_date:

            if (
                employee.status == "Active"
                and end_date < as_of_date
            ):
                rows.append(
                    make_row(
                        employee=employee,
                        severity="CRITICAL",
                        exception_type=
                            "Expired Fixed-Term Contract",
                        contract_end_date=end_date,
                        description=(
                            "Employee is Active but "
                            f"fixed-term contract expired "
                            f"on {end_date}."
                        ),
                    )
                )

            elif (
                employee.status == "Active"
                and as_of_date
                <= end_date
                <= warning_limit
            ):
                days_remaining = (
                    end_date - as_of_date
                ).days

                rows.append(
                    make_row(
                        employee=employee,
                        severity="WARNING",
                        exception_type=
                            "Contract Expiring Soon",
                        contract_end_date=end_date,
                        description=(
                            "Fixed-term contract expires "
                            f"in {days_remaining} day(s), "
                            f"on {end_date}."
                        ),
                    )
                )

    #
    # Indefinite contract consistency
    #
    if (
        contract_type == INDEFINITE
        and end_date
    ):
        rows.append(
            make_row(
                employee=employee,
                severity="WARNING",
                exception_type=
                    "Indefinite Contract With End Date",
                contract_end_date=end_date,
                description=(
                    "Indefinite-term contract has "
                    "a Contract End Date. Verify "
                    "the employee record."
                ),
            )
        )

    #
    # Confirmation / probation control
    #
    if (
        employee.status == "Active"
        and scheduled_confirmation
        and scheduled_confirmation < as_of_date
        and not final_confirmation
    ):
        days_overdue = (
            as_of_date
            - scheduled_confirmation
        ).days

        rows.append(
            make_row(
                employee=employee,
                severity="WARNING",
                exception_type=
                    "Overdue Confirmation",
                description=(
                    "Scheduled confirmation date "
                    f"passed {days_overdue} day(s) ago "
                    "and no final confirmation date "
                    "is recorded."
                ),
            )
        )

    #
    # Renewal consistency
    #
    if (
        renewal_number > 0
        and not renewal_date
    ):
        rows.append(
            make_row(
                employee=employee,
                severity="CRITICAL",
                exception_type=
                    "Renewal Data Inconsistent",
                description=(
                    "Contract Renewal Number is "
                    f"{renewal_number}, but Last "
                    "Contract Renewal Date is blank."
                ),
            )
        )

    if (
        renewal_date
        and renewal_number == 0
    ):
        rows.append(
            make_row(
                employee=employee,
                severity="CRITICAL",
                exception_type=
                    "Renewal Data Inconsistent",
                description=(
                    "Last Contract Renewal Date "
                    "is populated but Contract "
                    "Renewal Number is zero."
                ),
            )
        )

    return rows


def make_row(
    employee,
    severity,
    exception_type,
    description,
    contract_end_date=None,
):
    return {
        "severity":
            severity,

        "exception_type":
            exception_type,

        "employee":
            employee.name,

        "employee_name":
            employee.employee_name,

        "status":
            employee.status,

        "employment_type":
            employee.employment_type,

        "contract_type":
            employee.custom_contract_type,

        "contract_form":
            employee.custom_contract_form,

        "date_of_joining":
            employee.date_of_joining,

        "contract_end_date":
            contract_end_date
            or employee.contract_end_date,

        "scheduled_confirmation_date":
            employee.scheduled_confirmation_date,

        "final_confirmation_date":
            employee.final_confirmation_date,

        "description":
            description,
    }


def row_matches_filters(
    row,
    filters,
):
    if (
        filters.severity
        and row["severity"]
        != filters.severity
    ):
        return False

    if (
        filters.exception_type
        and row["exception_type"]
        != filters.exception_type
    ):
        return False

    return True


def severity_order(severity):
    return {
        "CRITICAL": 0,
        "WARNING": 1,
        "INFO": 2,
    }.get(
        severity,
        99,
    )


def get_columns():
    return [
        {
            "label": _("Severity"),
            "fieldname": "severity",
            "fieldtype": "Data",
            "width": 90,
        },
        {
            "label": _("Exception Type"),
            "fieldname": "exception_type",
            "fieldtype": "Data",
            "width": 220,
        },
        {
            "label": _("Employee"),
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 125,
        },
        {
            "label": _("Employee Name"),
            "fieldname": "employee_name",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 90,
        },
        {
            "label": _("Employment Type"),
            "fieldname": "employment_type",
            "fieldtype": "Link",
            "options": "Employment Type",
            "width": 150,
        },
        {
            "label": _("Contract Type"),
            "fieldname": "contract_type",
            "fieldtype": "Data",
            "width": 210,
        },
        {
            "label": _("Contract Form"),
            "fieldname": "contract_form",
            "fieldtype": "Data",
            "width": 110,
        },
        {
            "label": _("Date of Joining"),
            "fieldname": "date_of_joining",
            "fieldtype": "Date",
            "width": 105,
        },
        {
            "label": _("Contract End"),
            "fieldname": "contract_end_date",
            "fieldtype": "Date",
            "width": 105,
        },
        {
            "label": _("Scheduled Confirmation"),
            "fieldname":
                "scheduled_confirmation_date",
            "fieldtype": "Date",
            "width": 145,
        },
        {
            "label": _("Final Confirmation"),
            "fieldname":
                "final_confirmation_date",
            "fieldtype": "Date",
            "width": 130,
        },
        {
            "label": _("Description"),
            "fieldname": "description",
            "fieldtype": "Data",
            "width": 420,
        },
    ]
