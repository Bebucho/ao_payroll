import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
    filters = frappe._dict(filters or {})

    validate_filters(filters)

    return get_columns(), get_data(filters)


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


def get_data(filters):
    conditions = [
        "ads.company = %(company)s",
        "ads.docstatus = 1",
        "ads.payroll_date >= %(from_date)s",
        "ads.payroll_date <= %(to_date)s",
    ]

    values = {
        "company": filters.company,
        "from_date": filters.from_date,
        "to_date": filters.to_date,
    }

    if filters.employee:
        conditions.append(
            "ads.employee = %(employee)s"
        )
        values["employee"] = filters.employee

    if filters.salary_component:
        conditions.append(
            "ads.salary_component = %(salary_component)s"
        )
        values["salary_component"] = (
            filters.salary_component
        )

    if filters.ref_doctype:
        conditions.append(
            "ads.ref_doctype = %(ref_doctype)s"
        )
        values["ref_doctype"] = (
            filters.ref_doctype
        )

    rows = frappe.db.sql(
        f"""
        SELECT
            ads.name,
            ads.payroll_date,
            ads.employee,
            ads.employee_name,
            ads.department,
            ads.salary_component,
            ads.type,
            ads.currency,
            ads.amount,
            ads.is_recurring,
            ads.from_date,
            ads.to_date,
            ads.ref_doctype,
            ads.ref_docname,
            ads.overwrite_salary_structure_amount,
            ads.deduct_full_tax_on_selected_payroll_date,
            ads.owner,
            ads.creation,
            ads.modified_by,
            ads.modified,
            ads.amended_from
        FROM
            `tabAdditional Salary` ads
        WHERE
            {" AND ".join(conditions)}
        ORDER BY
            ads.payroll_date DESC,
            ads.employee ASC,
            ads.creation DESC
        """,
        values,
        as_dict=True,
    )

    data = []

    for row in rows:
        classification = classify(row)

        result = {
            "payroll_date":
                row.payroll_date,

            "employee":
                row.employee,

            "employee_name":
                row.employee_name,

            "department":
                row.department,

            "salary_component":
                row.salary_component,

            "component_type":
                row.type,

            "amount":
                flt(row.amount),

            "currency":
                row.currency,

            "classification":
                classification,

            "is_recurring":
                row.is_recurring,

            "from_date":
                row.from_date,

            "to_date":
                row.to_date,

            "ref_doctype":
                row.ref_doctype,

            "ref_docname":
                row.ref_docname,

            "overwrite_salary_structure_amount":
                row.overwrite_salary_structure_amount,

            "deduct_full_tax_on_selected_payroll_date":
                row.deduct_full_tax_on_selected_payroll_date,

            "created_by":
                row.owner,

            "created_on":
                row.creation,

            "last_modified_by":
                row.modified_by,

            "last_modified_on":
                row.modified,

            "amended_from":
                row.amended_from,

            "additional_salary":
                row.name,
        }

        if row_matches_filters(
            result,
            filters,
        ):
            data.append(result)

    return data


def classify(row):
    if row.is_recurring:
        return "RECURRING"

    if row.ref_doctype == "Cessacao Contrato":
        return "TERMINATION"

    if row.ref_doctype == "Pedido Subsidio Ferias":
        return "HOLIDAY REQUEST"

    if row.ref_doctype:
        return "HR PROCESS"

    return "MANUAL"


def row_matches_filters(row, filters):
    if (
        filters.classification
        and row["classification"]
        != filters.classification
    ):
        return False

    show = filters.show or "All"

    if show == "Manual Only":
        return row["classification"] == "MANUAL"

    if show == "Referenced Only":
        return bool(
            row["ref_doctype"]
            and row["ref_docname"]
        )

    return True


def get_columns():
    return [
        {
            "label": _("Payroll Date"),
            "fieldname": "payroll_date",
            "fieldtype": "Date",
            "width": 105,
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
            "width": 180,
        },
        {
            "label": _("Department"),
            "fieldname": "department",
            "fieldtype": "Link",
            "options": "Department",
            "width": 150,
        },
        {
            "label": _("Salary Component"),
            "fieldname": "salary_component",
            "fieldtype": "Link",
            "options": "Salary Component",
            "width": 180,
        },
        {
            "label": _("Type"),
            "fieldname": "component_type",
            "fieldtype": "Data",
            "width": 90,
        },
        {
            "label": _("Amount"),
            "fieldname": "amount",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": _("Currency"),
            "fieldname": "currency",
            "fieldtype": "Link",
            "options": "Currency",
            "width": 75,
        },
        {
            "label": _("Classification"),
            "fieldname": "classification",
            "fieldtype": "Data",
            "width": 125,
        },
        {
            "label": _("Recurring"),
            "fieldname": "is_recurring",
            "fieldtype": "Check",
            "width": 80,
        },
        {
            "label": _("From Date"),
            "fieldname": "from_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": _("To Date"),
            "fieldname": "to_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": _("Reference Type"),
            "fieldname": "ref_doctype",
            "fieldtype": "Link",
            "options": "DocType",
            "width": 150,
        },
        {
            "label": _("Reference Document"),
            "fieldname": "ref_docname",
            "fieldtype": "Dynamic Link",
            "options": "ref_doctype",
            "width": 170,
        },
        {
            "label": _("Overwrite Structure"),
            "fieldname":
                "overwrite_salary_structure_amount",
            "fieldtype": "Check",
            "width": 115,
        },
        {
            "label": _("Full Tax"),
            "fieldname":
                "deduct_full_tax_on_selected_payroll_date",
            "fieldtype": "Check",
            "width": 80,
        },
        {
            "label": _("Created By"),
            "fieldname": "created_by",
            "fieldtype": "Link",
            "options": "User",
            "width": 170,
        },
        {
            "label": _("Created On"),
            "fieldname": "created_on",
            "fieldtype": "Datetime",
            "width": 145,
        },
        {
            "label": _("Last Modified By"),
            "fieldname": "last_modified_by",
            "fieldtype": "Link",
            "options": "User",
            "width": 170,
        },
        {
            "label": _("Last Modified On"),
            "fieldname": "last_modified_on",
            "fieldtype": "Datetime",
            "width": 145,
        },
        {
            "label": _("Amended From"),
            "fieldname": "amended_from",
            "fieldtype": "Link",
            "options": "Additional Salary",
            "width": 165,
        },
        {
            "label": _("Additional Salary"),
            "fieldname": "additional_salary",
            "fieldtype": "Link",
            "options": "Additional Salary",
            "width": 170,
        },
    ]
