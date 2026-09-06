frappe.query_reports["Payroll Exceptions Control"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            reqd: 1,
        },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.month_start(),
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.get_today(),
        },
        {
            fieldname: "employee",
            label: __("Employee"),
            fieldtype: "Link",
            options: "Employee",
            get_query: function () {
                return {
                    filters: {
                        company:
                            frappe.query_report.get_filter_value(
                                "company"
                            ),
                    },
                };
            },
        },
        {
            fieldname: "severity",
            label: __("Severity"),
            fieldtype: "Select",
            options: "\nCRITICAL\nWARNING\nINFO",
        },
        {
            fieldname: "exception_type",
            label: __("Exception Type"),
            fieldtype: "Select",
            options:
                "\nNo Active SSA" +
                "\nDuplicate SSA Effective Date" +
                "\nSalary Slip Without Payroll Entry" +
                "\nSubmitted Slip Without Journal Entry" +
                "\nPayroll Entry Without Submitted Slips" +
                "\nRelieved Employee Paid" +
                "\nNon-Positive Net Pay" +
                "\nManual Additional Salary" +
                "\nMissing INSS Component" +
                "\nMissing IRT Component" +
                "\nMissing Payroll Configuration" +
                "\nNew Employee" +
                "\nEmployee Leaving",
        },
    ],
};
