import json

import frappe


WORKSPACE = "Angola Payroll"


def execute():
    workspace = frappe.get_doc(
        "Workspace",
        WORKSPACE,
    )

    # ------------------------------------------------------------------
    # Workspace visual layout
    # ------------------------------------------------------------------

    content = [
        {
            "id": "ao_payroll_header",
            "type": "header",
            "data": {
                "text": '<span class="h4">Angola Payroll</span>',
                "col": 12,
            },
        },

        # Existing payroll cards
        {
            "id": "ao_config",
            "type": "card",
            "data": {
                "card_name": "Configuracoes",
                "col": 4,
            },
        },
        {
            "id": "ao_processing",
            "type": "card",
            "data": {
                "card_name": "Processamentos",
                "col": 4,
            },
        },
        {
            "id": "ao_reports",
            "type": "card",
            "data": {
                "card_name": "Relatorios",
                "col": 4,
            },
        },

        # HR section
        {
            "id": "hr_header",
            "type": "paragraph",
            "data": {
                "text": '<span class="h3">Human Resources</span>',
                "col": 12,
            },
        },
        {
            "id": "hr_employees_contracts",
            "type": "card",
            "data": {
                "card_name": "Employees and Contracts",
                "col": 4,
            },
        },
        {
            "id": "hr_leave_attendance",
            "type": "card",
            "data": {
                "card_name": "Leave and Attendance",
                "col": 4,
            },
        },
        {
            "id": "hr_overtime",
            "type": "card",
            "data": {
                "card_name": "Overtime",
                "col": 4,
            },
        },

        # Control section
        {
            "id": "control_header",
            "type": "paragraph",
            "data": {
                "text": '<span class="h3">Control and Audit</span>',
                "col": 12,
            },
        },
        {
            "id": "hr_control",
            "type": "card",
            "data": {
                "card_name": "HR Control",
                "col": 4,
            },
        },
    ]

    workspace.content = json.dumps(
        content,
        separators=(",", ":"),
    )

    # ------------------------------------------------------------------
    # Rebuild card links
    # ------------------------------------------------------------------

    workspace.set("links", [])

    def card(label):
        workspace.append(
            "links",
            {
                "type": "Card Break",
                "label": label,
            },
        )

    def doctype(label, link_to=None):
        workspace.append(
            "links",
            {
                "type": "Link",
                "label": label,
                "link_type": "DocType",
                "link_to": link_to or label,
            },
        )

    def report(label, link_to=None):
        workspace.append(
            "links",
            {
                "type": "Link",
                "label": label,
                "link_type": "Report",
                "link_to": link_to or label,
            },
        )

    # ------------------------------------------------------------------
    # PAYROLL CONFIGURATION
    # ------------------------------------------------------------------

    card("Configuracoes")

    doctype(
        "Angola Payroll Settings",
        "Angola Payroll Settings",
    )
    doctype(
        "IRT Tables",
        "IRT Tables",
    )
    doctype(
        "Tipo de Falta",
        "Tipo de Falta",
    )
    doctype(
        "Salary Component",
        "Salary Component",
    )
    doctype(
        "Salary Structure",
        "Salary Structure",
    )
    doctype(
        "Salary Structure Assignment",
        "Salary Structure Assignment",
    )

    # ------------------------------------------------------------------
    # PAYROLL PROCESSING
    # ------------------------------------------------------------------

    card("Processamentos")

    doctype(
        "Payroll Accrual",
        "Payroll Accrual",
    )
    doctype(
        "Pedido Subsidio Ferias",
        "Pedido Subsidio Ferias",
    )
    doctype(
        "Payroll Entry",
        "Payroll Entry",
    )
    doctype(
        "Salary Slip",
        "Salary Slip",
    )
    doctype(
        "Additional Salary",
        "Additional Salary",
    )

    # ------------------------------------------------------------------
    # PAYROLL REPORTS
    # ------------------------------------------------------------------

    card("Relatorios")

    report(
        "Salary Change Audit",
        "Salary Change Audit",
    )
    report(
        "Payroll Month-on-Month Variance",
        "Payroll Month-on-Month Variance",
    )
    report(
        "Payroll-to-GL Reconciliation",
        "Payroll-to-GL Reconciliation",
    )
    report(
        "Payroll Exceptions Control",
        "Payroll Exceptions Control",
    )

    if frappe.db.exists(
        "Report",
        "Additional Salary Audit",
    ):
        report(
            "Additional Salary Audit",
            "Additional Salary Audit",
        )

    # ------------------------------------------------------------------
    # EMPLOYEES AND CONTRACTS
    # ------------------------------------------------------------------

    card("Employees and Contracts")

    doctype(
        "Employee",
        "Employee",
    )
    doctype(
        "Employee Onboarding",
        "Employee Onboarding",
    )
    doctype(
        "Employee Promotion",
        "Employee Promotion",
    )
    doctype(
        "Employee Transfer",
        "Employee Transfer",
    )
    doctype(
        "Employee Separation",
        "Employee Separation",
    )
    doctype(
        "Cessacao Contrato",
        "Cessacao Contrato",
    )

    # ------------------------------------------------------------------
    # LEAVE AND ATTENDANCE
    # ------------------------------------------------------------------

    card("Leave and Attendance")

    doctype(
        "Leave Application",
        "Leave Application",
    )
    doctype(
        "Leave Allocation",
        "Leave Allocation",
    )
    doctype(
        "Attendance",
        "Attendance",
    )
    doctype(
        "Employee Checkin",
        "Employee Checkin",
    )
    doctype(
        "Leave Type",
        "Leave Type",
    )
    doctype(
        "Leave Policy",
        "Leave Policy",
    )

    # ------------------------------------------------------------------
    # OVERTIME
    # ------------------------------------------------------------------

    card("Overtime")

    doctype(
        "Overtime Request",
        "Overtime Request",
    )
    doctype(
        "Overtime Processing",
        "Overtime Processing",
    )
    report(
        "Overtime Control",
        "Overtime Control",
    )

    # ------------------------------------------------------------------
    # HR CONTROL
    # ------------------------------------------------------------------

    card("HR Control")

    report(
        "Employment Contract Exceptions",
        "Employment Contract Exceptions",
    )
    report(
        "HR Transaction Exceptions",
        "HR Transaction Exceptions",
    )
    report(
        "Leave and Attendance Exceptions",
        "Leave and Attendance Exceptions",
    )
    report(
        "Overtime Control",
        "Overtime Control",
    )

    workspace.save(
        ignore_permissions=True
    )

    frappe.db.commit()

    return {
        "workspace": workspace.name,
        "links": len(workspace.links),
        "cards": [
            "Configuracoes",
            "Processamentos",
            "Relatorios",
            "Employees and Contracts",
            "Leave and Attendance",
            "Overtime",
            "HR Control",
        ],
    }
