import calendar
from datetime import date

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate

from ao_payroll.payroll import accruals


MONTHS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}


class PayrollAccrual(Document):

    def validate(self):
        self._set_posting_date()
        self._validate_month()
        self._validate_submitted_period()

    def before_submit(self):
        self._set_posting_date()
        self._validate_month()
        self._validate_submitted_period()

        # Recalculate at submission time.
        # The submitted document must represent the current ledger,
        # not a stale calculation made earlier.
        self.calculate()

        self.flags.ignore_validate_update_after_submit = True

    def on_submit(self):
        result = accruals.create_monthly_accrual_journal_entry(
            company=self.company,
            posting_date=self.posting_date,
        )

        if not result.get("journal_entry"):
            frappe.throw(
                _(
                    "There is no accrual movement to post "
                    "for this period."
                )
            )

        self.db_set(
            "journal_entry",
            result["journal_entry"],
            update_modified=False,
        )

        posting_date = getdate(
            self.posting_date
        )

        if posting_date.month == 12:
            reversal_date = date(
                posting_date.year + 1,
                1,
                1,
            )
        else:
            reversal_date = date(
                posting_date.year,
                posting_date.month + 1,
                1,
            )

        self.db_set(
            "reversal_date",
            reversal_date,
            update_modified=False,
        )

        reversal = accruals.create_reversal_journal_entry(
            journal_entry=result["journal_entry"],
            posting_date=reversal_date,
            payroll_accrual=self.name,
        )

        if reversal.get("journal_entry"):
            self.db_set(
                "reversal_journal_entry",
                reversal["journal_entry"],
                update_modified=False,
            )

    def on_cancel(self):
        # The reversal must be cancelled first. Otherwise cancelling
        # the accrual would leave an unsupported future accounting
        # movement in the ledger.
        if self.reversal_journal_entry and frappe.db.exists(
            "Journal Entry",
            self.reversal_journal_entry,
        ):
            reversal = frappe.get_doc(
                "Journal Entry",
                self.reversal_journal_entry,
            )

            if reversal.docstatus == 1:
                reversal.cancel()

        if self.journal_entry and frappe.db.exists(
            "Journal Entry",
            self.journal_entry,
        ):
            je = frappe.get_doc(
                "Journal Entry",
                self.journal_entry,
            )

            if je.docstatus == 1:
                je.cancel()

    def _set_posting_date(self):
        if not self.year or not self.month:
            return

        month_number = MONTHS.get(
            self.month
        )

        if not month_number:
            return

        last_day = calendar.monthrange(
            cint(self.year),
            month_number,
        )[1]

        self.posting_date = (
            f"{cint(self.year)}-"
            f"{month_number:02d}-"
            f"{last_day:02d}"
        )

    def _validate_month(self):
        if self.month and self.month not in MONTHS:
            frappe.throw(
                _("Invalid payroll accrual month.")
            )

    def _validate_submitted_period(self):
        if (
            not self.company
            or not self.year
            or not self.month
        ):
            return

        duplicate = frappe.db.get_value(
            "Payroll Accrual",
            {
                "company": self.company,
                "year": cint(self.year),
                "month": self.month,
                "docstatus": 1,
                "name": ["!=", self.name or ""],
            },
            "name",
        )

        if duplicate:
            frappe.throw(
                _(
                    "Payroll Accrual for {0} {1} "
                    "is already submitted as {2}."
                ).format(
                    self.month,
                    self.year,
                    duplicate,
                )
            )

    @frappe.whitelist()
    def calculate(self):
        self._set_posting_date()
        self._validate_month()
        self._validate_submitted_period()

        if not self.company:
            frappe.throw(
                _("Company is required.")
            )

        if not self.year:
            frappe.throw(
                _("Year is required.")
            )

        if not self.month:
            frappe.throw(
                _("Month is required.")
            )

        result = accruals.calculate_monthly_accrual(
            company=self.company,
            posting_date=self.posting_date,
        )

        self.holiday_target = flt(
            result["holiday_target"],
            2,
        )

        self.holiday_gl_balance = flt(
            result["holiday_gl_balance"],
            2,
        )

        self.holiday_movement = flt(
            result["holiday_movement"],
            2,
        )

        self.christmas_target = flt(
            result["christmas_target"],
            2,
        )

        self.christmas_gl_balance = flt(
            result["christmas_gl_balance"],
            2,
        )

        self.christmas_movement = flt(
            result["christmas_movement"],
            2,
        )

        self.set(
            "details",
            [],
        )

        for row in result["employees"]:
            employee_name = frappe.db.get_value(
                "Employee",
                row["employee"],
                "employee_name",
            )

            self.append(
                "details",
                {
                    "employee": row["employee"],
                    "employee_name": employee_name,
                    "salary_structure_assignment":
                        row.get(
                            "salary_structure_assignment"
                        ),
                    "base_salary":
                        row.get(
                            "base_salary"
                        ),
                    "earned_service_months":
                        row.get(
                            "earned_service_months"
                        ),
                    "holiday_earned":
                        row.get(
                            "holiday_earned"
                        ),
                    "holiday_paid":
                        row.get(
                            "holiday_paid"
                        ),
                    "holiday_target":
                        row.get(
                            "holiday_target"
                        ),
                    "christmas_earned":
                        row.get(
                            "christmas_earned"
                        ),
                    "christmas_paid":
                        row.get(
                            "christmas_paid"
                        ),
                    "christmas_target":
                        row.get(
                            "christmas_target"
                        ),
                },
            )

        return {
            "holiday_target":
                self.holiday_target,
            "holiday_gl_balance":
                self.holiday_gl_balance,
            "holiday_movement":
                self.holiday_movement,

            "christmas_target":
                self.christmas_target,
            "christmas_gl_balance":
                self.christmas_gl_balance,
            "christmas_movement":
                self.christmas_movement,

            "employees":
                len(self.details),
        }


@frappe.whitelist()
def get_available_months(
    company,
    year,
):
    """
    Return months that do not already have a submitted
    Payroll Accrual for company/year.
    """

    if not company or not year:
        return list(
            MONTHS.keys()
        )

    submitted = frappe.get_all(
        "Payroll Accrual",
        filters={
            "company": company,
            "year": cint(year),
            "docstatus": 1,
        },
        pluck="month",
    )

    submitted = set(
        submitted
    )

    return [
        month
        for month in MONTHS
        if month not in submitted
    ]
