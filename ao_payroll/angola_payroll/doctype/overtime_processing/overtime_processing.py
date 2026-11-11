import frappe
from ao_payroll.payroll.settings import get_payroll_settings
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class OvertimeProcessing(Document):

    def validate(self):
        self.validate_request()
        self.set_salary_component()
        self.validate_dates()
        self.validate_values()
        self.validate_duplicate_processing()
        self.calculate_amount()

    def validate_request(self):
        if not self.overtime_request:
            return

        request = frappe.get_doc(
            "Overtime Request",
            self.overtime_request,
        )

        if request.docstatus != 1:
            frappe.throw(
                _("Overtime Request must be submitted.")
            )

        if request.approval_status != "Approved":
            frappe.throw(
                _("Overtime Request must be Approved.")
            )

        if flt(request.approved_hours) <= 0:
            frappe.throw(
                _("Overtime Request has no approved hours.")
            )

        self.employee = request.employee
        self.employee_name = request.employee_name
        self.company = request.company
        self.department = request.department
        self.overtime_date = request.overtime_date
        self.approved_hours = request.approved_hours

    def set_salary_component(self):
        settings = get_payroll_settings(
            company=self.company,
            reference_date=self.overtime_date,
        )

        self.salary_component = (
            settings.overtime_salary_component
        )

        if not self.salary_component:
            frappe.throw(
                _(
                    "Overtime Salary Component is not configured "
                    "in Angola Payroll Settings."
                )
            )

    def validate_dates(self):
        if (
            self.overtime_date
            and self.payroll_date
            and getdate(self.payroll_date)
            < getdate(self.overtime_date)
        ):
            frappe.throw(
                _(
                    "Payroll Date cannot be before "
                    "Overtime Date."
                )
            )

        if not self.employee or not self.payroll_date:
            return

        relieving_date = frappe.db.get_value(
            "Employee",
            self.employee,
            "relieving_date",
        )

        if (
            relieving_date
            and getdate(self.payroll_date)
            > getdate(relieving_date)
        ):
            frappe.throw(
                _(
                    "Payroll Date cannot be after the "
                    "employee's Relieving Date."
                )
            )

    def validate_values(self):
        if flt(self.approved_hours) <= 0:
            frappe.throw(
                _("Approved Hours must be greater than zero.")
            )

        if flt(self.hourly_base) <= 0:
            frappe.throw(
                _("Hourly Base must be greater than zero.")
            )

        if flt(self.multiplier) <= 0:
            frappe.throw(
                _("Multiplier must be greater than zero.")
            )

        if not self.salary_component:
            frappe.throw(
                _("Salary Component is mandatory.")
            )

        component_type = frappe.db.get_value(
            "Salary Component",
            self.salary_component,
            "type",
        )

        if component_type != "Earning":
            frappe.throw(
                _(
                    "Overtime Salary Component must "
                    "be an Earning."
                )
            )

    def calculate_amount(self):
        self.calculated_amount = flt(
            flt(self.approved_hours)
            * flt(self.hourly_base)
            * flt(self.multiplier),
            2,
        )

    def validate_duplicate_processing(self):
        if not self.overtime_request:
            return

        duplicate = frappe.db.get_value(
            "Overtime Processing",
            {
                "overtime_request": self.overtime_request,
                "docstatus": ["<", 2],
                "name": ["!=", self.name],
            },
            "name",
        )

        if duplicate:
            frappe.throw(
                _(
                    "Overtime Request {0} is already "
                    "being processed in {1}."
                ).format(
                    self.overtime_request,
                    duplicate,
                )
            )

    def before_submit(self):
        self.set_salary_component()
        self.calculate_amount()

        if flt(self.calculated_amount) <= 0:
            frappe.throw(
                _("Calculated Amount must be greater than zero.")
            )

    def on_submit(self):
        additional_salary = self.create_additional_salary()

        self.db_set(
            "additional_salary",
            additional_salary.name,
            update_modified=False,
        )

    def on_cancel(self):
        if not self.additional_salary:
            return

        if not frappe.db.exists(
            "Additional Salary",
            self.additional_salary,
        ):
            return

        additional_salary = frappe.get_doc(
            "Additional Salary",
            self.additional_salary,
        )

        if additional_salary.docstatus == 1:
            additional_salary.cancel()

        self.db_set(
            "additional_salary",
            None,
            update_modified=False,
        )

    def create_additional_salary(self):
        existing = frappe.db.get_value(
            "Additional Salary",
            {
                "ref_doctype": "Overtime Processing",
                "ref_docname": self.name,
                "docstatus": ["<", 2],
            },
            "name",
        )

        if existing:
            frappe.throw(
                _(
                    "Additional Salary already exists "
                    "for this Overtime Processing: {0}"
                ).format(existing)
            )

        currency = frappe.db.get_value(
            "Company",
            self.company,
            "default_currency",
        )

        additional_salary = frappe.new_doc(
            "Additional Salary"
        )

        additional_salary.employee = self.employee
        additional_salary.company = self.company
        additional_salary.payroll_date = self.payroll_date
        additional_salary.salary_component = self.salary_component
        additional_salary.currency = currency
        additional_salary.amount = flt(
            self.calculated_amount
        )

        additional_salary.ref_doctype = (
            "Overtime Processing"
        )
        additional_salary.ref_docname = self.name

        additional_salary.insert()
        additional_salary.submit()

        return additional_salary
