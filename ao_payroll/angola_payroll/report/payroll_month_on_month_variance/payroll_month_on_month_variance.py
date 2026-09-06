import calendar

import frappe
from frappe import _
from frappe.utils import (
    add_months,
    flt,
    get_first_day,
    get_last_day,
    getdate,
)


BASE_COMPONENT = "Salario Base"


def execute(filters=None):
    filters = frappe._dict(filters or {})

    validate_filters(filters)

    periods = get_periods(filters.payroll_month)

    previous_slips = get_salary_slips(
        company=filters.company,
        start_date=periods["previous_start"],
        end_date=periods["previous_end"],
        employee=filters.employee,
    )

    current_slips = get_salary_slips(
        company=filters.company,
        start_date=periods["current_start"],
        end_date=periods["current_end"],
        employee=filters.employee,
    )

    all_slip_names = list({
        row.name
        for row in previous_slips.values()
    } | {
        row.name
        for row in current_slips.values()
    })

    components = get_components(all_slip_names)

    settings = frappe.get_single(
        "Angola Payroll Settings"
    )

    data = build_data(
        previous_slips=previous_slips,
        current_slips=current_slips,
        components=components,
        settings=settings,
        filters=filters,
    )

    return get_columns(), data


def validate_filters(filters):
    if not filters.company:
        frappe.throw(_("Company is required."))

    if not filters.payroll_month:
        frappe.throw(_("Payroll Month is required."))


def get_periods(payroll_month):
    current_start = get_first_day(
        getdate(payroll_month)
    )

    current_end = get_last_day(
        current_start
    )

    previous_start = get_first_day(
        add_months(current_start, -1)
    )

    previous_end = get_last_day(
        previous_start
    )

    return {
        "current_start": current_start,
        "current_end": current_end,
        "previous_start": previous_start,
        "previous_end": previous_end,
    }


def get_salary_slips(
    company,
    start_date,
    end_date,
    employee=None,
):
    filters = {
        "company": company,
        "docstatus": 1,
        "start_date": ["<=", end_date],
        "end_date": [">=", start_date],
    }

    if employee:
        filters["employee"] = employee

    rows = frappe.get_all(
        "Salary Slip",
        filters=filters,
        fields=[
            "name",
            "employee",
            "employee_name",
            "start_date",
            "end_date",
            "posting_date",
            "gross_pay",
            "total_deduction",
            "net_pay",
            "payroll_entry",
            "creation",
        ],
        order_by=(
            "employee asc, "
            "end_date desc, "
            "creation desc"
        ),
    )

    #
    # Keep one submitted slip per employee for the period.
    # If an amended slip exists, the newest submitted document
    # is the economically relevant one.
    #
    result = {}

    for row in rows:
        if row.employee not in result:
            result[row.employee] = row

    return result


def get_components(slip_names):
    if not slip_names:
        return {}

    rows = frappe.get_all(
        "Salary Detail",
        filters={
            "parent": ["in", slip_names],
            "parenttype": "Salary Slip",
        },
        fields=[
            "parent",
            "parentfield",
            "salary_component",
            "amount",
            "statistical_component",
            "do_not_include_in_total",
            "additional_salary",
        ],
        order_by="parent asc, idx asc",
    )

    result = {}

    for row in rows:
        result.setdefault(
            row.parent,
            {},
        )

        result[row.parent][
            row.salary_component
        ] = {
            "amount": flt(row.amount),
            "parentfield": row.parentfield,
            "statistical_component":
                bool(row.statistical_component),
            "do_not_include_in_total":
                bool(row.do_not_include_in_total),
            "additional_salary":
                row.additional_salary,
        }

    return result


def component_amount(
    components,
    slip_name,
    component,
):
    if not slip_name or not component:
        return 0.0

    return flt(
        components
        .get(slip_name, {})
        .get(component, {})
        .get("amount", 0)
    )


def build_data(
    previous_slips,
    current_slips,
    components,
    settings,
    filters,
):
    employees = sorted(
        set(previous_slips)
        | set(current_slips)
    )

    result = []

    for employee in employees:
        previous = previous_slips.get(
            employee
        )

        current = current_slips.get(
            employee
        )

        row = build_row(
            employee=employee,
            previous=previous,
            current=current,
            components=components,
            settings=settings,
            filters=filters,
        )

        if row_matches_filter(
            row,
            filters,
        ):
            result.append(row)

    result.sort(
        key=lambda row: (
            status_sort_order(
                row["status"]
            ),
            -abs(
                flt(
                    row["gross_variance"]
                )
            ),
            row["employee"],
        )
    )

    return result


def build_row(
    employee,
    previous,
    current,
    components,
    settings,
    filters,
):
    previous_name = (
        previous.name
        if previous
        else None
    )

    current_name = (
        current.name
        if current
        else None
    )

    previous_base = component_amount(
        components,
        previous_name,
        BASE_COMPONENT,
    )

    current_base = component_amount(
        components,
        current_name,
        BASE_COMPONENT,
    )

    previous_gross = (
        flt(previous.gross_pay)
        if previous
        else 0
    )

    current_gross = (
        flt(current.gross_pay)
        if current
        else 0
    )

    previous_net = (
        flt(previous.net_pay)
        if previous
        else 0
    )

    current_net = (
        flt(current.net_pay)
        if current
        else 0
    )

    inss_component = (
        settings.inss_salary_component
        or "Seguranca Social"
    )

    irt_component = (
        settings.irt_salary_component
        or (
            "Imposto Sobre o "
            "Rendimento do Trabalho"
        )
    )

    previous_inss = component_amount(
        components,
        previous_name,
        inss_component,
    )

    current_inss = component_amount(
        components,
        current_name,
        inss_component,
    )

    previous_irt = component_amount(
        components,
        previous_name,
        irt_component,
    )

    current_irt = component_amount(
        components,
        current_name,
        irt_component,
    )

    base_variance = (
        current_base
        - previous_base
    )

    gross_variance = (
        current_gross
        - previous_gross
    )

    net_variance = (
        current_net
        - previous_net
    )

    inss_variance = (
        current_inss
        - previous_inss
    )

    irt_variance = (
        current_irt
        - previous_irt
    )

    main_cause, component_variance = (
        get_main_cause(
            previous_name,
            current_name,
            components,
        )
    )

    status = determine_status(
        previous=previous,
        current=current,
        gross_variance=gross_variance,
        previous_gross=previous_gross,
        filters=filters,
    )

    employee_name = (
        current.employee_name
        if current
        else (
            previous.employee_name
            if previous
            else None
        )
    )

    return {
        "employee":
            employee,

        "employee_name":
            employee_name,

        "previous_base":
            previous_base,

        "current_base":
            current_base,

        "base_variance":
            base_variance,

        "base_variance_percent":
            percentage_change(
                previous_base,
                current_base,
            ),

        "previous_gross":
            previous_gross,

        "current_gross":
            current_gross,

        "gross_variance":
            gross_variance,

        "gross_variance_percent":
            percentage_change(
                previous_gross,
                current_gross,
            ),

        "previous_net":
            previous_net,

        "current_net":
            current_net,

        "net_variance":
            net_variance,

        "net_variance_percent":
            percentage_change(
                previous_net,
                current_net,
            ),

        "previous_inss":
            previous_inss,

        "current_inss":
            current_inss,

        "inss_variance":
            inss_variance,

        "previous_irt":
            previous_irt,

        "current_irt":
            current_irt,

        "irt_variance":
            irt_variance,

        "main_cause":
            main_cause,

        "component_variance":
            component_variance,

        "previous_salary_slip":
            previous_name,

        "current_salary_slip":
            current_name,

        "previous_payroll_entry":
            previous.payroll_entry
            if previous
            else None,

        "current_payroll_entry":
            current.payroll_entry
            if current
            else None,

        "status":
            status,
    }


def percentage_change(
    previous,
    current,
):
    previous = flt(previous)
    current = flt(current)

    if not previous:
        if current:
            return 100.0

        return 0.0

    return (
        (current - previous)
        / abs(previous)
        * 100
    )


def get_main_cause(
    previous_slip,
    current_slip,
    components,
):
    previous_components = (
        components.get(
            previous_slip,
            {},
        )
        if previous_slip
        else {}
    )

    current_components = (
        components.get(
            current_slip,
            {},
        )
        if current_slip
        else {}
    )

    component_names = (
        set(previous_components)
        | set(current_components)
    )

    candidates = []

    for component in component_names:
        previous_row = (
            previous_components.get(
                component,
                {},
            )
        )

        current_row = (
            current_components.get(
                component,
                {},
            )
        )

        #
        # Derived/statistical components must never become
        # the explanation for the economic variance.
        #
        if (
            previous_row.get(
                "statistical_component"
            )
            or current_row.get(
                "statistical_component"
            )
        ):
            continue

        previous_amount = flt(
            previous_row.get(
                "amount",
                0,
            )
        )

        current_amount = flt(
            current_row.get(
                "amount",
                0,
            )
        )

        variance = (
            current_amount
            - previous_amount
        )

        if abs(variance) < 0.005:
            continue

        candidates.append(
            (
                abs(variance),
                component,
                variance,
            )
        )

    if not candidates:
        return None, 0.0

    candidates.sort(
        reverse=True
    )

    _, component, variance = (
        candidates[0]
    )

    return component, variance


def determine_status(
    previous,
    current,
    gross_variance,
    previous_gross,
    filters,
):
    if current and not previous:
        return "NEW EMPLOYEE"

    if previous and not current:
        return "LEFT PAYROLL"

    if not previous and not current:
        return "EXCEPTION"

    variance_percent = abs(
        percentage_change(
            previous_gross,
            (
                previous_gross
                + gross_variance
            ),
        )
    )

    minimum_percent = flt(
        filters.minimum_variance_percent
    )

    minimum_absolute = flt(
        filters.minimum_absolute_variance
    )

    exceeds_percent = (
        minimum_percent
        and variance_percent
        >= minimum_percent
    )

    exceeds_absolute = (
        minimum_absolute
        and abs(gross_variance)
        >= minimum_absolute
    )

    #
    # If both thresholds are zero, any actual difference
    # is considered a variance.
    #
    if (
        not minimum_percent
        and not minimum_absolute
        and abs(gross_variance) >= 0.005
    ):
        return "VARIANCE"

    if (
        exceeds_percent
        or exceeds_absolute
    ):
        return "VARIANCE"

    return "UNCHANGED"


def row_matches_filter(
    row,
    filters,
):
    show = (
        filters.show
        or "Variances Only"
    )

    if show == "All Employees":
        return True

    if show == "Variances Only":
        return row["status"] in (
            "VARIANCE",
            "NEW EMPLOYEE",
            "LEFT PAYROLL",
            "EXCEPTION",
        )

    if show == "Exceptions Only":
        return row["status"] in (
            "NEW EMPLOYEE",
            "LEFT PAYROLL",
            "EXCEPTION",
        )

    return True


def status_sort_order(status):
    order = {
        "EXCEPTION": 0,
        "NEW EMPLOYEE": 1,
        "LEFT PAYROLL": 2,
        "VARIANCE": 3,
        "UNCHANGED": 4,
    }

    return order.get(
        status,
        99,
    )


def get_columns():
    return [
        {
            "label": _("Employee"),
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 120,
        },
        {
            "label": _("Employee Name"),
            "fieldname": "employee_name",
            "fieldtype": "Data",
            "width": 180,
        },

        {
            "label": _("Previous Base"),
            "fieldname": "previous_base",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": _("Current Base"),
            "fieldname": "current_base",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": _("Base Δ"),
            "fieldname": "base_variance",
            "fieldtype": "Currency",
            "width": 110,
        },
        {
            "label": _("Base Δ %"),
            "fieldname": "base_variance_percent",
            "fieldtype": "Percent",
            "width": 90,
        },

        {
            "label": _("Previous Gross"),
            "fieldname": "previous_gross",
            "fieldtype": "Currency",
            "width": 125,
        },
        {
            "label": _("Current Gross"),
            "fieldname": "current_gross",
            "fieldtype": "Currency",
            "width": 125,
        },
        {
            "label": _("Gross Δ"),
            "fieldname": "gross_variance",
            "fieldtype": "Currency",
            "width": 115,
        },
        {
            "label": _("Gross Δ %"),
            "fieldname": "gross_variance_percent",
            "fieldtype": "Percent",
            "width": 95,
        },

        {
            "label": _("Previous Net"),
            "fieldname": "previous_net",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": _("Current Net"),
            "fieldname": "current_net",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": _("Net Δ"),
            "fieldname": "net_variance",
            "fieldtype": "Currency",
            "width": 110,
        },
        {
            "label": _("Net Δ %"),
            "fieldname": "net_variance_percent",
            "fieldtype": "Percent",
            "width": 90,
        },

        {
            "label": _("Previous INSS"),
            "fieldname": "previous_inss",
            "fieldtype": "Currency",
            "width": 110,
        },
        {
            "label": _("Current INSS"),
            "fieldname": "current_inss",
            "fieldtype": "Currency",
            "width": 110,
        },
        {
            "label": _("INSS Δ"),
            "fieldname": "inss_variance",
            "fieldtype": "Currency",
            "width": 100,
        },

        {
            "label": _("Previous IRT"),
            "fieldname": "previous_irt",
            "fieldtype": "Currency",
            "width": 110,
        },
        {
            "label": _("Current IRT"),
            "fieldname": "current_irt",
            "fieldtype": "Currency",
            "width": 110,
        },
        {
            "label": _("IRT Δ"),
            "fieldname": "irt_variance",
            "fieldtype": "Currency",
            "width": 100,
        },

        {
            "label": _("Main Cause"),
            "fieldname": "main_cause",
            "fieldtype": "Link",
            "options": "Salary Component",
            "width": 180,
        },
        {
            "label": _("Component Δ"),
            "fieldname": "component_variance",
            "fieldtype": "Currency",
            "width": 115,
        },

        {
            "label": _("Previous Salary Slip"),
            "fieldname": "previous_salary_slip",
            "fieldtype": "Link",
            "options": "Salary Slip",
            "width": 190,
        },
        {
            "label": _("Current Salary Slip"),
            "fieldname": "current_salary_slip",
            "fieldtype": "Link",
            "options": "Salary Slip",
            "width": 190,
        },

        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 115,
        },
    ]
