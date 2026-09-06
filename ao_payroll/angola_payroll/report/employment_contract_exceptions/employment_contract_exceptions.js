frappe.query_reports["Employment Contract Exceptions"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            reqd: 1,
        },
        {
            fieldname: "as_of_date",
            label: __("As Of Date"),
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
                "\nExpired Fixed-Term Contract" +
                "\nFixed-Term Without End Date" +
                "\nFixed-Term Without Legal Reason" +
                "\nFixed-Term Verbal Contract" +
                "\nContract Expiring Soon" +
                "\nOverdue Confirmation" +
                "\nIndefinite Contract With End Date" +
                "\nRenewal Data Inconsistent" +
                "\nMissing Contract Classification",
        },
        {
            fieldname: "expiry_warning_days",
            label: __("Expiry Warning Days"),
            fieldtype: "Int",
            default: 30,
        },
    ],
};
