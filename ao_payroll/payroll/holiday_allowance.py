import frappe
from frappe.utils import flt, getdate

from ao_payroll.payroll import calculator
from ao_payroll.payroll.settings import get_payroll_settings


def calculate_leave_block_holiday_allowance(
    leave_application,
    base_salary,
):
    """
    Calculate Subsidio de Ferias for one approved Ferias block.

    Does not create payroll records.

    Formula for proportional-per-block policy:

        annual entitlement
        x block leave days
        / annual leave entitlement days

    Payment is always capped by the remaining annual entitlement.
    """

    if isinstance(leave_application, str):
        leave = frappe.get_doc(
            "Leave Application",
            leave_application,
        )
    else:
        leave = leave_application

    if leave.docstatus != 1:
        frappe.throw(
            f"Leave Application {leave.name} must be submitted."
        )

    if leave.status != "Approved":
        frappe.throw(
            f"Leave Application {leave.name} must be Approved."
        )

    if leave.leave_type != "Ferias":
        frappe.throw(
            f"Leave Application {leave.name} is not Ferias."
        )

    settings = get_payroll_settings(
        employee=leave.employee,
        reference_date=leave.from_date,
    )

    mode = getattr(
        settings,
        "custom_holiday_allowance_payment_mode",
        None,
    )

    if mode != "Per Leave Block":
        frappe.throw(
            "Holiday Allowance Payment Mode must be "
            "'Per Leave Block'."
        )

    block_method = getattr(
        settings,
        "custom_holiday_allowance_block_method",
        None,
    )

    year = getdate(
        leave.from_date
    ).year

    balance = (
        calculator.calculate_holiday_allowance_balance(
            employee=leave.employee,
            year=year,
            base_salary=base_salary,
        )
    )

    entitlement_days = flt(
        balance["entitlement_days"]
    )

    annual_entitlement = flt(
        balance["annual_entitlement"]
    )

    remaining = flt(
        balance["remaining"]
    )

    block_days = flt(
        leave.total_leave_days
    )

    if entitlement_days <= 0:
        frappe.throw(
            f"Employee {leave.employee} has no holiday "
            f"entitlement for {year}."
        )

    if block_days <= 0:
        frappe.throw(
            f"Leave Application {leave.name} has no leave days."
        )

    if block_method == "Full on First Block":
        calculated_amount = annual_entitlement

    elif block_method == "Proportional Per Block":
        calculated_amount = (
            annual_entitlement
            * block_days
            / entitlement_days
        )

    else:
        frappe.throw(
            "Invalid Leave Block Payment Method in "
            "Angola Payroll Settings."
        )

    payable = min(
        flt(calculated_amount),
        remaining,
    )

    return {
        "leave_application": leave.name,
        "employee": leave.employee,
        "year": year,
        "block_days": flt(
            block_days,
            2,
        ),
        "entitlement_days": flt(
            entitlement_days,
            2,
        ),
        "annual_entitlement": flt(
            annual_entitlement,
            2,
        ),
        "already_paid": flt(
            balance["paid"],
            2,
        ),
        "remaining_before_payment": flt(
            remaining,
            2,
        ),
        "block_method": block_method,
        "calculated_amount": flt(
            calculated_amount,
            2,
        ),
        "payable_amount": flt(
            payable,
            2,
        ),
    }


def create_leave_block_holiday_allowance(
    leave_application,
    base_salary,
    payroll_date,
):
    """
    Create one Additional Salary for an approved Ferias block.

    payroll_date is deliberately explicit. The orchestration layer
    will later decide which payroll period constitutes "before leave".

    Duplicate control:
      Leave Application + Subsidio de Ferias
    """

    result = calculate_leave_block_holiday_allowance(
        leave_application=leave_application,
        base_salary=base_salary,
    )

    if result["payable_amount"] <= 0:
        return {
            **result,
            "additional_salary": None,
            "created": False,
        }

    settings = get_payroll_settings(
        employee=result["employee"],
        reference_date=payroll_date,
    )

    component = getattr(
        settings,
        "holyday_allowance_salary_component",
        None,
    )

    if not component:
        frappe.throw(
            "Subsidio de Ferias Salary Component "
            "is not configured."
        )

    existing = frappe.db.get_value(
        "Additional Salary",
        {
            "employee": result["employee"],
            "salary_component": component,
            "ref_doctype": "Leave Application",
            "ref_docname": result["leave_application"],
            "docstatus": ["!=", 2],
        },
        "name",
    )

    if existing:
        frappe.throw(
            f"Leave Application {result['leave_application']} "
            f"already generated Additional Salary {existing}."
        )

    additional = frappe.new_doc(
        "Additional Salary"
    )

    additional.employee = result["employee"]
    additional.salary_component = component
    additional.payroll_date = getdate(
        payroll_date
    )
    additional.amount = flt(
        result["payable_amount"],
        2,
    )

    additional.ref_doctype = (
        "Leave Application"
    )
    additional.ref_docname = (
        result["leave_application"]
    )

    additional.overwrite_salary_structure_amount = 0

    additional.insert()
    additional.submit()

    return {
        **result,
        "additional_salary": additional.name,
        "created": True,
    }


def calculate_fixed_month_holiday_allowance(
    employee,
    year,
    base_salary,
    payroll_date,
):
    """
    Fixed Month policy.

    Pays the employee's remaining annual holiday allowance
    only when payroll_date falls in the configured month.
    """

    import calendar

    settings = get_payroll_settings(
        employee=employee,
        reference_date=payroll_date,
    )

    if (
        settings.custom_holiday_allowance_payment_mode
        != "Fixed Month"
    ):
        frappe.throw(
            "Holiday Allowance Payment Mode must be "
            "'Fixed Month'."
        )

    configured_month = (
        settings.custom_holiday_allowance_fixed_month
    )

    if not configured_month:
        frappe.throw(
            "Holiday Allowance Fixed Month is not configured."
        )

    try:
        configured_month_number = list(
            calendar.month_name
        ).index(configured_month)
    except ValueError:
        frappe.throw(
            f"Invalid Holiday Allowance Fixed Month: "
            f"{configured_month}"
        )

    payroll_date = getdate(
        payroll_date
    )

    balance = (
        calculator.calculate_holiday_allowance_balance(
            employee=employee,
            year=year,
            base_salary=base_salary,
        )
    )

    triggered = (
        payroll_date.year == int(year)
        and payroll_date.month
        == configured_month_number
    )

    payable = (
        flt(balance["remaining"])
        if triggered
        else 0
    )

    return {
        **balance,
        "payment_mode": "Fixed Month",
        "configured_month": configured_month,
        "payroll_date": payroll_date,
        "triggered": triggered,
        "payable_amount": flt(
            payable,
            2,
        ),
    }


def calculate_monthly_duodecimo_holiday_allowance(
    employee,
    year,
    base_salary,
    payroll_date,
):
    """
    Monthly Duodecimos policy.

    Normal monthly amount is 1/12 of the employee's annual
    holiday allowance entitlement.

    The annual balance remains authoritative and caps the
    payment, preventing overpayment.

    Any residual balance caused by rounding or partial-year
    circumstances remains visible for later settlement.
    """

    settings = get_payroll_settings(
        employee=employee,
        reference_date=payroll_date,
    )

    if (
        settings.custom_holiday_allowance_payment_mode
        != "Monthly Duodecimos"
    ):
        frappe.throw(
            "Holiday Allowance Payment Mode must be "
            "'Monthly Duodecimos'."
        )

    payroll_date = getdate(
        payroll_date
    )

    balance = (
        calculator.calculate_holiday_allowance_balance(
            employee=employee,
            year=year,
            base_salary=base_salary,
        )
    )

    annual_entitlement = flt(
        balance["annual_entitlement"]
    )

    normal_installment = (
        annual_entitlement / 12
    )

    payable = min(
        normal_installment,
        flt(balance["remaining"]),
    )

    if payroll_date.year != int(year):
        payable = 0

    return {
        **balance,
        "payment_mode": "Monthly Duodecimos",
        "payroll_date": payroll_date,
        "normal_installment": flt(
            normal_installment,
            2,
        ),
        "payable_amount": flt(
            payable,
            2,
        ),
    }


def calculate_employee_request_holiday_allowance(
    employee,
    year,
    base_salary,
    requested_amount,
    payroll_date,
):
    """
    Employee Request policy.

    HR/payroll supplies the approved requested amount.
    This function only validates it against the employee's
    remaining annual entitlement.

    Approval workflow will be implemented separately.
    """

    settings = get_payroll_settings(
        employee=employee,
        reference_date=payroll_date,
    )

    if (
        settings.custom_holiday_allowance_payment_mode
        != "Employee Request"
    ):
        frappe.throw(
            "Holiday Allowance Payment Mode must be "
            "'Employee Request'."
        )

    requested_amount = flt(
        requested_amount,
        2,
    )

    if requested_amount <= 0:
        frappe.throw(
            "Requested holiday allowance amount "
            "must be greater than zero."
        )

    payroll_date = getdate(
        payroll_date
    )

    if payroll_date.year != int(year):
        frappe.throw(
            "Holiday allowance request payroll date "
            "must belong to the entitlement year."
        )

    balance = (
        calculator.calculate_holiday_allowance_balance(
            employee=employee,
            year=year,
            base_salary=base_salary,
        )
    )

    payable = min(
        requested_amount,
        flt(balance["remaining"]),
    )

    return {
        **balance,
        "payment_mode": "Employee Request",
        "payroll_date": payroll_date,
        "requested_amount": requested_amount,
        "payable_amount": flt(
            payable,
            2,
        ),
        "request_capped": (
            requested_amount
            > flt(balance["remaining"])
        ),
    }


def calculate_salary_slip_holiday_allowance(
    employee,
    base_salary,
    payroll_start_date,
    payroll_end_date,
):
    """
    Determine the automatic Subsidio de Ferias amount for
    one Salary Slip.

    Automatic modes:
      - Fixed Month
      - Monthly Duodecimos
      - Per Leave Block

    Employee Request deliberately returns zero here because
    that mode is handled through Additional Salary.
    """

    payroll_start_date = getdate(
        payroll_start_date
    )
    payroll_end_date = getdate(
        payroll_end_date
    )

    settings = get_payroll_settings(
        employee=employee,
        reference_date=payroll_end_date,
    )

    mode = getattr(
        settings,
        "custom_holiday_allowance_payment_mode",
        None,
    )

    # -----------------------------------------------------
    # Employee Request
    #
    # Manual/approved event. It must come through
    # Additional Salary, not automatic Salary Slip logic.
    # -----------------------------------------------------

    if mode == "Employee Request":
        return {
            "payment_mode": mode,
            "amount": 0.0,
            "source_leave_applications": [],
        }

    year = payroll_end_date.year

    # -----------------------------------------------------
    # Fixed Month
    # -----------------------------------------------------

    if mode == "Fixed Month":
        result = (
            calculate_fixed_month_holiday_allowance(
                employee=employee,
                year=year,
                base_salary=base_salary,
                payroll_date=payroll_end_date,
            )
        )

        return {
            "payment_mode": mode,
            "amount": flt(
                result["payable_amount"],
                2,
            ),
            "source_leave_applications": [],
            "detail": result,
        }

    # -----------------------------------------------------
    # Monthly Duodecimos
    # -----------------------------------------------------

    if mode == "Monthly Duodecimos":
        result = (
            calculate_monthly_duodecimo_holiday_allowance(
                employee=employee,
                year=year,
                base_salary=base_salary,
                payroll_date=payroll_end_date,
            )
        )

        return {
            "payment_mode": mode,
            "amount": flt(
                result["payable_amount"],
                2,
            ),
            "source_leave_applications": [],
            "detail": result,
        }

    # -----------------------------------------------------
    # Per Leave Block
    # -----------------------------------------------------

    if mode == "Per Leave Block":

        leaves = frappe.get_all(
            "Leave Application",
            filters={
                "employee": employee,
                "leave_type": "Ferias",
                "status": "Approved",
                "docstatus": 1,
                "from_date": [
                    "between",
                    [
                        payroll_start_date,
                        payroll_end_date,
                    ],
                ],
            },
            fields=[
                "name",
                "from_date",
                "to_date",
                "total_leave_days",
            ],
            order_by="from_date asc",
        )

        if not leaves:
            return {
                "payment_mode": mode,
                "amount": 0.0,
                "source_leave_applications": [],
            }

        balance = (
            calculator.calculate_holiday_allowance_balance(
                employee=employee,
                year=year,
                base_salary=base_salary,
            )
        )

        entitlement_days = flt(
            balance["entitlement_days"]
        )

        annual_entitlement = flt(
            balance["annual_entitlement"]
        )

        remaining = flt(
            balance["remaining"]
        )

        if (
            entitlement_days <= 0
            or remaining <= 0
        ):
            return {
                "payment_mode": mode,
                "amount": 0.0,
                "source_leave_applications": [
                    row.name
                    for row in leaves
                ],
                "detail": balance,
            }

        block_method = getattr(
            settings,
            "custom_holiday_allowance_block_method",
            None,
        )

        if block_method == "Full on First Block":

            calculated_amount = (
                annual_entitlement
            )

        elif (
            block_method
            == "Proportional Per Block"
        ):

            total_block_days = sum(
                flt(row.total_leave_days)
                for row in leaves
            )

            calculated_amount = (
                annual_entitlement
                * total_block_days
                / entitlement_days
            )

        else:
            frappe.throw(
                "Invalid Leave Block Payment Method "
                "in Angola Payroll Settings."
            )

        payable = min(
            calculated_amount,
            remaining,
        )

        return {
            "payment_mode": mode,
            "block_method": block_method,
            "amount": flt(
                payable,
                2,
            ),
            "calculated_amount": flt(
                calculated_amount,
                2,
            ),
            "source_leave_applications": [
                row.name
                for row in leaves
            ],
            "detail": balance,
        }

    frappe.throw(
        f"Invalid Holiday Allowance Payment Mode: {mode}"
    )
