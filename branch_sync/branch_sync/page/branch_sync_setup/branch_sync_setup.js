frappe.pages["branch-sync-setup"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Branch Sync — Setup Wizard"),
		single_column: true,
	});

	new BranchSyncWizard(wrapper);
};

class BranchSyncWizard {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.step = 1;
		this.data = {};
		this.loadSavedSettings();
	}

	loadSavedSettings() {
		frappe.call({
			method: "branch_sync.api.get_settings",
			callback: (r) => {
				if (r.message) {
					this.data = r.message;
				}
				this.render();
			},
		});
	}

	render() {
		this.body = $(this.wrapper).find(".layout-main-section");
		this.body.empty();
		this.body.html(`
			<div class="branch-sync-wizard" style="max-width:680px;margin:32px auto;">
				<div class="wizard-steps" style="display:flex;gap:8px;margin-bottom:32px;">
					${[1,2,3,4,5].map(i => `
						<div class="step-dot" data-step="${i}" style="
							flex:1;height:6px;border-radius:3px;
							background:${this.step >= i ? "var(--primary)" : "var(--gray-200)"};
							transition:background .3s;
						"></div>
					`).join("")}
				</div>
				<div class="wizard-body"></div>
			</div>
		`);
		this.renderStep();
	}

	renderStep() {
		const body = this.body.find(".wizard-body");
		body.empty();

		const steps = {
			1: () => this.renderStep1(body),
			2: () => this.renderStep2(body),
			3: () => this.renderStep3(body),
			4: () => this.renderStep4(body),
			5: () => this.renderStep5(body),
		};
		steps[this.step]();
	}

	// ── Step 1: Center connection ────────────────────────────────────────────
	renderStep1(body) {
		body.html(`
			<h3>${__("Step 1 of 5 — Connect to Center")}</h3>
			<p class="text-muted">${__("Enter the center ERPNext URL and API credentials.")}</p>
			<div class="form-group">
				<label>${__("Center URL")}</label>
				<input id="center_url" class="form-control" placeholder="https://erp.pcpmukalla.com"
					value="${this.data.center_url || ""}">
			</div>
			<div class="form-group">
				<label>${__("API Key")}</label>
				<input id="center_api_key" class="form-control" placeholder="API Key"
					value="${this.data.center_api_key || ""}">
			</div>
			<div class="form-group">
				<label>${__("API Secret")}</label>
				<input id="center_api_secret" class="form-control" type="password" placeholder="API Secret"
					value="${this.data.center_api_secret || ""}">
			</div>
			<div id="conn_result" style="margin:12px 0;"></div>
			<button class="btn btn-primary" id="btn_test">${__("Test Connection")}</button>
		`);

		body.find("#btn_test").on("click", () => this.testConnection());
	}

	testConnection() {
		const url = this.body.find("#center_url").val().trim();
		const key = this.body.find("#center_api_key").val().trim();
		const secret = this.body.find("#center_api_secret").val().trim();
		const result = this.body.find("#conn_result");

		if (!url || !key || !secret) {
			result.html(`<div class="alert alert-warning">${__("All fields are required.")}</div>`);
			return;
		}

		result.html(`<div class="text-muted">${__("Connecting…")}</div>`);

		frappe.call({
			method: "branch_sync.api.test_connection",
			args: { center_url: url, center_api_key: key, center_api_secret: secret },
			callback: (r) => {
				if (r.message && r.message.ok) {
					this.data.center_url = url;
					this.data.center_api_key = key;
					this.data.center_api_secret = secret;
					result.html(`<div class="alert alert-success">✅ ${r.message.message}</div>`);
					setTimeout(() => this.goTo(2), 800);
				} else {
					result.html(`<div class="alert alert-danger">❌ ${r.message ? r.message.message : __("Connection failed")}</div>`);
				}
			},
		});
	}

	// ── Step 2: Branch info ──────────────────────────────────────────────────
	renderStep2(body) {
		body.html(`
			<h3>${__("Step 2 of 5 — Branch Information")}</h3>
			<p class="text-muted">${__("Configure this branch's identity.")}</p>
			<div class="form-group">
				<label>${__("Branch Name")}</label>
				<input id="branch_name" class="form-control" placeholder="${__("e.g. Plus Care Pharmacy Mukalla")}"
					value="${this.data.branch_name || ""}">
			</div>
			<div class="form-group">
				<label>${__("Naming Prefix")}</label>
				<input id="branch_prefix" class="form-control" placeholder="MUKALLA"
					value="${this.data.branch_prefix || ""}">
				<small class="text-muted">${__("All documents will be prefixed: MUKALLA-SINV-2026-00001")}</small>
			</div>
			<div class="form-group">
				<label>${__("Branch Warehouse")}</label>
				<select id="branch_warehouse" class="form-control">
					<option value="">${__("Loading…")}</option>
				</select>
			</div>
			<br>
			<button class="btn btn-default" id="btn_back">${__("Back")}</button>
			<button class="btn btn-primary" id="btn_next" style="margin-left:8px">${__("Next")}</button>
		`);

		// Load warehouses
		frappe.db.get_list("Warehouse", { fields: ["name"], limit: 100 }).then((rows) => {
			const sel = body.find("#branch_warehouse");
			sel.empty().append(`<option value="">${__("Select…")}</option>`);
			rows.forEach((r) => sel.append(`<option value="${r.name}" ${r.name === this.data.branch_warehouse ? "selected" : ""}>${r.name}</option>`));
		});

		body.find("#btn_back").on("click", () => this.goTo(1));
		body.find("#btn_next").on("click", () => {
			const name = body.find("#branch_name").val().trim();
			const prefix = body.find("#branch_prefix").val().trim().toUpperCase();
			const wh = body.find("#branch_warehouse").val();
			if (!name || !prefix || !wh) {
				frappe.msgprint(__("All fields are required."));
				return;
			}
			this.data.branch_name = name;
			this.data.branch_prefix = prefix;
			this.data.branch_warehouse = wh;
			this.goTo(3);
		});
	}

	// ── Step 3: Naming Series ────────────────────────────────────────────────
	renderStep3(body) {
		body.html(`
			<h3>${__("Step 3 of 5 — Naming Series")}</h3>
			<p class="text-muted">${__("Configuring naming series automatically…")}</p>
			<div id="naming_results" style="margin:16px 0;"></div>
		`);

		frappe.call({
			method: "branch_sync.api.configure_naming_series",
			args: { prefix: this.data.branch_prefix },
			callback: (r) => {
				const res = r.message || {};
				let html = "<table class='table table-bordered'><thead><tr><th>DocType</th><th>Series</th><th>Status</th></tr></thead><tbody>";
				Object.entries(res).forEach(([dt, info]) => {
					html += `<tr>
						<td>${dt}</td>
						<td><code>${info.series}</code></td>
						<td>${info.ok ? "✅" : "❌ " + (info.error || "")}</td>
					</tr>`;
				});
				html += "</tbody></table>";
				html += `<button class="btn btn-primary" id="btn_next_3">${__("Next")}</button>`;
				body.find("#naming_results").html(html);
				body.find("#btn_next_3").on("click", () => this.goTo(4));
			},
		});
	}

	// ── Step 4: Initial Pull ─────────────────────────────────────────────────
	renderStep4(body) {
		body.html(`
			<h3>${__("Step 4 of 5 — Initial Data Pull")}</h3>
			<p class="text-muted">
				${__("Pull master data from center (Items, Prices, Customers…).")}
				<br>
				${__("Skip if this branch already has data from a backup.")}
			</p>
			<div style="display:flex;gap:12px;margin-top:24px;">
				<button class="btn btn-primary" id="btn_pull">
					⬇️ ${__("Pull from Center")}
				</button>
				<button class="btn btn-default" id="btn_skip_pull">
					${__("Skip — Pull Later")}
				</button>
			</div>
			<div style="margin-top:20px;">
				<div class="progress" style="height:8px;display:none;" id="pull_progress">
					<div class="progress-bar progress-bar-striped active" id="pull_bar"
						style="width:0%;transition:width 1s;"></div>
				</div>
				<div id="pull_status" class="text-muted" style="margin-top:8px;"></div>
			</div>
		`);

		body.find("#btn_pull").on("click", () => {
			body.find("#btn_pull, #btn_skip_pull").prop("disabled", true);
			body.find("#pull_progress").show();
			body.find("#pull_status").text(__("Saving settings…"));
			this.saveAndPull(body);
		});

		body.find("#btn_skip_pull").on("click", () => {
			body.find("#btn_pull, #btn_skip_pull").prop("disabled", true);
			body.find("#pull_status").text(__("Saving settings…"));
			this.saveSettings(() => this.goTo(5));
		});
	}

	saveSettings(callback) {
		frappe.call({
			method: "branch_sync.api.complete_setup",
			args: {
				branch_name: this.data.branch_name,
				branch_prefix: this.data.branch_prefix,
				branch_warehouse: this.data.branch_warehouse,
				center_url: this.data.center_url,
				center_api_key: this.data.center_api_key,
				center_api_secret: this.data.center_api_secret,
			},
			callback,
		});
	}

	saveAndPull(body) {
		this.saveSettings(() => {
			body.find("#pull_bar").css("width", "30%");
			body.find("#pull_status").text(__("Settings saved. Pulling data…"));

			frappe.call({
				method: "branch_sync.api.run_initial_pull",
				callback: (r) => {
					body.find("#pull_bar").css("width", "100%");
					if (r.message && r.message.ok) {
						body.find("#pull_status").html(`✅ ${__("Master data pulled successfully.")}`);
						setTimeout(() => this.goTo(5), 1000);
					} else {
						body.find("#pull_status").html(`❌ ${__("Pull failed. Check error logs.")}`);
						body.find("#btn_pull, #btn_skip_pull").prop("disabled", false);
					}
				},
			});
		});
	}

	// ── Step 5: Summary ──────────────────────────────────────────────────────
	renderStep5(body) {
		body.html(`
			<h3>✅ ${__("Setup Complete!")}</h3>
			<br>
			<table class="table table-bordered">
				<tr><td>${__("Branch Name")}</td><td><strong>${this.data.branch_name}</strong></td></tr>
				<tr><td>${__("Naming Prefix")}</td><td><code>${this.data.branch_prefix}</code></td></tr>
				<tr><td>${__("Warehouse")}</td><td>${this.data.branch_warehouse}</td></tr>
				<tr><td>${__("Center URL")}</td><td>${this.data.center_url}</td></tr>
				<tr><td>${__("Connection")}</td><td>✅ Online</td></tr>
				<tr><td>${__("Naming Series")}</td><td>✅ Configured</td></tr>
				<tr><td>${__("Master Data")}</td><td>✅ Pulled</td></tr>
			</table>
			<br>
			<button class="btn btn-primary btn-lg" id="btn_dashboard">
				${__("Go to Sync Dashboard")} →
			</button>
		`);

		body.find("#btn_dashboard").on("click", () => {
			frappe.set_route("branch-sync-dashboard");
		});
	}

	goTo(step) {
		this.step = step;
		this.body.find(".step-dot").each(function () {
			const s = parseInt($(this).data("step"));
			$(this).css("background", step >= s ? "var(--primary)" : "var(--gray-200)");
		});
		this.renderStep();
	}
}
