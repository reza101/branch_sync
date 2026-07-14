import time
import frappe
from branch_sync.sync.client import (
    get_settings, center_insert, write_log
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
    from branch_sync.sync.client import center_get
    if not settings:
        settings = get_settings()

    start = time.time()

    try:
        existing = center_get(settings, doctype, docname)

        if existing:
            if existing.get("docstatus") == 1:
                # Already submitted on center — nothing to do
                write_log("Push", doctype, docname, "Skipped", duration=time.time() - start)
                return
            # Exists as draft — skip create, go straight to submit
        else:
            # Push dependencies first
            ensure_dependencies(doctype, docname, settings)

            # Build payload and insert
            doc = frappe.get_doc(doctype, docname)
            payload = _build_payload(doc, settings)
            center_insert(settings, doctype, payload)

        # Submit on center if needed
        if doctype in SUBMITTABLE_DOCTYPES:
            _submit_on_center(settings, doctype, docname)

        write_log("Push", doctype, docname, "Success", duration=time.time() - start)

    except Exception as e:
        write_log("Push", doctype, docname, "Failed",
                  error_message=str(e), duration=time.time() - start)
        raise


CHILD_STRIP_FIELDS = {
    "name", "owner", "creation", "modified", "modified_by",
    "parent", "parenttype", "parentfield", "docstatus", "doctype",
    # Strip bundle reference — center creates its own bundle on submit
    "serial_and_batch_bundle",
}


def _build_payload(doc, settings):
    import json
    raw = {k: v for k, v in doc.as_dict().items() if k not in STRIP_FIELDS}
    data = json.loads(frappe.as_json(raw))

    for key, val in data.items():
        if not isinstance(val, list):
            continue
        cleaned = []
        for row in val:
            if not isinstance(row, dict):
                continue
            # If batch_no is empty but bundle has it, extract it before stripping
            if not row.get("batch_no") and row.get("serial_and_batch_bundle"):
                row["batch_no"] = _batch_no_from_bundle(row["serial_and_batch_bundle"])
            cleaned.append({ck: cv for ck, cv in row.items() if ck not in CHILD_STRIP_FIELDS})
        data[key] = cleaned

    return data


def _batch_no_from_bundle(bundle_name):
    """Extract the first batch_no from a Serial and Batch Bundle's entries."""
    try:
        entries = frappe.get_all(
            "Serial and Batch Entry",
            filters={"parent": bundle_name},
            fields=["batch_no"],
            limit=1,
        )
        return entries[0].batch_no if entries else None
    except Exception:
        return None


def _submit_on_center(settings, doctype, docname):
    import requests
    from branch_sync.sync.client import _base_url
    r = requests.put(
        f"{_base_url(settings)}/api/resource/{doctype}/{docname}",
        json={"docstatus": 1},
        headers=settings.get_auth_headers(),
        timeout=30,
    )
    if not r.ok:
        raise Exception(f"Submit failed HTTP {r.status_code}: {r.text[:800]}")


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
