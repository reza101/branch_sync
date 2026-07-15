import frappe
import requests
from branch_sync.sync.client import get_settings, _resource_url


def cancel_on_center(doctype, docname, settings=None):
    """Cancel a document on center (set docstatus=2)."""
    if not settings:
        settings = get_settings()
    r = requests.put(
        _resource_url(settings, doctype, docname),
        json={"docstatus": 2},
        headers=settings.get_auth_headers(),
        timeout=15,
    )
    if not r.ok and r.status_code != 404:
        raise Exception(f"Cancel failed HTTP {r.status_code}: {r.text[:400]}")


def delete_on_center(doctype, docname, settings=None):
    """Delete a document on center."""
    if not settings:
        settings = get_settings()
    r = requests.delete(
        _resource_url(settings, doctype, docname),
        headers=settings.get_auth_headers(),
        timeout=15,
    )
    if not r.ok and r.status_code != 404:
        raise Exception(f"Delete failed HTTP {r.status_code}: {r.text[:400]}")


# --- Frappe doc_event hooks (enqueue to queue for offline safety) ---

def sync_cancel(doc, method):
    """on_cancel hook — enqueue Cancel action."""
    from branch_sync.sync.queue import enqueue_on_cancel
    enqueue_on_cancel(doc, method)


def sync_delete(doc, method):
    """on_trash hook — enqueue Delete action (doc still exists at this point)."""
    from branch_sync.sync.queue import enqueue_on_trash
    enqueue_on_trash(doc, method)
