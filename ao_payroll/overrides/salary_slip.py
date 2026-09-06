import re

import frappe

from frappe.utils import flt, date_diff, getdate
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip

from ao_payroll.payroll import calculator
from ao_payroll.payroll import holiday_allowance
from ao_payroll.payroll import christmas_allowance


class AOSalarySlip(SalarySlip):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.whitelisted_globals.update({
            "date_diff": date_diff,
        })

    def on_submit(self):
        super().on_submit()

        self._ao_link_leave_applications()

    def on_cancel(self):
        self._ao_unlink_leave_applications()

        super().on_cancel()

    def _ao_link_leave_applications(self):
        effects = calculator.get_employee_attendance_effects(
            employee=self.employee,
            payroll_start_date=self.start_date,
            payroll_end_date=self.end_date,
        )

        leave_records = effects.get(
            "leave_records",
            [],
        )

        for record in leave_records:
            leave_application = record.get(
                "leave_application"
            )

            if not leave_application:
                continue

            leave_data = frappe.db.get_value(
                "Leave Application",
                leave_application,
                [
                    "to_date",
                    "processar_mes_seguinte",
                    "salary_slip",
                ],
                as_dict=True,
            )

            if not leave_data:
                continue

            # Normal cross-month leave must remain available until
            # every payroll-period portion has been recognized.
            #
            # Therefore only the Salary Slip containing the end of
            # the leave finally consumes/links the Leave Application.
            #
            # Deferred leave is different: it is consumed when its
            # deferred payroll recognition occurs.
            if (
                not leave_data.processar_mes_seguinte
                and leave_data.to_date
                and getdate(self.end_date)
                < getdate(leave_data.to_date)
            ):
                continue

            current_salary_slip = (
                leave_data.salary_slip
            )

            if (
                current_salary_slip
                and current_salary_slip != self.name
            ):
                frappe.throw(
                    f"Leave Application "
                    f"{leave_application} is already "
                    f"linked to Salary Slip "
                    f"{current_salary_slip}."
                )

            frappe.db.set_value(
                "Leave Application",
                leave_application,
                "salary_slip",
                self.name,
                update_modified=False,
            )

    def _ao_unlink_leave_applications(self):
        leave_applications = frappe.get_all(
            "Leave Application",
            filters={
                "salary_slip": self.name,
            },
            pluck="name",
        )

        for leave_application in leave_applications:
            frappe.db.set_value(
                "Leave Application",
                leave_application,
                "salary_slip",
                None,
                update_modified=False,
            )

    def set_salary_structure_assignment(self):
        self._salary_structure_assignment = frappe.db.get_value(
            "Salary Structure Assignment",
            {
                "employee": self.employee,
                "salary_structure": self.salary_structure,
                "from_date": ("<=", self.actual_start_date),
                "docstatus": 1,
            },
            "*",
            order_by="from_date desc, creation desc",
            as_dict=True,
        )

        if not self._salary_structure_assignment:
            frappe.throw(
                f"No valid Salary Structure Assignment found for "
                f"{self.employee} on {self.actual_start_date}."
            )

        self.base = flt(
            self._salary_structure_assignment.get("base", 0)
        )

    def get_payroll_exchange_rate(
        self,
        from_currency="USD",
        to_currency="KZ",
    ):
        reference_date = getdate(self.end_date)

        exchange = frappe.db.get_value(
            "Currency Exchange",
            {
                "from_currency": from_currency,
                "to_currency": to_currency,
                "date": ("<=", reference_date),
            },
            [
                "name",
                "date",
                "exchange_rate",
            ],
            order_by="date desc, creation desc",
            as_dict=True,
        )

        if not exchange:
            frappe.throw(
                f"No Currency Exchange rate found for "
                f"{from_currency} -> {to_currency} "
                f"on or before {reference_date}."
            )

        rate = flt(exchange.exchange_rate)

        if rate <= 0:
            frappe.throw(
                f"Invalid Currency Exchange rate in "
                f"{exchange.name}: {rate}"
            )

        return {
            "name": exchange.name,
            "date": exchange.date,
            "rate": rate,
            "from_currency": from_currency,
            "to_currency": to_currency,
        }

    def get_assignment_currency_fields(self):
        """
        Return monetary Salary Structure Assignment fields actually
        referenced by the active Salary Structure.

        This keeps USD conversion independent of customer-specific
        field names.
        """
        fields = {"base"}

        if not self.salary_structure:
            return tuple(fields)

        structure = frappe.get_cached_doc(
            "Salary Structure",
            self.salary_structure,
        )

        assignment_meta = frappe.get_meta(
            "Salary Structure Assignment"
        )

        monetary_fields = {
            df.fieldname
            for df in assignment_meta.fields
            if df.fieldtype in (
                "Currency",
                "Float",
            )
        }

        monetary_fields.add("base")

        expressions = []

        for component_type in (
            "earnings",
            "deductions",
        ):
            for row in structure.get(component_type):
                if row.condition:
                    expressions.append(
                        row.condition
                    )

                if row.formula:
                    expressions.append(
                        row.formula
                    )

        expression_text = "\n".join(
            expressions
        )

        for fieldname in monetary_fields:
            if re.search(
                rf"\b{re.escape(fieldname)}\b",
                expression_text,
            ):
                fields.add(fieldname)

        return tuple(
            sorted(fields)
        )

    def apply_assignment_currency_conversion(
        self,
        data,
    ):
        """
        Convert monetary Salary Structure Assignment values to KZ
        when the assignment is denominated in USD.
        """
        self._ao_payroll_exchange = None
        self._ao_converted_assignment_fields = ()

        # Protect against accidental repeated conversion of
        # the same evaluation dictionary.
        if data.get("_ao_currency_converted"):
            return data

        moeda_usd = int(
            data.get("moeda_usd") or 0
        )

        if not moeda_usd:
            return data

        exchange = self.get_payroll_exchange_rate(
            from_currency="USD",
            to_currency="KZ",
        )

        exchange_rate = flt(
            exchange["rate"]
        )

        fields = self.get_assignment_currency_fields()

        converted_fields = []

        for fieldname in fields:
            if fieldname not in data:
                continue

            value = data.get(fieldname)

            if value is None:
                continue

            data[fieldname] = (
                flt(value)
                * exchange_rate
            )

            converted_fields.append(
                fieldname
            )

        self.base = flt(
            data.get("base")
        )

        data["payroll_exchange_rate"] = exchange_rate
        data["payroll_exchange_rate_date"] = exchange["date"]
        data["payroll_exchange_record"] = exchange["name"]
        data["_ao_currency_converted"] = 1

        self._ao_payroll_exchange = exchange
        self._ao_converted_assignment_fields = tuple(
            converted_fields
        )

        return data

    def get_data_for_eval(self):
        data, default_data = super().get_data_for_eval()

        # Salary Structure conditions/formulas expect date objects.
        # ERPNext may provide these as strings in the evaluation
        # dictionary, so normalize them before evaluation.
        if data.get("start_date"):
            data["start_date"] = getdate(
                data["start_date"]
            )

        if data.get("end_date"):
            data["end_date"] = getdate(
                data["end_date"]
            )

        if data.get("payroll_period_start_date"):
            data["payroll_period_start_date"] = getdate(
                data["payroll_period_start_date"]
            )

        if data.get("payroll_period_end_date"):
            data["payroll_period_end_date"] = getdate(
                data["payroll_period_end_date"]
            )

        data = self.apply_assignment_currency_conversion(
            data
        )

        data["numero_de_dependentes"] = flt(
            data.get("numero_de_dependentes", 0)
        )

        data["custom_base_abf"] = flt(
            data.get("custom_base_abf", 0)
        )

        data["custom_base_sa"] = flt(
            data.get("custom_base_sa", 0)
        )

        data["custom_base_st"] = flt(
            data.get("custom_base_st", 0)
        )

        data["custom_tem_isencao_de_horario"] = int(
            data.get(
                "custom_tem_isencao_de_horario",
                0,
            )
        )

        data["custom_base_iht"] = flt(
            data.get("custom_base_iht", 0)
        )

        data["variable"] = flt(
            data.get("variable", 0)
        )

        attendance_effects = calculator.get_employee_attendance_effects(
            employee=self.employee,
            payroll_start_date=self.start_date,
            payroll_end_date=self.end_date,
        )

        self._ao_attendance_effects = attendance_effects

        data["dias_falta_salario"] = flt(
            attendance_effects.get(
                "dias_falta_salario",
                0,
            )
        )

        data["dias_falta_alimentacao"] = flt(
            attendance_effects.get(
                "dias_falta_alimentacao",
                0,
            )
        )

        data["dias_falta_transporte"] = flt(
            attendance_effects.get(
                "dias_falta_transporte",
                0,
            )
        )

        data["dias_ferias"] = flt(
            attendance_effects.get(
                "dias_ferias",
                0,
            )
        )

        data["perde_premio_assiduidade"] = bool(
            attendance_effects.get(
                "perde_premio_assiduidade",
                False,
            )
        )

        data["atraso_horas"] = flt(
            attendance_effects.get(
                "atraso_horas",
                0,
            )
        )

        data["atraso_minutos"] = flt(
            attendance_effects.get(
                "atraso_minutos",
                0,
            )
        )

        data["payroll_reference_date"] = getdate(
            self.end_date
        )

        default_data.update(data)

        return data, default_data

    def get_ao_payroll_settings(self):
        if not getattr(self, "_ao_payroll_settings", None):
            self._ao_payroll_settings = frappe.get_single(
                "Angola Payroll Settings"
            )

        return self._ao_payroll_settings

    def apply_ao_statutory_allowances(self):
        """
        Calculate statutory Holiday and Christmas allowances.

        Rates and Salary Component mappings come from
        Angola Payroll Settings.

        The Salary Component itself remains authoritative for
        IRT and INSS incidence.
        """
        settings = self.get_ao_payroll_settings()

        holiday_component = (
            settings.holyday_allowance_salary_component
        )

        christmas_component = (
            settings.christmas_allowance_salary_component
        )

        holiday_rate = flt(
            settings.holiday_allowance_rate
        )

        christmas_rate = flt(
            settings.christmas_allowance_rate
        )

        # -------------------------------------------------
        # Holiday Allowance
        #
        # Deterministic company policy is authoritative.
        #
        # Automatic modes:
        # - Fixed Month
        # - Monthly Duodecimos
        # - Per Leave Block
        #
        # Employee Request is deliberately handled through
        # Additional Salary and returns zero here.
        # -------------------------------------------------

        holiday_amount = 0

        if holiday_component:
            holiday_result = (
                holiday_allowance
                .calculate_salary_slip_holiday_allowance(
                    employee=self.employee,
                    base_salary=self.base,
                    payroll_start_date=self.start_date,
                    payroll_end_date=self.end_date,
                )
            )

            holiday_amount = flt(
                holiday_result.get(
                    "amount",
                    0,
                )
            )

            # Termination processing may already have supplied the
            # proportional holiday allowance to this pending Salary
            # Slip through Additional Salary.
            #
            # The annual paid-balance helper intentionally counts only
            # submitted Salary Slips, so the current pending slip is not
            # represented there yet. Prevent the automatic allowance
            # path from paying the same entitlement twice.
            termination_holiday_amount = sum(
                flt(row.amount)
                for row in self.earnings
                if row.salary_component
                == "Proporcional Subsidio Ferias"
            )

            holiday_amount = max(
                0,
                holiday_amount
                - termination_holiday_amount,
            )

            if holiday_amount:
                self._ao_set_component(
                    "earnings",
                    holiday_component,
                    holiday_amount,
                )

            self._ao_holiday_allowance_result = (
                holiday_result
            )

        # -------------------------------------------------
        # Christmas Allowance
        #
        # Deterministic company payment policy.
        #
        # Automatic modes:
        # - Fixed Month
        # - Payment Blocks
        # - Monthly Duodecimos
        # -------------------------------------------------

        christmas_amount = 0

        if christmas_component:
            christmas_result = (
                christmas_allowance
                .calculate_salary_slip_christmas_allowance(
                    employee=self.employee,
                    base_salary=self.base,
                    payroll_start_date=self.start_date,
                    payroll_end_date=self.end_date,
                )
            )

            christmas_amount = flt(
                christmas_result.get(
                    "amount",
                    0,
                )
            )

            # Same protection for the proportional Christmas
            # settlement generated by Cessacao Contrato.
            termination_christmas_amount = sum(
                flt(row.amount)
                for row in self.earnings
                if row.salary_component
                == "Proporcional Subsidio Natal"
            )

            christmas_amount = max(
                0,
                christmas_amount
                - termination_christmas_amount,
            )

            if christmas_amount:
                self._ao_set_component(
                    "earnings",
                    christmas_component,
                    christmas_amount,
                )

            self._ao_christmas_allowance_result = (
                christmas_result
            )

        self._ao_allowances_result = {
            "holiday_component": holiday_component,
            "holiday_rate": holiday_rate,
            "holiday_amount": flt(
                holiday_amount
            ),
            "christmas_component": christmas_component,
            "christmas_rate": christmas_rate,
            "christmas_amount": flt(
                christmas_amount
            ),
        }

    def calculate_ao_inss(self):
        inss_base = 0

        for earning in self.earnings:
            if not earning.salary_component:
                continue

            incidencia_inss = frappe.db.get_value(
                "Salary Component",
                earning.salary_component,
                "incidencia_inss",
            )

            if incidencia_inss:
                inss_base += flt(
                    earning.amount
                )

        employee_rate = calculator.get_inss_employee_rate()

        inss = round(
            inss_base * employee_rate
        )

        return {
            "base_inss": flt(inss_base),
            "inss_rate": flt(
                employee_rate * 100
            ),
            "inss": flt(inss),
        }

    def calculate_ao_irt(self, ao_inss):
        base_irt = 0
        total_deductible_subsidies = 0
        abono_familia = 0

        for earning in self.earnings:
            if not earning.salary_component:
                continue

            amount = flt(
                earning.amount
            )

            incidencia_irt = frappe.db.get_value(
                "Salary Component",
                earning.salary_component,
                "incidencia_irt",
            )

            if incidencia_irt:
                base_irt += amount

            if (
                earning.salary_component
                == "Abono de Familia"
            ):
                abono_familia += amount

            custom_subsidio_dedutivel = (
                frappe.db.get_value(
                    "Salary Component",
                    earning.salary_component,
                    "custom_subsidio_dedutivel",
                )
            )

            if custom_subsidio_dedutivel:
                total_deductible_subsidies += amount

        payroll_year = getdate(
            self.end_date
        ).year

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

        deductible_subsidies = max(
            total_deductible_subsidies
            - threshold,
            0,
        )

        base_irt = (
            base_irt
            - flt(ao_inss["inss"])
            - abono_familia
            - deductible_subsidies
        )

        base_irt = max(
            base_irt,
            0,
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

        irt = round(
            fixed_amount
            + marginal_tax
        )

        return {
            "base_irt": flt(
                base_irt
            ),
            "payroll_year": payroll_year,
            "irt_table": table_name,
            "irt_slab": slab.name,
            "from_amount": from_amount,
            "to_amount": to_amount,
            "fixed_amount": fixed_amount,
            "marginal_rate": marginal_rate,
            "taxable_excess": flt(
                taxable_excess
            ),
            "marginal_tax": flt(
                marginal_tax
            ),
            "total_deductible_subsidies": flt(
                total_deductible_subsidies
            ),
            "threshold": flt(
                threshold
            ),
            "deductible_subsidies": flt(
                deductible_subsidies
            ),
            "abono_familia": flt(
                abono_familia
            ),
            "inss": flt(
                ao_inss["inss"]
            ),
            "irt": flt(
                irt
            ),
        }

    def calculate_net_pay(
        self,
        skip_tax_breakup_computation=False,
    ):
        # Native earnings calculation
        if self.salary_structure:
            self.calculate_component_amounts(
                "earnings"
            )

        # End-of-contract payroll:
        # when Cessacao Contrato has supplied a proportional
        # salary through Additional Salary, the normal recurring
        # Salario Base must not also be paid.
        proportional_salary = frappe.db.exists(
            "Additional Salary",
            {
                "employee": self.employee,
                "salary_component": "Proporcional Salario",
                "payroll_date": [
                    "between",
                    [self.start_date, self.end_date],
                ],
                "docstatus": 1,
            },
        )

        if proportional_salary:
            self.set(
                "earnings",
                [
                    row
                    for row in self.earnings
                    if row.salary_component != "Salario Base"
                ],
            )

        # AO statutory earnings must be populated before
        # gross pay, INSS and IRT are calculated.
        self.apply_ao_statutory_allowances()

        self.gross_pay = self.get_component_totals(
            "earnings",
            depends_on_payment_days=1,
        )

        self.base_gross_pay = flt(
            flt(self.gross_pay)
            * flt(self.exchange_rate),
            self.precision(
                "base_gross_pay"
            ),
        )

        # Native/company deductions
        if self.salary_structure:
            self.calculate_component_amounts(
                "deductions"
            )

        # Remove AO statutory placeholders/native rows.
        settings = self.get_ao_payroll_settings()

        inss_component = settings.inss_salary_component
        irt_component = settings.irt_salary_component
        irt_base_component = settings.irt_base_salary_component
        gross_component = settings.gross_salary_component
        net_component = settings.net_salary_component

        required_components = {
            "INSS": inss_component,
            "IRT": irt_component,
            "IRT Base": irt_base_component,
            "Gross": gross_component,
            "Net": net_component,
        }

        missing = [
            label
            for label, component in required_components.items()
            if not component
        ]

        if missing:
            frappe.throw(
                "Angola Payroll Settings is missing "
                "Salary Component mapping for: "
                + ", ".join(missing)
            )

        self.set(
            "deductions",
            [
                row
                for row in self.deductions
                if row.salary_component not in (
                    inss_component,
                    irt_component,
                    irt_base_component,
                )
            ],
        )

        # AO statutory calculations
        ao_inss = self.calculate_ao_inss()

        ao_irt = self.calculate_ao_irt(
            ao_inss
        )

        # Salário Ilíquido
        self._ao_set_component(
            "earnings",
            gross_component,
            self.gross_pay,
        )

        # INSS
        self._ao_set_component(
            "deductions",
            inss_component,
            ao_inss["inss"],
        )

        # Ilíquido para IRT
        self._ao_set_component(
            "deductions",
            irt_base_component,
            ao_irt["base_irt"],
        )

        # IRT
        self._ao_set_component(
            "deductions",
            irt_component,
            ao_irt["irt"],
        )

        self.set_precision_for_component_amounts()

        # Native net pay arithmetic
        self.set_net_pay()

        # Normalize monetary totals to Salary Slip field precision.
        self.gross_pay = flt(
            self.gross_pay,
            self.precision("gross_pay"),
        )

        self.total_deduction = flt(
            self.total_deduction,
            self.precision("total_deduction"),
        )

        self.net_pay = flt(
            self.net_pay,
            self.precision("net_pay"),
        )

        self.base_gross_pay = flt(
            self.base_gross_pay,
            self.precision("base_gross_pay"),
        )

        self.base_net_pay = flt(
            self.base_net_pay,
            self.precision("base_net_pay"),
        )

        # Salário Líquido
        self._ao_set_component(
            "earnings",
            net_component,
            self.net_pay,
        )

        self._ao_inss_result = ao_inss
        self._ao_irt_result = ao_irt

        # AO Payroll is authoritative for IRT.
        # Do not call compute_income_tax_breakup().

    def _ao_set_component(
        self,
        component_type,
        salary_component,
        amount,
    ):
        amount = flt(
            amount
        )

        component_data = frappe.get_cached_doc(
            "Salary Component",
            salary_component,
        )

        # ---------------------------------------------------------
        # Find authoritative Salary Structure row.
        # ---------------------------------------------------------

        structure_row = None

        if self.salary_structure:
            structure = frappe.get_cached_doc(
                "Salary Structure",
                self.salary_structure,
            )

            for row in structure.get(
                component_type
            ):
                if (
                    row.salary_component
                    == salary_component
                ):
                    structure_row = row
                    break

        # ---------------------------------------------------------
        # Find existing Salary Slip row.
        # ---------------------------------------------------------

        target_row = None

        for row in self.get(
            component_type
        ):
            if (
                row.salary_component
                == salary_component
            ):
                target_row = row
                break

        # ---------------------------------------------------------
        # Create row if it does not yet exist.
        # ---------------------------------------------------------

        if not target_row:
            target_row = self.append(
                component_type,
                {
                    "salary_component":
                        salary_component,

                    "abbr":
                        component_data.salary_component_abbr,
                },
            )

        # ---------------------------------------------------------
        # Explicit calculated values.
        # ---------------------------------------------------------

        target_row.set(
            "salary_component",
            salary_component,
        )

        target_row.set(
            "abbr",
            component_data.salary_component_abbr,
        )

        target_row.set(
            "amount",
            amount,
        )

        target_row.set(
            "default_amount",
            amount,
        )

        # ---------------------------------------------------------
        # Preserve native Salary Detail metadata from structure.
        #
        # This is critical for statistical components such as IIRT,
        # SI and SL. ERPNext get_component_totals() reads
        # do_not_include_in_total directly from the Salary Detail.
        # ---------------------------------------------------------

        if structure_row:
            target_row.set(
                "statistical_component",
                structure_row.statistical_component,
            )

            target_row.set(
                "depends_on_payment_days",
                structure_row.depends_on_payment_days,
            )

            target_row.set(
                "exempted_from_income_tax",
                structure_row.exempted_from_income_tax,
            )

            target_row.set(
                "is_tax_applicable",
                structure_row.is_tax_applicable,
            )

            target_row.set(
                "is_flexible_benefit",
                structure_row.is_flexible_benefit,
            )

            target_row.set(
                "variable_based_on_taxable_salary",
                structure_row.variable_based_on_taxable_salary,
            )

            target_row.set(
                "do_not_include_in_total",
                structure_row.do_not_include_in_total,
            )

            target_row.set(
                "do_not_include_in_accounts",
                structure_row.do_not_include_in_accounts,
            )

            target_row.set(
                "deduct_full_tax_on_selected_payroll_date",
                structure_row.deduct_full_tax_on_selected_payroll_date,
            )
