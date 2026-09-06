import frappe


def validate(doc, method=None):
    """
    Salary Slip validation hook for ao_payroll.
    Payroll calculation is handled by AOSalarySlip.calculate_net_pay().
    """
    pass
