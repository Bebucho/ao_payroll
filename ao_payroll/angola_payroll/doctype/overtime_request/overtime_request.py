import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class OvertimeRequest(Document):

    def before_insert(self):
        if not self.requested_by:
            self.requested_by = frappe.session.user

    def validate(self):
        self.validate_employee()
        self.validate_hours()
        self.validate_overtime_date()
        self.validate_approval()
        self.validate_duplicate_request()

    def validate_employee(self):
        if not self.employee:
            return

        employee = frappe.db.get_value(
            "Employee",
            self.employee,
            [
                "status",
                "date_of_joining",
            ],
            as_dict=True,
        )

        if not employee:
            frappe.throw(
                _("Employee {0} does not exist.").format(
                    self.employee
                )
            )

        if employee.status not in (
            "Active",
            "Suspended",
        ):
            frappe.throw(
                _(
                    "Overtime Request cannot be created "
                    "for employee {0} with status {1}."
                ).format(
                    self.employee,
                    employee.status,
                )
            )

    def validate_hours(self):
        requested_hours = flt(
            self.requested_hours
        )

        approved_hours = flt(
            self.approved_hours
        )

        if requested_hours <= 0:
            frappe.throw(
                _("Requested Hours must be greater than zero.")
            )

        if approved_hours < 0:
            frappe.throw(
                _("Approved Hours cannot be negative.")
            )

        if (
            approved_hours
            and approved_hours > requested_hours
        ):
            frappe.throw(
                _(
                    "Approved Hours cannot exceed "
                    "Requested Hours."
                )
            )

    def validate_overtime_date(self):
        if (
            not self.employee
            or not self.overtime_date
        ):
            return

        joining_date = frappe.db.get_value(
            "Employee",
            self.employee,
            "date_of_joining",
        )

        if (
            joining_date
            and getdate(self.overtime_date)
            < getdate(joining_date)
        ):
            frappe.throw(
                _(
                    "Overtime Date cannot be before "
                    "the employee's Date of Joining."
                )
            )

    def validate_approval(self):
        if self.approval_status == "Approved":
            if not self.approver:
                frappe.throw(
                    _(
                        "Approver is mandatory when "
                        "Overtime Request is Approved."
                    )
                )

            if flt(self.approved_hours) <= 0:
                frappe.throw(
                    _(
                        "Approved Hours must be greater "
                        "than zero when Overtime Request "
                        "is Approved."
                    )
                )

        if self.approval_status == "Rejected":
            if not self.approver:
                frappe.throw(
                    _(
                        "Approver is mandatory when "
                        "Overtime Request is Rejected."
                    )
                )

    def validate_duplicate_request(self):
        if (
            not self.employee
            or not self.overtime_date
        ):
            return

        duplicate = frappe.db.get_value(
            "Overtime Request",
            {
                "employee": self.employee,
                "overtime_date": self.overtime_date,
                "docstatus": ["<", 2],
                "name": ["!=", self.name],
            },
            "name",
        )

        if duplicate:
            frappe.throw(
                _(
                    "An Overtime Request already exists "
                    "for employee {0} on {1}: {2}"
                ).format(
                    self.employee,
                    self.overtime_date,
                    duplicate,
                )
            )

    def before_submit(self):
        if self.approval_status != "Approved":
            frappe.throw(
                _(
                    "Only an Approved Overtime Request "
                    "can be submitted."
                )
            )
