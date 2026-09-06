import frappe


def validate_leave_type_active(doc, method=None):
    leave_type = getattr(
        doc,
        "leave_type",
        None,
    )

    if not leave_type:
        return

    inactive = frappe.db.get_value(
        "Leave Type",
        leave_type,
        "custom_inactive_for_new_requests",
    )

    if inactive:
        frappe.throw(
            f"Leave Type '{leave_type}' is inactive for new requests."
        )


def validate_attendance_payroll_source(doc, method=None):
    """
    Keep payroll treatment source unambiguous:

    - On Leave -> Leave Application / Leave Type
    - Absent   -> Tipo de Falta

    Historical records are not modified.
    """

    if doc.status == "On Leave" and doc.get("tipo_de_faltas"):
        frappe.throw(
            "Attendance marked as On Leave cannot have Tipo de Falta. "
            "Payroll treatment must come from the approved Leave Application."
        )

    if doc.status == "Absent" and not doc.get("tipo_de_faltas"):
        frappe.throw(
            "Attendance marked as Absent requires Tipo de Falta."
        )
