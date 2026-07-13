frappe.ui.form.on("Branch Sync Settings", {
	refresh(frm) {
		if (!frm.doc.is_setup_complete) return;

		frappe.call({
			method: "branch_sync.api.get_version_info",
			callback(r) {
				const d = r.message;
				if (!d || !d.ok) return;

				if (d.has_mismatch) {
					const rows = d.mismatch
						.map(
							(m) =>
								`<tr>
									<td><strong>${m.app}</strong></td>
									<td>${m.local}</td>
									<td>${m.center}</td>
								</tr>`
						)
						.join("");

					frm.dashboard.add_comment(
						`<div style="padding:4px 0">
							<strong>⚠️ Version Mismatch — Center vs Local</strong>
							<table class="table table-bordered table-sm" style="margin-top:8px;margin-bottom:0">
								<thead>
									<tr><th>App</th><th>Local</th><th>Center</th></tr>
								</thead>
								<tbody>${rows}</tbody>
							</table>
							<small class="text-muted">
								Consider updating local to match center to avoid field compatibility issues.
							</small>
						</div>`,
						"orange",
						true
					);
				} else {
					frm.dashboard.add_comment("✅ Local and center versions match.", "green", true);
				}
			},
		});
	},
});
