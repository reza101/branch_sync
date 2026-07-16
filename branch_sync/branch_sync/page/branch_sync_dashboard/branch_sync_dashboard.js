frappe.pages["branch-sync-dashboard"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Branch Sync Dashboard"),
		single_column: true,
	});

	const page = wrapper.page;

	page.add_action_item(__("Retry Failed"), () => {
		frappe.call({
			method: "branch_sync.api.retry_failed",
			callback: () => {
				frappe.show_alert({ message: __("Failed items reset to Pending"), indicator: "green" });
				dashboard.load();
			},
		});
	});

	page.add_action_item(__("Pull Master Data Now"), () => {
		frappe.show_alert({ message: __("Pulling…"), indicator: "blue" });
		frappe.call({
			method: "branch_sync.api.run_initial_pull",
			callback: () => {
				frappe.show_alert({ message: __("Pull complete"), indicator: "green" });
				dashboard.load();
			},
		});
	});

	page.add_action_item(__("Setup Wizard"), () => {
		frappe.set_route("branch-sync-setup");
	});

	page.add_action_item(__("View Log"), () => {
		frappe.set_route("List", "Branch Sync Log");
	});

	page.add_action_item(__("View Queue"), () => {
		frappe.set_route("List", "Branch Sync Queue");
	});

	const dashboard = new BranchSyncDashboard(wrapper);
	dashboard.load();

	// Auto-refresh every 30 seconds
	const interval = setInterval(() => dashboard.load(), 30000);
	$(wrapper).on("hide", () => clearInterval(interval));
};

class BranchSyncDashboard {
	constructor(wrapper) {
		this.body = $(wrapper).find(".layout-main-section");
	}

	load() {
		frappe.call({
			method: "branch_sync.api.get_dashboard_data",
			callback: (r) => {
				if (r.message) this.render(r.message);
			},
		});
	}

	render(d) {
		const connColor = d.connection_status === "Online" ? "green" : "red";
		const connIcon = d.connection_status === "Online" ? "✅" : "🔴";

		this.body.html(`
			<div style="max-width:900px;margin:24px auto;">

				<!-- Status Cards -->
				<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px;">
					${this.card(__("Connection"), `${connIcon} ${d.connection_status || "—"}`, connColor)}
					${this.card(__("Pending"), d.pending, d.pending > 0 ? "orange" : "gray")}
					${this.card(__("Failed"), d.failed, d.failed > 0 ? "red" : "gray")}
					${this.card(__("Synced Today"), d.synced_today, "green")}
				</div>

				<!-- Timestamps -->
				<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px;">
					<div class="card" style="padding:16px;border-radius:8px;border:1px solid var(--border-color);">
						<div class="text-muted small">${__("Last Push")}</div>
						<div><strong>${d.last_push_at ? frappe.datetime.str_to_user(d.last_push_at) : __("Never")}</strong></div>
					</div>
					<div class="card" style="padding:16px;border-radius:8px;border:1px solid var(--border-color);">
						<div class="text-muted small">${__("Last Pull")}</div>
						<div><strong>${d.last_pull_at ? frappe.datetime.str_to_user(d.last_pull_at) : __("Never")}</strong></div>
					</div>
				</div>

				<!-- Recent Logs -->
				<h5>${__("Recent Activity")}</h5>
				<table class="table table-bordered table-sm">
					<thead>
						<tr>
							<th>${__("Type")}</th>
							<th>${__("DocType")}</th>
							<th>${__("Document")}</th>
							<th>${__("Status")}</th>
							<th>${__("Time")}</th>
						</tr>
					</thead>
					<tbody>
						${(d.recent_logs || []).map(l => `
							<tr>
								<td>${l.sync_type}</td>
								<td>${l.doctype_name}</td>
								<td>${l.document_name}</td>
								<td>
									<span class="indicator-pill ${l.status === "Success" ? "green" : l.status === "Failed" ? "red" : "gray"}">
										${l.status}
									</span>
								</td>
								<td>${l.timestamp ? frappe.datetime.str_to_user(l.timestamp) : ""}</td>
							</tr>
						`).join("") || `<tr><td colspan="5" class="text-center text-muted">${__("No activity yet")}</td></tr>`}
					</tbody>
				</table>
			</div>
		`);
	}

	card(label, value, color) {
		const colors = {
			green: "#d4edda", red: "#f8d7da", orange: "#fff3cd",
			gray: "var(--fg-color)", blue: "#cce5ff",
		};
		return `
			<div style="
				padding:20px;border-radius:8px;
				border:1px solid var(--border-color);
				background:${colors[color] || colors.gray};
				text-align:center;
			">
				<div class="text-muted small">${label}</div>
				<div style="font-size:1.8rem;font-weight:700;">${value}</div>
			</div>
		`;
	}
}
