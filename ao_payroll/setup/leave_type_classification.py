import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


CLASSIFICATIONS = {
    "Ferias": "Statutory",
    "Leave Without Pay": "Operational",
    "Maternity Leave": "Statutory",
    "Sick Leave": "Statutory",
    "Compensatory Off": "Operational",
    "Casual Leave": "Company Policy",
    "Privilege Leave": "Company Policy",
    "Subsidio de Ferias": "Legacy",
}


def execute():
    create_custom_fields(
        {
            "Leave Type": [
                {
                    "fieldname": "custom_angola_leave_category",
                    "label": "Angola Leave Category",
                    "fieldtype": "Select",
                    "options": (
                        "\n"
                        "Statutory\n"
                        "Company Policy\n"
                        "Operational\n"
                        "Legacy"
                    ),
                    "insert_after": "leave_type_name",
                },
            ]
        },
        update=True,
    )

    for leave_type, category in CLASSIFICATIONS.items():
        if frappe.db.exists("Leave Type", leave_type):
            frappe.db.set_value(
                "Leave Type",
                leave_type,
                "custom_angola_leave_category",
                category,
                update_modified=False,
            )

    frappe.clear_document_cache("Leave Type")


if __name__ == "__main__":
    execute()
