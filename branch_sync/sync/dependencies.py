import frappe
from branch_sync.sync.client import center_exists, center_insert

# Fields per doctype to extract dependency names from
DEPENDENCY_FIELDS = {
    "Purchase Invoice": {
        "Supplier": ["supplier"],
        "Batch": ["items.batch_no"],
    },
    "Sales Invoice": {
        "Customer": ["customer"],
        "Batch": ["items.batch_no"],
    },
    "Payment Entry": {
        "Customer": ["party"],   # when party_type == Customer
        "Supplier": ["party"],   # when party_type == Supplier
    },
    "Stock Entry": {
        "Batch": ["items.batch_no"],
    },
    "Stock Reconciliation": {
        "Batch": ["items.batch_no"],
    },
    "POS Invoice": {
        "Customer": ["customer"],
        "Batch": ["items.batch_no"],
    },
    # POS Opening/Closing Entry have no linked deps that need pre-push
}

# Fields to push for each dependency doctype
DEPENDENCY_PUSH_FIELDS = {
    "Supplier": [
        "supplier_name", "supplier_group", "supplier_type",
        "country", "mobile_no", "email_id", "tax_id",
    ],
    "Customer": [
        "customer_name", "customer_group", "customer_type",
        "territory", "mobile_no", "email_id", "tax_id",
    ],
    "Batch": [
        "batch_id", "item", "expiry_date", "manufacturing_date",
        "supplier", "description",
        # batch_qty intentionally excluded — recalculated from SLE
    ],
}


def ensure_dependencies(doctype, docname, settings):
    """Push all missing dependencies to center before pushing main doc."""
    doc = frappe.get_doc(doctype, docname)
    dep_map = DEPENDENCY_FIELDS.get(doctype, {})

    for dep_doctype, field_paths in dep_map.items():
        names = _extract_names(doc, field_paths, doctype, dep_doctype)

        # batch_no may be stored in Serial and Batch Bundle entries, not in items directly
        if dep_doctype == "Batch":
            names |= _extract_batch_names_from_bundles(doc)

        for name in names:
            if name and not center_exists(settings, dep_doctype, name):
                _push_dependency(dep_doctype, name, settings)


def _extract_batch_names_from_bundles(doc):
    """Extract batch_no values from Serial and Batch Bundle entries for items
    where batch_no is empty but serial_and_batch_bundle is set."""
    batch_names = set()
    for row in (doc.get("items") or []):
        if row.get("batch_no"):
            continue
        bundle_name = row.get("serial_and_batch_bundle")
        if not bundle_name:
            continue
        try:
            entries = frappe.get_all(
                "Serial and Batch Entry",
                filters={"parent": bundle_name},
                fields=["batch_no"],
            )
            for entry in entries:
                if entry.batch_no:
                    batch_names.add(entry.batch_no)
        except Exception:
            pass
    return batch_names


def _extract_names(doc, field_paths, parent_doctype, dep_doctype):
    names = set()
    for path in field_paths:
        if "." in path:
            table_field, child_field = path.split(".", 1)
            for row in (doc.get(table_field) or []):
                val = row.get(child_field)
                if val:
                    names.add(val)
        else:
            # Handle Payment Entry party_type filter
            if parent_doctype == "Payment Entry" and path == "party":
                if doc.party_type == dep_doctype:
                    val = doc.get(path)
                    if val:
                        names.add(val)
            else:
                val = doc.get(path)
                if val:
                    names.add(val)
    return names


def _push_dependency(dep_doctype, name, settings):
    import json
    dep_doc = frappe.get_doc(dep_doctype, name)
    fields = DEPENDENCY_PUSH_FIELDS.get(dep_doctype, [])

    raw = {"name": name}
    for f in fields:
        raw[f] = dep_doc.get(f)

    # Serialize date/datetime/Decimal objects
    data = json.loads(frappe.as_json(raw))

    try:
        center_insert(settings, dep_doctype, data)
    except Exception as e:
        frappe.log_error(
            title=f"Branch Sync: dependency push failed ({dep_doctype} {name})",
            message=str(e),
        )
        raise


_BUNDLE_STRIP = {"owner", "creation", "modified", "modified_by", "doctype"}
_BUNDLE_ENTRY_STRIP = {
    "name", "owner", "creation", "modified", "modified_by",
    "parent", "parenttype", "parentfield", "doctype",
}


def _push_serial_batch_bundle(name, settings):
    """Push Serial and Batch Bundle to center preserving its UUID name.

    Bundle is pushed as draft with voucher_no cleared to break the circular
    reference (invoice doesn't exist on center yet). When the invoice is
    submitted on center, ERPNext links the bundle and submits it automatically.
    """
    import json

    doc = frappe.get_doc("Serial and Batch Bundle", name)
    data = {}
    for k, v in doc.as_dict().items():
        if k in _BUNDLE_STRIP:
            continue
        if isinstance(v, list):
            data[k] = [
                {ek: ev for ek, ev in row.items() if ek not in _BUNDLE_ENTRY_STRIP}
                for row in v if isinstance(row, dict)
            ]
        else:
            data[k] = v

    # Clear voucher link — center doesn't have the invoice yet (circular dep)
    data["voucher_no"] = ""
    data["docstatus"] = 0  # keep draft; invoice submission will submit it

    data = json.loads(frappe.as_json(data))

    try:
        center_insert(settings, "Serial and Batch Bundle", data)
    except Exception as e:
        frappe.log_error(
            title=f"Branch Sync: Serial and Batch Bundle push failed ({name})",
            message=str(e),
        )
        raise
