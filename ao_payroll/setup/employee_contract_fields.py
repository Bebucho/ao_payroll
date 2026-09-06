import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    custom_fields = {
        "Employee": [
            {
                "fieldname": "custom_angola_contract_section",
                "label": "Angola Employment Contract",
                "fieldtype": "Section Break",
                "insert_after": "employment_type",
            },
            {
                "fieldname": "custom_contract_type",
                "label": "Contract Type",
                "fieldtype": "Select",
                "options": (
                    "\n"
                    "Contrato por Tempo Indeterminado\n"
                    "Contrato por Tempo Determinado\n"
                    "Teletrabalho\n"
                    "Comissão de Serviço\n"
                    "Contrato de Aprendizagem\n"
                    "Contrato de Estágio\n"
                    "Outro Contrato Especial"
                ),
                "insert_after": "custom_angola_contract_section",
            },
            {
                "fieldname": "custom_contract_form",
                "label": "Contract Form",
                "fieldtype": "Select",
                "options": "\nEscrito\nVerbal",
                "insert_after": "custom_contract_type",
            },
            {
                "fieldname": "custom_contract_column",
                "fieldtype": "Column Break",
                "insert_after": "custom_contract_form",
            },
            {
                "fieldname": "custom_fixed_term_reason",
                "label": "Fixed-Term Legal Reason",
                "fieldtype": "Small Text",
                "insert_after": "custom_contract_column",
                "depends_on": (
                    "eval:doc.custom_contract_type=="
                    "'Contrato por Tempo Determinado'"
                ),
            },
            {
                "fieldname": "custom_contract_renewal_number",
                "label": "Contract Renewal Number",
                "fieldtype": "Int",
                "default": "0",
                "non_negative": 1,
                "insert_after": "custom_fixed_term_reason",
            },
            {
                "fieldname": "custom_last_contract_renewal_date",
                "label": "Last Contract Renewal Date",
                "fieldtype": "Date",
                "insert_after": "custom_contract_renewal_number",
            },
        ]
    }

    create_custom_fields(
        custom_fields,
        update=True,
    )

    frappe.clear_document_cache("Employee")


if __name__ == "__main__":
    execute()
