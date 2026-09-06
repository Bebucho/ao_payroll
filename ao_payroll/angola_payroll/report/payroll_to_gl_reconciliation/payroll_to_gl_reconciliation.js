frappe.query_reports["Payroll-to-GL Reconciliation"] = {
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
            fieldname: "payroll_entry",
            label: __("Payroll Entry"),
            fieldtype: "Link",
            options: "Payroll Entry",
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
            fieldname: "show",
            label: __("Show"),
            fieldtype: "Select",
            options: "All\nMismatches Only",
            default: "All",
        },
    ],
};
