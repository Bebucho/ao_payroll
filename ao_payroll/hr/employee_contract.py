import frappe
from frappe import _
from frappe.utils import getdate


FIXED_TERM = "Contrato por Tempo Determinado"
INDEFINITE = "Contrato por Tempo Indeterminado"


def validate_employee_contract(doc, method=None):
    contract_type = doc.get("custom_contract_type")
    contract_form = doc.get("custom_contract_form")

    joining_date = doc.get("date_of_joining")
    contract_end_date = doc.get("contract_end_date")

    scheduled_confirmation = doc.get(
        "scheduled_confirmation_date"
    )
    final_confirmation = doc.get(
        "final_confirmation_date"
    )

    renewal_number = doc.get(
        "custom_contract_renewal_number"
    ) or 0

    renewal_date = doc.get(
        "custom_last_contract_renewal_date"
    )

    fixed_term_reason = (
        doc.get("custom_fixed_term_reason") or ""
    ).strip()

    if joining_date and contract_end_date:
        if getdate(contract_end_date) < getdate(joining_date):
            frappe.throw(
                _("Contract End Date cannot be before Date of Joining.")
            )

    if joining_date and scheduled_confirmation:
        if getdate(scheduled_confirmation) < getdate(joining_date):
            frappe.throw(
                _("Scheduled Confirmation Date cannot be before Date of Joining.")
            )

    if joining_date and final_confirmation:
        if getdate(final_confirmation) < getdate(joining_date):
            frappe.throw(
                _("Confirmation Date cannot be before Date of Joining.")
            )

    if joining_date and renewal_date:
        if getdate(renewal_date) < getdate(joining_date):
            frappe.throw(
                _("Last Contract Renewal Date cannot be before Date of Joining.")
            )

    if contract_type == FIXED_TERM:
        if not contract_end_date:
            frappe.throw(
                _("Contract End Date is mandatory for a fixed-term contract.")
            )

        if not fixed_term_reason:
            frappe.throw(
                _("Fixed-Term Legal Reason is mandatory for a fixed-term contract.")
            )

        if not contract_form:
            frappe.throw(
                _("Contract Form is mandatory for a fixed-term contract.")
            )

        if contract_form == "Verbal":
            frappe.msgprint(
                _(
                    "Warning: this employee is recorded with a verbal "
                    "fixed-term contract. Verify that the applicable "
                    "legal exception permits this form."
                ),
                title=_("Contract Compliance Warning"),
                indicator="orange",
            )

    if contract_type == INDEFINITE and contract_end_date:
        frappe.msgprint(
            _(
                "An indefinite-term contract normally should not have "
                "a Contract End Date. Please verify this record."
            ),
            title=_("Contract Consistency Warning"),
            indicator="orange",
        )

    if renewal_number < 0:
        frappe.throw(
            _("Contract Renewal Number cannot be negative.")
        )

    if renewal_number > 0 and not renewal_date:
        frappe.throw(
            _(
                "Last Contract Renewal Date is mandatory when "
                "Contract Renewal Number is greater than zero."
            )
        )

    if renewal_date and renewal_number == 0:
        frappe.throw(
            _(
                "Contract Renewal Number must be greater than zero when "
                "Last Contract Renewal Date is provided."
            )
        )

    relieving_date = doc.get("relieving_date")

    if joining_date and relieving_date:
        if getdate(relieving_date) < getdate(joining_date):
            frappe.throw(
                _("Relieving Date cannot be before Date of Joining.")
            )
