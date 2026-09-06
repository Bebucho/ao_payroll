import frappe
from frappe.utils import getdate, today


def process_employee_cessations(reference_date=None):
    """
    Mark employees Left only after the approved termination date.

    Scheduled jobs call this without arguments.
    Tests may supply reference_date for deterministic execution.
    """

    current_date = getdate(
        reference_date or today()
    )

    cessations = frappe.get_all(
        "Cessacao Contrato",
        filters={
            "docstatus": 1,
            "data_saida": ["<", current_date],
        },
        fields=[
            "name",
            "funcionario",
            "data_saida",
        ],
    )

    for row in cessations:
        if not row.funcionario:
            continue

        employee = frappe.get_doc(
            "Employee",
            row.funcionario,
        )

        if employee.status == "Left":
            continue

        employee.status = "Left"

        if not employee.relieving_date:
            employee.relieving_date = row.data_saida

        employee.save(
            ignore_permissions=True
        )


def process_payroll_accrual_reversals():
    """
    Create due Payroll Accrual reversing entries.

    Safe to run daily:
    - only submitted Payroll Accruals
    - only where reversal date is due
    - only where no reversal JE is already linked
    """

    import frappe
    from frappe.utils import getdate, nowdate

    from ao_payroll.payroll.accruals import (
        create_reversal_journal_entry,
    )

    today = getdate(
        nowdate()
    )

    accruals = frappe.get_all(
        "Payroll Accrual",
        filters={
            "docstatus": 1,
            "reversal_date": ["<=", today],
            "reversal_journal_entry": ["is", "not set"],
        },
        fields=[
            "name",
            "journal_entry",
            "reversal_date",
        ],
    )

    for row in accruals:
        if not row.journal_entry:
            continue

        result = create_reversal_journal_entry(
            journal_entry=row.journal_entry,
            posting_date=row.reversal_date,
            payroll_accrual=row.name,
        )

        if result.get("journal_entry"):
            frappe.db.set_value(
                "Payroll Accrual",
                row.name,
                "reversal_journal_entry",
                result["journal_entry"],
                update_modified=False,
            )

            frappe.db.commit()
