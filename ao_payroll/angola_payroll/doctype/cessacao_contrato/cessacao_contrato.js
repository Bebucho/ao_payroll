// Copyright (c) 2026, AngolaERP and contributors
// For license information, please see license.txt

const calculated_fields = [
	"salario_proporcional",
	"subsidio_de_ferias_proporcional",
	"subsidio_natal_proporcional",
	"valor_ferias_nao_gozadas",
	"total_iliquido",
	"base_inss",
	"inss",
	"base_irt",
	"irt",
	"total_descontos",
	"valor_liquido"
];

function set_calculation_editability(frm) {
	const override = cint(frm.doc.custom_calculo_alterado);

	calculated_fields.forEach(fieldname => {
		frm.set_df_property(
			fieldname,
			"read_only",
			override ? 0 : 1
		);
	});

	frm.set_df_property(
		"custom_motivo_alteracao",
		"reqd",
		override ? 1 : 0
	);

	frm.set_df_property(
		"custom_motivo_alteracao",
		"read_only",
		override ? 0 : 1
	);

	frm.set_df_property(
		"custom_alterado_por",
		"read_only",
		1
	);

	frm.set_df_property(
		"custom_data",
		"read_only",
		1
	);

	frm.refresh_fields(calculated_fields);
	frm.refresh_field("custom_motivo_alteracao");
}


frappe.ui.form.on("Cessacao Contrato", {
	refresh(frm) {
		set_calculation_editability(frm);

		if (
			frm.doc.docstatus === 0
			&& !frm.is_new()
		) {
			frm.add_custom_button(__("Calcular"), async function () {
				try {
					const r = await frm.call("calcular");

					if (r.message) {
						await frm.refresh_fields();

						frappe.msgprint({
							title: __("Cálculo concluído"),
							message: `
								<b>Salário proporcional:</b>
								${format_currency(r.message.salario_proporcional)}<br>

								<b>Subsídio de férias proporcional:</b>
								${format_currency(r.message.subsidio_ferias_proporcional)}<br>

								<b>Subsídio de Natal proporcional:</b>
								${format_currency(r.message.subsidio_natal_proporcional)}<br>

								<b>Férias não gozadas:</b>
								${format_currency(r.message.valor_ferias_nao_gozadas)}<br>

								<b>Total Ilíquido:</b>
								${format_currency(r.message.total_iliquido)}<br>

								<b>INSS:</b>
								${format_currency(r.message.inss)}<br>

								<b>IRT:</b>
								${format_currency(r.message.irt)}<br>

								<b>Valor Líquido:</b>
								${format_currency(r.message.valor_liquido)}
							`,
							indicator: "green"
						});

						set_calculation_editability(frm);
					}
				} catch (e) {
					console.error(e);
				}
			});
		}
	},

	custom_calculo_alterado(frm) {
		set_calculation_editability(frm);
		frm.refresh();

		if (frm.doc.custom_calculo_alterado) {
			frm.set_value(
				"custom_alterado_por",
				frappe.session.user
			);

			frm.set_value(
				"custom_data",
				frappe.datetime.now_datetime()
			);

			frappe.msgprint({
				title: __("Alteração manual do cálculo"),
				message: __(
					"Os valores calculados foram desbloqueados. " +
					"Indique obrigatoriamente o motivo da alteração. " +
					"A submissão ficará sujeita à autorização definida no sistema."
				),
				indicator: "orange"
			});
		}
	}
});
