import frappe
from frappe import _
from frappe.utils import add_months, get_last_day, getdate, today


def execute(filters=None):
    filters = frappe._dict(filters or {})

    columns = get_columns()
    data = get_data(filters)

    severity_order = {
        "Critical": 1,
        "Warning": 2,
        "Info": 3,
    }

    data.sort(
        key=lambda row: (
            severity_order.get(row.get("severity"), 99),
            row.get("employee_name") or "",
            row.get("exception_type") or "",
            row.get("effective_date") or getdate("1900-01-01"),
        )
    )

    return columns, data


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
            "width": 250,
        },
        {
            "label": _("Employee"),
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 130,
        },
        {
            "label": _("Employee Name"),
            "fieldname": "employee_name",
            "fieldtype": "Data",
            "width": 220,
        },
        {
            "label": _("Company"),
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 180,
        },
        {
            "label": _("Effective Date"),
            "fieldname": "effective_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": _("Reference Type"),
            "fieldname": "reference_doctype",
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "label": _("Reference"),
            "fieldname": "reference_name",
            "fieldtype": "Dynamic Link",
            "options": "reference_doctype",
            "width": 180,
        },
        {
            "label": _("Details"),
            "fieldname": "details",
            "fieldtype": "Data",
            "width": 420,
        },
    ]


def get_data(filters):
    data = []

    check_attendance_sources(
        data,
        filters,
    )

    check_leave_applications(
        data,
        filters,
    )

    check_deferred_leave(
        data,
        filters,
    )

    check_cancelled_salary_links(
        data,
        filters,
    )

    if filters.get("severity"):
        data = [
            row
            for row in data
            if row.get("severity") == filters.severity
        ]

    if filters.get("exception_type"):
        data = [
            row
            for row in data
            if row.get("exception_type") == filters.exception_type
        ]

    return data


def employee_allowed(employee, filters):
    if filters.get("employee") and employee != filters.employee:
        return False

    if filters.get("company"):
        company = frappe.db.get_value(
            "Employee",
            employee,
            "company",
        )

        if company != filters.company:
            return False

    return True


def add_exception(
    data,
    severity,
    exception_type,
    employee,
    effective_date,
    reference_doctype,
    reference_name,
    details,
):
    employee_data = frappe.db.get_value(
        "Employee",
        employee,
        [
            "employee_name",
            "company",
        ],
        as_dict=True,
    ) or frappe._dict()

    data.append(
        {
            "severity": severity,
            "exception_type": exception_type,
            "employee": employee,
            "employee_name": employee_data.employee_name,
            "company": employee_data.company,
            "effective_date": effective_date,
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "details": details,
        }
    )


def check_attendance_sources(
    data,
    filters,
):
    attendance_filters = {
        "docstatus": ["<", 2],
    }

    if filters.get("from_date"):
        attendance_filters["attendance_date"] = [
            ">=",
            filters.from_date,
        ]

    rows = frappe.get_all(
        "Attendance",
        filters=attendance_filters,
        fields=[
            "name",
            "employee",
            "attendance_date",
            "status",
            "tipo_de_faltas",
            "leave_application",
        ],
    )

    for row in rows:
        if not employee_allowed(
            row.employee,
            filters,
        ):
            continue

        if (
            filters.get("to_date")
            and row.attendance_date
            and getdate(row.attendance_date)
            > getdate(filters.to_date)
        ):
            continue

        if (
            row.status == "Absent"
            and not row.tipo_de_faltas
        ):
            add_exception(
                data,
                "Critical",
                "Absent Without Tipo de Falta",
                row.employee,
                row.attendance_date,
                "Attendance",
                row.name,
                (
                    "Attendance is Absent but no "
                    "Tipo de Falta is defined."
                ),
            )

        if (
            row.status == "On Leave"
            and row.tipo_de_faltas
        ):
            add_exception(
                data,
                "Warning",
                "On Leave With Tipo de Falta",
                row.employee,
                row.attendance_date,
                "Attendance",
                row.name,
                (
                    "On Leave must use Leave Application / "
                    "Leave Type as payroll source, not Tipo de Falta."
                ),
            )

        if (
            row.status == "On Leave"
            and not row.leave_application
        ):
            add_exception(
                data,
                "Warning",
                "On Leave Without Leave Application",
                row.employee,
                row.attendance_date,
                "Attendance",
                row.name,
                (
                    "Attendance is On Leave but has no "
                    "linked Leave Application."
                ),
            )


def check_leave_applications(
    data,
    filters,
):
    leave_filters = {
        "docstatus": 1,
        "status": "Approved",
    }

    if filters.get("from_date"):
        leave_filters["to_date"] = [
            ">=",
            filters.from_date,
        ]

    rows = frappe.get_all(
        "Leave Application",
        filters=leave_filters,
        fields=[
            "name",
            "employee",
            "leave_type",
            "from_date",
            "to_date",
            "salary_slip",
            "processar_mes_seguinte",
        ],
    )

    for row in rows:
        if not employee_allowed(
            row.employee,
            filters,
        ):
            continue

        if (
            filters.get("to_date")
            and row.from_date
            and getdate(row.from_date)
            > getdate(filters.to_date)
        ):
            continue

        leave_type = frappe.db.get_value(
            "Leave Type",
            row.leave_type,
            [
                "custom_inactive_for_new_requests",
                "custom_angola_leave_category",
            ],
            as_dict=True,
        )

        if not leave_type:
            continue

        if leave_type.custom_inactive_for_new_requests:
            add_exception(
                data,
                "Warning",
                "Approved Leave Uses Inactive Leave Type",
                row.employee,
                row.from_date,
                "Leave Application",
                row.name,
                (
                    "Approved Leave Application uses a Leave Type "
                    "marked inactive for new requests."
                ),
            )


def check_deferred_leave(
    data,
    filters,
):
    rows = frappe.get_all(
        "Leave Application",
        filters={
            "docstatus": 1,
            "status": "Approved",
            "processar_mes_seguinte": 1,
            "salary_slip": ["is", "not set"],
        },
        fields=[
            "name",
            "employee",
            "from_date",
            "to_date",
        ],
    )

    as_of_date = getdate(
        filters.get("as_of_date") or today()
    )

    for row in rows:
        if not employee_allowed(
            row.employee,
            filters,
        ):
            continue

        if not row.to_date:
            continue

        intended_payroll_month_end = get_last_day(
            add_months(
                getdate(row.to_date),
                1,
            )
        )

        if as_of_date > intended_payroll_month_end:
            add_exception(
                data,
                "Critical",
                "Deferred Leave Not Processed",
                row.employee,
                row.to_date,
                "Leave Application",
                row.name,
                (
                    "Leave was marked Processar Mes Seguinte "
                    "but remains unlinked after the intended "
                    "next payroll month."
                ),
            )


def check_cancelled_salary_links(
    data,
    filters,
):
    rows = frappe.get_all(
        "Leave Application",
        filters={
            "docstatus": 1,
            "status": "Approved",
            "salary_slip": ["is", "set"],
        },
        fields=[
            "name",
            "employee",
            "from_date",
            "salary_slip",
        ],
    )

    for row in rows:
        if not employee_allowed(
            row.employee,
            filters,
        ):
            continue

        if not frappe.db.exists(
            "Salary Slip",
            row.salary_slip,
        ):
            add_exception(
                data,
                "Critical",
                "Missing Salary Slip Reference",
                row.employee,
                row.from_date,
                "Leave Application",
                row.name,
                (
                    "Leave Application references a Salary Slip "
                    "that no longer exists."
                ),
            )
            continue

        docstatus = frappe.db.get_value(
            "Salary Slip",
            row.salary_slip,
            "docstatus",
        )

        if docstatus == 2:
            add_exception(
                data,
                "Warning",
                "Leave Linked To Cancelled Salary Slip",
                row.employee,
                row.from_date,
                "Leave Application",
                row.name,
                (
                    "Leave Application remains linked to "
                    "a cancelled Salary Slip."
                ),
            )
