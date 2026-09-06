import frappe
from frappe import _
from frappe.utils import getdate, today


def execute(filters=None):
    filters = frappe._dict(filters or {})

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {
            "label": _("Control Status"),
            "fieldname": "control_status",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": _("Overtime Request"),
            "fieldname": "overtime_request",
            "fieldtype": "Link",
            "options": "Overtime Request",
            "width": 160,
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
            "label": _("Overtime Date"),
            "fieldname": "overtime_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": _("Requested Hours"),
            "fieldname": "requested_hours",
            "fieldtype": "Float",
            "width": 110,
        },
        {
            "label": _("Approved Hours"),
            "fieldname": "approved_hours",
            "fieldtype": "Float",
            "width": 110,
        },
        {
            "label": _("Approval Status"),
            "fieldname": "approval_status",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": _("Approver"),
            "fieldname": "approver",
            "fieldtype": "Link",
            "options": "User",
            "width": 170,
        },
        {
            "label": _("Processing"),
            "fieldname": "overtime_processing",
            "fieldtype": "Link",
            "options": "Overtime Processing",
            "width": 160,
        },
        {
            "label": _("Overtime Type"),
            "fieldname": "overtime_type",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": _("Multiplier"),
            "fieldname": "multiplier",
            "fieldtype": "Float",
            "width": 90,
        },
        {
            "label": _("Calculated Amount"),
            "fieldname": "calculated_amount",
            "fieldtype": "Currency",
            "width": 130,
        },
        {
            "label": _("Payroll Date"),
            "fieldname": "payroll_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": _("Additional Salary"),
            "fieldname": "additional_salary",
            "fieldtype": "Link",
            "options": "Additional Salary",
            "width": 160,
        },
        {
            "label": _("Details"),
            "fieldname": "details",
            "fieldtype": "Data",
            "width": 320,
        },
    ]


def get_data(filters):
    request_filters = {}

    if filters.get("company"):
        request_filters["company"] = filters.company

    if filters.get("employee"):
        request_filters["employee"] = filters.employee

    if filters.get("approval_status"):
        request_filters["approval_status"] = filters.approval_status

    if filters.get("from_date"):
        request_filters["overtime_date"] = [
            ">=",
            filters.from_date,
        ]

    requests = frappe.get_all(
        "Overtime Request",
        filters=request_filters,
        fields=[
            "name",
            "employee",
            "employee_name",
            "company",
            "overtime_date",
            "requested_hours",
            "approved_hours",
            "approval_status",
            "approver",
            "docstatus",
        ],
        order_by="overtime_date desc, modified desc",
    )

    if filters.get("to_date"):
        requests = [
            row for row in requests
            if row.overtime_date
            and getdate(row.overtime_date)
            <= getdate(filters.to_date)
        ]

    data = []

    for request in requests:
        processing = get_processing(
            request.name
        )

        control_status, details = get_control_status(
            request,
            processing,
        )

        if (
            filters.get("control_status")
            and control_status
            != filters.control_status
        ):
            continue

        data.append(
            {
                "control_status": control_status,
                "overtime_request": request.name,
                "employee": request.employee,
                "employee_name": request.employee_name,
                "company": request.company,
                "overtime_date": request.overtime_date,
                "requested_hours": request.requested_hours,
                "approved_hours": request.approved_hours,
                "approval_status": request.approval_status,
                "approver": request.approver,
                "overtime_processing": (
                    processing.name
                    if processing else None
                ),
                "overtime_type": (
                    processing.overtime_type
                    if processing else None
                ),
                "multiplier": (
                    processing.multiplier
                    if processing else None
                ),
                "calculated_amount": (
                    processing.calculated_amount
                    if processing else None
                ),
                "payroll_date": (
                    processing.payroll_date
                    if processing else None
                ),
                "additional_salary": (
                    processing.additional_salary
                    if processing else None
                ),
                "details": details,
            }
        )

    return data


def get_processing(overtime_request):
    rows = frappe.get_all(
        "Overtime Processing",
        filters={
            "overtime_request": overtime_request,
            "docstatus": ["<", 2],
        },
        fields=[
            "name",
            "docstatus",
            "overtime_type",
            "multiplier",
            "calculated_amount",
            "payroll_date",
            "additional_salary",
        ],
        order_by="creation desc",
        limit=1,
    )

    return rows[0] if rows else None


def get_control_status(
    request,
    processing,
):
    if request.docstatus == 2:
        return (
            "Cancelled",
            "Overtime Request is cancelled.",
        )

    if request.approval_status == "Rejected":
        return (
            "Rejected",
            "Overtime Request was rejected.",
        )

    if request.approval_status == "Pending":
        return (
            "Pending Approval",
            "Overtime Request is awaiting approval.",
        )

    if request.approval_status == "Approved":
        if request.docstatus != 1:
            return (
                "Approved Not Submitted",
                "Request is marked Approved but is not submitted.",
            )

        if not processing:
            return (
                "Approved Unprocessed",
                "Approved overtime has not yet been processed for payroll.",
            )

        if processing.docstatus == 0:
            return (
                "Processing Draft",
                "Overtime Processing exists but is still in Draft.",
            )

        if processing.docstatus == 1:
            if not processing.additional_salary:
                return (
                    "Processed Missing Additional Salary",
                    "Submitted processing has no Additional Salary reference.",
                )

            if not frappe.db.exists(
                "Additional Salary",
                processing.additional_salary,
            ):
                return (
                    "Missing Additional Salary",
                    "Referenced Additional Salary no longer exists.",
                )

            additional_salary = frappe.db.get_value(
                "Additional Salary",
                processing.additional_salary,
                [
                    "docstatus",
                    "payroll_date",
                ],
                as_dict=True,
            )

            if additional_salary.docstatus == 2:
                return (
                    "Additional Salary Cancelled",
                    "Overtime Processing points to a cancelled Additional Salary.",
                )

            return (
                "Processed",
                "Overtime is approved and has been converted to Additional Salary.",
            )

    return (
        "Review",
        "Overtime transaction requires review.",
    )
