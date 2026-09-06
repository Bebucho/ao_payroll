import frappe
from frappe import _
from frappe.utils import getdate, today


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
        key=lambda x: (
            severity_order.get(x.get("severity"), 99),
            x.get("employee_name") or "",
            x.get("exception_type") or "",
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
            "width": 220,
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
    as_of_date = getdate(filters.get("as_of_date") or today())

    employee_filters = {}

    if filters.get("company"):
        employee_filters["company"] = filters.company

    if filters.get("employee"):
        employee_filters["name"] = filters.employee

    employees = frappe.get_all(
        "Employee",
        filters=employee_filters,
        fields=[
            "name",
            "employee_name",
            "company",
            "status",
            "date_of_joining",
            "relieving_date",
            "contract_end_date",
            "custom_contract_type",
        ],
    )

    employee_map = {
        row.name: row
        for row in employees
    }

    data = []

    check_employee_state(
        data,
        employees,
        as_of_date,
    )

    check_cessacao_contrato(
        data,
        employee_map,
        as_of_date,
    )

    check_employee_separation(
        data,
        employee_map,
        as_of_date,
    )

    check_employee_onboarding(
        data,
        employee_map,
    )

    check_promotion_transfer_dates(
        data,
        employee_map,
    )

    if filters.get("severity"):
        data = [
            row
            for row in data
            if row.get("severity") == filters.severity
        ]

    return data


def add_exception(
    data,
    severity,
    exception_type,
    employee=None,
    employee_name=None,
    company=None,
    effective_date=None,
    reference_doctype=None,
    reference_name=None,
    details=None,
):
    data.append(
        {
            "severity": severity,
            "exception_type": exception_type,
            "employee": employee,
            "employee_name": employee_name,
            "company": company,
            "effective_date": effective_date,
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "details": details,
        }
    )


def check_employee_state(
    data,
    employees,
    as_of_date,
):
    for employee in employees:

        if (
            employee.status == "Left"
            and not employee.relieving_date
        ):
            add_exception(
                data,
                "Critical",
                "Left Without Relieving Date",
                employee.name,
                employee.employee_name,
                employee.company,
                reference_doctype="Employee",
                reference_name=employee.name,
                details=(
                    "Employee status is Left but "
                    "Relieving Date is empty."
                ),
            )

        if (
            employee.status == "Active"
            and employee.relieving_date
            and getdate(employee.relieving_date)
            < as_of_date
        ):
            add_exception(
                data,
                "Critical",
                "Active After Relieving Date",
                employee.name,
                employee.employee_name,
                employee.company,
                employee.relieving_date,
                "Employee",
                employee.name,
                (
                    "Employee remains Active after "
                    "the recorded Relieving Date."
                ),
            )

        if (
            employee.status == "Active"
            and employee.contract_end_date
            and getdate(employee.contract_end_date)
            < as_of_date
        ):
            add_exception(
                data,
                "Critical",
                "Active After Contract End",
                employee.name,
                employee.employee_name,
                employee.company,
                employee.contract_end_date,
                "Employee",
                employee.name,
                (
                    "Employee remains Active after "
                    "Contract End Date."
                ),
            )


def check_cessacao_contrato(
    data,
    employee_map,
    as_of_date,
):
    cessacoes = frappe.get_all(
        "Cessacao Contrato",
        filters={
            "docstatus": 1,
        },
        fields=[
            "name",
            "funcionario",
            "data_saida",
            "status",
        ],
    )

    for cessacao in cessacoes:
        employee = employee_map.get(
            cessacao.funcionario
        )

        if not employee:
            continue

        if not cessacao.data_saida:
            add_exception(
                data,
                "Critical",
                "Termination Without Exit Date",
                employee.name,
                employee.employee_name,
                employee.company,
                reference_doctype="Cessacao Contrato",
                reference_name=cessacao.name,
                details=(
                    "Submitted Cessacao Contrato "
                    "has no Data Saida."
                ),
            )
            continue

        exit_date = getdate(
            cessacao.data_saida
        )

        if (
            exit_date <= as_of_date
            and employee.status != "Left"
        ):
            add_exception(
                data,
                "Critical",
                "Termination Effective But Employee Not Left",
                employee.name,
                employee.employee_name,
                employee.company,
                exit_date,
                "Cessacao Contrato",
                cessacao.name,
                (
                    "Termination date has passed but "
                    "Employee status is not Left."
                ),
            )

        if not employee.relieving_date:
            add_exception(
                data,
                "Warning",
                "Termination Without Relieving Date",
                employee.name,
                employee.employee_name,
                employee.company,
                exit_date,
                "Cessacao Contrato",
                cessacao.name,
                (
                    "Submitted termination exists but "
                    "Employee Relieving Date is empty."
                ),
            )

        elif (
            getdate(employee.relieving_date)
            != exit_date
        ):
            add_exception(
                data,
                "Warning",
                "Termination Date Mismatch",
                employee.name,
                employee.employee_name,
                employee.company,
                exit_date,
                "Cessacao Contrato",
                cessacao.name,
                (
                    "Cessacao Data Saida does not "
                    "match Employee Relieving Date."
                ),
            )

        separation = frappe.db.get_value(
            "Employee Separation",
            {
                "employee": employee.name,
                "docstatus": 1,
            },
            "name",
        )

        if not separation:
            add_exception(
                data,
                "Info",
                "No Employee Separation",
                employee.name,
                employee.employee_name,
                employee.company,
                exit_date,
                "Cessacao Contrato",
                cessacao.name,
                (
                    "Legal/payroll termination exists "
                    "but no submitted Employee Separation "
                    "offboarding document exists."
                ),
            )


def check_employee_separation(
    data,
    employee_map,
    as_of_date,
):
    separations = frappe.get_all(
        "Employee Separation",
        filters={
            "docstatus": 1,
        },
        fields=[
            "name",
            "employee",
            "boarding_status",
            "boarding_begins_on",
        ],
    )

    for separation in separations:
        employee = employee_map.get(
            separation.employee
        )

        if not employee:
            continue

        if (
            separation.boarding_status
            == "Completed"
        ):
            cessacao = frappe.db.get_value(
                "Cessacao Contrato",
                {
                    "funcionario": employee.name,
                    "docstatus": 1,
                },
                "name",
            )

            if not cessacao:
                add_exception(
                    data,
                    "Warning",
                    "Completed Separation Without Termination",
                    employee.name,
                    employee.employee_name,
                    employee.company,
                    separation.boarding_begins_on,
                    "Employee Separation",
                    separation.name,
                    (
                        "Employee Separation is Completed "
                        "but no submitted Cessacao Contrato "
                        "was found."
                    ),
                )


def check_employee_onboarding(
    data,
    employee_map,
):
    onboardings = frappe.get_all(
        "Employee Onboarding",
        filters={
            "docstatus": 1,
            "boarding_status": "Completed",
        },
        fields=[
            "name",
            "employee",
            "employee_name",
            "company",
            "date_of_joining",
        ],
    )

    for onboarding in onboardings:

        if not onboarding.employee:
            add_exception(
                data,
                "Warning",
                "Completed Onboarding Without Employee",
                employee_name=onboarding.employee_name,
                company=onboarding.company,
                effective_date=onboarding.date_of_joining,
                reference_doctype="Employee Onboarding",
                reference_name=onboarding.name,
                details=(
                    "Employee Onboarding is Completed "
                    "but no Employee is linked."
                ),
            )
            continue

        employee = employee_map.get(
            onboarding.employee
        )

        if (
            employee
            and not employee.custom_contract_type
        ):
            add_exception(
                data,
                "Warning",
                "Onboarded Employee Without Contract Type",
                employee.name,
                employee.employee_name,
                employee.company,
                onboarding.date_of_joining,
                "Employee Onboarding",
                onboarding.name,
                (
                    "Completed onboarding employee "
                    "has no Angola Contract Type."
                ),
            )


def check_promotion_transfer_dates(
    data,
    employee_map,
):
    promotions = frappe.get_all(
        "Employee Promotion",
        filters={
            "docstatus": 1,
        },
        fields=[
            "name",
            "employee",
            "promotion_date",
        ],
    )

    for promotion in promotions:
        employee = employee_map.get(
            promotion.employee
        )

        if (
            employee
            and employee.date_of_joining
            and promotion.promotion_date
            and getdate(promotion.promotion_date)
            < getdate(employee.date_of_joining)
        ):
            add_exception(
                data,
                "Critical",
                "Promotion Before Joining Date",
                employee.name,
                employee.employee_name,
                employee.company,
                promotion.promotion_date,
                "Employee Promotion",
                promotion.name,
                (
                    "Promotion Date precedes "
                    "Employee Date of Joining."
                ),
            )

    transfers = frappe.get_all(
        "Employee Transfer",
        filters={
            "docstatus": 1,
        },
        fields=[
            "name",
            "employee",
            "transfer_date",
        ],
    )

    for transfer in transfers:
        employee = employee_map.get(
            transfer.employee
        )

        if (
            employee
            and employee.date_of_joining
            and transfer.transfer_date
            and getdate(transfer.transfer_date)
            < getdate(employee.date_of_joining)
        ):
            add_exception(
                data,
                "Critical",
                "Transfer Before Joining Date",
                employee.name,
                employee.employee_name,
                employee.company,
                transfer.transfer_date,
                "Employee Transfer",
                transfer.name,
                (
                    "Transfer Date precedes "
                    "Employee Date of Joining."
                ),
            )
