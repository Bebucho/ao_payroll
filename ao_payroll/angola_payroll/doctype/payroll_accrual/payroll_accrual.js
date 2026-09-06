frappe.ui.form.on("Payroll Accrual", {
    refresh(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(
                __("Calculate"),
                async function () {
                    if (
                        !frm.doc.company ||
                        !frm.doc.year ||
                        !frm.doc.month
                    ) {
                        frappe.msgprint(
                            __(
                                "Select Company, Year and Month first."
                            )
                        );
                        return;
                    }

                    await frm.call(
                        "calculate"
                    );

                    frm.refresh_fields();

                    frappe.show_alert({
                        message: __(
                            "Payroll accrual calculated."
                        ),
                        indicator: "green",
                    });
                }
            );
        }

        if (
            frm.doc.docstatus === 1 &&
            frm.doc.journal_entry
        ) {
            frm.add_custom_button(
                __("Accounting Ledger"),
                function () {
                    frappe.set_route(
                        "query-report",
                        "General Ledger",
                        {
                            company: frm.doc.company,
                            voucher_no: frm.doc.journal_entry,
                            from_date: frm.doc.posting_date,
                            to_date: frm.doc.posting_date,
                        }
                    );
                },
                __("View")
            );
        }

        load_available_months(frm);
    },

    company(frm) {
        load_available_months(frm);
    },

    year(frm) {
        load_available_months(frm);
    },

    month(frm) {
        set_posting_date(frm);
    },
});


async function load_available_months(frm) {
    if (
        !frm.doc.company ||
        !frm.doc.year ||
        frm.doc.docstatus !== 0
    ) {
        return;
    }

    const response = await frappe.call({
        method:
            "ao_payroll.angola_payroll.doctype.payroll_accrual.payroll_accrual.get_available_months",
        args: {
            company: frm.doc.company,
            year: frm.doc.year,
        },
    });

    const months = response.message || [];

    frm.set_df_property(
        "month",
        "options",
        [""].concat(months).join("\n")
    );

    if (
        frm.doc.month &&
        !months.includes(frm.doc.month)
    ) {
        await frm.set_value(
            "month",
            null
        );
    }
}


function set_posting_date(frm) {
    const month_numbers = {
        January: 1,
        February: 2,
        March: 3,
        April: 4,
        May: 5,
        June: 6,
        July: 7,
        August: 8,
        September: 9,
        October: 10,
        November: 11,
        December: 12,
    };

    if (
        !frm.doc.year ||
        !frm.doc.month
    ) {
        return;
    }

    const month =
        month_numbers[frm.doc.month];

    const last_day =
        new Date(
            frm.doc.year,
            month,
            0
        ).getDate();

    const posting_date =
        String(frm.doc.year)
        + "-"
        + String(month).padStart(2, "0")
        + "-"
        + String(last_day).padStart(2, "0");

    frm.set_value(
        "posting_date",
        posting_date
    );
}
