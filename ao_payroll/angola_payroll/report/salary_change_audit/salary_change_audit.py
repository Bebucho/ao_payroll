import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
    filters = frappe._dict(filters or {})

    validate_filters(filters)

    columns = get_columns()
    data = get_data(filters)

    return columns, data


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


def get_columns():
    return [
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
            "width": 180,
        },
        {
            "label": _("Effective Date"),
            "fieldname": "effective_date",
            "fieldtype": "Date",
            "width": 105,
        },
        {
            "label": _("Previous Base"),
            "fieldname": "previous_base",
            "fieldtype": "Float",
            "precision": 2,
            "width": 120,
        },
        {
            "label": _("New Base"),
            "fieldname": "new_base",
            "fieldtype": "Float",
            "precision": 2,
            "width": 120,
        },
        {
            "label": _("Difference"),
            "fieldname": "difference",
            "fieldtype": "Float",
            "precision": 2,
            "width": 115,
        },
        {
            "label": _("Difference %"),
            "fieldname": "difference_percent",
            "fieldtype": "Percent",
            "width": 100,
        },
        {
            "label": _("Previous Currency Basis"),
            "fieldname": "previous_currency_basis",
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "label": _("New Currency Basis"),
            "fieldname": "new_currency_basis",
            "fieldtype": "Data",
            "width": 125,
        },
        {
            "label": _("Previous Structure"),
            "fieldname": "previous_structure",
            "fieldtype": "Link",
            "options": "Salary Structure",
            "width": 190,
        },
        {
            "label": _("New Structure"),
            "fieldname": "new_structure",
            "fieldtype": "Link",
            "options": "Salary Structure",
            "width": 190,
        },
        {
            "label": _("Event Type"),
            "fieldname": "event_type",
            "fieldtype": "Data",
            "width": 125,
        },
        {
            "label": _("Previous Assignment"),
            "fieldname": "previous_assignment",
            "fieldtype": "Link",
            "options": "Salary Structure Assignment",
            "width": 175,
        },
        {
            "label": _("New Assignment"),
            "fieldname": "new_assignment",
            "fieldtype": "Link",
            "options": "Salary Structure Assignment",
            "width": 175,
        },
        {
            "label": _("Created By"),
            "fieldname": "created_by",
            "fieldtype": "Link",
            "options": "User",
            "width": 180,
        },
        {
            "label": _("Created On"),
            "fieldname": "created_on",
            "fieldtype": "Datetime",
            "width": 150,
        },
        {
            "label": _("Amended From"),
            "fieldname": "amended_from",
            "fieldtype": "Link",
            "options": "Salary Structure Assignment",
            "width": 175,
        },
    ]


def get_data(filters):
    assignments = get_assignments(filters)

    by_employee = {}

    for row in assignments:
        by_employee.setdefault(
            row.employee,
            [],
        ).append(row)

    employee_names = dict(
        frappe.get_all(
            "Employee",
            filters={
                "name": [
                    "in",
                    list(by_employee.keys()),
                ],
            },
            fields=[
                "name",
                "employee_name",
            ],
            as_list=True,
        )
    ) if by_employee else {}

    output = []

    for employee, rows in by_employee.items():

        rows.sort(
            key=lambda row: (
                getdate(row.from_date),
                row.creation,
                row.name,
            )
        )

        previous = None

        for current in rows:

            event = classify_event(
                previous,
                current,
            )

            if in_report_period(
                current,
                filters,
            ):
                result = build_row(
                    employee=employee,
                    employee_name=employee_names.get(
                        employee
                    ),
                    previous=previous,
                    current=current,
                    event=event,
                )

                if row_matches_filters(
                    result,
                    filters,
                ):
                    output.append(result)

            previous = current

    output.sort(
        key=lambda row: (
            row["effective_date"],
            row["employee"],
        ),
        reverse=True,
    )

    return output


def get_assignments(filters):
    """
    We deliberately retrieve assignments before From Date as
    well, because the report needs the preceding assignment
    in order to determine whether the first displayed row is
    actually a salary change.
    """

    conditions = [
        "ssa.company = %(company)s",
        "ssa.docstatus = 1",
    ]

    values = {
        "company": filters.company,
        "to_date": filters.to_date,
    }

    if filters.employee:
        conditions.append(
            "ssa.employee = %(employee)s"
        )
        values["employee"] = filters.employee

    if filters.use_creation_date:
        conditions.append(
            "DATE(ssa.creation) <= %(to_date)s"
        )
    else:
        conditions.append(
            "ssa.from_date <= %(to_date)s"
        )

    return frappe.db.sql(
        f"""
        SELECT
            ssa.name,
            ssa.employee,
            ssa.salary_structure,
            ssa.from_date,
            ssa.base,
            ssa.currency,
            COALESCE(ssa.moeda_usd, 0)
                AS moeda_usd,
            ssa.owner,
            ssa.creation,
            ssa.amended_from
        FROM
            `tabSalary Structure Assignment` ssa
        WHERE
            {" AND ".join(conditions)}
        ORDER BY
            ssa.employee,
            ssa.from_date,
            ssa.creation,
            ssa.name
        """,
        values,
        as_dict=True,
    )


def classify_event(previous, current):
    if not previous:
        return "New Assignment"

    previous_basis = get_currency_basis(
        previous
    )

    current_basis = get_currency_basis(
        current
    )

    if previous_basis != current_basis:
        return "Currency Change"

    if not same_number(
        previous.base,
        current.base,
    ):
        return "Salary Change"

    if (
        previous.salary_structure
        != current.salary_structure
    ):
        return "Structure Change"

    if current.amended_from:
        return "Amendment"

    return "Amendment"


def get_currency_basis(row):
    if row.moeda_usd:
        return "USD"

    if row.currency:
        return row.currency

    return "KZ"


def same_number(left, right):
    return abs(
        flt(left) - flt(right)
    ) < 0.005


def build_row(
    employee,
    employee_name,
    previous,
    current,
    event,
):
    previous_basis = (
        get_currency_basis(previous)
        if previous
        else None
    )

    new_basis = get_currency_basis(
        current
    )

    previous_base = (
        flt(previous.base)
        if previous
        else None
    )

    new_base = flt(
        current.base
    )

    difference = None
    difference_percent = None

    #
    # A numeric variance is meaningful only when both
    # assignments use the same contractual currency basis.
    #
    if (
        previous
        and previous_basis == new_basis
    ):
        difference = (
            new_base - previous_base
        )

        if previous_base:
            difference_percent = (
                difference
                / previous_base
                * 100
            )

    return {
        "employee":
            employee,

        "employee_name":
            employee_name,

        "effective_date":
            current.from_date,

        "previous_base":
            previous_base,

        "new_base":
            new_base,

        "difference":
            flt(difference, 2)
            if difference is not None
            else None,

        "difference_percent":
            flt(difference_percent, 2)
            if difference_percent is not None
            else None,

        "previous_currency_basis":
            previous_basis,

        "new_currency_basis":
            new_basis,

        "previous_structure":
            previous.salary_structure
            if previous
            else None,

        "new_structure":
            current.salary_structure,

        "event_type":
            event,

        "previous_assignment":
            previous.name
            if previous
            else None,

        "new_assignment":
            current.name,

        "created_by":
            current.owner,

        "created_on":
            current.creation,

        "amended_from":
            current.amended_from,
    }


def in_report_period(
    row,
    filters,
):
    start = getdate(
        filters.from_date
    )

    end = getdate(
        filters.to_date
    )

    if filters.use_creation_date:
        value = getdate(
            row.creation
        )
    else:
        value = getdate(
            row.from_date
        )

    return start <= value <= end


def row_matches_filters(
    row,
    filters,
):
    if (
        filters.event_type
        and row["event_type"]
        != filters.event_type
    ):
        return False

    if filters.economic_changes_only:
        if row["event_type"] not in (
            "Salary Change",
            "Currency Change",
            "New Assignment",
        ):
            return False

    return True
