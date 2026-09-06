import frappe
from frappe import _
from frappe.utils import getdate


def _get_employee_dates(employee):
    if not employee:
        return None

    return frappe.db.get_value(
        "Employee",
        employee,
        [
            "date_of_joining",
            "relieving_date",
            "status",
        ],
        as_dict=True,
    )


def _validate_effective_date(
    employee,
    effective_date,
    transaction_label,
):
    if not employee or not effective_date:
        return

    employee_data = _get_employee_dates(employee)

    if not employee_data:
        frappe.throw(
            _("Employee {0} does not exist.").format(
                employee
            )
        )

    effective_date = getdate(effective_date)

    if (
        employee_data.date_of_joining
        and effective_date
        < getdate(employee_data.date_of_joining)
    ):
        frappe.throw(
            _(
                "{0} Date cannot be before the "
                "employee's Date of Joining."
            ).format(transaction_label)
        )

    if (
        employee_data.relieving_date
        and effective_date
        > getdate(employee_data.relieving_date)
    ):
        frappe.throw(
            _(
                "{0} Date cannot be after the "
                "employee's Relieving Date."
            ).format(transaction_label)
        )


def validate_employee_promotion(doc, method=None):
    _validate_effective_date(
        doc.employee,
        doc.promotion_date,
        "Promotion",
    )


def validate_employee_transfer(doc, method=None):
    _validate_effective_date(
        doc.employee,
        doc.transfer_date,
        "Transfer",
    )


def validate_employee_onboarding(doc, method=None):
    """
    Employee Onboarding remains an HRMS operational transaction.
    Metagest only validates lifecycle consistency.
    """
    if not doc.date_of_joining:
        return

    if doc.employee:
        employee = frappe.db.get_value(
            "Employee",
            doc.employee,
            [
                "date_of_joining",
                "custom_contract_type",
            ],
            as_dict=True,
        )

        if not employee:
            frappe.throw(
                _("Linked Employee {0} does not exist.").format(
                    doc.employee
                )
            )

        if (
            employee.date_of_joining
            and getdate(employee.date_of_joining)
            != getdate(doc.date_of_joining)
        ):
            frappe.throw(
                _(
                    "Employee Onboarding Date of Joining "
                    "must match the linked Employee."
                )
            )

        if (
            doc.boarding_status == "Completed"
            and not employee.custom_contract_type
        ):
            frappe.throw(
                _(
                    "Completed Employee Onboarding requires "
                    "the linked Employee to have an Angola "
                    "Contract Type."
                )
            )


def validate_employee_separation(doc, method=None):
    """
    Employee Separation controls operational offboarding.
    Cessacao Contrato remains the legal/payroll termination source.
    """
    if not doc.employee or not doc.boarding_begins_on:
        return

    employee = frappe.db.get_value(
        "Employee",
        doc.employee,
        [
            "date_of_joining",
            "relieving_date",
        ],
        as_dict=True,
    )

    if not employee:
        frappe.throw(
            _("Employee {0} does not exist.").format(
                doc.employee
            )
        )

    if (
        employee.date_of_joining
        and getdate(doc.boarding_begins_on)
        < getdate(employee.date_of_joining)
    ):
        frappe.throw(
            _(
                "Separation Begins On cannot be before "
                "the employee's Date of Joining."
            )
        )

    cessacao = frappe.db.get_value(
        "Cessacao Contrato",
        {
            "funcionario": doc.employee,
            "docstatus": 1,
        },
        [
            "name",
            "data_saida",
        ],
        as_dict=True,
        order_by="creation desc",
    )

    if (
        cessacao
        and cessacao.data_saida
        and getdate(doc.boarding_begins_on)
        > getdate(cessacao.data_saida)
    ):
        frappe.throw(
            _(
                "Employee Separation cannot begin after "
                "the termination date defined in "
                "Cessacao Contrato {0}."
            ).format(
                cessacao.name
            )
        )
