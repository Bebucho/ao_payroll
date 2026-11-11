# Copyright (c) 2026, AngolaERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from ao_payroll.payroll import calculator
from frappe.utils import add_days, flt, get_first_day, get_last_day, getdate


class CessacaoContrato(Document):
    def validate(self):
        self.validate_employee_exit_data()
        self.validate_salary_structure_assignment()

    def before_submit(self):
        self.validate_employee_exit_data()
        self.validate_salary_structure_assignment()

        if self.custom_calculo_alterado:
            if not self.custom_motivo_alteracao:
                frappe.throw(
                    _("É obrigatório indicar o Motivo da Alteração.")
                )

            user = frappe.session.user
            roles = frappe.get_roles(user)

            if (
                "Payroll Override Approver" not in roles
                and "System Manager" not in roles
            ):
                frappe.throw(
                    _(
                        "O utilizador {0} não tem autorização para "
                        "submeter uma cessação com cálculo alterado."
                    ).format(user)
                )

            self.custom_alterado_por = user
            self.custom_data = frappe.utils.now_datetime()

            # Preserve approved manual settlement values, but
            # recompute statutory bases, deductions and totals.
            self.calcular()

            if not self.custom_calculado:
                frappe.throw(
                    _(
                        "Não é possível submeter a cessação do contrato "
                        "sem executar primeiro o cálculo."
                    )
                )

            return

        # Normal path: always recalculate immediately before Submit
        # so no stale values can be submitted.
        self.calcular()

        if not self.custom_calculado:
            frappe.throw(
                _(
                    "Não é possível submeter a cessação do contrato "
                    "sem executar primeiro o cálculo."
                )
            )

    def validate_employee_exit_data(self):
        if not self.funcionario:
            frappe.throw(_("Seleccione o Funcionário."))

        employee = frappe.get_doc("Employee", self.funcionario)

        missing = []

        if not employee.relieving_date:
            missing.append("Data de Saída")

        if not employee.custom_motivo_de_saida:
            missing.append("Motivo de Saída")

        if not employee.aviso_previo:
            missing.append("Aviso Prévio")

        if not employee.hora_semanal:
            missing.append("Hora Semanal")

        if missing:
            frappe.throw(
                _(
                    "Não é possível processar a cessação do contrato.<br><br>"
                    "Complete primeiro no cadastro do Funcionário:<br>- {0}"
                ).format("<br>- ".join(missing))
            )

        self.nome_funcionario = employee.employee_name
        self.data_saida = employee.relieving_date
        self.motivo_cessacao_contrato = employee.custom_motivo_de_saida
        self.aviso_previo = employee.aviso_previo
        self.custom_hora_semanal = employee.hora_semanal

    def validate_salary_structure_assignment(self):
        assignment = frappe.get_all(
            "Salary Structure Assignment",
            filters={
                "employee": self.funcionario,
                "docstatus": 1,
                "from_date": ["<=", getdate(self.data_saida)],
            },
            fields=[
                "name",
                "salary_structure",
                "from_date",
                "base",
                "currency",
            ],
            order_by="from_date desc, creation desc",
            limit=1,
        )

        if not assignment:
            frappe.throw(
                _(
                    "Não existe Salary Structure Assignment válido para "
                    "o funcionário {0} na Data de Saída {1}."
                ).format(
                    self.funcionario,
                    self.data_saida,
                )
            )

        self._termination_salary_assignment = assignment[0]

    def on_submit(self):
        # The settlement itself is already validated/recalculated
        # in before_submit(). Now hand the approved components to
        # ERPNext payroll.
        self.create_additional_salary_records()

    def on_cancel(self):
        self.cancel_additional_salary_records()

    def create_additional_salary_records(self):
        employee = frappe.get_doc(
            "Employee",
            self.funcionario,
        )

        assignment = frappe.get_doc(
            "Salary Structure Assignment",
            self._termination_salary_assignment.name,
        )

        additional_salary_meta = frappe.get_meta(
            "Additional Salary"
        )

        components = [
            (
                "Proporcional Salario",
                flt(self.salario_proporcional),
            ),
            (
                "Proporcional Subsidio Ferias",
                flt(self.subsidio_de_ferias_proporcional),
            ),
            (
                "Proporcional Subsidio Natal",
                flt(self.subsidio_natal_proporcional),
            ),
            (
                "Ferias não Gozadas",
                flt(self.valor_ferias_nao_gozadas),
            ),
        ]

        # HR-approved additional earnings and deductions.
        for row in self.table_yexo or []:
            if not row.componente_salarial:
                continue

            components.append(
                (
                    row.componente_salarial,
                    flt(row.valor),
                )
            )

        created = []

        for salary_component, amount in components:
            if not salary_component or amount <= 0:
                continue

            component = frappe.get_doc(
                "Salary Component",
                salary_component,
            )

            if component.type not in (
                "Earning",
                "Deduction",
            ):
                frappe.throw(
                    _(
                        "O Componente Salarial {0} não é "
                        "Earning nem Deduction."
                    ).format(salary_component)
                )

            values = {
                "doctype": "Additional Salary",
                "employee": self.funcionario,
                "salary_component": salary_component,
                "amount": amount,
                "payroll_date": self.data_saida,
                "company": (
                    assignment.company
                    or employee.company
                ),
            }

            # Keep native ERPNext fields optional so this remains
            # compatible with the installed HRMS v15 schema.
            if additional_salary_meta.has_field(
                "overwrite_salary_structure_amount"
            ):
                values[
                    "overwrite_salary_structure_amount"
                ] = 0

            if additional_salary_meta.has_field("currency"):
                values["currency"] = (
                    assignment.currency
                    or frappe.db.get_value(
                        "Company",
                        employee.company,
                        "default_currency",
                    )
                )

            if additional_salary_meta.has_field(
                "ref_doctype"
            ):
                values["ref_doctype"] = (
                    "Cessacao Contrato"
                )

            if additional_salary_meta.has_field(
                "ref_docname"
            ):
                values["ref_docname"] = self.name

            if additional_salary_meta.has_field(
                "remarks"
            ):
                values["remarks"] = (
                    f"Cessacao Contrato: {self.name}"
                )

            doc = frappe.get_doc(values)

            doc.insert(
                ignore_permissions=True
            )
            doc.submit()

            created.append(doc.name)

        if not created:
            frappe.throw(
                _(
                    "A cessação não possui valores para "
                    "transferir para o payroll."
                )
            )

        frappe.msgprint(
            _(
                "{0} registo(s) de Additional Salary "
                "criado(s) para o payroll de {1}."
            ).format(
                len(created),
                self.data_saida,
            )
        )

    def cancel_additional_salary_records(self):
        meta = frappe.get_meta(
            "Additional Salary"
        )

        filters = {
            "employee": self.funcionario,
            "payroll_date": self.data_saida,
            "docstatus": 1,
        }

        if (
            meta.has_field("ref_doctype")
            and meta.has_field("ref_docname")
        ):
            filters.update(
                {
                    "ref_doctype":
                        "Cessacao Contrato",
                    "ref_docname":
                        self.name,
                }
            )

        elif meta.has_field("remarks"):
            filters["remarks"] = (
                f"Cessacao Contrato: {self.name}"
            )

        else:
            # Do not risk cancelling unrelated Additional Salary
            # records when the installed schema has no reference
            # mechanism.
            frappe.throw(
                _(
                    "Não é possível identificar com segurança "
                    "os Additional Salary ligados a esta cessação."
                )
            )

        names = frappe.get_all(
            "Additional Salary",
            filters=filters,
            pluck="name",
        )

        for name in names:
            additional_salary = frappe.get_doc(
                "Additional Salary",
                name,
            )

            additional_salary.cancel()

    @frappe.whitelist()
    def calcular(self):
        self.validate_employee_exit_data()
        self.validate_salary_structure_assignment()

        employee = frappe.get_doc(
            "Employee",
            self.funcionario,
        )

        assignment = frappe.get_doc(
            "Salary Structure Assignment",
            self._termination_salary_assignment.name,
        )

        base = flt(assignment.base)
        weekly_hours = flt(employee.hora_semanal)

        if base <= 0:
            frappe.throw(
                _("O Salary Structure Assignment não possui salário base válido.")
            )

        if weekly_hours <= 0:
            frappe.throw(
                _("O funcionário não possui Hora Semanal válida.")
            )

        self.custom_hora_semanal = weekly_hours

        # Legal hourly basis.
        hourly_rate = (base * 12) / (52 * weekly_hours)

        # Do not silently calculate foreign-currency salaries as KZ.
        if getattr(assignment, "moeda_usd", 0):
            frappe.throw(
                _(
                    "A remuneração deste funcionário está definida em USD. "
                    "A conversão cambial da cessação deve ser aplicada antes "
                    "do cálculo."
                )
            )

        exit_date = getdate(self.data_saida)

        # Audit/context values used by the return payload.
        # In override mode the automatic objective calculation
        # is intentionally skipped, so these need safe defaults.
        holiday_list = None
        working_days_month = 0
        working_days_until_exit = 0
        complete_months = 0
        annual_factor = 0

        if not self.custom_calculo_alterado:
            # -------------------------------------------------
            # SALÁRIO PROPORCIONAL
            # -------------------------------------------------

            month_start = getdate(get_first_day(exit_date))
            month_end = getdate(get_last_day(exit_date))

            calculation_start = month_start

            if employee.date_of_joining:
                joining_date = getdate(employee.date_of_joining)

                if joining_date > exit_date:
                    frappe.throw(
                        _("A Data de Entrada é posterior à Data de Saída.")
                    )

                if joining_date > month_start:
                    calculation_start = joining_date

            holiday_list = (
                employee.holiday_list
                or frappe.db.get_value(
                    "Company",
                    employee.company,
                    "default_holiday_list",
                )
            )

            if not holiday_list:
                frappe.throw(
                    _(
                        "Não existe Holiday List definida para o funcionário "
                        "nem para a empresa."
                    )
                )

            working_days_month = self._count_working_days(
                month_start,
                month_end,
                holiday_list,
            )

            working_days_until_exit = self._count_working_days(
                calculation_start,
                exit_date,
                holiday_list,
            )

            if working_days_month <= 0:
                frappe.throw(
                    _("O mês da cessação não possui dias de trabalho calculáveis.")
                )

            self.salario_proporcional = round(
                base * working_days_until_exit / working_days_month,
                2,
            )

            # -------------------------------------------------
            # SUBSÍDIO DE FÉRIAS / NATAL PROPORCIONAIS
            #
            # Proporção baseada em meses completos trabalhados
            # no ano da cessação.
            # -------------------------------------------------

            settings = calculator.get_payroll_settings(
                company=employee.company,
                reference_date=exit_date,
            )
            holiday_rate = flt(settings.holiday_allowance_rate)
            christmas_rate = flt(settings.christmas_allowance_rate)

            joining_date = (
                getdate(employee.date_of_joining)
                if employee.date_of_joining
                else getdate(f"{exit_date.year}-01-01")
            )

            complete_months = 0

            for month in range(1, 13):
                month_first = getdate(
                    f"{exit_date.year}-{month:02d}-01"
                )
                month_last = getdate(
                    get_last_day(month_first)
                )

                # Count only months in which the employee
                # was employed from the first through the
                # last day of that month.
                if (
                    joining_date <= month_first
                    and exit_date >= month_last
                ):
                    complete_months += 1

            annual_factor = complete_months / 12

            holiday_entitlement_to_exit = round(
                base
                * (holiday_rate / 100)
                * annual_factor,
                2,
            )

            christmas_entitlement_to_exit = round(
                base
                * (christmas_rate / 100)
                * annual_factor,
                2,
            )

            # Amounts already paid through submitted Salary Slips
            # in the termination year must reduce the settlement.
            #
            # The calculator helpers include both the normal allowance
            # component and the proportional termination component.
            holiday_paid = flt(
                calculator.get_holiday_allowance_paid(
                    self.funcionario,
                    exit_date.year,
                )
            )

            christmas_paid = flt(
                calculator.get_christmas_allowance_paid(
                    self.funcionario,
                    exit_date.year,
                )
            )

            self.subsidio_de_ferias_proporcional = round(
                max(
                    0,
                    holiday_entitlement_to_exit
                    - holiday_paid,
                ),
                2,
            )

            self.subsidio_natal_proporcional = round(
                max(
                    0,
                    christmas_entitlement_to_exit
                    - christmas_paid,
                ),
                2,
            )

            # -------------------------------------------------
            # FÉRIAS NÃO GOZADAS
            # HR defines the quantity; payroll values it.
            # -------------------------------------------------

            leave_days = flt(self.dias_ferias_nao_gozadas)

            if leave_days < 0:
                frappe.throw(
                    _("Dias de Férias Não Gozadas não pode ser negativo.")
                )

            leave_amount_per_day = flt(
                getattr(
                    assignment,
                    "leave_encashment_amount_per_day",
                    0,
                )
            )

            if leave_days and leave_amount_per_day <= 0:
                frappe.throw(
                    _(
                        "Foram indicados Dias de Férias Não Gozadas, mas "
                        "o Salary Structure Assignment não possui "
                        "Leave Encashment Amount Per Day."
                    )
                )

            self.valor_ferias_nao_gozadas = round(
                leave_days * leave_amount_per_day,
                2,
            )


        else:
            # Override mode:
            # preserve manually entered settlement values.
            # Statutory bases, taxes and totals are recalculated below.
            self.salario_proporcional = flt(
                self.salario_proporcional
            )
            self.subsidio_de_ferias_proporcional = flt(
                self.subsidio_de_ferias_proporcional
            )
            self.subsidio_natal_proporcional = flt(
                self.subsidio_natal_proporcional
            )
            self.valor_ferias_nao_gozadas = flt(
                self.valor_ferias_nao_gozadas
            )

        # -------------------------------------------------
        # COMPONENTES ADICIONAIS DEFINIDOS PELO RH
        # -------------------------------------------------

        additional_earnings = 0
        additional_deductions = 0

        for row in self.table_yexo or []:
            if not row.componente_salarial:
                frappe.throw(
                    _(
                        "Existe uma linha em Componentes Adicionais "
                        "sem Componente Salarial."
                    )
                )

            amount = flt(row.valor)

            if amount < 0:
                frappe.throw(
                    _(
                        "O valor do componente {0} não pode ser negativo."
                    ).format(row.componente_salarial)
                )

            component_type = frappe.db.get_value(
                "Salary Component",
                row.componente_salarial,
                "type",
            )

            if not component_type:
                frappe.throw(
                    _(
                        "Componente Salarial {0} não encontrado."
                    ).format(row.componente_salarial)
                )

            if component_type == "Earning":
                additional_earnings += amount

            elif component_type == "Deduction":
                additional_deductions += amount

            else:
                frappe.throw(
                    _(
                        "O componente {0} possui tipo inválido: {1}."
                    ).format(
                        row.componente_salarial,
                        component_type,
                    )
                )

        objective_earnings = (
            flt(self.salario_proporcional)
            + flt(self.subsidio_de_ferias_proporcional)
            + flt(self.subsidio_natal_proporcional)
            + flt(self.valor_ferias_nao_gozadas)
        )

        self.total_iliquido = round(
            objective_earnings + additional_earnings,
            2,
        )

        # -------------------------------------------------
        # STATUTORY INCIDENCE
        #
        # The termination document decides amounts.
        # Salary Component configuration decides incidence.
        # -------------------------------------------------

        statutory_earnings = [
            {
                "salary_component": "Proporcional Salario",
                "amount": flt(self.salario_proporcional),
            },
            {
                "salary_component": "Proporcional Subsidio Ferias",
                "amount": flt(
                    self.subsidio_de_ferias_proporcional
                ),
            },
            {
                "salary_component": "Proporcional Subsidio Natal",
                "amount": flt(
                    self.subsidio_natal_proporcional
                ),
            },
            {
                "salary_component": "Ferias não Gozadas",
                "amount": flt(
                    self.valor_ferias_nao_gozadas
                ),
            },
        ]

        # HR-selected earning components participate in
        # statutory incidence according to Salary Component.
        for row in self.table_yexo or []:
            if not row.componente_salarial:
                continue

            component_type = frappe.db.get_value(
                "Salary Component",
                row.componente_salarial,
                "type",
            )

            if component_type == "Earning":
                statutory_earnings.append(
                    {
                        "salary_component":
                            row.componente_salarial,
                        "amount": flt(row.valor),
                    }
                )

        # -------------------------------------------------
        # INSS
        # -------------------------------------------------

        inss_base = 0

        for earning in statutory_earnings:
            component = earning["salary_component"]
            amount = flt(earning["amount"])

            incidencia_inss = frappe.db.get_value(
                "Salary Component",
                component,
                "incidencia_inss",
            )

            if incidencia_inss:
                inss_base += amount

        inss_rate = calculator.get_inss_employee_rate(
            company=employee.company,
            reference_date=exit_date,
        )

        inss_amount = round(
            inss_base * inss_rate
        )

        self.base_inss = round(
            inss_base,
            2,
        )

        self.inss = flt(
            inss_amount
        )

        # -------------------------------------------------
        # IRT BASE
        #
        # Same incidence model used by Salary Slip:
        # taxable earnings
        # - INSS
        # - Abono de Familia
        # - deductible subsidies above configured threshold
        # -------------------------------------------------

        irt_incidence_base = 0
        deductible_subsidies = 0
        abono_familia = 0

        for earning in statutory_earnings:
            component = earning["salary_component"]
            amount = flt(earning["amount"])

            incidencia_irt = frappe.db.get_value(
                "Salary Component",
                component,
                "incidencia_irt",
            )

            if incidencia_irt:
                irt_incidence_base += amount

            if component == "Abono de Familia":
                abono_familia += amount

            is_deductible_subsidy = frappe.db.get_value(
                "Salary Component",
                component,
                "custom_subsidio_dedutivel",
            )

            if is_deductible_subsidy:
                deductible_subsidies += amount

        payroll_year = getdate(
            self.data_saida
        ).year

        irt_table = frappe.db.get_value(
            "IRT Tables",
            {
                "year": payroll_year,
                "active": 1,
            },
            "name",
            order_by="modified desc",
        )

        if not irt_table:
            frappe.throw(
                _(
                    "Não existe tabela IRT activa para o ano {0}."
                ).format(payroll_year)
            )

        subsidy_threshold = flt(
            frappe.db.get_value(
                "IRT Tables",
                irt_table,
                "custom_subsidy_treshold",
            )
        )

        deductible_excess = max(
            deductible_subsidies - subsidy_threshold,
            0,
        )

        irt_base = (
            irt_incidence_base
            - flt(self.inss)
            - abono_familia
            - deductible_excess
        )

        irt_base = max(
            irt_base,
            0,
        )

        self.base_irt = round(
            irt_base,
            2,
        )

        irt_result = calculator.calculate_irt(
            self.base_irt,
            payroll_year,
        )

        self.irt = flt(
            irt_result.get("irt", 0)
        )

        # -------------------------------------------------
        # FINAL DEDUCTIONS / NET
        # -------------------------------------------------

        self.total_descontos = round(
            additional_deductions
            + flt(self.inss)
            + flt(self.irt),
            2,
        )

        self.valor_liquido = round(
            self.total_iliquido
            - self.total_descontos,
            2,
        )

        self.custom_calculado = 1

        return {
            "base": base,
            "hora_semanal": weekly_hours,
            "valor_hora": round(hourly_rate, 6),
            "holiday_list": holiday_list,
            "dias_trabalho_mes": working_days_month,
            "dias_trabalho_ate_saida": working_days_until_exit,
            "meses_completos": complete_months,
            "factor_anual": annual_factor,
            "salario_proporcional": self.salario_proporcional,
            "subsidio_ferias_proporcional":
                self.subsidio_de_ferias_proporcional,
            "subsidio_natal_proporcional":
                self.subsidio_natal_proporcional,
            "dias_ferias_nao_gozadas":
                self.dias_ferias_nao_gozadas,
            "valor_ferias_nao_gozadas":
                self.valor_ferias_nao_gozadas,
            "componentes_adicionais_earnings":
                round(additional_earnings, 2),
            "componentes_adicionais_deductions":
                round(additional_deductions, 2),
            "total_iliquido":
                self.total_iliquido,
            "base_inss":
                self.base_inss,
            "inss":
                self.inss,
            "base_irt":
                self.base_irt,
            "irt":
                self.irt,
            "total_descontos":
                self.total_descontos,
            "valor_liquido":
                self.valor_liquido,
            "calculado":
                self.custom_calculado,
        }

    def _count_working_days(self, start_date, end_date, holiday_list):
        start_date = getdate(start_date)
        end_date = getdate(end_date)

        if end_date < start_date:
            return 0

        holiday_rows = frappe.get_all(
            "Holiday",
            filters={
                "parent": holiday_list,
                "holiday_date": [
                    "between",
                    [start_date, end_date],
                ],
            },
            fields=["holiday_date"],
        )

        holidays = {
            getdate(row.holiday_date)
            for row in holiday_rows
        }

        total = 0
        current_date = start_date

        while current_date <= end_date:
            # AngolaERP standard schedule:
            # Monday-Friday = normal working days
            # Saturday = complementary weekly rest
            # Sunday = weekly rest
            is_weekday = current_date.weekday() < 5

            if is_weekday and current_date not in holidays:
                total += 1

            current_date = getdate(
                add_days(current_date, 1)
            )

        return total
