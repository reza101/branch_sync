import frappe
from branch_sync.sync.client import center_exists, center_insert

# Fields per doctype to extract dependency names from
DEPENDENCY_FIELDS = {
    "Purchase Invoice": {
        "Supplier": ["supplier"],
        "Batch": ["items.batch_no"],
    },
    "Purchase Receipt": {
        "Supplier": ["supplier"],
        "Batch": ["items.batch_no"],
    },
    "Sales Invoice": {
        "Customer": ["customer"],
        "Batch": ["items.batch_no"],
    },
    "Delivery Note": {
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
    "POS Opening Entry": {
        "POS Profile": ["pos_profile"],
    },
    "Journal Entry": {},
    "Delivery Order": {
        "Delivery Zone": ["delivery_zone"],
        "Customer": ["customer"],
    },
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
    "Delivery Zone": [
        "zone_name", "zone_code", "is_active", "priority",
        "center_latitude", "center_longitude", "radius_km",
        "base_delivery_fee", "per_km_charge", "free_delivery_threshold",
        "min_order_value", "service_start_time", "service_end_time",
        "service_days", "average_eta_minutes",
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

    # Ensure all warehouses referenced in this doc exist on center
    if doctype in ("Stock Entry", "Stock Reconciliation", "Purchase Receipt",
                   "Delivery Note", "POS Invoice"):
        _ensure_warehouses_for_doc(doc, settings)

    # Payment Entry: ensure bank account exists on center
    if doctype == "Payment Entry":
        _ensure_bank_account(doc.get("bank_account"), settings)

    # POS Invoice/Closing Entry: find open POS Opening Entry via pos_profile and push it
    if doctype in ("POS Invoice", "POS Closing Entry"):
        _ensure_pos_opening_entry(doc, settings)


def _ensure_warehouses_for_doc(doc, settings):
    """Collect all warehouse references from header and items, push missing ones."""
    warehouses = set()
    for field in ("warehouse", "set_warehouse", "from_warehouse", "to_warehouse"):
        val = doc.get(field)
        if val:
            warehouses.add(val)
    for row in (doc.get("items") or []):
        for field in ("warehouse", "s_warehouse", "t_warehouse", "from_warehouse"):
            val = row.get(field)
            if val:
                warehouses.add(val)
    for wh in warehouses:
        _ensure_warehouse(wh, settings)


def _ensure_warehouse(name, settings):
    """Recursively push warehouse and its parents to center."""
    if not name or center_exists(settings, "Warehouse", name):
        return
    import json
    wh = frappe.get_doc("Warehouse", name)
    if wh.parent_warehouse:
        _ensure_warehouse(wh.parent_warehouse, settings)
    data = json.loads(frappe.as_json({
        "name": wh.name,
        "warehouse_name": wh.warehouse_name,
        "parent_warehouse": wh.parent_warehouse,
        "company": wh.company,
        "warehouse_type": wh.warehouse_type,
        "is_group": wh.is_group,
    }))
    center_insert(settings, "Warehouse", data)


def _ensure_bank_account(name, settings):
    """Push bank account to center if missing."""
    if not name or center_exists(settings, "Bank Account", name):
        return
    import json
    ba = frappe.get_doc("Bank Account", name)
    data = json.loads(frappe.as_json({
        "name": ba.name,
        "account_name": ba.account_name,
        "bank": ba.bank,
        "account": ba.account,
        "company": ba.company,
        "is_default": ba.is_default,
        "is_company_account": ba.is_company_account,
    }))
    center_insert(settings, "Bank Account", data)


def _ensure_pos_opening_entry(pos_invoice_doc, settings):
    """Find the active POS Opening Entry for this invoice's POS Profile and push it."""
    pos_profile = pos_invoice_doc.get("pos_profile")
    if not pos_profile:
        return

    # Push POS Profile first
    if not center_exists(settings, "POS Profile", pos_profile):
        _push_dependency("POS Profile", pos_profile, settings)

    # Find submitted open entry for this profile
    opening_entry = frappe.db.get_value(
        "POS Opening Entry",
        {"pos_profile": pos_profile, "docstatus": 1},
        "name",
        order_by="creation desc",
    )
    if opening_entry and not center_exists(settings, "POS Opening Entry", opening_entry):
        _push_dependency("POS Opening Entry", opening_entry, settings)


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


# Doctypes pushed as full documents (all fields + child tables)
FULL_DOC_PUSH = {"POS Profile", "POS Opening Entry"}
# POS Profile is not submittable — only POS Opening Entry needs submit after push

# Child table system fields to strip
_DEP_CHILD_STRIP = {
    "name", "owner", "creation", "modified", "modified_by",
    "parent", "parenttype", "parentfield", "doctype",
}

_DEP_STRIP = {
    "owner", "creation", "modified", "modified_by", "doctype",
    "amended_from", "_user_tags", "__islocal", "__unsaved",
}


def _push_dependency(dep_doctype, name, settings):
    import json
    dep_doc = frappe.get_doc(dep_doctype, name)

    if dep_doctype in FULL_DOC_PUSH:
        # Resolve nested dependencies first (e.g. POS Profile before POS Opening Entry)
        nested = DEPENDENCY_FIELDS.get(dep_doctype, {})
        for nested_doctype, nested_paths in nested.items():
            nested_names = _extract_names(dep_doc, nested_paths, dep_doctype, nested_doctype)
            for nested_name in nested_names:
                if nested_name and not center_exists(settings, nested_doctype, nested_name):
                    _push_dependency(nested_doctype, nested_name, settings)

        was_submitted = dep_doc.docstatus == 1
        raw = {k: v for k, v in dep_doc.as_dict().items() if k not in _DEP_STRIP}
        # Insert as draft (Frappe always creates as draft via REST)
        raw["docstatus"] = 0
        data = json.loads(frappe.as_json(raw))
        for key, val in data.items():
            if isinstance(val, list):
                data[key] = [
                    {ck: cv for ck, cv in row.items() if ck not in _DEP_CHILD_STRIP}
                    for row in val if isinstance(row, dict)
                ]
    else:
        was_submitted = False
        fields = DEPENDENCY_PUSH_FIELDS.get(dep_doctype, [])
        raw = {"name": name}
        for f in fields:
            raw[f] = dep_doc.get(f)
        data = json.loads(frappe.as_json(raw))

    try:
        center_insert(settings, dep_doctype, data)
        # Submit on center if the original doc was submitted (e.g. POS Opening Entry)
        if was_submitted:
            from branch_sync.sync.push import _submit_on_center
            _submit_on_center(settings, dep_doctype, name)
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
