import unittest
import frappe

from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from ao_payroll.payroll import calculator
from ao_payroll.payroll.settings import get_payroll_settings
from ao_payroll.tasks import process_employee_cessations
from unittest.mock import patch, MagicMock


from frappe.exceptions import ValidationError
from frappe.utils import getdate
from ao_payroll.hr.employee_contract import validate_employee_contract
from ao_payroll.angola_payroll.report.employment_contract_exceptions import (
    employment_contract_exceptions,
)

class TestPayrollRegression2026(FrappeTestCase):

    TERMINATION = "Vanessa Da Nazaré Monteiro Das Neves Dias-1"
    EMPLOYEE = "HE-EMP/006"

    # ---------------------------------------------------------
    # REG-010 — HOLIDAY ALLOWANCE RATE
    # ---------------------------------------------------------

    def test_reg_010_holiday_allowance_rate(self):
        settings = get_payroll_settings(
            employee=self.EMPLOYEE,
            year=2026,
        )

        self.assertAlmostEqual(
            flt(settings.holiday_allowance_rate),
            50.00,
            places=2,
            msg=(
                "Holiday allowance statutory/configuration "
                "rate changed."
            ),
        )

        base_salary = 1000000.00

        expected_allowance = (
            base_salary
            * flt(settings.holiday_allowance_rate)
            / 100
        )

        self.assertAlmostEqual(
            expected_allowance,
            500000.00,
            places=2,
        )


    # ---------------------------------------------------------
    # REG-011 — CHRISTMAS ALLOWANCE RATE
    # ---------------------------------------------------------

    def test_reg_011_christmas_allowance_rate(self):
        settings = get_payroll_settings(
            employee=self.EMPLOYEE,
            year=2026,
        )

        self.assertAlmostEqual(
            flt(settings.christmas_allowance_rate),
            50.00,
            places=2,
            msg=(
                "Christmas allowance statutory/configuration "
                "rate changed."
            ),
        )

        base_salary = 1000000.00

        expected_allowance = (
            base_salary
            * flt(settings.christmas_allowance_rate)
            / 100
        )

        self.assertAlmostEqual(
            expected_allowance,
            500000.00,
            places=2,
        )


    # ---------------------------------------------------------
    # REG-012 — HOLIDAY ALLOWANCE INCIDENCE
    # ---------------------------------------------------------

    def test_reg_012_holiday_allowance_incidence(self):
        component = frappe.db.get_value(
            "Salary Component",
            "Subsidio de Ferias",
            [
                "type",
                "incidencia_inss",
                "incidencia_irt",
                "custom_subsidio_dedutivel",
            ],
            as_dict=True,
        )

        self.assertTrue(component)

        self.assertEqual(
            component.type,
            "Earning",
        )

        self.assertEqual(
            component.incidencia_inss,
            0,
        )

        self.assertEqual(
            component.incidencia_irt,
            1,
        )

        self.assertEqual(
            component.custom_subsidio_dedutivel,
            0,
        )


    # ---------------------------------------------------------
    # REG-013 — CHRISTMAS ALLOWANCE INCIDENCE
    # ---------------------------------------------------------

    def test_reg_013_christmas_allowance_incidence(self):
        component = frappe.db.get_value(
            "Salary Component",
            "Subsidio de Natal",
            [
                "type",
                "incidencia_inss",
                "incidencia_irt",
                "custom_subsidio_dedutivel",
            ],
            as_dict=True,
        )

        self.assertTrue(component)

        self.assertEqual(
            component.type,
            "Earning",
        )

        self.assertEqual(
            component.incidencia_inss,
            1,
        )

        self.assertEqual(
            component.incidencia_irt,
            1,
        )

        self.assertEqual(
            component.custom_subsidio_dedutivel,
            0,
        )


    # ---------------------------------------------------------
    # REG-007 — TIPO DE FALTA / INJUSTIFICADA
    # ---------------------------------------------------------

    def test_reg_007_tipo_falta_injustificada(self):
        treatment = frappe.db.get_value(
            "Tipo de Falta",
            "Falta Injustificada",
            [
                "activo",
                "deduz_salario",
                "deduz_subsidio_alimentacao",
                "deduz_subsidio_transporte",
                "afeta_premio_assiduidade",
            ],
            as_dict=True,
        )

        self.assertTrue(treatment)
        self.assertEqual(treatment.activo, 1)
        self.assertEqual(treatment.deduz_salario, 1)
        self.assertEqual(
            treatment.deduz_subsidio_alimentacao,
            1,
        )
        self.assertEqual(
            treatment.deduz_subsidio_transporte,
            1,
        )
        self.assertEqual(
            treatment.afeta_premio_assiduidade,
            1,
        )


    # ---------------------------------------------------------
    # REG-008 — JUSTIFIED PAID ABSENCE
    # ---------------------------------------------------------

    def test_reg_008_tipo_falta_justificada_com_salario(self):
        treatment = frappe.db.get_value(
            "Tipo de Falta",
            "Falta Justificada C/Salario",
            [
                "activo",
                "deduz_salario",
                "deduz_subsidio_alimentacao",
                "deduz_subsidio_transporte",
                "afeta_premio_assiduidade",
            ],
            as_dict=True,
        )

        self.assertTrue(treatment)
        self.assertEqual(treatment.activo, 1)

        # Paid justified absence must not reduce salary.
        self.assertEqual(
            treatment.deduz_salario,
            0,
        )

        # But employee was not present, so daily subsidies
        # remain affected.
        self.assertEqual(
            treatment.deduz_subsidio_alimentacao,
            1,
        )

        self.assertEqual(
            treatment.deduz_subsidio_transporte,
            1,
        )

        self.assertEqual(
            treatment.afeta_premio_assiduidade,
            1,
        )


    # ---------------------------------------------------------
    # REG-009 — ATTENDANCE BONUS EXCEPTION
    # ---------------------------------------------------------

    def test_reg_009_tipo_falta_dia_pai(self):
        treatment = frappe.db.get_value(
            "Tipo de Falta",
            "Dia do Pai - Nascimento de Filho",
            [
                "activo",
                "deduz_salario",
                "deduz_subsidio_alimentacao",
                "deduz_subsidio_transporte",
                "afeta_premio_assiduidade",
            ],
            as_dict=True,
        )

        self.assertTrue(treatment)
        self.assertEqual(treatment.activo, 1)

        self.assertEqual(
            treatment.deduz_salario,
            0,
        )

        self.assertEqual(
            treatment.deduz_subsidio_alimentacao,
            1,
        )

        self.assertEqual(
            treatment.deduz_subsidio_transporte,
            1,
        )

        # This is the distinguishing control:
        # paternal birth leave must not remove
        # the attendance bonus.
        self.assertEqual(
            treatment.afeta_premio_assiduidade,
            0,
        )


    # ---------------------------------------------------------
    # REG-004 — SALARY ABSENCE DEDUCTION
    # ---------------------------------------------------------

    def test_reg_004_salary_absence_deduction(self):
        """
        One salary-deductible absence day.

        Base salary: 1,000,000
        Working days: 20

        Expected deduction:
        1,000,000 / 20 = 50,000
        """

        result = calculator.calculate_gross_salary(
            employee="REG-TEST-EMPLOYEE",
            payroll_start_date="2099-01-01",
            payroll_end_date="2099-01-31",
            salario_base=1000000,
            subsidio_alimentacao=30000,
            subsidio_transporte=30000,
            dias_uteis=20,
            absence_effects={
                "salary_deduction_days": 1,
                "meal_deduction_days": 0,
                "transport_deduction_days": 0,
                "attendance_bonus_affected": False,
            },
        )

        self.assertAlmostEqual(
            flt(result["deducao_salario"]),
            50000.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["salary_deduction_days"]),
            1.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["salario_iliquido"]),
            1010000.00,
            places=2,
        )


    # ---------------------------------------------------------
    # REG-005 — MEAL / TRANSPORT ABSENCE
    # ---------------------------------------------------------

    def test_reg_005_meal_transport_absence_deduction(self):
        """
        Two absence days affect meal and transport allowances.

        Monthly allowance: 30,000
        Working days: 20
        Daily allowance: 1,500

        Two days = 3,000 deduction.
        Allowance paid = 27,000.
        """

        result = calculator.calculate_gross_salary(
            employee="REG-TEST-EMPLOYEE",
            payroll_start_date="2099-02-01",
            payroll_end_date="2099-02-28",
            salario_base=1000000,
            subsidio_alimentacao=30000,
            subsidio_transporte=30000,
            dias_uteis=20,
            absence_effects={
                "salary_deduction_days": 0,
                "meal_deduction_days": 2,
                "transport_deduction_days": 2,
                "attendance_bonus_affected": False,
            },
        )

        self.assertAlmostEqual(
            flt(result["deducao_alimentacao"]),
            3000.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["deducao_transporte"]),
            3000.00,
            places=2,
        )

        earnings = {
            row["salary_component"]: flt(row["amount"])
            for row in result["earnings"]
        }

        self.assertAlmostEqual(
            earnings["Subsidio de Alimentacao"],
            27000.00,
            places=2,
        )

        self.assertAlmostEqual(
            earnings["Subsidio de Transporte"],
            27000.00,
            places=2,
        )


    # ---------------------------------------------------------
    # REG-006 — MIXED ABSENCE EFFECTS
    # ---------------------------------------------------------

    def test_reg_006_mixed_absence_effects(self):
        """
        Regression for the rule-matrix principle:

        One day affects salary.
        Two days affect meal.
        Two days affect transport.

        Different payroll effects must remain independent.
        """

        result = calculator.calculate_gross_salary(
            employee="REG-TEST-EMPLOYEE",
            payroll_start_date="2099-03-01",
            payroll_end_date="2099-03-31",
            salario_base=1000000,
            subsidio_alimentacao=30000,
            subsidio_transporte=30000,
            dias_uteis=20,
            absence_effects={
                "salary_deduction_days": 1,
                "meal_deduction_days": 2,
                "transport_deduction_days": 2,
                "attendance_bonus_affected": False,
            },
        )

        self.assertAlmostEqual(
            flt(result["salary_deduction_days"]),
            1.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["meal_deduction_days"]),
            2.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["transport_deduction_days"]),
            2.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["deducao_salario"]),
            50000.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["deducao_alimentacao"]),
            3000.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["deducao_transporte"]),
            3000.00,
            places=2,
        )

        absence_deductions = {
            row["salary_component"]: flt(row["amount"])
            for row in result["absence_deductions"]
        }

        self.assertAlmostEqual(
            absence_deductions["Falta - Salario"],
            50000.00,
            places=2,
        )

        self.assertAlmostEqual(
            absence_deductions[
                "Falta - Subsidio Alimentacao"
            ],
            3000.00,
            places=2,
        )

        self.assertAlmostEqual(
            absence_deductions[
                "Falta - Subsidio Transporte"
            ],
            3000.00,
            places=2,
        )


    # ---------------------------------------------------------
    # REG-001 — NORMAL MONTHLY SALARY
    # ---------------------------------------------------------

    def test_reg_001_normal_monthly_salary(self):
        """
        Vanessa July 2025 is the frozen normal-payroll baseline.

        No exceptional settlement components.
        Five recurring earnings.
        Only INSS and IRT deductions.
        """

        ss = frappe.get_doc(
            "Salary Slip",
            "Sal Slip/HE-EMP/006/00023",
        )

        self.assertEqual(ss.docstatus, 1)

        self.assertEqual(
            str(ss.start_date),
            "2025-07-01",
        )

        self.assertEqual(
            str(ss.end_date),
            "2025-07-31",
        )

        expected_earnings = {
            "Vencimento-R01": 1050000.00,
            "Subsídio de Transporte-R54": 30000.00,
            "Subsídio de Alimentação-R55": 30000.00,
            "Abono de Familia-R56": 40300.00,
            "Isenção de Horário-R57": 210000.00,
        }

        actual_earnings = {
            row.salary_component: flt(row.amount)
            for row in ss.earnings
        }

        self.assertEqual(
            set(actual_earnings),
            set(expected_earnings),
        )

        for component, expected_amount in expected_earnings.items():
            self.assertAlmostEqual(
                actual_earnings[component],
                expected_amount,
                places=2,
                msg=(
                    f"REG-001 regression in earning "
                    f"{component}"
                ),
            )

        self.assertAlmostEqual(
            flt(ss.gross_pay),
            1360300.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(ss.total_deduction),
            273133.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(ss.net_pay),
            1087167.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(ss.gross_pay)
            - flt(ss.total_deduction),
            flt(ss.net_pay),
            places=2,
        )


    # ---------------------------------------------------------
    # REG-002 — INSS
    # ---------------------------------------------------------

    def test_reg_002_inss(self):
        """
        Frozen statutory INSS result for Vanessa July 2025.

        Gross earnings:        1,360,300
        Abono de Familia:         40,300
        INSS incidence base:   1,320,000
        Employee INSS @ 3%:       39,600
        """

        ss = frappe.get_doc(
            "Salary Slip",
            "Sal Slip/HE-EMP/006/00023",
        )

        deductions = {
            row.salary_component: flt(row.amount)
            for row in ss.deductions
        }

        self.assertIn(
            "Segurança Social-D01",
            deductions,
        )

        expected_base_inss = 1320000.00
        expected_inss = 39600.00

        self.assertAlmostEqual(
            deductions["Segurança Social-D01"],
            expected_inss,
            places=2,
        )

        rate = flt(
            calculator.get_inss_employee_rate(
                employee=self.EMPLOYEE,
                reference_date="2025-07-31",
            )
        )

        self.assertAlmostEqual(
            rate,
            0.03,
            places=6,
        )

        calculated_inss = round(
            expected_base_inss * rate
        )

        self.assertAlmostEqual(
            calculated_inss,
            expected_inss,
            places=2,
        )


    # ---------------------------------------------------------
    # REG-003 — IRT
    # ---------------------------------------------------------

    def test_reg_003_irt(self):
        """
        Frozen IRT result for Vanessa July 2025.

        INSS incidence / taxable earnings: 1,320,000
        Less employee INSS:                   39,600
        IRT base:                          1,280,400
        IRT:                                 233,533
        """

        ss = frappe.get_doc(
            "Salary Slip",
            "Sal Slip/HE-EMP/006/00023",
        )

        deductions = {
            row.salary_component: flt(row.amount)
            for row in ss.deductions
        }

        self.assertIn(
            "IRT-D02",
            deductions,
        )

        expected_base_irt = 1280400.00
        expected_irt = 233533.00

        self.assertAlmostEqual(
            deductions["IRT-D02"],
            expected_irt,
            places=2,
        )

        calculated_irt = calculator.calculate_irt(
            expected_base_irt,
            2025,
        )

        self.assertAlmostEqual(
            flt(calculated_irt),
            expected_irt,
            places=2,
            msg=(
                "REG-003: current IRT table/calculator "
                "no longer reproduces the approved "
                "July 2025 payroll result."
            ),
        )


    # ---------------------------------------------------------
    # REG-023 — PAYROLL ACCRUAL JOURNAL ENTRY BALANCES
    # ---------------------------------------------------------

    def test_reg_023_payroll_accrual_journal_entry_balances(self):
        je = frappe.get_doc(
            "Journal Entry",
            "JV 26/469",
        )

        self.assertEqual(
            je.docstatus,
            1,
        )

        self.assertEqual(
            str(je.posting_date),
            "2026-09-30",
        )

        self.assertAlmostEqual(
            flt(je.total_debit),
            127661952.05,
            places=2,
        )

        self.assertAlmostEqual(
            flt(je.total_credit),
            127661952.05,
            places=2,
        )

        self.assertAlmostEqual(
            flt(je.total_debit),
            flt(je.total_credit),
            places=2,
            msg=(
                "REG-023: September payroll accrual "
                "Journal Entry is no longer balanced."
            ),
        )


    # ---------------------------------------------------------
    # REG-024 — PAYROLL ACCOUNTING STRUCTURE
    # ---------------------------------------------------------

    def test_reg_024_payroll_accounting_structure(self):
        je = frappe.get_doc(
            "Journal Entry",
            "JV 26/469",
        )

        accounts = {}

        for row in je.accounts:
            key = (
                row.account,
                row.reference_type,
                row.reference_name,
            )

            accounts[key] = {
                "debit": flt(
                    row.debit_in_account_currency
                ),
                "credit": flt(
                    row.credit_in_account_currency
                ),
            }

        expected = {
            (
                "72210000 - Ordenados e Salarios - HE",
                None,
                None,
            ): {
                "debit": 126874452.05,
                "credit": 43765075.67,
            },

            (
                "37520000 - Encargos a Liquidar - Subsidio de Natal - HE",
                None,
                None,
            ): {
                "debit": 393750.00,
                "credit": 0,
            },

            (
                "37510000 - Encargos a Liquidar - Subsidio de Ferias - HE",
                None,
                None,
            ): {
                "debit": 393750.00,
                "credit": 0,
            },

            (
                "34310000 - Imposto De Rendimento De Trabalho Dependentes - HE",
                None,
                None,
            ): {
                "debit": 0,
                "credit": 9116119.00,
            },

            (
                "34610000 - Instituto Nacional de Seguranca Social - HE",
                None,
                None,
            ): {
                "debit": 0,
                "credit": 1370766.00,
            },

            (
                "36110000 - Salarios a Pagar - HE",
                "Payroll Entry",
                "HR-PRUN-2026-00009",
            ): {
                "debit": 0,
                "credit": 73409991.38,
            },
        }

        # Salary expense appears twice in the JE, one debit
        # and one credit. Aggregate entries with the same key.
        aggregated = {}

        for row in je.accounts:
            key = (
                row.account,
                row.reference_type,
                row.reference_name,
            )

            if key not in aggregated:
                aggregated[key] = {
                    "debit": 0,
                    "credit": 0,
                }

            aggregated[key]["debit"] += flt(
                row.debit_in_account_currency
            )

            aggregated[key]["credit"] += flt(
                row.credit_in_account_currency
            )

        self.assertEqual(
            set(aggregated),
            set(expected),
            (
                "REG-024: payroll accounting "
                "account structure changed."
            ),
        )

        for key, expected_values in expected.items():
            self.assertAlmostEqual(
                aggregated[key]["debit"],
                expected_values["debit"],
                places=2,
                msg=f"REG-024 debit regression: {key}",
            )

            self.assertAlmostEqual(
                aggregated[key]["credit"],
                expected_values["credit"],
                places=2,
                msg=f"REG-024 credit regression: {key}",
            )


    # ---------------------------------------------------------
    # REG-025 — GL MATCHES PAYROLL JOURNAL ENTRY
    # ---------------------------------------------------------

    def test_reg_025_gl_matches_payroll_journal_entry(self):
        je = frappe.get_doc(
            "Journal Entry",
            "JV 26/469",
        )

        gl_entries = frappe.get_all(
            "GL Entry",
            filters={
                "voucher_type": "Journal Entry",
                "voucher_no": je.name,
                "is_cancelled": 0,
            },
            fields=[
                "account",
                "debit",
                "credit",
            ],
        )

        self.assertTrue(
            gl_entries,
            (
                "REG-025: no GL Entries found for "
                "September payroll accrual."
            ),
        )

        gl_debit = sum(
            flt(row.debit)
            for row in gl_entries
        )

        gl_credit = sum(
            flt(row.credit)
            for row in gl_entries
        )

        self.assertAlmostEqual(
            gl_debit,
            flt(je.total_debit),
            places=2,
            msg=(
                "REG-025: GL debit does not reconcile "
                "with Journal Entry."
            ),
        )

        self.assertAlmostEqual(
            gl_credit,
            flt(je.total_credit),
            places=2,
            msg=(
                "REG-025: GL credit does not reconcile "
                "with Journal Entry."
            ),
        )

        self.assertAlmostEqual(
            gl_debit,
            gl_credit,
            places=2,
            msg=(
                "REG-025: posted payroll GL "
                "is not balanced."
            ),
        )


    # ---------------------------------------------------------
    # HELPERS — CURRENT SEPTEMBER PAYROLL
    # ---------------------------------------------------------

    def _get_september_payroll_entry(self):
        return frappe.get_doc(
            "Payroll Entry",
            "HR-PRUN-2026-00011",
        )

    def _get_september_payroll_jv(self):
        """
        Find the accrual Journal Entry through the native
        Payroll Entry reference on Journal Entry Account.

        Do not hard-code a JV number.
        """

        parent = frappe.db.get_value(
            "Journal Entry Account",
            {
                "reference_type": "Payroll Entry",
                "reference_name": "HR-PRUN-2026-00011",
                "docstatus": 1,
            },
            "parent",
        )

        self.assertTrue(
            parent,
            "No submitted payroll accrual JV found.",
        )

        return frappe.get_doc(
            "Journal Entry",
            parent,
        )


    # ---------------------------------------------------------
    # REG-026 — EMPLOYER INSS 8%
    # ---------------------------------------------------------

    def test_reg_026_employer_inss(self):
        pe = self._get_september_payroll_entry()

        slips = [
            frappe.get_doc(
                "Salary Slip",
                row.name,
            )
            for row in frappe.get_all(
                "Salary Slip",
                filters={
                    "payroll_entry": pe.name,
                    "docstatus": 1,
                },
                fields=["name"],
            )
        ]

        result = pe.get_employer_inss(slips)

        self.assertAlmostEqual(
            flt(result["base"]),
            43242221.35,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["rate"]),
            0.08,
            places=6,
        )

        # Employer contribution is rounded employee by employee.
        self.assertAlmostEqual(
            flt(result["amount"]),
            3459377.00,
            places=2,
        )

        # Employer INSS must not affect employee net salary.
        total_net = sum(
            flt(ss.net_pay)
            for ss in slips
        )

        total_net_again = sum(
            flt(ss.gross_pay)
            - flt(ss.total_deduction)
            for ss in slips
        )

        self.assertAlmostEqual(
            total_net,
            total_net_again,
            places=2,
        )


    # ---------------------------------------------------------
    # REG-027 — EMPLOYER INSS ACCOUNTING
    # ---------------------------------------------------------

    def test_reg_027_employer_inss_accounting(self):
        je = self._get_september_payroll_jv()

        expense_debit = 0
        inss_credit = 0

        for row in je.accounts:
            if (
                row.account
                == "72520000 - Seguranca Social - HE"
            ):
                expense_debit += flt(
                    row.debit_in_account_currency
                )

            if (
                row.account
                == "34610000 - Instituto Nacional de Seguranca Social - HE"
            ):
                inss_credit += flt(
                    row.credit_in_account_currency
                )

        self.assertAlmostEqual(
            expense_debit,
            3459377.00,
            places=2,
            msg=(
                "REG-027: employer INSS expense "
                "posting changed."
            ),
        )

        # Employee 3% + Employer 8%.
        self.assertAlmostEqual(
            inss_credit,
            4756643.00,
            places=2,
            msg=(
                "REG-027: total INSS liability "
                "does not reconcile."
            ),
        )


    # ---------------------------------------------------------
    # REG-028 — STATISTICAL COMPONENTS NEVER POST TO GL
    # ---------------------------------------------------------

    def test_reg_028_statistical_components_do_not_post(self):
        pe = self._get_september_payroll_entry()

        for component in (
            "Salario Iliquido",
            "Salario Liquido",
            "Iliquido p/IRT",
        ):
            statistical = frappe.db.get_value(
                "Salary Component",
                component,
                "statistical_component",
            )

            self.assertEqual(
                statistical,
                1,
                f"{component} must remain statistical.",
            )

            item = {
                "salary_component": component,
            }

            self.assertFalse(
                pe.should_add_component_to_accrual_jv(
                    "earnings"
                    if component
                    in (
                        "Salario Iliquido",
                        "Salario Liquido",
                    )
                    else "deductions",
                    item,
                ),
                (
                    f"REG-028: {component} must never "
                    "enter payroll accrual accounting."
                ),
            )


    # ---------------------------------------------------------
    # REG-029 — TERMINATION SALARY IS NOT DUPLICATED
    # ---------------------------------------------------------

    def test_reg_029_termination_salary_not_duplicated(self):
        slip_name = frappe.db.get_value(
            "Salary Slip",
            {
                "payroll_entry":
                    "HR-PRUN-2026-00011",
                "employee":
                    "HE-EMP/006",
                "docstatus": 1,
            },
            "name",
        )

        self.assertTrue(
            slip_name,
            "Vanessa September Salary Slip not found.",
        )

        ss = frappe.get_doc(
            "Salary Slip",
            slip_name,
        )

        earnings = {
            row.salary_component:
                flt(row.amount)
            for row in ss.earnings
        }

        self.assertIn(
            "Proporcional Salario",
            earnings,
        )

        self.assertNotIn(
            "Salario Base",
            earnings,
            (
                "REG-029: recurring base salary must "
                "be suppressed when termination "
                "Proporcional Salario exists."
            ),
        )


    # ---------------------------------------------------------
    # REG-030 — ADDITIONAL SALARY TYPE BEHAVIOUR
    # ---------------------------------------------------------

    def test_reg_030_additional_salary_type_behaviour(self):
        slip_name = frappe.db.get_value(
            "Salary Slip",
            {
                "payroll_entry":
                    "HR-PRUN-2026-00011",
                "employee":
                    "HE-EMP/006",
                "docstatus": 1,
            },
            "name",
        )

        self.assertTrue(
            slip_name,
            (
                "REG-030: required submitted Salary Slip "
                "for HE-EMP/006 / HR-PRUN-2026-00011 "
                "is missing from the regression database."
            ),
        )

        ss = frappe.get_doc(
            "Salary Slip",
            slip_name,
        )

        earning_additional = {
            row.salary_component:
                row.additional_salary
            for row in ss.earnings
            if row.additional_salary
        }

        deduction_additional = {
            row.salary_component:
                row.additional_salary
            for row in ss.deductions
            if row.additional_salary
        }

        self.assertIn(
            "Salário Vincendo",
            earning_additional,
        )

        self.assertIn(
            "Proporcional Salario",
            earning_additional,
        )

        self.assertIn(
            "Proporcional Subsidio Ferias",
            earning_additional,
        )

        self.assertIn(
            "Proporcional Subsidio Natal",
            earning_additional,
        )

        self.assertIn(
            "Indemnização por Falta Aviso Prévio",
            deduction_additional,
        )

        self.assertNotIn(
            "Indemnização por Falta Aviso Prévio",
            earning_additional,
        )


    # ---------------------------------------------------------
    # REG-031 — PAYROLL ACCRUAL BALANCES
    # ---------------------------------------------------------

    def test_reg_031_payroll_accrual_balances(self):
        je = self._get_september_payroll_jv()

        debit = sum(
            flt(
                row.debit_in_account_currency
            )
            for row in je.accounts
        )

        credit = sum(
            flt(
                row.credit_in_account_currency
            )
            for row in je.accounts
        )

        self.assertAlmostEqual(
            debit,
            credit,
            places=2,
            msg=(
                "REG-031: payroll accrual "
                "Journal Entry is not balanced."
            ),
        )

        self.assertAlmostEqual(
            debit,
            flt(je.total_debit),
            places=2,
        )

        self.assertAlmostEqual(
            credit,
            flt(je.total_credit),
            places=2,
        )


    # ---------------------------------------------------------
    # REG-032 — TAX PARTY MAPPING
    # ---------------------------------------------------------

    def test_reg_032_tax_party_mapping(self):
        je = self._get_september_payroll_jv()

        inss_rows = [
            row
            for row in je.accounts
            if row.account
            == (
                "34610000 - Instituto Nacional "
                "de Seguranca Social - HE"
            )
        ]

        irt_rows = [
            row
            for row in je.accounts
            if row.account
            == (
                "34310000 - Imposto De Rendimento "
                "De Trabalho Dependentes - HE"
            )
        ]

        self.assertTrue(inss_rows)
        self.assertTrue(irt_rows)

        for row in inss_rows:
            self.assertEqual(
                row.party_type,
                "Estado",
            )

            self.assertEqual(
                row.party,
                "INSS",
            )

        for row in irt_rows:
            self.assertEqual(
                row.party_type,
                "Estado",
            )

            self.assertEqual(
                row.party,
                "IRT",
            )


    # ---------------------------------------------------------
    # REG-033 — USD ASSIGNMENT CONVERSION
    # ---------------------------------------------------------

    def test_reg_033_usd_assignment_conversion(self):
        assignment = frappe.get_doc(
            "Salary Structure Assignment",
            "HR-SSA-26-09-00023-1",
        )

        self.assertEqual(
            assignment.employee,
            "HE-EMP/003",
        )

        self.assertEqual(
            int(assignment.moeda_usd or 0),
            1,
            (
                "REG-033 fixture must remain a USD "
                "salary assignment."
            ),
        )

        self.assertAlmostEqual(
            flt(assignment.base),
            6750.00,
            places=2,
        )

        ss = frappe.new_doc(
            "Salary Slip"
        )

        ss.employee = assignment.employee
        ss.salary_structure = (
            assignment.salary_structure
        )
        ss.start_date = "2026-09-01"
        ss.end_date = "2026-09-30"

        exchange = (
            ss.get_payroll_exchange_rate(
                from_currency="USD",
                to_currency="KZ",
            )
        )

        self.assertEqual(
            str(exchange["date"]),
            "2026-08-20",
            (
                "REG-033: payroll must use the latest "
                "exchange rate on or before payroll "
                "end date."
            ),
        )

        self.assertAlmostEqual(
            flt(exchange["rate"]),
            912.7985,
            places=4,
        )

        data = assignment.as_dict()

        converted = (
            ss.apply_assignment_currency_conversion(
                data
            )
        )

        expected_base = (
            6750.00
            * 912.7985
        )

        self.assertAlmostEqual(
            flt(converted["base"]),
            expected_base,
            places=3,
            msg=(
                "REG-033: USD base salary was not "
                "converted correctly to KZ."
            ),
        )

        self.assertAlmostEqual(
            flt(converted["base"]),
            6161389.875,
            places=3,
        )

        self.assertAlmostEqual(
            flt(
                converted[
                    "payroll_exchange_rate"
                ]
            ),
            912.7985,
            places=4,
        )

        self.assertEqual(
            converted[
                "payroll_exchange_record"
            ],
            (
                "2026-08-20-USD-KZ-"
                "Selling-Buying"
            ),
        )

        self.assertEqual(
            str(
                converted[
                    "payroll_exchange_rate_date"
                ]
            ),
            "2026-08-20",
        )

        # Calling the conversion method again on the
        # same evaluation dictionary must not multiply
        # the salary by the exchange rate a second time.
        converted_again = (
            ss.apply_assignment_currency_conversion(
                converted
            )
        )

        self.assertAlmostEqual(
            flt(converted_again["base"]),
            expected_base,
            places=3,
            msg=(
                "REG-033: salary was converted "
                "more than once."
            ),
        )

    # ---------------------------------------------------------
    # REG-034 — FERIAS DO NOT DEDUCT BASE SALARY
    # ---------------------------------------------------------

    def test_reg_034_ferias_do_not_deduct_salary(self):

        leave = frappe._dict({
            "name": "TEST-FERIAS-001",
            "leave_type": "Ferias",
            "from_date": getdate("2026-09-14"),
            "to_date": getdate("2026-09-18"),
            "half_day": 0,
            "half_day_date": None,
            "total_leave_days": 5,
        })

        treatment = frappe._dict({
            "custom_deduz_salario": 0,
            "custom_deduz_subsidio_alimentacao": 1,
            "custom_deduz_subsidio_transporte": 1,
            "custom_afeta_premio_assiduidade": 1,
            "custom_recuperavel_do_inss": 0,
        })

        def fake_get_all(doctype, *args, **kwargs):
            if doctype == "Leave Application":
                return [leave]

            if doctype == "Attendance":
                return []

            return []

        with (
            patch(
                "ao_payroll.payroll.calculator."
                "frappe.get_all",
                side_effect=fake_get_all,
            ),
            patch(
                "ao_payroll.payroll.calculator."
                "frappe.db.get_value",
                return_value=treatment,
            ),
            patch(
                "ao_payroll.payroll.calculator."
                "get_number_of_leave_days",
                return_value=5,
            ),
        ):
            result = (
                calculator
                .get_employee_attendance_effects(
                    employee="TEST-EMP",
                    payroll_start_date="2026-09-01",
                    payroll_end_date="2026-09-30",
                )
            )

        self.assertEqual(
            flt(result["dias_falta_salario"]),
            0,
            (
                "REG-034: annual leave must not "
                "reduce base salary."
            ),
        )


    # ---------------------------------------------------------
    # REG-035 — FERIAS REDUCE MEAL AND TRANSPORT
    # ---------------------------------------------------------

    def test_reg_035_ferias_reduce_presence_allowances(self):

        leave = frappe._dict({
            "name": "TEST-FERIAS-002",
            "leave_type": "Ferias",
            "from_date": getdate("2026-09-14"),
            "to_date": getdate("2026-09-18"),
            "half_day": 0,
            "half_day_date": None,
            "total_leave_days": 5,
        })

        treatment = frappe._dict({
            "custom_deduz_salario": 0,
            "custom_deduz_subsidio_alimentacao": 1,
            "custom_deduz_subsidio_transporte": 1,
            "custom_afeta_premio_assiduidade": 1,
            "custom_recuperavel_do_inss": 0,
        })

        def fake_get_all(doctype, *args, **kwargs):
            if doctype == "Leave Application":
                return [leave]

            if doctype == "Attendance":
                return []

            return []

        with (
            patch(
                "ao_payroll.payroll.calculator."
                "frappe.get_all",
                side_effect=fake_get_all,
            ),
            patch(
                "ao_payroll.payroll.calculator."
                "frappe.db.get_value",
                return_value=treatment,
            ),
            patch(
                "ao_payroll.payroll.calculator."
                "get_number_of_leave_days",
                return_value=5,
            ),
        ):
            result = (
                calculator
                .get_employee_attendance_effects(
                    employee="TEST-EMP",
                    payroll_start_date="2026-09-01",
                    payroll_end_date="2026-09-30",
                )
            )

        self.assertEqual(
            flt(result["dias_ferias"]),
            5,
        )

        self.assertEqual(
            flt(
                result[
                    "dias_falta_alimentacao"
                ]
            ),
            5,
            (
                "REG-035: Ferias must reduce "
                "meal allowance by leave days."
            ),
        )

        self.assertEqual(
            flt(
                result[
                    "dias_falta_transporte"
                ]
            ),
            5,
            (
                "REG-035: Ferias must reduce "
                "transport allowance by leave days."
            ),
        )


    # ---------------------------------------------------------
    # REG-036 — FERIAS AFFECT ATTENDANCE/EFFECTIVENESS
    # ---------------------------------------------------------

    def test_reg_036_ferias_affect_attendance_bonus(self):

        leave = frappe._dict({
            "name": "TEST-FERIAS-003",
            "leave_type": "Ferias",
            "from_date": getdate("2026-09-14"),
            "to_date": getdate("2026-09-18"),
            "half_day": 0,
            "half_day_date": None,
            "total_leave_days": 5,
        })

        treatment = frappe._dict({
            "custom_deduz_salario": 0,
            "custom_deduz_subsidio_alimentacao": 1,
            "custom_deduz_subsidio_transporte": 1,
            "custom_afeta_premio_assiduidade": 1,
            "custom_recuperavel_do_inss": 0,
        })

        def fake_get_all(doctype, *args, **kwargs):
            if doctype == "Leave Application":
                return [leave]

            if doctype == "Attendance":
                return []

            return []

        with (
            patch(
                "ao_payroll.payroll.calculator."
                "frappe.get_all",
                side_effect=fake_get_all,
            ),
            patch(
                "ao_payroll.payroll.calculator."
                "frappe.db.get_value",
                return_value=treatment,
            ),
            patch(
                "ao_payroll.payroll.calculator."
                "get_number_of_leave_days",
                return_value=5,
            ),
        ):
            result = (
                calculator
                .get_employee_attendance_effects(
                    employee="TEST-EMP",
                    payroll_start_date="2026-09-01",
                    payroll_end_date="2026-09-30",
                )
            )

        self.assertTrue(
            result[
                "perde_premio_assiduidade"
            ],
            (
                "REG-036: Ferias must affect "
                "attendance/effectiveness when "
                "Leave Type policy says so."
            ),
        )


    # ---------------------------------------------------------
    # REG-037 — LEAVE PREVENTS ATTENDANCE DOUBLE COUNTING
    # ---------------------------------------------------------

    def test_reg_037_leave_prevents_double_counting(self):

        leave = frappe._dict({
            "name": "TEST-FERIAS-004",
            "leave_type": "Ferias",
            "from_date": getdate("2026-09-14"),
            "to_date": getdate("2026-09-18"),
            "half_day": 0,
            "half_day_date": None,
            "total_leave_days": 5,
        })

        attendance = frappe._dict({
            "name": "TEST-ATT-001",
            "attendance_date":
                getdate("2026-09-14"),
            "status": "Absent",
            "tipo_de_faltas":
                "Falta Injustificada",
        })

        leave_treatment = frappe._dict({
            "custom_deduz_salario": 0,
            "custom_deduz_subsidio_alimentacao": 1,
            "custom_deduz_subsidio_transporte": 1,
            "custom_afeta_premio_assiduidade": 1,
            "custom_recuperavel_do_inss": 0,
        })

        absence_treatment = frappe._dict({
            "deduz_salario": 1,
            "deduz_subsidio_alimentacao": 1,
            "deduz_subsidio_transporte": 1,
            "afeta_premio_assiduidade": 1,
        })

        def fake_get_all(doctype, *args, **kwargs):
            if doctype == "Leave Application":
                return [leave]

            if doctype == "Attendance":
                return [attendance]

            return []

        def fake_get_value(
            doctype,
            filters,
            fields=None,
            **kwargs,
        ):
            if doctype == "Leave Type":
                return leave_treatment

            if doctype == "Tipo de Falta":
                return absence_treatment

            return None

        def fake_leave_days(
            employee,
            leave_type,
            from_date,
            to_date,
            half_day,
            half_day_date,
        ):
            # Whole leave block.
            if (
                getdate(from_date)
                == getdate("2026-09-14")
                and getdate(to_date)
                == getdate("2026-09-18")
            ):
                return 5

            # Individual covered date queried by
            # double-count protection.
            if (
                getdate(from_date)
                == getdate("2026-09-14")
                and getdate(to_date)
                == getdate("2026-09-14")
            ):
                return 1

            return 0

        with (
            patch(
                "ao_payroll.payroll.calculator."
                "frappe.get_all",
                side_effect=fake_get_all,
            ),
            patch(
                "ao_payroll.payroll.calculator."
                "frappe.db.get_value",
                side_effect=fake_get_value,
            ),
            patch(
                "ao_payroll.payroll.calculator."
                "get_number_of_leave_days",
                side_effect=fake_leave_days,
            ),
        ):
            result = (
                calculator
                .get_employee_attendance_effects(
                    employee="TEST-EMP",
                    payroll_start_date="2026-09-01",
                    payroll_end_date="2026-09-30",
                )
            )

        # The competing unjustified absence must not
        # deduct salary because approved leave owns
        # that date.
        self.assertEqual(
            flt(result["dias_falta_salario"]),
            0,
            (
                "REG-037: Attendance was double "
                "counted on an approved leave date."
            ),
        )

        # Only the five Ferias days affect these
        # allowances — not 5 + the Attendance record.
        self.assertEqual(
            flt(
                result[
                    "dias_falta_alimentacao"
                ]
            ),
            5,
        )

        self.assertEqual(
            flt(
                result[
                    "dias_falta_transporte"
                ]
            ),
            5,
        )

        self.assertEqual(
            len(result["attendance_records"]),
            0,
            (
                "REG-037: covered Attendance should "
                "not enter payroll effects."
            ),
        )

        self.assertEqual(
            len(result["leave_records"]),
            1,
        )


    # ---------------------------------------------------------
    # REG-038 — HOLIDAY ALLOWANCE PROPORTIONAL LEAVE BLOCK
    # ---------------------------------------------------------

    def test_reg_038_holiday_allowance_proportional_block(self):
        from ao_payroll.payroll import holiday_allowance

        leave = frappe._dict({
            "name": "TEST-HOLIDAY-001",
            "employee": "TEST-EMP",
            "leave_type": "Ferias",
            "from_date": getdate("2026-09-14"),
            "to_date": getdate("2026-09-18"),
            "total_leave_days": 5,
            "docstatus": 1,
            "status": "Approved",
        })

        settings = frappe._dict({
            "custom_holiday_allowance_payment_mode":
                "Per Leave Block",
            "custom_holiday_allowance_block_method":
                "Proportional Per Block",
        })

        balance = {
            "entitlement_days": 22.0,
            "annual_entitlement": 500000.0,
            "paid": 0.0,
            "remaining": 500000.0,
        }

        with (
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "frappe.get_doc",
                return_value=leave,
            ),
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "get_payroll_settings",
                return_value=settings,
            ),
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "calculator.calculate_holiday_allowance_balance",
                return_value=balance,
            ),
        ):
            result = (
                holiday_allowance
                .calculate_leave_block_holiday_allowance(
                    leave_application="TEST-HOLIDAY-001",
                    base_salary=1000000,
                )
            )

        self.assertAlmostEqual(
            flt(result["calculated_amount"]),
            113636.36,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["payable_amount"]),
            113636.36,
            places=2,
        )


    # ---------------------------------------------------------
    # REG-039 — HOLIDAY ALLOWANCE CAPPED BY REMAINING BALANCE
    # ---------------------------------------------------------

    def test_reg_039_holiday_allowance_capped_by_remaining(self):
        from ao_payroll.payroll import holiday_allowance

        leave = frappe._dict({
            "name": "TEST-HOLIDAY-002",
            "employee": "TEST-EMP",
            "leave_type": "Ferias",
            "from_date": getdate("2026-09-14"),
            "to_date": getdate("2026-09-18"),
            "total_leave_days": 5,
            "docstatus": 1,
            "status": "Approved",
        })

        settings = frappe._dict({
            "custom_holiday_allowance_payment_mode":
                "Per Leave Block",
            "custom_holiday_allowance_block_method":
                "Proportional Per Block",
        })

        balance = {
            "entitlement_days": 22.0,
            "annual_entitlement": 500000.0,
            "paid": 450000.0,
            "remaining": 50000.0,
        }

        with (
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "frappe.get_doc",
                return_value=leave,
            ),
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "get_payroll_settings",
                return_value=settings,
            ),
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "calculator.calculate_holiday_allowance_balance",
                return_value=balance,
            ),
        ):
            result = (
                holiday_allowance
                .calculate_leave_block_holiday_allowance(
                    leave_application="TEST-HOLIDAY-002",
                    base_salary=1000000,
                )
            )

        self.assertAlmostEqual(
            flt(result["calculated_amount"]),
            113636.36,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["payable_amount"]),
            50000.0,
            places=2,
            msg=(
                "REG-039: holiday allowance payment "
                "must never exceed remaining annual entitlement."
            ),
        )


    # ---------------------------------------------------------
    # REG-040 — EXHAUSTED ENTITLEMENT PRODUCES ZERO PAYMENT
    # ---------------------------------------------------------

    def test_reg_040_holiday_allowance_exhausted_balance(self):
        from ao_payroll.payroll import holiday_allowance

        leave = frappe._dict({
            "name": "TEST-HOLIDAY-003",
            "employee": "TEST-EMP",
            "leave_type": "Ferias",
            "from_date": getdate("2026-09-14"),
            "to_date": getdate("2026-09-18"),
            "total_leave_days": 5,
            "docstatus": 1,
            "status": "Approved",
        })

        settings = frappe._dict({
            "custom_holiday_allowance_payment_mode":
                "Per Leave Block",
            "custom_holiday_allowance_block_method":
                "Proportional Per Block",
        })

        balance = {
            "entitlement_days": 22.0,
            "annual_entitlement": 500000.0,
            "paid": 500000.0,
            "remaining": 0.0,
        }

        with (
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "frappe.get_doc",
                return_value=leave,
            ),
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "get_payroll_settings",
                return_value=settings,
            ),
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "calculator.calculate_holiday_allowance_balance",
                return_value=balance,
            ),
        ):
            result = (
                holiday_allowance
                .calculate_leave_block_holiday_allowance(
                    leave_application="TEST-HOLIDAY-003",
                    base_salary=1000000,
                )
            )

        self.assertEqual(
            flt(result["payable_amount"]),
            0,
        )


    # ---------------------------------------------------------
    # REG-041 — FULL ON FIRST LEAVE BLOCK
    # ---------------------------------------------------------

    def test_reg_041_holiday_allowance_full_first_block(self):
        from ao_payroll.payroll import holiday_allowance

        leave = frappe._dict({
            "name": "TEST-HOLIDAY-004",
            "employee": "TEST-EMP",
            "leave_type": "Ferias",
            "from_date": getdate("2026-09-14"),
            "to_date": getdate("2026-09-18"),
            "total_leave_days": 5,
            "docstatus": 1,
            "status": "Approved",
        })

        settings = frappe._dict({
            "custom_holiday_allowance_payment_mode":
                "Per Leave Block",
            "custom_holiday_allowance_block_method":
                "Full on First Block",
        })

        balance = {
            "entitlement_days": 22.0,
            "annual_entitlement": 500000.0,
            "paid": 0.0,
            "remaining": 500000.0,
        }

        with (
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "frappe.get_doc",
                return_value=leave,
            ),
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "get_payroll_settings",
                return_value=settings,
            ),
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "calculator.calculate_holiday_allowance_balance",
                return_value=balance,
            ),
        ):
            result = (
                holiday_allowance
                .calculate_leave_block_holiday_allowance(
                    leave_application="TEST-HOLIDAY-004",
                    base_salary=1000000,
                )
            )

        self.assertAlmostEqual(
            flt(result["calculated_amount"]),
            500000.0,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["payable_amount"]),
            500000.0,
            places=2,
        )


    # ---------------------------------------------------------
    # REG-042 — DUPLICATE LEAVE APPLICATION IS BLOCKED
    # ---------------------------------------------------------

    def test_reg_042_holiday_allowance_duplicate_blocked(self):
        from ao_payroll.payroll import holiday_allowance

        calculated = {
            "leave_application": "TEST-HOLIDAY-005",
            "employee": "TEST-EMP",
            "year": 2026,
            "block_days": 5.0,
            "entitlement_days": 22.0,
            "annual_entitlement": 500000.0,
            "already_paid": 0.0,
            "remaining_before_payment": 500000.0,
            "block_method": "Proportional Per Block",
            "calculated_amount": 113636.36,
            "payable_amount": 113636.36,
        }

        settings = frappe._dict({
            "holyday_allowance_salary_component":
                "Subsidio de Ferias",
        })

        with (
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "calculate_leave_block_holiday_allowance",
                return_value=calculated,
            ),
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "get_payroll_settings",
                return_value=settings,
            ),
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "frappe.db.get_value",
                return_value="HR-ADSAL-TEST-001",
            ),
        ):
            with self.assertRaises(
                frappe.ValidationError
            ):
                holiday_allowance.create_leave_block_holiday_allowance(
                    leave_application="TEST-HOLIDAY-005",
                    base_salary=1000000,
                    payroll_date="2026-09-30",
                )


    # ---------------------------------------------------------
    # REG-043 — FIXED MONTH TRIGGER
    # ---------------------------------------------------------

    def test_reg_043_holiday_allowance_fixed_month(self):
        from ao_payroll.payroll import holiday_allowance

        settings = frappe._dict({
            "custom_holiday_allowance_payment_mode":
                "Fixed Month",
            "custom_holiday_allowance_fixed_month":
                "June",
        })

        balance = {
            "year": 2026,
            "service_months": 12,
            "entitlement_days": 22.0,
            "annual_entitlement": 500000.0,
            "rate": 0.5,
            "paid": 0.0,
            "remaining": 500000.0,
            "overpaid": 0.0,
        }

        with (
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "get_payroll_settings",
                return_value=settings,
            ),
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "calculator.calculate_holiday_allowance_balance",
                return_value=balance,
            ),
        ):
            june = (
                holiday_allowance
                .calculate_fixed_month_holiday_allowance(
                    employee="TEST-EMP",
                    year=2026,
                    base_salary=1000000,
                    payroll_date="2026-06-30",
                )
            )

            may = (
                holiday_allowance
                .calculate_fixed_month_holiday_allowance(
                    employee="TEST-EMP",
                    year=2026,
                    base_salary=1000000,
                    payroll_date="2026-05-31",
                )
            )

        self.assertTrue(june["triggered"])
        self.assertAlmostEqual(
            flt(june["payable_amount"]),
            500000.0,
            places=2,
        )

        self.assertFalse(may["triggered"])
        self.assertEqual(
            flt(may["payable_amount"]),
            0,
        )


    # ---------------------------------------------------------
    # REG-044 — MONTHLY DUODECIMOS
    # ---------------------------------------------------------

    def test_reg_044_holiday_allowance_duodecimos(self):
        from ao_payroll.payroll import holiday_allowance

        settings = frappe._dict({
            "custom_holiday_allowance_payment_mode":
                "Monthly Duodecimos",
        })

        balance = {
            "year": 2026,
            "service_months": 12,
            "entitlement_days": 22.0,
            "annual_entitlement": 500000.0,
            "rate": 0.5,
            "paid": 0.0,
            "remaining": 500000.0,
            "overpaid": 0.0,
        }

        with (
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "get_payroll_settings",
                return_value=settings,
            ),
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "calculator.calculate_holiday_allowance_balance",
                return_value=balance,
            ),
        ):
            result = (
                holiday_allowance
                .calculate_monthly_duodecimo_holiday_allowance(
                    employee="TEST-EMP",
                    year=2026,
                    base_salary=1000000,
                    payroll_date="2026-01-31",
                )
            )

        self.assertAlmostEqual(
            flt(result["normal_installment"]),
            41666.67,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["payable_amount"]),
            41666.67,
            places=2,
        )


    # ---------------------------------------------------------
    # REG-045 — EMPLOYEE REQUEST NORMAL CASE
    # ---------------------------------------------------------

    def test_reg_045_holiday_allowance_employee_request(self):
        from ao_payroll.payroll import holiday_allowance

        settings = frappe._dict({
            "custom_holiday_allowance_payment_mode":
                "Employee Request",
        })

        balance = {
            "year": 2026,
            "service_months": 12,
            "entitlement_days": 22.0,
            "annual_entitlement": 500000.0,
            "rate": 0.5,
            "paid": 0.0,
            "remaining": 500000.0,
            "overpaid": 0.0,
        }

        with (
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "get_payroll_settings",
                return_value=settings,
            ),
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "calculator.calculate_holiday_allowance_balance",
                return_value=balance,
            ),
        ):
            result = (
                holiday_allowance
                .calculate_employee_request_holiday_allowance(
                    employee="TEST-EMP",
                    year=2026,
                    base_salary=1000000,
                    requested_amount=200000,
                    payroll_date="2026-04-30",
                )
            )

        self.assertAlmostEqual(
            flt(result["requested_amount"]),
            200000.0,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["payable_amount"]),
            200000.0,
            places=2,
        )

        self.assertFalse(
            result["request_capped"]
        )


    # ---------------------------------------------------------
    # REG-046 — EMPLOYEE REQUEST CAPPED
    # ---------------------------------------------------------

    def test_reg_046_holiday_allowance_employee_request_cap(self):
        from ao_payroll.payroll import holiday_allowance

        settings = frappe._dict({
            "custom_holiday_allowance_payment_mode":
                "Employee Request",
        })

        balance = {
            "year": 2026,
            "service_months": 12,
            "entitlement_days": 22.0,
            "annual_entitlement": 500000.0,
            "rate": 0.5,
            "paid": 0.0,
            "remaining": 500000.0,
            "overpaid": 0.0,
        }

        with (
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "get_payroll_settings",
                return_value=settings,
            ),
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "calculator.calculate_holiday_allowance_balance",
                return_value=balance,
            ),
        ):
            result = (
                holiday_allowance
                .calculate_employee_request_holiday_allowance(
                    employee="TEST-EMP",
                    year=2026,
                    base_salary=1000000,
                    requested_amount=600000,
                    payroll_date="2026-04-30",
                )
            )

        self.assertAlmostEqual(
            flt(result["requested_amount"]),
            600000.0,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["payable_amount"]),
            500000.0,
            places=2,
        )

        self.assertTrue(
            result["request_capped"]
        )


    # ---------------------------------------------------------
    # REG-047 — SALARY SLIP PER LEAVE BLOCK WITH BALANCE
    # ---------------------------------------------------------

    def test_reg_047_salary_slip_holiday_leave_block(self):
        from ao_payroll.payroll import holiday_allowance

        settings = frappe._dict({
            "custom_holiday_allowance_payment_mode":
                "Per Leave Block",
            "custom_holiday_allowance_block_method":
                "Proportional Per Block",
        })

        leave = frappe._dict({
            "name": "TEST-HOLIDAY-DISPATCH-001",
            "from_date": getdate("2026-09-14"),
            "to_date": getdate("2026-09-18"),
            "total_leave_days": 5,
        })

        balance = {
            "year": 2026,
            "service_months": 12,
            "entitlement_days": 22.0,
            "annual_entitlement": 500000.0,
            "rate": 0.5,
            "paid": 0.0,
            "remaining": 500000.0,
            "overpaid": 0.0,
        }

        with (
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "get_payroll_settings",
                return_value=settings,
            ),
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "frappe.get_all",
                return_value=[leave],
            ),
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "calculator.calculate_holiday_allowance_balance",
                return_value=balance,
            ),
        ):
            result = (
                holiday_allowance
                .calculate_salary_slip_holiday_allowance(
                    employee="TEST-EMP",
                    base_salary=1000000,
                    payroll_start_date="2026-09-01",
                    payroll_end_date="2026-09-30",
                )
            )

        self.assertEqual(
            result["payment_mode"],
            "Per Leave Block",
        )

        self.assertAlmostEqual(
            flt(result["amount"]),
            113636.36,
            places=2,
        )

        self.assertEqual(
            result["source_leave_applications"],
            ["TEST-HOLIDAY-DISPATCH-001"],
        )


    # ---------------------------------------------------------
    # REG-048 — SALARY SLIP PER LEAVE BLOCK EXHAUSTED
    # ---------------------------------------------------------

    def test_reg_048_salary_slip_holiday_exhausted(self):
        from ao_payroll.payroll import holiday_allowance

        settings = frappe._dict({
            "custom_holiday_allowance_payment_mode":
                "Per Leave Block",
            "custom_holiday_allowance_block_method":
                "Proportional Per Block",
        })

        leave = frappe._dict({
            "name": "TEST-HOLIDAY-DISPATCH-002",
            "from_date": getdate("2026-09-14"),
            "to_date": getdate("2026-09-18"),
            "total_leave_days": 5,
        })

        balance = {
            "year": 2026,
            "service_months": 12,
            "entitlement_days": 22.0,
            "annual_entitlement": 500000.0,
            "rate": 0.5,
            "paid": 500000.0,
            "remaining": 0.0,
            "overpaid": 0.0,
        }

        with (
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "get_payroll_settings",
                return_value=settings,
            ),
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "frappe.get_all",
                return_value=[leave],
            ),
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "calculator.calculate_holiday_allowance_balance",
                return_value=balance,
            ),
        ):
            result = (
                holiday_allowance
                .calculate_salary_slip_holiday_allowance(
                    employee="TEST-EMP",
                    base_salary=1000000,
                    payroll_start_date="2026-09-01",
                    payroll_end_date="2026-09-30",
                )
            )

        self.assertEqual(
            flt(result["amount"]),
            0,
            (
                "REG-048: exhausted annual holiday "
                "allowance must not enter Salary Slip."
            ),
        )


    # ---------------------------------------------------------
    # REG-049 — SALARY SLIP FIXED MONTH DISPATCH
    # ---------------------------------------------------------

    def test_reg_049_salary_slip_holiday_fixed_month(self):
        from ao_payroll.payroll import holiday_allowance

        settings = frappe._dict({
            "custom_holiday_allowance_payment_mode":
                "Fixed Month",
        })

        fixed_result = {
            "payable_amount": 500000.0,
        }

        with (
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "get_payroll_settings",
                return_value=settings,
            ),
            patch(
                "ao_payroll.payroll.holiday_allowance."
                "calculate_fixed_month_holiday_allowance",
                return_value=fixed_result,
            ) as fixed_mock,
        ):
            result = (
                holiday_allowance
                .calculate_salary_slip_holiday_allowance(
                    employee="TEST-EMP",
                    base_salary=1000000,
                    payroll_start_date="2026-06-01",
                    payroll_end_date="2026-06-30",
                )
            )

        self.assertAlmostEqual(
            flt(result["amount"]),
            500000.0,
            places=2,
        )

        fixed_mock.assert_called_once_with(
            employee="TEST-EMP",
            year=2026,
            base_salary=1000000,
            payroll_date=getdate("2026-06-30"),
        )


    # ---------------------------------------------------------
    # REG-050 — EMPLOYEE REQUEST NEVER AUTO-ENTERS SALARY SLIP
    # ---------------------------------------------------------

    def test_reg_050_employee_request_not_automatic(self):
        from ao_payroll.payroll import holiday_allowance

        settings = frappe._dict({
            "custom_holiday_allowance_payment_mode":
                "Employee Request",
        })

        with patch(
            "ao_payroll.payroll.holiday_allowance."
            "get_payroll_settings",
            return_value=settings,
        ):
            result = (
                holiday_allowance
                .calculate_salary_slip_holiday_allowance(
                    employee="TEST-EMP",
                    base_salary=1000000,
                    payroll_start_date="2026-04-01",
                    payroll_end_date="2026-04-30",
                )
            )

        self.assertEqual(
            flt(result["amount"]),
            0,
        )

        self.assertEqual(
            result["payment_mode"],
            "Employee Request",
        )

        self.assertEqual(
            result["source_leave_applications"],
            [],
        )


    # ---------------------------------------------------------
    # REG-051 — HOLIDAY REQUEST DRAFT CALCULATION
    # ---------------------------------------------------------

    def test_reg_051_holiday_request_draft_calculation(self):
        from ao_payroll.angola_payroll.doctype.pedido_subsidio_ferias.pedido_subsidio_ferias import (
            PedidoSubsidioFerias,
        )

        doc = PedidoSubsidioFerias({
            "doctype": "Pedido Subsidio Ferias",
            "employee": "TEST-EMP",
            "entitlement_year": 2026,
            "payroll_date": "2026-04-30",
            "requested_amount": 200000,
        })

        settings = frappe._dict({
            "custom_holiday_allowance_payment_mode":
                "Employee Request",
        })

        assignment = frappe._dict({
            "name": "TEST-SSA-001",
            "base": 1000000,
        })

        request_result = {
            "annual_entitlement": 500000.0,
            "paid": 100000.0,
            "remaining": 400000.0,
            "payable_amount": 200000.0,
            "request_capped": False,
        }

        with (
            patch(
                "ao_payroll.angola_payroll.doctype."
                "pedido_subsidio_ferias.pedido_subsidio_ferias."
                "get_payroll_settings",
                return_value=settings,
            ),
            patch(
                "ao_payroll.angola_payroll.doctype."
                "pedido_subsidio_ferias.pedido_subsidio_ferias."
                "frappe.db.get_value",
                return_value=assignment,
            ),
            patch(
                "ao_payroll.angola_payroll.doctype."
                "pedido_subsidio_ferias.pedido_subsidio_ferias."
                "holiday_allowance."
                "calculate_employee_request_holiday_allowance",
                return_value=request_result,
            ),
        ):
            doc.validate()

        self.assertEqual(
            doc.salary_structure_assignment,
            "TEST-SSA-001",
        )

        self.assertAlmostEqual(
            flt(doc.base_salary),
            1000000.0,
            places=2,
        )

        self.assertAlmostEqual(
            flt(doc.annual_entitlement),
            500000.0,
            places=2,
        )

        self.assertAlmostEqual(
            flt(doc.already_paid),
            100000.0,
            places=2,
        )

        self.assertAlmostEqual(
            flt(doc.remaining_before_request),
            400000.0,
            places=2,
        )

        self.assertAlmostEqual(
            flt(doc.approved_amount),
            200000.0,
            places=2,
        )


    # ---------------------------------------------------------
    # REG-052 — HOLIDAY REQUEST ABOVE BALANCE IS BLOCKED
    # ---------------------------------------------------------

    def test_reg_052_holiday_request_above_balance_blocked(self):
        from ao_payroll.angola_payroll.doctype.pedido_subsidio_ferias.pedido_subsidio_ferias import (
            PedidoSubsidioFerias,
        )

        doc = PedidoSubsidioFerias({
            "doctype": "Pedido Subsidio Ferias",
            "employee": "TEST-EMP",
            "entitlement_year": 2026,
            "payroll_date": "2026-04-30",
            "requested_amount": 600000,
            "base_salary": 1000000,
        })

        request_result = {
            "annual_entitlement": 500000.0,
            "paid": 0.0,
            "remaining": 500000.0,
            "payable_amount": 500000.0,
            "request_capped": True,
        }

        with patch(
            "ao_payroll.angola_payroll.doctype."
            "pedido_subsidio_ferias.pedido_subsidio_ferias."
            "holiday_allowance."
            "calculate_employee_request_holiday_allowance",
            return_value=request_result,
        ):
            with self.assertRaises(
                frappe.ValidationError
            ):
                doc._calculate_request()


    # ---------------------------------------------------------
    # REG-053 — SUBMIT CREATES ONE ADDITIONAL SALARY
    # ---------------------------------------------------------

    def test_reg_053_holiday_request_creates_additional_salary(self):
        from ao_payroll.angola_payroll.doctype.pedido_subsidio_ferias.pedido_subsidio_ferias import (
            PedidoSubsidioFerias,
        )

        doc = PedidoSubsidioFerias({
            "doctype": "Pedido Subsidio Ferias",
            "name": "TEST-PSF-001",
            "employee": "TEST-EMP",
            "payroll_date": "2026-04-30",
            "approved_amount": 200000,
        })

        settings = frappe._dict({
            "holyday_allowance_salary_component":
                "Subsidio de Ferias",
        })

        additional = MagicMock()
        additional.name = "TEST-ADS-001"

        doc.db_set = MagicMock()

        with (
            patch(
                "ao_payroll.angola_payroll.doctype."
                "pedido_subsidio_ferias.pedido_subsidio_ferias."
                "get_payroll_settings",
                return_value=settings,
            ),
            patch(
                "ao_payroll.angola_payroll.doctype."
                "pedido_subsidio_ferias.pedido_subsidio_ferias."
                "frappe.db.get_value",
                return_value=None,
            ),
            patch(
                "ao_payroll.angola_payroll.doctype."
                "pedido_subsidio_ferias.pedido_subsidio_ferias."
                "frappe.new_doc",
                return_value=additional,
            ),
        ):
            doc._create_additional_salary()

        self.assertEqual(
            additional.employee,
            "TEST-EMP",
        )

        self.assertEqual(
            additional.salary_component,
            "Subsidio de Ferias",
        )

        self.assertEqual(
            getdate(additional.payroll_date),
            getdate("2026-04-30"),
        )

        self.assertAlmostEqual(
            flt(additional.amount),
            200000.0,
            places=2,
        )

        self.assertEqual(
            additional.ref_doctype,
            "Pedido Subsidio Ferias",
        )

        self.assertEqual(
            additional.ref_docname,
            "TEST-PSF-001",
        )

        additional.insert.assert_called_once()
        additional.submit.assert_called_once()

        doc.db_set.assert_called_once_with(
            "additional_salary",
            "TEST-ADS-001",
            update_modified=False,
        )


    # ---------------------------------------------------------
    # REG-054 — DUPLICATE REQUEST GENERATION IS BLOCKED
    # ---------------------------------------------------------

    def test_reg_054_holiday_request_duplicate_additional_salary_blocked(self):
        from ao_payroll.angola_payroll.doctype.pedido_subsidio_ferias.pedido_subsidio_ferias import (
            PedidoSubsidioFerias,
        )

        doc = PedidoSubsidioFerias({
            "doctype": "Pedido Subsidio Ferias",
            "name": "TEST-PSF-002",
            "employee": "TEST-EMP",
            "payroll_date": "2026-04-30",
            "approved_amount": 200000,
        })

        settings = frappe._dict({
            "holyday_allowance_salary_component":
                "Subsidio de Ferias",
        })

        with (
            patch(
                "ao_payroll.angola_payroll.doctype."
                "pedido_subsidio_ferias.pedido_subsidio_ferias."
                "get_payroll_settings",
                return_value=settings,
            ),
            patch(
                "ao_payroll.angola_payroll.doctype."
                "pedido_subsidio_ferias.pedido_subsidio_ferias."
                "frappe.db.get_value",
                return_value="TEST-ADS-EXISTING",
            ),
        ):
            with self.assertRaises(
                frappe.ValidationError
            ):
                doc._create_additional_salary()


    # ---------------------------------------------------------
    # REG-055 — CANCELLING REQUEST CANCELS ADDITIONAL SALARY
    # ---------------------------------------------------------

    def test_reg_055_holiday_request_cancel_cascades(self):
        from ao_payroll.angola_payroll.doctype.pedido_subsidio_ferias.pedido_subsidio_ferias import (
            PedidoSubsidioFerias,
        )

        doc = PedidoSubsidioFerias({
            "doctype": "Pedido Subsidio Ferias",
            "name": "TEST-PSF-003",
            "additional_salary": "TEST-ADS-003",
        })

        additional = MagicMock()
        additional.docstatus = 1

        with (
            patch(
                "ao_payroll.angola_payroll.doctype."
                "pedido_subsidio_ferias.pedido_subsidio_ferias."
                "frappe.db.exists",
                return_value=True,
            ),
            patch(
                "ao_payroll.angola_payroll.doctype."
                "pedido_subsidio_ferias.pedido_subsidio_ferias."
                "frappe.get_doc",
                return_value=additional,
            ),
        ):
            doc._cancel_additional_salary()

        additional.cancel.assert_called_once()


    # ---------------------------------------------------------
    # REG-021 — EMPLOYEE REMAINS ACTIVE THROUGH EXIT DATE
    # ---------------------------------------------------------

    @patch("ao_payroll.tasks.frappe.get_doc")
    @patch("ao_payroll.tasks.frappe.get_all")
    def test_reg_021_employee_active_through_exit_date(
        self,
        mock_get_all,
        mock_get_doc,
    ):
        """
        On the actual termination date the employee must
        still remain payroll-valid.

        The query uses data_saida < current_date, therefore
        a 30 September termination is not processed on
        30 September.
        """

        mock_get_all.return_value = []

        process_employee_cessations(
            reference_date="2026-09-30"
        )

        mock_get_all.assert_called_once()

        filters = (
            mock_get_all.call_args.kwargs[
                "filters"
            ]
        )

        self.assertEqual(
            filters["docstatus"],
            1,
        )

        self.assertEqual(
            filters["data_saida"][0],
            "<",
        )

        self.assertEqual(
            str(filters["data_saida"][1]),
            "2026-09-30",
        )

        # No Employee should be touched because the exit
        # date itself is still payroll-valid.
        mock_get_doc.assert_not_called()


    # ---------------------------------------------------------
    # REG-022 — EMPLOYEE LEFT DAY AFTER EXIT
    # ---------------------------------------------------------

    @patch("ao_payroll.tasks.frappe.get_doc")
    @patch("ao_payroll.tasks.frappe.get_all")
    def test_reg_022_employee_left_after_exit_date(
        self,
        mock_get_all,
        mock_get_doc,
    ):
        """
        A termination dated 30 September must be processed
        from 1 October onwards.
        """

        cessation = frappe._dict(
            {
                "name": "REG-TEST-CESSATION",
                "funcionario": "REG-TEST-EMPLOYEE",
                "data_saida": "2026-09-30",
            }
        )

        mock_get_all.return_value = [
            cessation
        ]

        employee = MagicMock()
        employee.status = "Active"
        employee.relieving_date = None

        mock_get_doc.return_value = employee

        process_employee_cessations(
            reference_date="2026-10-01"
        )

        mock_get_doc.assert_called_once_with(
            "Employee",
            "REG-TEST-EMPLOYEE",
        )

        self.assertEqual(
            employee.status,
            "Left",
        )

        self.assertEqual(
            employee.relieving_date,
            "2026-09-30",
        )

        employee.save.assert_called_once_with(
            ignore_permissions=True
        )


    # ---------------------------------------------------------
    # REG-014 — AUTOMATIC PROPORTIONAL SALARY
    # ---------------------------------------------------------

    def test_reg_014_termination_proportional_salary(self):
        doc = frappe.get_doc(
            "Cessacao Contrato",
            self.TERMINATION,
        )

        # Force the normal calculation path in memory only.
        doc.custom_calculo_alterado = 0
        doc.calcular()

        self.assertAlmostEqual(
            flt(doc.salario_proporcional),
            1050000.00,
            places=2,
            msg=(
                "REG-014: automatic proportional salary "
                "for Vanessa changed."
            ),
        )


    # ---------------------------------------------------------
    # REG-015 — PROPORTIONAL HOLIDAY ALLOWANCE
    # ---------------------------------------------------------

    def test_reg_015_termination_holiday_proportional(self):
        doc = frappe.get_doc(
            "Cessacao Contrato",
            self.TERMINATION,
        )

        doc.custom_calculo_alterado = 0

        with patch(
            "ao_payroll.angola_payroll.doctype."
            "cessacao_contrato.cessacao_contrato."
            "calculator.get_holiday_allowance_paid",
            return_value=0,
        ):
            doc.calcular()

        self.assertAlmostEqual(
            flt(doc.subsidio_de_ferias_proporcional),
            393750.00,
            places=2,
            msg=(
                "REG-015: proportional holiday allowance "
                "before prior payment changed."
            ),
        )

        with patch(
            "ao_payroll.angola_payroll.doctype."
            "cessacao_contrato.cessacao_contrato."
            "calculator.get_holiday_allowance_paid",
            return_value=393750.00,
        ):
            doc.calcular()

        self.assertAlmostEqual(
            flt(doc.subsidio_de_ferias_proporcional),
            0.00,
            places=2,
            msg=(
                "REG-015: previously paid holiday allowance "
                "must reduce termination settlement."
            ),
        )


    # ---------------------------------------------------------
    # REG-016 — PROPORTIONAL CHRISTMAS ALLOWANCE
    # ---------------------------------------------------------

    def test_reg_016_termination_christmas_proportional(self):
        doc = frappe.get_doc(
            "Cessacao Contrato",
            self.TERMINATION,
        )

        doc.custom_calculo_alterado = 0

        with patch(
            "ao_payroll.angola_payroll.doctype."
            "cessacao_contrato.cessacao_contrato."
            "calculator.get_christmas_allowance_paid",
            return_value=0,
        ):
            doc.calcular()

        self.assertAlmostEqual(
            flt(doc.subsidio_natal_proporcional),
            393750.00,
            places=2,
            msg=(
                "REG-016: proportional Christmas allowance "
                "before prior payment changed."
            ),
        )

        with patch(
            "ao_payroll.angola_payroll.doctype."
            "cessacao_contrato.cessacao_contrato."
            "calculator.get_christmas_allowance_paid",
            return_value=393750.00,
        ):
            doc.calcular()

        self.assertAlmostEqual(
            flt(doc.subsidio_natal_proporcional),
            0.00,
            places=2,
            msg=(
                "REG-016: previously paid Christmas allowance "
                "must reduce termination settlement."
            ),
        )


    # ---------------------------------------------------------
    # REG-017 — AUTHORIZED OVERRIDE PRESERVATION
    # ---------------------------------------------------------

    def test_reg_017_termination_override_preserves_manual_value(self):
        doc = frappe.get_doc(
            "Cessacao Contrato",
            self.TERMINATION,
        )

        doc.custom_calculo_alterado = 1

        doc.salario_proporcional = 2500000.00
        doc.subsidio_de_ferias_proporcional = 393750.00
        doc.subsidio_natal_proporcional = 393750.00
        doc.valor_ferias_nao_gozadas = 0

        doc.calcular()

        self.assertAlmostEqual(
            flt(doc.salario_proporcional),
            2500000.00,
            places=2,
            msg=(
                "REG-017: manual termination salary "
                "was overwritten by calcular()."
            ),
        )

        self.assertAlmostEqual(
            flt(doc.subsidio_de_ferias_proporcional),
            393750.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(doc.subsidio_natal_proporcional),
            393750.00,
            places=2,
        )


    # ---------------------------------------------------------
    # REG-018 — OVERRIDE RECALCULATES DOWNSTREAM RESULTS
    # ---------------------------------------------------------

    def test_reg_018_termination_override_recalculates_statutory_results(self):
        doc = frappe.get_doc(
            "Cessacao Contrato",
            self.TERMINATION,
        )

        # These values were approved and submitted.
        expected = {
            "total_iliquido":
                flt(doc.total_iliquido),

            "base_inss":
                flt(doc.base_inss),

            "inss":
                flt(doc.inss),

            "base_irt":
                flt(doc.base_irt),

            "irt":
                flt(doc.irt),

            "total_descontos":
                flt(doc.total_descontos),

            "valor_liquido":
                flt(doc.valor_liquido),
        }

        self.assertEqual(
            doc.custom_calculo_alterado,
            1,
            (
                "REG-018 baseline must remain the "
                "approved override document."
            ),
        )

        # Re-run the engine. Manual objective amounts must
        # remain, but statutory results must be reproducible.
        doc.calcular()

        for fieldname, expected_value in expected.items():
            self.assertAlmostEqual(
                flt(doc.get(fieldname)),
                expected_value,
                places=2,
                msg=(
                    f"REG-018 regression in "
                    f"{fieldname}"
                ),
            )

        # Gross must reconcile with the objective earnings
        # plus the approved additional earning.
        self.assertAlmostEqual(
            flt(doc.total_iliquido),
            3337500.00,
            places=2,
        )

        # INSS incidence base is:
        # Proportional Salary
        # + Proportional Christmas Allowance
        # + Salário Vincendo
        self.assertAlmostEqual(
            flt(doc.base_inss),
            2943750.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(doc.inss),
            88312.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(doc.base_irt),
            2855438.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(doc.total_iliquido)
            - flt(doc.total_descontos),
            flt(doc.valor_liquido),
            places=2,
        )


    # ---------------------------------------------------------
    # REG-019 — ADDITIONAL SALARY HANDOFF
    # ---------------------------------------------------------

    def test_reg_019_termination_additional_salary_handoff(self):
        rows = frappe.get_all(
            "Additional Salary",
            filters={
                "ref_doctype":
                    "Cessacao Contrato",

                "ref_docname":
                    self.TERMINATION,

                "docstatus": 1,
            },
            fields=[
                "salary_component",
                "amount",
                "payroll_date",
            ],
            order_by="creation asc",
        )

        expected = {
            "Proporcional Salario":
                2500000.00,

            "Proporcional Subsidio Ferias":
                393750.00,

            "Proporcional Subsidio Natal":
                393750.00,

            "Salário Vincendo":
                50000.00,

            "Indemnização por Falta Aviso Prévio":
                50000.00,
        }

        actual = {
            row.salary_component:
                flt(row.amount)
            for row in rows
        }

        self.assertEqual(
            set(actual),
            set(expected),
            (
                "REG-019: termination payroll "
                "handoff component set changed."
            ),
        )

        for component, expected_amount in expected.items():
            self.assertAlmostEqual(
                actual[component],
                expected_amount,
                places=2,
            )

        for row in rows:
            self.assertEqual(
                str(row.payroll_date),
                "2026-09-30",
            )


    # ---------------------------------------------------------
    # REG-020 — NO STATUTORY ADDITIONAL SALARY
    # ---------------------------------------------------------

    def test_reg_020_no_inss_irt_additional_salary(self):
        rows = frappe.get_all(
            "Additional Salary",
            filters={
                "ref_doctype":
                    "Cessacao Contrato",

                "ref_docname":
                    self.TERMINATION,

                "docstatus": 1,

                "salary_component": [
                    "in",
                    [
                        "Seguranca Social",
                        "Segurança Social-D01",
                        "Imposto Sobre o Rendimento do Trabalho",
                        "IRT-D02",
                    ],
                ],
            },
            pluck="salary_component",
        )

        self.assertEqual(
            rows,
            [],
            (
                "REG-020: INSS/IRT must be generated "
                "by Salary Slip, never transferred "
                "as Additional Salary."
            ),
        )


    def test_vanessa_termination_calculation_is_stable(self):
        """
        Characterization test.

        The submitted settlement is our approved baseline.
        Re-running the calculator must reproduce exactly the same
        payroll values.
        """

        doc = frappe.get_doc(
            "Cessacao Contrato",
            self.TERMINATION,
        )

        self.assertEqual(
            doc.docstatus,
            1,
            "Regression baseline must be a submitted document.",
        )

        expected = {
            "salario_proporcional":
                flt(doc.salario_proporcional),

            "subsidio_de_ferias_proporcional":
                flt(doc.subsidio_de_ferias_proporcional),

            "subsidio_natal_proporcional":
                flt(doc.subsidio_natal_proporcional),

            "valor_ferias_nao_gozadas":
                flt(doc.valor_ferias_nao_gozadas),

            "total_iliquido":
                flt(doc.total_iliquido),

            "base_inss":
                flt(doc.base_inss),

            "inss":
                flt(doc.inss),

            "base_irt":
                flt(doc.base_irt),

            "irt":
                flt(doc.irt),

            "total_descontos":
                flt(doc.total_descontos),

            "valor_liquido":
                flt(doc.valor_liquido),
        }

        # Recalculate without saving the submitted document.
        doc.calcular()

        for fieldname, expected_value in expected.items():
            actual_value = flt(
                doc.get(fieldname)
            )

            self.assertAlmostEqual(
                actual_value,
                expected_value,
                places=2,
                msg=(
                    f"Payroll regression in {fieldname}: "
                    f"expected {expected_value}, "
                    f"got {actual_value}"
                ),
            )

    def test_vanessa_termination_additional_salary_handoff(self):
        """
        Cessacao Contrato must transfer settlement components
        into submitted Additional Salary records.
        """

        records = frappe.get_all(
            "Additional Salary",
            filters={
                "ref_doctype":
                    "Cessacao Contrato",

                "ref_docname":
                    self.TERMINATION,

                "docstatus": 1,
            },
            fields=[
                "salary_component",
                "amount",
                "payroll_date",
            ],
        )

        by_component = {
            row.salary_component: flt(row.amount)
            for row in records
        }

        expected = {
            "Proporcional Salario":
                2500000.00,

            "Proporcional Subsidio Ferias":
                393750.00,

            "Proporcional Subsidio Natal":
                393750.00,

            "Salário Vincendo":
                50000.00,

            "Indemnização por Falta Aviso Prévio":
                50000.00,
        }

        self.assertEqual(
            set(by_component),
            set(expected),
            (
                "Additional Salary component set changed. "
                f"Expected {set(expected)}, "
                f"got {set(by_component)}"
            ),
        )

        for component, expected_amount in expected.items():
            self.assertAlmostEqual(
                by_component[component],
                expected_amount,
                places=2,
                msg=(
                    f"Incorrect Additional Salary amount "
                    f"for {component}"
                ),
            )

        for row in records:
            self.assertEqual(
                str(row.payroll_date),
                "2026-09-30",
            )

    def test_statutory_results_are_not_additional_salary(self):
        """
        INSS and IRT are calculated by Salary Slip.
        They must never be transferred as termination
        Additional Salary records.
        """

        statutory_components = frappe.get_all(
            "Additional Salary",
            filters={
                "ref_doctype":
                    "Cessacao Contrato",

                "ref_docname":
                    self.TERMINATION,

                "salary_component": [
                    "in",
                    [
                        "Seguranca Social",
                        "Imposto Sobre o Rendimento do Trabalho",
                    ],
                ],
            },
            pluck="salary_component",
        )

        self.assertEqual(
            statutory_components,
            [],
            (
                "INSS/IRT must not be created as "
                "Additional Salary."
            ),
        )


    # ---------------------------------------------------------
    # REG-056 — CHRISTMAS ALLOWANCE FIXED MONTH
    # ---------------------------------------------------------

    def test_reg_056_christmas_allowance_fixed_month(self):
        from ao_payroll.payroll import christmas_allowance

        settings = frappe._dict({
            "christmas_allowance_rate": 50,
            "custom_christmas_allowance_payment_mode":
                "Fixed Month",
            "custom_christmas_allowance_payment_month":
                "November",
            "custom_christmas_allowance_payment_blocks":
                [],
        })

        employee = frappe._dict({
            "date_of_joining": getdate("2020-01-01"),
            "relieving_date": None,
        })

        with (
            patch(
                "ao_payroll.payroll.christmas_allowance."
                "get_payroll_settings",
                return_value=settings,
            ),
            patch(
                "ao_payroll.payroll.christmas_allowance."
                "frappe.get_doc",
                return_value=employee,
            ),
            patch(
                "ao_payroll.payroll.christmas_allowance."
                "calculator.get_christmas_allowance_paid",
                return_value=0,
            ),
        ):
            result = (
                christmas_allowance
                .calculate_salary_slip_christmas_allowance(
                    employee="TEST-EMP",
                    base_salary=1100000,
                    payroll_start_date="2026-11-01",
                    payroll_end_date="2026-11-30",
                )
            )

        self.assertEqual(
            result["payment_mode"],
            "Fixed Month",
        )

        self.assertAlmostEqual(
            flt(result["annual_entitlement"]),
            550000.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["amount"]),
            550000.00,
            places=2,
        )


    # ---------------------------------------------------------
    # REG-057 — CHRISTMAS ALLOWANCE MONTHLY DUODECIMOS
    # ---------------------------------------------------------

    def test_reg_057_christmas_allowance_duodecimos(self):
        from ao_payroll.payroll import christmas_allowance

        settings = frappe._dict({
            "christmas_allowance_rate": 50,
            "custom_christmas_allowance_payment_mode":
                "Monthly Duodecimos",
            "custom_christmas_allowance_payment_month":
                "November",
            "custom_christmas_allowance_payment_blocks":
                [],
        })

        employee = frappe._dict({
            "date_of_joining": getdate("2020-01-01"),
            "relieving_date": None,
        })

        with (
            patch(
                "ao_payroll.payroll.christmas_allowance."
                "get_payroll_settings",
                return_value=settings,
            ),
            patch(
                "ao_payroll.payroll.christmas_allowance."
                "frappe.get_doc",
                return_value=employee,
            ),
            patch(
                "ao_payroll.payroll.christmas_allowance."
                "calculator.get_christmas_allowance_paid",
                return_value=0,
            ),
        ):
            result = (
                christmas_allowance
                .calculate_salary_slip_christmas_allowance(
                    employee="TEST-EMP",
                    base_salary=1100000,
                    payroll_start_date="2026-09-01",
                    payroll_end_date="2026-09-30",
                )
            )

        self.assertEqual(
            result["payment_mode"],
            "Monthly Duodecimos",
        )

        self.assertAlmostEqual(
            flt(result["annual_entitlement"]),
            550000.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["earned_to_date"]),
            412500.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["amount"]),
            412500.00,
            places=2,
        )


    # ---------------------------------------------------------
    # REG-058 — CHRISTMAS ALLOWANCE PAYMENT BLOCKS
    # ---------------------------------------------------------

    def test_reg_058_christmas_allowance_payment_blocks(self):
        from ao_payroll.payroll import christmas_allowance

        settings = frappe._dict({
            "christmas_allowance_rate": 50,
            "custom_christmas_allowance_payment_mode":
                "Payment Blocks",
            "custom_christmas_allowance_payment_month":
                "November",
            "custom_christmas_allowance_payment_blocks": [
                frappe._dict({
                    "month": "November",
                    "percentage": 50,
                }),
                frappe._dict({
                    "month": "December",
                    "percentage": 50,
                }),
            ],
        })

        employee = frappe._dict({
            "date_of_joining": getdate("2020-01-01"),
            "relieving_date": None,
        })

        with (
            patch(
                "ao_payroll.payroll.christmas_allowance."
                "get_payroll_settings",
                return_value=settings,
            ),
            patch(
                "ao_payroll.payroll.christmas_allowance."
                "frappe.get_doc",
                return_value=employee,
            ),
            patch(
                "ao_payroll.payroll.christmas_allowance."
                "calculator.get_christmas_allowance_paid",
                return_value=0,
            ),
        ):
            result = (
                christmas_allowance
                .calculate_salary_slip_christmas_allowance(
                    employee="TEST-EMP",
                    base_salary=1100000,
                    payroll_start_date="2026-11-01",
                    payroll_end_date="2026-11-30",
                )
            )

        self.assertEqual(
            result["payment_mode"],
            "Payment Blocks",
        )

        self.assertAlmostEqual(
            flt(result["block_percentage"]),
            50.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["annual_entitlement"]),
            550000.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["amount"]),
            275000.00,
            places=2,
        )


    # ---------------------------------------------------------
    # REG-059 — CHRISTMAS PRIOR PAYMENT PREVENTS DUPLICATION
    # ---------------------------------------------------------

    def test_reg_059_christmas_allowance_paid_balance(self):
        from ao_payroll.payroll import christmas_allowance

        settings = frappe._dict({
            "christmas_allowance_rate": 50,
            "custom_christmas_allowance_payment_mode":
                "Fixed Month",
            "custom_christmas_allowance_payment_month":
                "November",
            "custom_christmas_allowance_payment_blocks":
                [],
        })

        employee = frappe._dict({
            "date_of_joining": getdate("2020-01-01"),
            "relieving_date": None,
        })

        with (
            patch(
                "ao_payroll.payroll.christmas_allowance."
                "get_payroll_settings",
                return_value=settings,
            ),
            patch(
                "ao_payroll.payroll.christmas_allowance."
                "frappe.get_doc",
                return_value=employee,
            ),
            patch(
                "ao_payroll.payroll.christmas_allowance."
                "calculator.get_christmas_allowance_paid",
                return_value=550000,
            ),
        ):
            result = (
                christmas_allowance
                .calculate_salary_slip_christmas_allowance(
                    employee="TEST-EMP",
                    base_salary=1100000,
                    payroll_start_date="2026-11-01",
                    payroll_end_date="2026-11-30",
                )
            )

        self.assertAlmostEqual(
            flt(result["paid"]),
            550000.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["remaining"]),
            0.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["amount"]),
            0.00,
            places=2,
        )


    # ---------------------------------------------------------
    # REG-060 — TERMINATED EMPLOYEE CHRISTMAS ALREADY SETTLED
    # ---------------------------------------------------------

    def test_reg_060_terminated_employee_christmas_settled(self):
        from ao_payroll.payroll import christmas_allowance

        settings = frappe._dict({
            "christmas_allowance_rate": 50,
            "custom_christmas_allowance_payment_mode":
                "Fixed Month",
            "custom_christmas_allowance_payment_month":
                "November",
            "custom_christmas_allowance_payment_blocks":
                [],
        })

        employee = frappe._dict({
            "date_of_joining": getdate("2020-01-01"),
            "relieving_date": getdate("2026-09-30"),
        })

        with (
            patch(
                "ao_payroll.payroll.christmas_allowance."
                "get_payroll_settings",
                return_value=settings,
            ),
            patch(
                "ao_payroll.payroll.christmas_allowance."
                "frappe.get_doc",
                return_value=employee,
            ),
            patch(
                "ao_payroll.payroll.christmas_allowance."
                "calculator.get_christmas_allowance_paid",
                return_value=393750,
            ),
        ):
            result = (
                christmas_allowance
                .calculate_salary_slip_christmas_allowance(
                    employee="TEST-EMP",
                    base_salary=1050000,
                    payroll_start_date="2026-11-01",
                    payroll_end_date="2026-11-30",
                )
            )

        self.assertAlmostEqual(
            flt(result["annual_entitlement"]),
            393750.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["paid"]),
            393750.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["remaining"]),
            0.00,
            places=2,
        )

        self.assertAlmostEqual(
            flt(result["amount"]),
            0.00,
            places=2,
        )


# REG-HR-CONTRACT-001
def make_contract_employee():
    doc = frappe.new_doc("Employee")
    doc.employee_name = "Regression Contract Employee"
    doc.company = "HAMAD ENERGY"
    doc.date_of_joining = getdate("2026-01-01")
    doc.status = "Active"
    return doc


class TestAngolaEmploymentContract(unittest.TestCase):

    def test_fixed_term_requires_end_date(self):
        doc = make_contract_employee()
        doc.custom_contract_type = "Contrato por Tempo Determinado"
        doc.custom_contract_form = "Escrito"
        doc.custom_fixed_term_reason = "Substituição temporária"

        try:
            validate_employee_contract(doc)
            assert False
        except ValidationError as exc:
            assert "Contract End Date is mandatory" in str(exc)

    def test_fixed_term_requires_legal_reason(self):
        doc = make_contract_employee()
        doc.custom_contract_type = "Contrato por Tempo Determinado"
        doc.custom_contract_form = "Escrito"
        doc.contract_end_date = getdate("2026-12-31")

        try:
            validate_employee_contract(doc)
            assert False
        except ValidationError as exc:
            assert "Fixed-Term Legal Reason is mandatory" in str(exc)

    def test_fixed_term_requires_contract_form(self):
        doc = make_contract_employee()
        doc.custom_contract_type = "Contrato por Tempo Determinado"
        doc.custom_fixed_term_reason = "Substituição temporária"
        doc.contract_end_date = getdate("2026-12-31")

        try:
            validate_employee_contract(doc)
            assert False
        except ValidationError as exc:
            assert "Contract Form is mandatory" in str(exc)

    def test_contract_end_cannot_precede_joining(self):
        doc = make_contract_employee()
        doc.custom_contract_type = "Contrato por Tempo Determinado"
        doc.custom_contract_form = "Escrito"
        doc.custom_fixed_term_reason = "Substituição temporária"
        doc.contract_end_date = getdate("2025-12-31")

        try:
            validate_employee_contract(doc)
            assert False
        except ValidationError as exc:
            assert (
                "Contract End Date cannot be before Date of Joining"
                in str(exc)
            )

    def test_renewal_number_requires_date(self):
        doc = make_contract_employee()
        doc.custom_contract_type = "Contrato por Tempo Indeterminado"
        doc.custom_contract_renewal_number = 1

        try:
            validate_employee_contract(doc)
            assert False
        except ValidationError as exc:
            assert "Last Contract Renewal Date is mandatory" in str(exc)

    def test_renewal_date_requires_number(self):
        doc = make_contract_employee()
        doc.custom_contract_type = "Contrato por Tempo Indeterminado"
        doc.custom_contract_renewal_number = 0
        doc.custom_last_contract_renewal_date = getdate("2026-06-01")

        try:
            validate_employee_contract(doc)
            assert False
        except ValidationError as exc:
            assert "Contract Renewal Number must be greater than zero" in str(exc)

    @patch("frappe.msgprint")
    def test_verbal_fixed_term_warns_not_blocks(self, mock_msgprint):
        doc = make_contract_employee()
        doc.custom_contract_type = "Contrato por Tempo Determinado"
        doc.custom_contract_form = "Verbal"
        doc.custom_fixed_term_reason = "Legal exception test"
        doc.contract_end_date = getdate("2026-12-31")

        validate_employee_contract(doc)

        assert mock_msgprint.called

    def test_exception_report_expired_active_contract(self):
        employee = frappe._dict({
            "name": "TEST-EMP",
            "employee_name": "Test Employee",
            "status": "Active",
            "employment_type": "Full-time",
            "date_of_joining": getdate("2025-01-01"),
            "contract_end_date": getdate("2026-08-31"),
            "scheduled_confirmation_date": None,
            "final_confirmation_date": None,
            "relieving_date": None,
            "notice_number_of_days": 0,
            "custom_contract_type": "Contrato por Tempo Determinado",
            "custom_contract_form": "Escrito",
            "custom_fixed_term_reason": "Regression test",
            "custom_contract_renewal_number": 0,
            "custom_last_contract_renewal_date": None,
        })

        filters = frappe._dict({
            "as_of_date": "2026-09-06",
            "expiry_warning_days": 30,
        })

        rows = employment_contract_exceptions.evaluate_employee(
            employee,
            filters,
        )

        assert any(
            row["severity"] == "CRITICAL"
            and row["exception_type"] == "Expired Fixed-Term Contract"
            for row in rows
        )

    def test_exception_report_missing_classification(self):
        employee = frappe._dict({
            "name": "TEST-EMP",
            "employee_name": "Test Employee",
            "status": "Active",
            "employment_type": "Full-time",
            "date_of_joining": getdate("2025-01-01"),
            "contract_end_date": None,
            "scheduled_confirmation_date": None,
            "final_confirmation_date": None,
            "relieving_date": None,
            "notice_number_of_days": 0,
            "custom_contract_type": None,
            "custom_contract_form": None,
            "custom_fixed_term_reason": None,
            "custom_contract_renewal_number": 0,
            "custom_last_contract_renewal_date": None,
        })

        filters = frappe._dict({
            "as_of_date": "2026-09-06",
            "expiry_warning_days": 30,
        })

        rows = employment_contract_exceptions.evaluate_employee(
            employee,
            filters,
        )

        assert any(
            row["severity"] == "INFO"
            and row["exception_type"] == "Missing Contract Classification"
            for row in rows
        )


# REG-HR-LEAVE-DEFER-001
class TestDeferredLeavePayroll(unittest.TestCase):

    def _make_leave(self, process_next_month=0, salary_slip=None):
        return frappe._dict({
            "name": "TEST-LAP-001",
            "leave_type": "Leave Without Pay",
            "from_date": getdate("2026-01-20"),
            "to_date": getdate("2026-01-20"),
            "half_day": 0,
            "half_day_date": None,
            "total_leave_days": 1,
            "processar_mes_seguinte": process_next_month,
            "salary_slip": salary_slip,
        })

    @patch("frappe.get_all")
    @patch("frappe.db.get_value")
    @patch(
        "ao_payroll.payroll.calculator."
        "get_number_of_leave_days"
    )
    def test_normal_leave_processed_in_original_month(
        self,
        mock_leave_days,
        mock_get_value,
        mock_get_all,
    ):
        leave = self._make_leave(
            process_next_month=0
        )

        def fake_get_all(doctype, **kwargs):
            if doctype == "Leave Application":
                filters = kwargs.get("filters", {})

                if filters.get("processar_mes_seguinte") == 0:
                    return [leave]

                return []

            if doctype == "Attendance":
                return []

            return []

        mock_get_all.side_effect = fake_get_all

        mock_get_value.return_value = frappe._dict({
            "custom_deduz_salario": 1,
            "custom_deduz_subsidio_alimentacao": 1,
            "custom_deduz_subsidio_transporte": 1,
            "custom_afeta_premio_assiduidade": 1,
            "custom_recuperavel_do_inss": 0,
        })

        mock_leave_days.return_value = 1

        result = calculator.get_employee_attendance_effects(
            "TEST-EMP",
            "2026-01-01",
            "2026-01-31",
        )

        assert result["dias_falta_salario"] == 1
        assert len(result["leave_records"]) == 1
        assert (
            result["leave_records"][0][
                "deferred_to_current_payroll"
            ]
            is False
        )

    @patch("frappe.get_all")
    @patch("frappe.db.get_value")
    @patch(
        "ao_payroll.payroll.calculator."
        "get_number_of_leave_days"
    )
    def test_deferred_leave_not_processed_in_original_month(
        self,
        mock_leave_days,
        mock_get_value,
        mock_get_all,
    ):
        leave = self._make_leave(
            process_next_month=1
        )

        def fake_get_all(doctype, **kwargs):
            if doctype == "Leave Application":
                return []

            if doctype == "Attendance":
                return []

            return []

        mock_get_all.side_effect = fake_get_all

        result = calculator.get_employee_attendance_effects(
            "TEST-EMP",
            "2026-01-01",
            "2026-01-31",
        )

        assert result["dias_falta_salario"] == 0
        assert result["leave_records"] == []

    @patch("frappe.get_all")
    @patch("frappe.db.get_value")
    @patch(
        "ao_payroll.payroll.calculator."
        "get_number_of_leave_days"
    )
    def test_deferred_leave_processed_next_month(
        self,
        mock_leave_days,
        mock_get_value,
        mock_get_all,
    ):
        leave = self._make_leave(
            process_next_month=1
        )

        def fake_get_all(doctype, **kwargs):
            if doctype == "Leave Application":
                filters = kwargs.get("filters", {})

                if filters.get("processar_mes_seguinte") == 1:
                    return [leave]

                return []

            if doctype == "Attendance":
                return []

            return []

        mock_get_all.side_effect = fake_get_all

        mock_get_value.return_value = frappe._dict({
            "custom_deduz_salario": 1,
            "custom_deduz_subsidio_alimentacao": 1,
            "custom_deduz_subsidio_transporte": 1,
            "custom_afeta_premio_assiduidade": 1,
            "custom_recuperavel_do_inss": 0,
        })

        mock_leave_days.return_value = 1

        result = calculator.get_employee_attendance_effects(
            "TEST-EMP",
            "2026-02-01",
            "2026-02-28",
        )

        assert result["dias_falta_salario"] == 1
        assert len(result["leave_records"]) == 1

        record = result["leave_records"][0]

        assert record["processar_mes_seguinte"] is True
        assert (
            record["deferred_to_current_payroll"]
            is True
        )

        assert record["from_date"] == getdate(
            "2026-01-20"
        )

        assert record["to_date"] == getdate(
            "2026-01-20"
        )

    @patch("frappe.get_all")
    def test_deferred_leave_not_processed_two_months_later(
        self,
        mock_get_all,
    ):
        def fake_get_all(doctype, **kwargs):
            return []

        mock_get_all.side_effect = fake_get_all

        result = calculator.get_employee_attendance_effects(
            "TEST-EMP",
            "2026-03-01",
            "2026-03-31",
        )

        assert result["dias_falta_salario"] == 0
        assert result["leave_records"] == []

    @patch("frappe.get_all")
    def test_processed_leave_not_reprocessed(
        self,
        mock_get_all,
    ):
        def fake_get_all(doctype, **kwargs):
            return []

        mock_get_all.side_effect = fake_get_all

        result = calculator.get_employee_attendance_effects(
            "TEST-EMP",
            "2026-02-01",
            "2026-02-28",
        )

        assert result["leave_records"] == []
        assert result["dias_falta_salario"] == 0

    @patch("frappe.db.set_value")
    @patch("frappe.db.get_value")
    def test_salary_slip_submit_links_leave(
        self,
        mock_get_value,
        mock_set_value,
    ):
        from ao_payroll.overrides.salary_slip import AOSalarySlip

        slip = frappe.new_doc("Salary Slip")
        slip.name = "TEST-SLIP"
        slip.employee = "TEST-EMP"
        slip.start_date = getdate("2026-02-01")
        slip.end_date = getdate("2026-02-28")

        mock_get_value.return_value = frappe._dict({
            "to_date": getdate("2026-02-20"),
            "processar_mes_seguinte": 0,
            "salary_slip": None,
        })

        with patch(
            "ao_payroll.overrides.salary_slip."
            "calculator.get_employee_attendance_effects"
        ) as mock_effects:

            mock_effects.return_value = {
                "leave_records": [
                    {
                        "leave_application":
                            "TEST-LAP-001"
                    }
                ]
            }

            slip._ao_link_leave_applications()

        mock_set_value.assert_called_with(
            "Leave Application",
            "TEST-LAP-001",
            "salary_slip",
            "TEST-SLIP",
            update_modified=False,
        )

    @patch("frappe.db.set_value")
    @patch("frappe.get_all")
    def test_salary_slip_cancel_unlinks_leave(
        self,
        mock_get_all,
        mock_set_value,
    ):
        from ao_payroll.overrides.salary_slip import AOSalarySlip

        slip = frappe.new_doc("Salary Slip")
        slip.name = "TEST-SLIP"

        mock_get_all.return_value = [
            "TEST-LAP-001"
        ]

        slip._ao_unlink_leave_applications()

        mock_set_value.assert_called_with(
            "Leave Application",
            "TEST-LAP-001",
            "salary_slip",
            None,
            update_modified=False,
        )



# -------------------------------------------------------------------------
# REG-HR-LIFECYCLE-001
# Employee lifecycle transaction validation
# -------------------------------------------------------------------------

class TestHRLifecycleTransactions(unittest.TestCase):

    def _get_employee(self):
        employee = frappe.get_all(
            "Employee",
            filters={
                "date_of_joining": ["is", "set"],
            },
            fields=[
                "name",
                "date_of_joining",
                "relieving_date",
            ],
            limit=1,
        )

        if not employee:
            self.skipTest(
                "No Employee with Date of Joining available."
            )

        return employee[0]

    def test_reg_hr_lifecycle_001_valid_promotion_date(self):
        from ao_payroll.hr.employee_transactions import (
            validate_employee_promotion,
        )

        employee = self._get_employee()

        doc = frappe._dict({
            "employee": employee.name,
            "promotion_date": employee.date_of_joining,
        })

        validate_employee_promotion(doc)

    def test_reg_hr_lifecycle_002_promotion_before_joining_rejected(self):
        from frappe.utils import add_days
        from ao_payroll.hr.employee_transactions import (
            validate_employee_promotion,
        )

        employee = self._get_employee()

        doc = frappe._dict({
            "employee": employee.name,
            "promotion_date": add_days(
                employee.date_of_joining,
                -1,
            ),
        })

        with self.assertRaises(frappe.ValidationError):
            validate_employee_promotion(doc)

    def test_reg_hr_lifecycle_003_valid_transfer_date(self):
        from ao_payroll.hr.employee_transactions import (
            validate_employee_transfer,
        )

        employee = self._get_employee()

        doc = frappe._dict({
            "employee": employee.name,
            "transfer_date": employee.date_of_joining,
        })

        validate_employee_transfer(doc)

    def test_reg_hr_lifecycle_004_transfer_before_joining_rejected(self):
        from frappe.utils import add_days
        from ao_payroll.hr.employee_transactions import (
            validate_employee_transfer,
        )

        employee = self._get_employee()

        doc = frappe._dict({
            "employee": employee.name,
            "transfer_date": add_days(
                employee.date_of_joining,
                -1,
            ),
        })

        with self.assertRaises(frappe.ValidationError):
            validate_employee_transfer(doc)

    def test_reg_hr_lifecycle_005_transaction_exceptions_executes(self):
        from ao_payroll.angola_payroll.report.hr_transaction_exceptions.hr_transaction_exceptions import (
            execute,
        )

        columns, data = execute({})

        self.assertTrue(columns)
        self.assertIsInstance(data, list)
