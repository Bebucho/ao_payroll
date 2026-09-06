frappe.query_reports["Overtime Control"] = {
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
            fieldname: "approval_status",
            label: __("Approval Status"),
            fieldtype: "Select",
            options: "\nPending\nApproved\nRejected"
        },
        {
            fieldname: "control_status",
            label: __("Control Status"),
            fieldtype: "Select",
            options: "\nPending Approval\nApproved Not Submitted\nApproved Unprocessed\nProcessing Draft\nProcessed\nProcessed Missing Additional Salary\nMissing Additional Salary\nAdditional Salary Cancelled\nRejected\nCancelled\nReview"
        }
    ]
};
