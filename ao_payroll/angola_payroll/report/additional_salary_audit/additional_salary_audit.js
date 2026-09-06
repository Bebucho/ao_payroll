frappe.query_reports["Additional Salary Audit"] = {
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
            fieldname: "salary_component",
            label: __("Salary Component"),
            fieldtype: "Link",
            options: "Salary Component",
        },
        {
            fieldname: "ref_doctype",
            label: __("Reference Document Type"),
            fieldtype: "Link",
            options: "DocType",
        },
        {
            fieldname: "classification",
            label: __("Classification"),
            fieldtype: "Select",
            options:
                "\nMANUAL\nTERMINATION\nHOLIDAY REQUEST\nHR PROCESS\nRECURRING",
        },
        {
            fieldname: "show",
            label: __("Show"),
            fieldtype: "Select",
            options:
                "All\nManual Only\nReferenced Only",
            default: "All",
        },
    ],
};
