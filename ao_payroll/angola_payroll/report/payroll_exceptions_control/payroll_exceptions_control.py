import frappe
from ao_payroll.payroll.settings import get_payroll_settings
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)

    settings = get_payroll_settings(
        company=filters.company,
        reference_date=filters.to_date,
    )

    data = []

    data.extend(
        check_configuration(
            settings,
            filters,
        )
    )

    employees = get_employees(filters)

    data.extend(
        check_employees(
            employees,
            filters,
        )
    )

    data.extend(
        check_salary_structure_assignments(
            employees,
            filters,
        )
    )

    data.extend(
        check_salary_slips(
            settings,
            filters,
        )
    )

    data.extend(
        check_payroll_entries(
            filters,
        )
    )

    data.extend(
        check_additional_salary(
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
            row.get("employee") or "",
            row["exception_type"],
        )
    )

    return get_columns(), data


def validate_filters(filters):
    if not filters.company:
        frappe.throw(
            _("Company is required.")
        )

    if not filters.from_date:
        frappe.throw(
            _("From Date is required.")
        )

    if not filters.to_date:
        frappe.throw(
            _("To Date is required.")
        )

    if (
        getdate(filters.from_date)
        > getdate(filters.to_date)
    ):
        frappe.throw(
            _(
                "From Date cannot be "
                "after To Date."
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
            date_of_joining,
            relieving_date
        FROM
            `tabEmployee`
        WHERE
            {" AND ".join(conditions)}
        ORDER BY
            name
        """,
        values,
        as_dict=True,
    )


def check_configuration(
    settings,
    filters,
):
    missing = []

    required = {
        "INSS Salary Component":
            settings.inss_salary_component,

        "IRT Salary Component":
            settings.irt_salary_component,

        "INSS Employer Expense Account":
            settings.custom_inss_employer_expense_account,

        "INSS Liability Account":
            settings.custom_inss_liability_account,
    }

    for label, value in required.items():
        if not value:
            missing.append(label)

    if not missing:
        return []

    return [
        make_row(
            severity="CRITICAL",
            exception_type=
                "Missing Payroll Configuration",
            description=(
                "Missing Angola Payroll Settings: "
                + ", ".join(missing)
            ),
            reference_doctype=
                "Angola Payroll Settings",
            reference_name=
                "Angola Payroll Settings",
        )
    ]


def check_employees(
    employees,
    filters,
):
    rows = []

    period_start = getdate(
        filters.from_date
    )

    period_end = getdate(
        filters.to_date
    )

    for employee in employees:

        if (
            employee.date_of_joining
            and period_start
            <= getdate(
                employee.date_of_joining
            )
            <= period_end
        ):
            rows.append(
                make_row(
                    severity="INFO",
                    exception_type=
                        "New Employee",
                    employee=employee,
                    description=(
                        "Employee joined during "
                        "the selected payroll period."
                    ),
                    reference_doctype=
                        "Employee",
                    reference_name=
                        employee.name,
                )
            )

        if (
            employee.relieving_date
            and period_start
            <= getdate(
                employee.relieving_date
            )
            <= period_end
        ):
            rows.append(
                make_row(
                    severity="INFO",
                    exception_type=
                        "Employee Leaving",
                    employee=employee,
                    description=(
                        "Employee relieving date "
                        "falls within the selected "
                        "payroll period."
                    ),
                    reference_doctype=
                        "Employee",
                    reference_name=
                        employee.name,
                )
            )

    return rows


def check_salary_structure_assignments(
    employees,
    filters,
):
    rows = []

    period_end = getdate(
        filters.to_date
    )

    for employee in employees:

        #
        # Only employees who had already joined by period end
        # are expected to have an effective assignment.
        #
        if (
            employee.date_of_joining
            and getdate(
                employee.date_of_joining
            ) > period_end
        ):
            continue

        #
        # Employees relieved before the period started are not
        # expected to have an active payroll assignment.
        #
        if (
            employee.relieving_date
            and getdate(
                employee.relieving_date
            ) < getdate(
                filters.from_date
            )
        ):
            continue

        assignments = frappe.get_all(
            "Salary Structure Assignment",
            filters={
                "employee":
                    employee.name,
                "company":
                    filters.company,
                "docstatus":
                    1,
                "from_date": [
                    "<=",
                    filters.to_date,
                ],
            },
            fields=[
                "name",
                "from_date",
                "salary_structure",
            ],
            order_by=(
                "from_date desc, "
                "creation desc"
            ),
        )

        if not assignments:
            rows.append(
                make_row(
                    severity="CRITICAL",
                    exception_type=
                        "No Active SSA",
                    employee=employee,
                    description=(
                        "No submitted Salary Structure "
                        "Assignment is effective by the "
                        "end of the selected period."
                    ),
                    reference_doctype=
                        "Employee",
                    reference_name=
                        employee.name,
                )
            )

            continue

        #
        # Multiple historical assignments are valid.
        # The problematic case is more than one submitted
        # assignment effective on the same date.
        #
        grouped = {}

        for assignment in assignments:
            key = str(
                assignment.from_date
            )

            grouped.setdefault(
                key,
                [],
            ).append(
                assignment
            )

        for effective_date, group in grouped.items():
            if len(group) <= 1:
                continue

            rows.append(
                make_row(
                    severity="CRITICAL",
                    exception_type=
                        "Duplicate SSA Effective Date",
                    employee=employee,
                    description=(
                        f"{len(group)} submitted Salary "
                        "Structure Assignments have the "
                        f"same effective date "
                        f"{effective_date}: "
                        + ", ".join(
                            row.name
                            for row in group
                        )
                    ),
                    reference_doctype=
                        "Salary Structure Assignment",
                    reference_name=
                        group[0].name,
                )
            )

    return rows


def check_salary_slips(
    settings,
    filters,
):
    rows = []

    conditions = [
        "ss.company = %(company)s",
        "ss.docstatus = 1",
        "ss.end_date >= %(from_date)s",
        "ss.start_date <= %(to_date)s",
    ]

    values = {
        "company":
            filters.company,
        "from_date":
            filters.from_date,
        "to_date":
            filters.to_date,
    }

    if filters.employee:
        conditions.append(
            "ss.employee = %(employee)s"
        )

        values["employee"] = (
            filters.employee
        )

    slips = frappe.db.sql(
        f"""
        SELECT
            ss.name,
            ss.employee,
            ss.employee_name,
            ss.start_date,
            ss.end_date,
            ss.payroll_entry,
            ss.journal_entry,
            ss.gross_pay,
            ss.net_pay
        FROM
            `tabSalary Slip` ss
        WHERE
            {" AND ".join(conditions)}
        ORDER BY
            ss.employee,
            ss.end_date
        """,
        values,
        as_dict=True,
    )

    if not slips:
        return rows

    employee_data = {
        row.name: row
        for row in frappe.get_all(
            "Employee",
            filters={
                "name": [
                    "in",
                    list({
                        slip.employee
                        for slip in slips
                    }),
                ]
            },
            fields=[
                "name",
                "employee_name",
                "relieving_date",
            ],
        )
    }

    slip_names = [
        slip.name
        for slip in slips
    ]

    component_rows = frappe.get_all(
        "Salary Detail",
        filters={
            "parent": [
                "in",
                slip_names,
            ],
            "parenttype":
                "Salary Slip",
        },
        fields=[
            "parent",
            "salary_component",
            "amount",
        ],
    )

    components_by_slip = {}

    for component in component_rows:
        components_by_slip.setdefault(
            component.parent,
            set(),
        ).add(
            component.salary_component
        )

    inss_component = (
        settings.inss_salary_component
        or "Seguranca Social"
    )

    irt_component = (
        settings.irt_salary_component
        or (
            "Imposto Sobre o "
            "Rendimento do Trabalho"
        )
    )

    for slip in slips:

        employee = employee_data.get(
            slip.employee
        )

        employee_dict = frappe._dict({
            "name":
                slip.employee,
            "employee_name":
                slip.employee_name,
        })

        if not slip.payroll_entry:
            rows.append(
                make_row(
                    severity="CRITICAL",
                    exception_type=
                        "Salary Slip Without Payroll Entry",
                    employee=
                        employee_dict,
                    description=(
                        "Submitted Salary Slip "
                        "has no Payroll Entry."
                    ),
                    reference_doctype=
                        "Salary Slip",
                    reference_name=
                        slip.name,
                )
            )

        if not slip.journal_entry:
            rows.append(
                make_row(
                    severity="CRITICAL",
                    exception_type=
                        "Submitted Slip Without Journal Entry",
                    employee=
                        employee_dict,
                    description=(
                        "Submitted Salary Slip "
                        "has no linked Journal Entry."
                    ),
                    reference_doctype=
                        "Salary Slip",
                    reference_name=
                        slip.name,
                )
            )

        if flt(slip.net_pay) <= 0:
            rows.append(
                make_row(
                    severity="WARNING",
                    exception_type=
                        "Non-Positive Net Pay",
                    employee=
                        employee_dict,
                    amount=
                        slip.net_pay,
                    description=(
                        "Submitted Salary Slip "
                        "has net pay less than "
                        "or equal to zero."
                    ),
                    reference_doctype=
                        "Salary Slip",
                    reference_name=
                        slip.name,
                )
            )

        if (
            employee
            and employee.relieving_date
            and getdate(
                employee.relieving_date
            ) < getdate(
                slip.start_date
            )
        ):
            rows.append(
                make_row(
                    severity="CRITICAL",
                    exception_type=
                        "Relieved Employee Paid",
                    employee=
                        employee_dict,
                    amount=
                        slip.net_pay,
                    description=(
                        "Employee relieving date "
                        "is before the Salary Slip "
                        "payroll period."
                    ),
                    reference_doctype=
                        "Salary Slip",
                    reference_name=
                        slip.name,
                )
            )

        slip_components = (
            components_by_slip.get(
                slip.name,
                set(),
            )
        )

        if (
            inss_component
            not in slip_components
        ):
            rows.append(
                make_row(
                    severity="WARNING",
                    exception_type=
                        "Missing INSS Component",
                    employee=
                        employee_dict,
                    description=(
                        f"Salary Slip does not "
                        f"contain configured INSS "
                        f"component "
                        f"{inss_component}."
                    ),
                    reference_doctype=
                        "Salary Slip",
                    reference_name=
                        slip.name,
                )
            )

        if (
            irt_component
            not in slip_components
        ):
            rows.append(
                make_row(
                    severity="WARNING",
                    exception_type=
                        "Missing IRT Component",
                    employee=
                        employee_dict,
                    description=(
                        f"Salary Slip does not "
                        f"contain configured IRT "
                        f"component "
                        f"{irt_component}."
                    ),
                    reference_doctype=
                        "Salary Slip",
                    reference_name=
                        slip.name,
                )
            )

    return rows


def check_payroll_entries(filters):
    rows = []

    payroll_entries = frappe.get_all(
        "Payroll Entry",
        filters={
            "company":
                filters.company,
            "docstatus":
                1,
            "posting_date": [
                "between",
                [
                    filters.from_date,
                    filters.to_date,
                ],
            ],
        },
        fields=[
            "name",
            "posting_date",
            "start_date",
            "end_date",
        ],
    )

    for payroll_entry in payroll_entries:

        submitted_slips = frappe.db.count(
            "Salary Slip",
            {
                "payroll_entry":
                    payroll_entry.name,
                "docstatus":
                    1,
            },
        )

        if submitted_slips:
            continue

        rows.append(
            make_row(
                severity="CRITICAL",
                exception_type=
                    "Payroll Entry Without Submitted Slips",
                description=(
                    "Submitted Payroll Entry "
                    "has no submitted Salary Slips."
                ),
                reference_doctype=
                    "Payroll Entry",
                reference_name=
                    payroll_entry.name,
            )
        )

    return rows


def check_additional_salary(filters):
    conditions = [
        "company = %(company)s",
        "docstatus = 1",
        "payroll_date >= %(from_date)s",
        "payroll_date <= %(to_date)s",
        "(ref_doctype IS NULL OR ref_doctype = '')",
        "(ref_docname IS NULL OR ref_docname = '')",
    ]

    values = {
        "company":
            filters.company,
        "from_date":
            filters.from_date,
        "to_date":
            filters.to_date,
    }

    if filters.employee:
        conditions.append(
            "employee = %(employee)s"
        )

        values["employee"] = (
            filters.employee
        )

    records = frappe.db.sql(
        f"""
        SELECT
            name,
            employee,
            employee_name,
            salary_component,
            amount,
            payroll_date
        FROM
            `tabAdditional Salary`
        WHERE
            {" AND ".join(conditions)}
        ORDER BY
            payroll_date,
            employee
        """,
        values,
        as_dict=True,
    )

    rows = []

    for record in records:
        employee = frappe._dict({
            "name":
                record.employee,
            "employee_name":
                record.employee_name,
        })

        rows.append(
            make_row(
                severity="WARNING",
                exception_type=
                    "Manual Additional Salary",
                employee=employee,
                amount=record.amount,
                description=(
                    f"Manual Additional Salary: "
                    f"{record.salary_component} "
                    f"on {record.payroll_date}."
                ),
                reference_doctype=
                    "Additional Salary",
                reference_name=
                    record.name,
            )
        )

    return rows


def make_row(
    severity,
    exception_type,
    description,
    employee=None,
    amount=None,
    reference_doctype=None,
    reference_name=None,
):
    return {
        "severity":
            severity,

        "exception_type":
            exception_type,

        "employee":
            employee.name
            if employee
            else None,

        "employee_name":
            employee.employee_name
            if employee
            else None,

        "amount":
            flt(amount)
            if amount is not None
            else None,

        "description":
            description,

        "reference_doctype":
            reference_doctype,

        "reference_name":
            reference_name,
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
            "width": 190,
        },
        {
            "label": _("Amount"),
            "fieldname": "amount",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": _("Description"),
            "fieldname": "description",
            "fieldtype": "Data",
            "width": 420,
        },
        {
            "label": _("Reference Type"),
            "fieldname": "reference_doctype",
            "fieldtype": "Link",
            "options": "DocType",
            "width": 170,
        },
        {
            "label": _("Reference"),
            "fieldname": "reference_name",
            "fieldtype": "Dynamic Link",
            "options": "reference_doctype",
            "width": 190,
        },
    ]
