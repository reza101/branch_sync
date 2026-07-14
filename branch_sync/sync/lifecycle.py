import frappe
import requests
from branch_sync.sync.client import get_settings, _base_url, is_center_reachable


def _get_settings():
    settings = get_settings()
    if not settings.is_setup_complete:
        return None
    return settings


def sync_cancel(doc, method):
    """Cancel the document on center when cancelled on branch."""
    settings = _get_settings()
    if not settings:
        return
    if not is_center_reachable(settings):
        return

    try:
        r = requests.put(
            f"{_base_url(settings)}/api/resource/{doc.doctype}/{doc.name}",
            json={"docstatus": 2},
            headers=settings.get_auth_headers(),
            timeout=15,
        )
        if not r.ok and r.status_code != 404:
            frappe.log_error(
                title=f"Branch Sync: cancel failed ({doc.doctype} {doc.name})",
                message=f"HTTP {r.status_code}: {r.text[:500]}",
            )
    except Exception as e:
        frappe.log_error(
            title=f"Branch Sync: cancel error ({doc.doctype} {doc.name})",
            message=str(e),
        )


def sync_delete(doc, method):
    """Delete the document on center when deleted on branch."""
    settings = _get_settings()
    if not settings:
        return
    if not is_center_reachable(settings):
        return

    try:
        r = requests.delete(
            f"{_base_url(settings)}/api/resource/{doc.doctype}/{doc.name}",
            headers=settings.get_auth_headers(),
            timeout=15,
        )
        if not r.ok and r.status_code != 404:
            frappe.log_error(
                title=f"Branch Sync: delete failed ({doc.doctype} {doc.name})",
                message=f"HTTP {r.status_code}: {r.text[:500]}",
            )
    except Exception as e:
        frappe.log_error(
            title=f"Branch Sync: delete error ({doc.doctype} {doc.name})",
            message=str(e),
        )
