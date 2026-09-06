frappe.query_reports["Leave and Attendance Exceptions"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company"
        },
        {
            fieldname: "employee",
            label: __("Employee"),
            fieldtype: "Link",
            options: "Employee"
        },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date"
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date"
        },
        {
            fieldname: "as_of_date",
            label: __("As Of Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today()
        },
        {
            fieldname: "severity",
            label: __("Severity"),
            fieldtype: "Select",
            options: "\nCritical\nWarning\nInfo"
        },
        {
            fieldname: "exception_type",
            label: __("Exception Type"),
            fieldtype: "Select",
            options:
                "\nAbsent Without Tipo de Falta" +
                "\nOn Leave With Tipo de Falta" +
                "\nOn Leave Without Leave Application" +
                "\nApproved Leave Uses Inactive Leave Type" +
                "\nDeferred Leave Not Processed" +
                "\nMissing Salary Slip Reference" +
                "\nLeave Linked To Cancelled Salary Slip"
        }
    ]
};
