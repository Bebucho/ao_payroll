frappe.query_reports["Payroll Month-on-Month Variance"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            reqd: 1,
        },
        {
            fieldname: "payroll_month",
            label: __("Payroll Month"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.month_start(),
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
            fieldname: "minimum_variance_percent",
            label: __("Minimum Variance %"),
            fieldtype: "Percent",
            default: 10,
        },
        {
            fieldname: "minimum_absolute_variance",
            label: __("Minimum Absolute Variance"),
            fieldtype: "Currency",
            default: 0,
        },
        {
            fieldname: "show",
            label: __("Show"),
            fieldtype: "Select",
            options:
                "All Employees\nVariances Only\nExceptions Only",
            default: "Variances Only",
        },
    ],
};
