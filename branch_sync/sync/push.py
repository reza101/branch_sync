import time
import frappe
from branch_sync.sync.client import (
    get_settings, center_insert, center_exists, write_log
)
from branch_sync.sync.dependencies import ensure_dependencies

# Fields stripped before pushing to center (internal Frappe metadata)
STRIP_FIELDS = {
    "amended_from", "docstatus", "idx", "owner", "creation",
    "modified", "modified_by", "_user_tags", "__islocal",
    "__unsaved", "doctype",
}

# Doctypes that can be pushed and their submit method
SUBMITTABLE_DOCTYPES = {
    "Sales Invoice", "Purchase Invoice", "Payment Entry",
    "Stock Entry", "Stock Reconciliation",
}


def push_document(doctype, docname, settings=None):
    """Push one submitted document to center, resolving dependencies first."""
    if not settings:
        settings = get_settings()

    start = time.time()

    try:
        # Skip if already exists on center
        if center_exists(settings, doctype, docname):
            write_log("Push", doctype, docname, "Skipped", duration=time.time() - start)
            return

        # Push dependencies first
        ensure_dependencies(doctype, docname, settings)

        # Build payload
        doc = frappe.get_doc(doctype, docname)
        payload = _build_payload(doc, settings)

        # Insert on center
        center_insert(settings, doctype, payload)

        # Submit on center if needed
        if doctype in SUBMITTABLE_DOCTYPES:
            _submit_on_center(settings, doctype, docname)

        write_log("Push", doctype, docname, "Success", duration=time.time() - start)

    except Exception as e:
        write_log("Push", doctype, docname, "Failed",
                  error_message=str(e), duration=time.time() - start)
        raise


def _build_payload(doc, settings):
    data = {}
    for key, val in doc.as_dict().items():
        if key in STRIP_FIELDS:
            continue
        data[key] = val

    # Remap warehouse to branch warehouse name (same name, different instance)
    # Both sides use the same warehouse name — no remapping needed by design

    return data


def _submit_on_center(settings, doctype, docname):
    import requests
    from branch_sync.sync.client import _base_url
    r = requests.post(
        f"{_base_url(settings)}/api/resource/{doctype}/{docname}",
        json={"data": {"docstatus": 1}},
        headers=settings.get_auth_headers(),
        timeout=30,
    )
    r.raise_for_status()


def push_stock_reconciliation():
    """Called by scheduler at 06:00 daily."""
    settings = get_settings()
    if not settings.is_setup_complete:
        return
    from branch_sync.sync.client import is_center_reachable
    if not is_center_reachable(settings):
        return

    pending = frappe.get_all(
        "Branch Sync Queue",
        filters={"status": "Pending", "doctype_name": "Stock Reconciliation"},
        fields=["name", "doctype_name", "document_name"],
        order_by="posting_date asc, posting_time asc",
    )
    for item in pending:
        _process_queue_item(item, settings)
