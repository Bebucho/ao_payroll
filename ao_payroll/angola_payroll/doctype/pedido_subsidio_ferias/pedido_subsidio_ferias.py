import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate

from ao_payroll.payroll import holiday_allowance


class PedidoSubsidioFerias(Document):

    def validate(self):
        self._validate_policy()
        self._validate_dates()
        self._load_salary_assignment()
        self._calculate_request()

    def on_submit(self):
        self._create_additional_salary()

    def on_cancel(self):
        self._cancel_additional_salary()

    def _validate_policy(self):
        settings = frappe.get_single(
            "Angola Payroll Settings"
        )

        mode = getattr(
            settings,
            "custom_holiday_allowance_payment_mode",
            None,
        )

        if mode != "Employee Request":
            frappe.throw(
                "Pedido individual de Subsídio de Férias "
                "só é permitido quando o modo configurado é "
                "'Employee Request'."
            )

    def _validate_dates(self):
        payroll_date = getdate(
            self.payroll_date
        )

        if payroll_date.year != int(
            self.entitlement_year
        ):
            frappe.throw(
                "A Data de Processamento deve pertencer "
                "ao Ano de Direito."
            )

        if flt(self.requested_amount) <= 0:
            frappe.throw(
                "O Valor Solicitado deve ser superior a zero."
            )

    def _load_salary_assignment(self):
        assignment = frappe.db.get_value(
            "Salary Structure Assignment",
            {
                "employee": self.employee,
                "docstatus": 1,
                "from_date": [
                    "<=",
                    self.payroll_date,
                ],
            },
            [
                "name",
                "base",
            ],
            order_by="from_date desc, creation desc",
            as_dict=True,
        )

        if not assignment:
            frappe.throw(
                f"Não existe Salary Structure Assignment "
                f"activo para {self.employee} em "
                f"{self.payroll_date}."
            )

        self.salary_structure_assignment = (
            assignment.name
        )

        self.base_salary = flt(
            assignment.base,
            2,
        )

    def _get_reserved_amount(self):
        """
        Amount already approved through other submitted holiday
        requests but not yet consumed by a submitted Salary Slip.

        Submitted requests reserve entitlement immediately.
        Cancelled requests release the reservation.
        """
        requests = frappe.get_all(
            "Pedido Subsidio Ferias",
            filters={
                "employee": self.employee,
                "entitlement_year": self.entitlement_year,
                "docstatus": 1,
                "name": ["!=", self.name or ""],
            },
            fields=[
                "name",
                "approved_amount",
                "additional_salary",
                "payroll_date",
            ],
        )

        reserved = 0

        for request in requests:
            amount = flt(request.approved_amount)

            if amount <= 0:
                continue

            # A submitted Salary Slip covering the request payroll
            # date means the request has entered payroll and should
            # already be represented by the paid-balance calculation.
            paid_in_payroll = False

            if request.payroll_date:
                paid_in_payroll = bool(
                    frappe.db.exists(
                        "Salary Slip",
                        {
                            "employee": self.employee,
                            "docstatus": 1,
                            "start_date": ["<=", request.payroll_date],
                            "end_date": [">=", request.payroll_date],
                        },
                    )
                )

            if not paid_in_payroll:
                reserved += amount

        return flt(reserved, 2)

    def _calculate_request(self):
        result = (
            holiday_allowance
            .calculate_employee_request_holiday_allowance(
                employee=self.employee,
                year=self.entitlement_year,
                base_salary=self.base_salary,
                requested_amount=self.requested_amount,
                payroll_date=self.payroll_date,
            )
        )

        self.annual_entitlement = flt(
            result["annual_entitlement"],
            2,
        )

        self.already_paid = flt(
            result["paid"],
            2,
        )

        reserved = self._get_reserved_amount()

        self.remaining_before_request = flt(
            max(
                0,
                flt(result["remaining"]) - reserved,
            ),
            2,
        )

        if flt(self.requested_amount) > self.remaining_before_request:
            frappe.throw(
                "O valor solicitado excede o saldo disponível "
                "de Subsídio de Férias. "
                f"Solicitado: {flt(self.requested_amount, 2):,.2f}. "
                f"Disponível: "
                f"{flt(self.remaining_before_request, 2):,.2f}."
            )

        self.approved_amount = flt(
            min(
                flt(self.requested_amount),
                flt(self.remaining_before_request),
            ),
            2,
        )

        if self.approved_amount <= 0:
            frappe.throw(
                "O colaborador não possui saldo disponível "
                "de Subsídio de Férias para este ano."
            )

    def _create_additional_salary(self):
        settings = frappe.get_single(
            "Angola Payroll Settings"
        )

        component = getattr(
            settings,
            "holyday_allowance_salary_component",
            None,
        )

        if not component:
            frappe.throw(
                "Salary Component de Subsídio de Férias "
                "não configurado."
            )

        existing = frappe.db.get_value(
            "Additional Salary",
            {
                "employee": self.employee,
                "salary_component": component,
                "ref_doctype": self.doctype,
                "ref_docname": self.name,
                "docstatus": ["!=", 2],
            },
            "name",
        )

        if existing:
            frappe.throw(
                f"Este pedido já originou "
                f"Additional Salary {existing}."
            )

        additional = frappe.new_doc(
            "Additional Salary"
        )

        additional.employee = self.employee
        additional.salary_component = component
        additional.payroll_date = getdate(
            self.payroll_date
        )

        additional.amount = flt(
            self.approved_amount,
            2,
        )

        additional.ref_doctype = self.doctype
        additional.ref_docname = self.name

        additional.overwrite_salary_structure_amount = 0

        additional.insert()
        additional.submit()

        self.db_set(
            "additional_salary",
            additional.name,
            update_modified=False,
        )

    def _cancel_additional_salary(self):
        if not self.additional_salary:
            return

        if not frappe.db.exists(
            "Additional Salary",
            self.additional_salary,
        ):
            return

        additional = frappe.get_doc(
            "Additional Salary",
            self.additional_salary,
        )

        if additional.docstatus == 1:
            additional.cancel()
