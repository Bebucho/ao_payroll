import frappe
from hrms.hr.doctype.leave_application.leave_application import get_number_of_leave_days
import math
from frappe.utils import (
    add_months,
    flt,
    get_first_day,
    get_last_day,
    getdate,
)


from ao_payroll.payroll.settings import get_payroll_settings


def get_inss_employee_rate(
    company=None,
    year=None,
    reference_date=None,
    employee=None,
):
    settings = get_payroll_settings(
        company=company,
        year=year,
        reference_date=reference_date,
        employee=employee,
    )
    return flt(settings.inss_employee_rate) / 100


def get_employee_attendance_effects(
    employee,
    payroll_start_date,
    payroll_end_date,
):
    """
    Determine payroll presence effects from:

    - Attendance + Tipo de Falta
    - approved Leave Application + Leave Type

    Master data is authoritative for payroll treatment.

    Leave Application does not create accounting entries here.
    custom_recuperavel_do_inss is informational only.
    """

    payroll_start_date = getdate(
        payroll_start_date
    )
    payroll_end_date = getdate(
        payroll_end_date
    )

    effects = {
        "salary_deduction_days": 0,
        "meal_deduction_days": 0,
        "transport_deduction_days": 0,
        "attendance_bonus_affected": False,
        "attendance_records": [],
        "leave_records": [],
        "vacation_days": 0,
        "inss_recoverable_leave_days": 0,
    }

    # -----------------------------------------------------
    # Approved Leave Applications
    # -----------------------------------------------------

    previous_month_date = add_months(
        payroll_start_date,
        -1,
    )

    previous_month_start = getdate(
        get_first_day(previous_month_date)
    )

    previous_month_end = getdate(
        get_last_day(previous_month_date)
    )

    leave_fields = [
        "name",
        "leave_type",
        "from_date",
        "to_date",
        "half_day",
        "half_day_date",
        "total_leave_days",
        "processar_mes_seguinte",
        "salary_slip",
    ]

    # -----------------------------------------------------
    # Normal leave:
    #
    # Process according to the actual leave dates, but only
    # when it has NOT explicitly been deferred.
    # -----------------------------------------------------

    current_leave_applications = frappe.get_all(
        "Leave Application",
        filters={
            "employee": employee,
            "docstatus": 1,
            "status": "Approved",
            "processar_mes_seguinte": 0,
            "salary_slip": ["is", "not set"],
            "from_date": [
                "<=",
                payroll_end_date,
            ],
            "to_date": [
                ">=",
                payroll_start_date,
            ],
        },
        fields=leave_fields,
        order_by="from_date asc",
    )

    # -----------------------------------------------------
    # Deferred leave:
    #
    # A leave from the immediately preceding calendar month
    # may be recognised in this payroll when HR explicitly
    # marked Processar Mes Seguinte.
    #
    # Historical dates remain unchanged. Only the payroll
    # recognition period moves.
    # -----------------------------------------------------

    deferred_leave_applications = frappe.get_all(
        "Leave Application",
        filters={
            "employee": employee,
            "docstatus": 1,
            "status": "Approved",
            "processar_mes_seguinte": 1,
            "salary_slip": ["is", "not set"],
            # Deferred leave is recognized in the payroll
            # immediately after the month in which the leave ends.
            #
            # Do not require from_date to be inside the previous
            # month: a leave may legitimately cross a month boundary.
            "to_date": [
                "between",
                [
                    previous_month_start,
                    previous_month_end,
                ],
            ],
        },
        fields=leave_fields,
        order_by="from_date asc",
    )

    leave_applications = []
    seen_leave_applications = set()

    for leave in (
        current_leave_applications
        + deferred_leave_applications
    ):
        if leave.name in seen_leave_applications:
            continue

        seen_leave_applications.add(
            leave.name
        )

        leave_applications.append(
            leave
        )

    for leave in leave_applications:
        treatment = frappe.db.get_value(
            "Leave Type",
            leave.leave_type,
            [
                "custom_deduz_salario",
                "custom_deduz_subsidio_alimentacao",
                "custom_deduz_subsidio_transporte",
                "custom_afeta_premio_assiduidade",
                "custom_recuperavel_do_inss",
            ],
            as_dict=True,
        )

        if not treatment:
            continue

        is_deferred = bool(
            leave.processar_mes_seguinte
            and getdate(leave.to_date)
            < payroll_start_date
        )

        if is_deferred:
            overlap_from = max(
                getdate(leave.from_date),
                previous_month_start,
            )

            overlap_to = min(
                getdate(leave.to_date),
                previous_month_end,
            )

        else:
            overlap_from = max(
                getdate(leave.from_date),
                payroll_start_date,
            )

            overlap_to = min(
                getdate(leave.to_date),
                payroll_end_date,
            )

        if overlap_from > overlap_to:
            continue

        half_day = 0
        half_day_date = None

        if (
            leave.half_day
            and leave.half_day_date
        ):
            candidate_half_day = getdate(
                leave.half_day_date
            )

            if (
                overlap_from
                <= candidate_half_day
                <= overlap_to
            ):
                half_day = 1
                half_day_date = (
                    candidate_half_day
                )

        leave_days = flt(
            get_number_of_leave_days(
                employee,
                leave.leave_type,
                overlap_from,
                overlap_to,
                half_day,
                half_day_date,
            )
        )

        if leave_days <= 0:
            continue

        if treatment.custom_deduz_salario:
            effects[
                "salary_deduction_days"
            ] += leave_days

        if (
            treatment
            .custom_deduz_subsidio_alimentacao
        ):
            effects[
                "meal_deduction_days"
            ] += leave_days

        if (
            treatment
            .custom_deduz_subsidio_transporte
        ):
            effects[
                "transport_deduction_days"
            ] += leave_days

        if (
            treatment
            .custom_afeta_premio_assiduidade
        ):
            effects[
                "attendance_bonus_affected"
            ] = True

        if (
            treatment
            .custom_recuperavel_do_inss
        ):
            effects[
                "inss_recoverable_leave_days"
            ] += leave_days

        if leave.leave_type == "Ferias":
            effects[
                "vacation_days"
            ] += leave_days

        effects["leave_records"].append(
            {
                "leave_application":
                    leave.name,
                "leave_type":
                    leave.leave_type,
                "from_date":
                    overlap_from,
                "to_date":
                    overlap_to,
                "leave_days":
                    leave_days,
                "processar_mes_seguinte":
                    bool(
                        leave.processar_mes_seguinte
                    ),
                "deferred_to_current_payroll":
                    bool(is_deferred),
                "deduz_salario":
                    bool(
                        treatment
                        .custom_deduz_salario
                    ),
                "deduz_subsidio_alimentacao":
                    bool(
                        treatment
                        .custom_deduz_subsidio_alimentacao
                    ),
                "deduz_subsidio_transporte":
                    bool(
                        treatment
                        .custom_deduz_subsidio_transporte
                    ),
                "afeta_premio_assiduidade":
                    bool(
                        treatment
                        .custom_afeta_premio_assiduidade
                    ),
                "recuperavel_do_inss":
                    bool(
                        treatment
                        .custom_recuperavel_do_inss
                    ),
            }
        )

    # -----------------------------------------------------
    # Helper: approved leave covers Attendance date?
    # -----------------------------------------------------

    def date_is_covered_by_leave(
        attendance_date,
    ):
        attendance_date = getdate(
            attendance_date
        )

        for leave in leave_applications:
            if not (
                getdate(leave.from_date)
                <= attendance_date
                <= getdate(leave.to_date)
            ):
                continue

            half_day = (
                1
                if (
                    leave.half_day
                    and leave.half_day_date
                    and getdate(
                        leave.half_day_date
                    )
                    == attendance_date
                )
                else 0
            )

            half_day_date = (
                attendance_date
                if half_day
                else None
            )

            days = flt(
                get_number_of_leave_days(
                    employee,
                    leave.leave_type,
                    attendance_date,
                    attendance_date,
                    half_day,
                    half_day_date,
                )
            )

            # A full leave day is authoritative over an
            # ordinary Attendance absence.
            if days >= 1:
                return True

        return False

    # -----------------------------------------------------
    # Attendance / Tipo de Falta
    # -----------------------------------------------------

    attendances = frappe.get_all(
        "Attendance",
        filters={
            "employee": employee,
            "docstatus": 1,
            "attendance_date": [
                "between",
                [
                    payroll_start_date,
                    payroll_end_date,
                ],
            ],
            "status": [
                "in",
                [
                    "Absent",
                    "Half Day",
                ],
            ],
        },
        fields=[
            "name",
            "attendance_date",
            "status",
            "tipo_de_faltas",
        ],
        order_by="attendance_date asc",
    )

    for attendance in attendances:

        if date_is_covered_by_leave(
            attendance.attendance_date
        ):
            continue

        tipo_de_falta = (
            attendance.get(
                "tipo_de_faltas"
            )
        )

        if not tipo_de_falta:
            continue

        treatment = frappe.db.get_value(
            "Tipo de Falta",
            {
                "name": tipo_de_falta,
                "activo": 1,
            },
            [
                "deduz_salario",
                "deduz_subsidio_alimentacao",
                "deduz_subsidio_transporte",
                "afeta_premio_assiduidade",
            ],
            as_dict=True,
        )

        if not treatment:
            frappe.throw(
                f"Tipo de Falta "
                f"'{tipo_de_falta}' "
                f"não encontrado ou inactivo."
            )

        absence_days = (
            0.5
            if attendance.status
            == "Half Day"
            else 1.0
        )

        if treatment.deduz_salario:
            effects[
                "salary_deduction_days"
            ] += absence_days

        if treatment.deduz_subsidio_alimentacao:
            effects[
                "meal_deduction_days"
            ] += absence_days

        if treatment.deduz_subsidio_transporte:
            effects[
                "transport_deduction_days"
            ] += absence_days

        if treatment.afeta_premio_assiduidade:
            effects[
                "attendance_bonus_affected"
            ] = True

        effects["attendance_records"].append(
            {
                "attendance":
                    attendance.name,
                "date":
                    attendance.attendance_date,
                "status":
                    attendance.status,
                "absence_days":
                    absence_days,
                "tipo_de_falta":
                    tipo_de_falta,
                "deduz_salario":
                    bool(
                        treatment.deduz_salario
                    ),
                "deduz_subsidio_alimentacao":
                    bool(
                        treatment
                        .deduz_subsidio_alimentacao
                    ),
                "deduz_subsidio_transporte":
                    bool(
                        treatment
                        .deduz_subsidio_transporte
                    ),
                "afeta_premio_assiduidade":
                    bool(
                        treatment
                        .afeta_premio_assiduidade
                    ),
            }
        )

    return {
        "dias_falta_salario":
            effects[
                "salary_deduction_days"
            ],

        "dias_falta_alimentacao":
            effects[
                "meal_deduction_days"
            ],

        "dias_falta_transporte":
            effects[
                "transport_deduction_days"
            ],

        "dias_ferias":
            effects[
                "vacation_days"
            ],

        "dias_licenca_recuperavel_inss":
            effects[
                "inss_recoverable_leave_days"
            ],

        "perde_premio_assiduidade":
            effects[
                "attendance_bonus_affected"
            ],

        "atraso_horas": 0,
        "atraso_minutos": 0,

        "attendance_records":
            effects[
                "attendance_records"
            ],

        "leave_records":
            effects[
                "leave_records"
            ],
    }




def calculate_holiday_allowance_entitlement(
    employee,
    year,
    base_salary,
):
    """
    Calculate annual Ferias / Subsidio de Ferias entitlement.

    Principles:
    - Full calendar-year service: 22 working days.
    - Admission year: 2 days per complete month of service,
      minimum 6, maximum 22.
    - Where service proration is enabled, a leaver's entitlement
      is limited to complete months served in the year.
    - Subsidy entitlement follows the same proportion of the
      configured annual holiday allowance rate.

    This function calculates entitlement only.
    It does not decide when the subsidy is paid.
    """

    settings = get_payroll_settings(
        employee=employee,
        year=year,
    )

    rate = (
        flt(settings.holiday_allowance_rate)
        / 100
    )

    employee_doc = frappe.get_doc(
        "Employee",
        employee,
    )

    joining_date = getdate(
        employee_doc.date_of_joining
    )

    relieving_date = (
        getdate(employee_doc.relieving_date)
        if employee_doc.relieving_date
        else None
    )

    year = int(year)

    year_start = getdate(
        f"{year}-01-01"
    )

    year_end = getdate(
        f"{year}-12-31"
    )

    # Employee had no service during this calendar year.
    if joining_date > year_end:
        return {
            "year": year,
            "service_months": 0,
            "entitlement_days": 0,
            "annual_entitlement": 0,
            "rate": rate,
        }

    if (
        relieving_date
        and relieving_date < year_start
    ):
        return {
            "year": year,
            "service_months": 0,
            "entitlement_days": 0,
            "annual_entitlement": 0,
            "rate": rate,
        }

    effective_start = max(
        joining_date,
        year_start,
    )

    effective_end = min(
        relieving_date or year_end,
        year_end,
    )

    prorate = bool(
        int(
            getattr(
                settings,
                "custom_holiday_allowance_prorate_service",
                0,
            )
            or 0
        )
    )

    full_year_service = (
        effective_start <= year_start
        and effective_end >= year_end
    )

    # -----------------------------------------------------
    # Count complete calendar months actually served.
    #
    # Example:
    # joins 01 Sep -> Sep, Oct, Nov, Dec = 4 months
    # joins 15 Sep -> Oct, Nov, Dec = 3 complete months
    # -----------------------------------------------------

    import calendar
    from datetime import date

    complete_months = 0

    for month in range(1, 13):
        month_start = date(
            year,
            month,
            1,
        )

        month_end = date(
            year,
            month,
            calendar.monthrange(
                year,
                month,
            )[1],
        )

        if (
            effective_start <= month_start
            and effective_end >= month_end
        ):
            complete_months += 1

    if (
        full_year_service
        or not prorate
    ):
        entitlement_days = 22.0

    elif joining_date.year == year:
        # Admission-year rule.
        entitlement_days = min(
            22.0,
            max(
                6.0,
                complete_months * 2.0,
            ),
        )

    else:
        # Existing employee leaving during the year.
        entitlement_days = min(
            22.0,
            complete_months * 2.0,
        )

    annual_entitlement = (
        flt(base_salary)
        * rate
        * entitlement_days
        / 22.0
    )

    return {
        "year": year,
        "service_months": complete_months,
        "entitlement_days": flt(
            entitlement_days,
            2,
        ),
        "annual_entitlement": flt(
            annual_entitlement,
            2,
        ),
        "rate": flt(
            rate,
            6,
        ),
    }




def get_holiday_allowance_paid(
    employee,
    year,
):
    """
    Return Subsidio de Ferias actually paid through submitted
    Salary Slips during the calendar year.

    Additional Salary alone does not count as paid.
    Only a component that reached a submitted Salary Slip
    reduces the employee's annual entitlement.
    """

    settings = get_payroll_settings(
        employee=employee,
        year=year,
    )

    component = getattr(
        settings,
        "holyday_allowance_salary_component",
        None,
    )

    if not component:
        frappe.throw(
            "Angola Payroll Settings has no "
            "Subsidio de Ferias Salary Component configured."
        )

    components = [
        component,
        "Proporcional Subsidio Ferias",
    ]

    year = int(year)

    year_start = getdate(
        f"{year}-01-01"
    )

    year_end = getdate(
        f"{year}-12-31"
    )

    paid = frappe.db.sql(
        """
        SELECT COALESCE(SUM(sd.amount), 0)
        FROM `tabSalary Detail` sd
        INNER JOIN `tabSalary Slip` ss
            ON ss.name = sd.parent
        WHERE
            sd.parenttype = 'Salary Slip'
            AND sd.parentfield = 'earnings'
            AND sd.salary_component IN %(components)s
            AND ss.employee = %(employee)s
            AND ss.docstatus = 1
            AND ss.end_date >= %(year_start)s
            AND ss.end_date <= %(year_end)s
        """,
        {
            "components": tuple(components),
            "employee": employee,
            "year_start": year_start,
            "year_end": year_end,
        },
    )[0][0]

    return flt(
        paid,
        2,
    )


def calculate_holiday_allowance_balance(
    employee,
    year,
    base_salary,
):
    """
    Annual control account for Subsidio de Ferias.

    annual entitlement
    - amount already paid through submitted payroll
    = remaining entitlement

    This is a payroll control balance only.
    It creates no accounting entry.
    """

    entitlement = (
        calculate_holiday_allowance_entitlement(
            employee=employee,
            year=year,
            base_salary=base_salary,
        )
    )

    paid = get_holiday_allowance_paid(
        employee=employee,
        year=year,
    )

    annual_entitlement = flt(
        entitlement["annual_entitlement"],
        2,
    )

    remaining = max(
        0,
        annual_entitlement - paid,
    )

    overpaid = max(
        0,
        paid - annual_entitlement,
    )

    return {
        **entitlement,
        "paid": flt(
            paid,
            2,
        ),
        "remaining": flt(
            remaining,
            2,
        ),
        "overpaid": flt(
            overpaid,
            2,
        ),
    }




def get_christmas_allowance_paid(
    employee,
    year,
):
    """
    Return Subsidio de Natal actually paid through submitted
    Salary Slips during the calendar year.

    Includes normal and termination proportional components.
    """

    settings = get_payroll_settings(
        employee=employee,
        year=year,
    )

    component = getattr(
        settings,
        "christmas_allowance_salary_component",
        None,
    )

    if not component:
        frappe.throw(
            "Angola Payroll Settings has no "
            "Subsidio de Natal Salary Component configured."
        )

    components = [
        component,
        "Proporcional Subsidio Natal",
    ]

    year = int(year)

    year_start = getdate(
        f"{year}-01-01"
    )

    year_end = getdate(
        f"{year}-12-31"
    )

    paid = frappe.db.sql(
        """
        SELECT COALESCE(SUM(sd.amount), 0)
        FROM `tabSalary Detail` sd
        INNER JOIN `tabSalary Slip` ss
            ON ss.name = sd.parent
        WHERE
            sd.parenttype = 'Salary Slip'
            AND sd.parentfield = 'earnings'
            AND sd.salary_component IN %(components)s
            AND ss.employee = %(employee)s
            AND ss.docstatus = 1
            AND ss.end_date >= %(year_start)s
            AND ss.end_date <= %(year_end)s
        """,
        {
            "components": tuple(components),
            "employee": employee,
            "year_start": year_start,
            "year_end": year_end,
        },
    )[0][0]

    return flt(
        paid,
        2,
    )



def calculate_gross_salary(
    employee,
    payroll_start_date,
    payroll_end_date,
    salario_base,
    abono_familia_unitario=0,
    numero_dependentes=0,
    subsidio_alimentacao=0,
    subsidio_transporte=0,
    outros_componentes=None,
    premio_efetividade=0,
    dias_uteis=0,
    absence_effects=None,
):
    salario_base = flt(salario_base)
    abono_familia_unitario = flt(abono_familia_unitario)
    subsidio_alimentacao = flt(subsidio_alimentacao)
    subsidio_transporte = flt(subsidio_transporte)
    premio_efetividade = flt(premio_efetividade)
    dias_uteis = flt(dias_uteis)

    if dias_uteis <= 0:
        frappe.throw("Dias úteis deve ser superior a zero.")

    if absence_effects is None:
        absence_effects = {
            "salary_deduction_days": 0,
            "meal_deduction_days": 0,
            "transport_deduction_days": 0,
            "attendance_bonus_affected": False,
        }

    salary_deduction_days = flt(
        absence_effects.get(
            "salary_deduction_days",
            0,
        )
    )

    meal_deduction_days = flt(
        absence_effects.get(
            "meal_deduction_days",
            0,
        )
    )

    transport_deduction_days = flt(
        absence_effects.get(
            "transport_deduction_days",
            0,
        )
    )

    attendance_bonus_affected = bool(
        absence_effects.get(
            "attendance_bonus_affected",
            False,
        )
    )

    total_faltas = max(
        salary_deduction_days,
        meal_deduction_days,
        transport_deduction_days,
    )

    valor_dia_salario = (
        salario_base / dias_uteis
    )

    valor_dia_alimentacao = (
        subsidio_alimentacao / dias_uteis
    )

    valor_dia_transporte = (
        subsidio_transporte / dias_uteis
    )

    deducao_salario = min(
        valor_dia_salario * salary_deduction_days,
        salario_base,
    )

    deducao_alimentacao = min(
        valor_dia_alimentacao * meal_deduction_days,
        subsidio_alimentacao,
    )

    deducao_transporte = min(
        valor_dia_transporte * transport_deduction_days,
        subsidio_transporte,
    )

    alimentacao_pago = (
        subsidio_alimentacao
        - deducao_alimentacao
    )

    transporte_pago = (
        subsidio_transporte
        - deducao_transporte
    )

    premio_efetividade_pago = (
        0
        if attendance_bonus_affected
        else premio_efetividade
    )

    earnings = []

    def add_earning(name, amount):
        amount = flt(amount)

        if amount != 0:
            earnings.append(
                {
                    "salary_component": name,
                    "amount": amount,
                }
            )

    add_earning(
        "Salario Base",
        salario_base,
    )

    add_earning(
        "Abono de Familia",
        abono_familia_unitario
        * numero_dependentes,
    )

    add_earning(
        "Subsidio de Alimentacao",
        alimentacao_pago,
    )

    add_earning(
        "Subsidio de Transporte",
        transporte_pago,
    )

    add_earning(
        "Premio Efetividade",
        premio_efetividade_pago,
    )

    if outros_componentes:
        for component in outros_componentes:
            add_earning(
                component["salary_component"],
                component["amount"],
            )

    additional_salaries = frappe.get_all(
        "Additional Salary",
        filters={
            "employee": employee,
            "payroll_date": [
                "between",
                [payroll_start_date, payroll_end_date],
            ],
            "docstatus": 1,
        },
        fields=[
            "name",
            "salary_component",
            "amount",
            "payroll_date",
        ],
        order_by="payroll_date asc",
    )

    additional_salary_details = []

    for additional_salary in additional_salaries:
        component = frappe.db.get_value(
            "Salary Component",
            additional_salary.salary_component,
            [
                "salary_component",
                "type",
                "incidencia_inss",
                "incidencia_irt",
                "custom_subsidio_dedutivel",
            ],
            as_dict=True,
        )

        if not component:
            frappe.throw(
                f"Salary Component "
                f"{additional_salary.salary_component} "
                f"não encontrado."
            )

        amount = flt(
            additional_salary.amount
        )

        add_earning(
            additional_salary.salary_component,
            amount,
        )

        additional_salary_details.append(
            {
                "additional_salary": additional_salary.name,
                "salary_component": additional_salary.salary_component,
                "amount": amount,
                "type": component.type,
                "incidencia_inss": bool(
                    component.incidencia_inss
                ),
                "incidencia_irt": bool(
                    component.incidencia_irt
                ),
                "custom_subsidio_dedutivel": bool(
                    component.custom_subsidio_dedutivel
                ),
            }
        )

    total_remuneracoes = sum(
        flt(item["amount"])
        for item in earnings
    )

    absence_deductions = [
        {
            "salary_component": "Falta - Salario",
            "amount": flt(deducao_salario),
        },
        {
            "salary_component": "Falta - Subsidio Alimentacao",
            "amount": flt(deducao_alimentacao),
        },
        {
            "salary_component": "Falta - Subsidio Transporte",
            "amount": flt(deducao_transporte),
        },
    ]

    salario_iliquido = (
        total_remuneracoes
        - deducao_salario
    )

    return {
        "employee": employee,
        "dias_uteis": flt(dias_uteis),
        "faltas_com_salario": 0,
        "faltas_sem_salario": salary_deduction_days,
        "faltas_injustificadas": 0,
        "total_faltas": flt(total_faltas),
        "salary_deduction_days": flt(
            salary_deduction_days
        ),
        "meal_deduction_days": flt(
            meal_deduction_days
        ),
        "transport_deduction_days": flt(
            transport_deduction_days
        ),
        "attendance_bonus_affected": attendance_bonus_affected,
        "earnings": earnings,
        "additional_salary_details": additional_salary_details,
        "absence_deductions": absence_deductions,
        "total_remuneracoes": flt(
            total_remuneracoes
        ),
        "deducao_salario": flt(
            deducao_salario
        ),
        "deducao_alimentacao": flt(
            deducao_alimentacao
        ),
        "deducao_transporte": flt(
            deducao_transporte
        ),
        "salario_iliquido": flt(
            salario_iliquido
        ),
    }


def calculate_inss_from_payroll(result, employee, payroll_end_date):
    inss_base = 0

    for earning in result.get("earnings", []):
        salary_component = earning.get(
            "salary_component"
        )

        if not salary_component:
            continue

        incidencia_inss = frappe.db.get_value(
            "Salary Component",
            salary_component,
            "incidencia_inss",
        )

        if incidencia_inss:
            inss_base += flt(
                earning.get("amount", 0)
            )

    employee_rate = get_inss_employee_rate(
        employee=employee,
        reference_date=payroll_end_date,
    )

    inss = math.ceil(
        inss_base * employee_rate
    )

    return {
        "base_inss": flt(inss_base),
        "inss_rate": flt(
            employee_rate * 100
        ),
        "inss": flt(inss),
    }


def calculate_irt_base(result, inss_result):
    salario_iliquido = flt(
        result.get("salario_iliquido", 0)
    )

    inss = flt(
        inss_result.get("inss", 0)
    )

    total_subsidios = 0

    for earning in result.get("earnings", []):
        salary_component = earning.get(
            "salary_component"
        )

        amount = flt(
            earning.get("amount", 0)
        )

        if not salary_component:
            continue

        custom_subsidio_dedutivel = frappe.db.get_value(
            "Salary Component",
            salary_component,
            "custom_subsidio_dedutivel",
        )

        if custom_subsidio_dedutivel:
            total_subsidios += amount

    payroll_year = (
        int(
            str(
                result.get(
                    "payroll_end_date",
                    "",
                )
            )[:4]
        )
        if result.get("payroll_end_date")
        else None
    )

    if payroll_year:
        table_name = frappe.db.get_value(
            "IRT Tables",
            {
                "year": payroll_year,
                "active": 1,
            },
            "name",
            order_by="modified desc",
        )

        if not table_name:
            frappe.throw(
                f"No active IRT table found for year "
                f"{payroll_year}."
            )

        threshold = flt(
            frappe.db.get_value(
                "IRT Tables",
                table_name,
                "custom_subsidy_treshold",
            )
        )
    else:
        threshold = 0

    subsidios_sujeitos_irt = max(
        total_subsidios - threshold,
        0,
    )

    base_irt = (
        salario_iliquido
        - inss
        - subsidios_sujeitos_irt
    )

    return {
        "salario_iliquido": flt(
            salario_iliquido
        ),
        "inss": flt(inss),
        "total_subsidios": flt(
            total_subsidios
        ),
        "threshold": flt(threshold),
        "subsidios_sujeitos_irt": flt(
            subsidios_sujeitos_irt
        ),
        "base_irt": flt(base_irt),
    }


def calculate_irt(base_irt, payroll_year):
    base_irt = flt(base_irt)
    payroll_year = int(payroll_year)

    if base_irt <= 0:
        return {
            "base_irt": 0.0,
            "payroll_year": payroll_year,
            "irt_table": None,
            "irt_slab": None,
            "from_amount": 0.0,
            "to_amount": 0.0,
            "fixed_amount": 0.0,
            "marginal_rate": 0.0,
            "irt": 0.0,
        }

    table_name = frappe.db.get_value(
        "IRT Tables",
        {
            "year": payroll_year,
            "active": 1,
        },
        "name",
        order_by="modified desc",
    )

    if not table_name:
        frappe.throw(
            f"No active IRT table found for year "
            f"{payroll_year}."
        )

    table = frappe.get_doc(
        "IRT Tables",
        table_name,
    )

    slab = None

    for row in table.brackets:
        from_amount = flt(
            row.from_amount
        )
        to_amount = flt(
            row.to_amount
        )

        if (
            base_irt >= from_amount
            and base_irt <= to_amount
        ):
            slab = row
            break

    if not slab:
        frappe.throw(
            f"No IRT slab found for base "
            f"{base_irt:,.2f} in IRT table "
            f"{table_name}."
        )

    from_amount = flt(
        slab.from_amount
    )
    to_amount = flt(
        slab.to_amount
    )
    fixed_amount = flt(
        slab.fixed_amount
    )
    marginal_rate = flt(
        slab.marginal_rate
    )

    taxable_excess = max(
        base_irt - from_amount,
        0,
    )

    marginal_tax = (
        taxable_excess
        * marginal_rate
        / 100
    )

    irt = math.ceil(
        fixed_amount + marginal_tax
    )

    return {
        "base_irt": flt(base_irt),
        "payroll_year": payroll_year,
        "irt_table": table_name,
        "irt_slab": slab.name,
        "from_amount": flt(from_amount),
        "to_amount": flt(to_amount),
        "fixed_amount": flt(fixed_amount),
        "marginal_rate": flt(marginal_rate),
        "taxable_excess": flt(
            taxable_excess
        ),
        "marginal_tax": flt(
            marginal_tax
        ),
        "irt": flt(irt),
    }


def calculate_net_salary(
    salario_iliquido,
    inss,
    irt,
    adiantamentos=0,
):
    salario_iliquido = flt(
        salario_iliquido
    )
    inss = flt(inss)
    irt = flt(irt)
    adiantamentos = flt(
        adiantamentos
    )

    salario_liquido = math.ceil(
        salario_iliquido
        - inss
        - irt
        - adiantamentos
    )

    return {
        "salario_iliquido": flt(
            salario_iliquido
        ),
        "inss": flt(inss),
        "irt": flt(irt),
        "adiantamentos": flt(
            adiantamentos
        ),
        "salario_liquido": flt(
            salario_liquido
        ),
    }

def get_employee_salary_inputs(
    employee,
    payroll_end_date,
):
    employee_data = frappe.db.get_value(
        "Employee",
        employee,
        [
            "employee",
            "employee_name",
            "numero_de_dependentes",
        ],
        as_dict=True,
    )

    if not employee_data:
        frappe.throw(
            f"Employee {employee} não encontrado."
        )

    assignment = frappe.db.get_value(
        "Salary Structure Assignment",
        {
            "employee": employee,
            "from_date": [
                "<=",
                payroll_end_date,
            ],
            "docstatus": 1,
        },
        [
            "name",
            "salary_structure",
            "base",
            "custom_base_abf",
            "custom_base_sa",
            "custom_base_st",
            "variable",
        ],
        order_by="from_date desc, creation desc",
        as_dict=True,
    )

    if not assignment:
        frappe.throw(
            f"Não existe Salary Structure Assignment "
            f"válido para {employee}."
        )

    return {
        "employee": employee_data,
        "assignment": assignment,
    }


def calculate_employee_payroll(
    employee,
    payroll_start_date,
    payroll_end_date,
    dias_uteis,
    premio_efetividade=0,
):
    inputs = get_employee_salary_inputs(
        employee,
        payroll_end_date,
    )

    employee_data = inputs["employee"]
    assignment = inputs["assignment"]

    absence_effects = get_employee_attendance_effects(
        employee=employee,
        payroll_start_date=payroll_start_date,
        payroll_end_date=payroll_end_date,
    )

    result = calculate_gross_salary(
        employee=employee,
        payroll_start_date=payroll_start_date,
        payroll_end_date=payroll_end_date,
        salario_base=flt(
            assignment.base
        ),
        abono_familia_unitario=flt(
            assignment.custom_base_abf
        ),
        numero_dependentes=flt(
            employee_data.numero_de_dependentes
        ),
        subsidio_alimentacao=flt(
            assignment.custom_base_sa
        ),
        subsidio_transporte=flt(
            assignment.custom_base_st
        ),
        premio_efetividade=flt(
            premio_efetividade
        ),
        dias_uteis=flt(dias_uteis),
        absence_effects=absence_effects,
    )

    result["payroll_start_date"] = (
        payroll_start_date
    )

    result["payroll_end_date"] = (
        payroll_end_date
    )

    result["absence_effects"] = (
        absence_effects
    )

    inss_result = calculate_inss_from_payroll(
        result,
        employee=employee,
        payroll_end_date=payroll_end_date,
    )

    irt_base_result = calculate_irt_base(
        result,
        inss_result,
    )

    payroll_year = int(
        str(payroll_end_date)[:4]
    )

    irt_result = calculate_irt(
        irt_base_result["base_irt"],
        payroll_year,
    )

    net_result = calculate_net_salary(
        salario_iliquido=result[
            "salario_iliquido"
        ],
        inss=inss_result["inss"],
        irt=irt_result["irt"],
    )

    result["inss_base"] = (
        inss_result["base_inss"]
    )

    result["inss_rate"] = (
        inss_result["inss_rate"]
    )

    result["inss"] = (
        inss_result["inss"]
    )

    result["irt_base"] = (
        irt_base_result["base_irt"]
    )

    result["irt_threshold"] = (
        irt_base_result["threshold"]
    )

    result["irt"] = (
        irt_result["irt"]
    )

    result["irt_table"] = (
        irt_result["irt_table"]
    )

    result["irt_slab"] = (
        irt_result["irt_slab"]
    )

    result["salario_liquido"] = (
        net_result["salario_liquido"]
    )

    result["employee_name"] = (
        employee_data.employee_name
    )

    result["salary_structure_assignment"] = (
        assignment.name
    )

    result["salary_structure"] = (
        assignment.salary_structure
    )

    result["numero_dependentes"] = flt(
        employee_data.numero_de_dependentes
    )

    result["salario_base"] = flt(
        assignment.base
    )

    return result
