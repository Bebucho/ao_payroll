import frappe
from ao_payroll.payroll.settings import get_payroll_settings

from frappe.utils import flt
from hrms.payroll.doctype.payroll_entry.payroll_entry import PayrollEntry


class AOPayrollEntry(PayrollEntry):

    def should_add_component_to_accrual_jv(
        self,
        component_type,
        item,
    ):
        # Statistical/helper Salary Components are calculation
        # and reporting values only. They must never create GL.
        statistical_component = frappe.get_cached_value(
            "Salary Component",
            item["salary_component"],
            "statistical_component",
        )

        if statistical_component:
            return False

        return super().should_add_component_to_accrual_jv(
            component_type,
            item,
        )

    def get_employer_inss(self, submitted_salary_slips):
        """
        Calculate employer INSS directly from the same
        earnings incidence base used for employee INSS.

        Employer INSS is a company charge only:
        it must never affect employee net salary.
        """

        if not submitted_salary_slips:
            return {
                "base": 0,
                "rate": 0,
                "amount": 0,
            }

        settings = get_payroll_settings(
            company=self.company,
            reference_date=self.end_date,
        )

        rate = (
            flt(settings.inss_employer_rate)
            / 100
        )

        total_inss_base = 0
        total_employer_inss = 0

        for salary_slip in submitted_salary_slips:
            # The caller normally passes Salary Slip docs,
            # but tolerate names as well.
            if isinstance(salary_slip, str):
                salary_slip = frappe.get_doc(
                    "Salary Slip",
                    salary_slip,
                )

            employee_inss_base = 0

            for earning in salary_slip.earnings or []:
                if not earning.salary_component:
                    continue

                component = frappe.get_cached_value(
                    "Salary Component",
                    earning.salary_component,
                    [
                        "incidencia_inss",
                        "statistical_component",
                    ],
                    as_dict=True,
                )

                if not component:
                    continue

                # Statistical/helper components must never
                # form part of the employer INSS base.
                if component.statistical_component:
                    continue

                if component.incidencia_inss:
                    employee_inss_base += flt(
                        earning.amount
                    )

            total_inss_base += employee_inss_base

            # Employer INSS is rounded per employee,
            # matching payroll contribution granularity.
            total_employer_inss += round(
                employee_inss_base * rate
            )

        return {
            "base": flt(total_inss_base, 2),
            "rate": flt(rate),
            "amount": flt(total_employer_inss, 2),
        }

    def add_employer_inss_accounts(
        self,
        accounts,
        submitted_salary_slips,
    ):
        result = self.get_employer_inss(
            submitted_salary_slips
        )

        amount = flt(result["amount"])

        if amount <= 0:
            return

        settings = get_payroll_settings(
            company=self.company,
            reference_date=self.end_date,
        )

        expense_account = (
            settings.custom_inss_employer_expense_account
        )

        liability_account = (
            settings.custom_inss_liability_account
        )

        missing = []

        if not expense_account:
            missing.append(
                "Employer INSS Expense Account"
            )

        if not liability_account:
            missing.append(
                "INSS Liability Account"
            )

        if missing:
            frappe.throw(
                "Angola Payroll Settings is missing: "
                + ", ".join(missing)
            )

        # Employer INSS does NOT alter payroll payable.
        # It is a separate company expense/liability pair.
        accounts.append(
            {
                "account": expense_account,
                "debit_in_account_currency": amount,
                "credit_in_account_currency": 0,
                "exchange_rate": 1,
                "cost_center": self.cost_center,
            }
        )

        accounts.append(
            {
                "account": liability_account,
                "debit_in_account_currency": 0,
                "credit_in_account_currency": amount,
                "exchange_rate": 1,
            }
        )

        self._ao_employer_inss = result

    def make_journal_entry(
        self,
        accounts,
        currencies,
        payroll_payable_account=None,
        voucher_type="Journal Entry",
        user_remark="",
        submitted_salary_slips=None,
        submit_journal_entry=False,
        employee_wise_accounting_enabled=False,
    ):
        print("\n=== AO PAYROLL make_journal_entry ===")

        print("Accounts BEFORE:")
        for row in accounts:
            print(
                row.get("account"),
                "party_type=", row.get("party_type"),
                "party=", row.get("party"),
                "debit=", row.get("debit_in_account_currency"),
                "credit=", row.get("credit_in_account_currency"),
            )

        # Add employer INSS only to the payroll accrual JV.
        # submitted_salary_slips is supplied by
        # make_accrual_jv_entry().
        if (
            submitted_salary_slips
            and payroll_payable_account
            == self.payroll_payable_account
        ):
            self.add_employer_inss_accounts(
                accounts,
                submitted_salary_slips,
            )

        print("Accounts AFTER:")
        for row in accounts:
            print(
                row.get("account"),
                "party_type=", row.get("party_type"),
                "party=", row.get("party"),
                "debit=", row.get("debit_in_account_currency"),
                "credit=", row.get("credit_in_account_currency"),
            )

        return super().make_journal_entry(
            accounts=accounts,
            currencies=currencies,
            payroll_payable_account=payroll_payable_account,
            voucher_type=voucher_type,
            user_remark=user_remark,
            submitted_salary_slips=submitted_salary_slips,
            submit_journal_entry=submit_journal_entry,
            employee_wise_accounting_enabled=employee_wise_accounting_enabled,
        )
