frappe.query_reports["Salary Change Audit"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            reqd: 1,
            default: frappe.defaults.get_user_default("Company"),
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
            fieldname: "event_type",
            label: __("Event Type"),
            fieldtype: "Select",
            options:
                "\nSalary Change\nStructure Change\nCurrency Change\nNew Assignment\nAmendment",
        },
        {
            fieldname: "economic_changes_only",
            label: __("Show Only Economic Changes"),
            fieldtype: "Check",
            default: 1,
        },
        {
            fieldname: "use_creation_date",
            label: __("Use Creation Date Instead of Effective Date"),
            fieldtype: "Check",
            default: 0,
        },
    ],
};
