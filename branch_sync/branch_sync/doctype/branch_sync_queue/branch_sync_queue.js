frappe.ui.form.on("Branch Sync Queue", {
	refresh(frm) {
		if (frm.doc.status === "Failed") {
			frm.add_custom_button(__("Resync Now"), () => {
				frappe.call({
					method: "branch_sync.api.resync_one",
					args: { queue_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Resyncing…"),
					callback: (r) => {
						const status = r.message?.status;
						frappe.show_alert({
							message: status === "Synced"
								? __("Synced successfully")
								: __("Resync attempted — status: {0}", [status]),
							indicator: status === "Synced" ? "green" : "orange",
						});
						frm.reload_doc();
					},
				});
			});
		}
	},
});
