import frappe
from frappe import _


@frappe.whitelist()
def test_connection(center_url, center_api_key, center_api_secret):
    """Step 1 of wizard: verify we can reach center with given credentials."""
    import requests
    try:
        r = requests.get(
            f"{center_url}/api/method/frappe.ping",
            headers={
                "Authorization": f"token {center_api_key}:{center_api_secret}",
            },
            timeout=8,
        )
        if r.ok:
            return {"ok": True, "message": _("Connected successfully")}
        return {"ok": False, "message": r.text[:200]}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@frappe.whitelist()
def configure_naming_series(prefix):
    """Step 3 of wizard: auto-configure naming series."""
    from branch_sync.sync.naming import configure_naming_series
    results = configure_naming_series(prefix)
    return results


@frappe.whitelist()
def run_initial_pull():
    """Step 4 of wizard: pull master data for the first time."""
    from branch_sync.sync.pull import sync_master_data
    sync_master_data()
    return {"ok": True}


@frappe.whitelist()
def complete_setup(branch_name, branch_prefix, branch_warehouse,
                   center_url, center_api_key, center_api_secret):
    """Save settings and mark setup complete."""
    settings = frappe.get_single("Branch Sync Settings")
    settings.branch_name = branch_name
    settings.branch_prefix = branch_prefix
    settings.branch_warehouse = branch_warehouse
    settings.center_url = center_url
    settings.center_api_key = center_api_key
    settings.center_api_secret = center_api_secret
    settings.is_setup_complete = 1
    settings.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def get_dashboard_data():
    """Data for sync dashboard."""
    pending = frappe.db.count("Branch Sync Queue", {"status": "Pending"})
    failed = frappe.db.count("Branch Sync Queue", {"status": "Failed"})
    synced_today = frappe.db.count("Branch Sync Queue", {
        "status": "Synced",
        "synced_at": [">=", frappe.utils.today()],
    })
    settings = frappe.get_single("Branch Sync Settings")
    recent_logs = frappe.get_all(
        "Branch Sync Log",
        fields=["sync_type", "doctype_name", "document_name", "status",
                "timestamp", "error_message"],
        order_by="timestamp desc",
        limit=20,
    )
    return {
        "pending": pending,
        "failed": failed,
        "synced_today": synced_today,
        "last_push_at": settings.last_push_at,
        "last_pull_at": settings.last_pull_at,
        "connection_status": settings.last_connection_status,
        "recent_logs": recent_logs,
    }


@frappe.whitelist()
def retry_failed():
    """Reset all Failed queue items back to Pending."""
    frappe.db.set_value(
        "Branch Sync Queue",
        {"status": "Failed"},
        {"status": "Pending", "retry_count": 0, "error_message": ""},
    )
    frappe.db.commit()
    return {"ok": True}
