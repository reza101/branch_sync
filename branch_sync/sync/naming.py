import frappe

NAMING_SERIES_DOCTYPES = [
    "Sales Invoice",
    "Purchase Invoice",
    "Purchase Receipt",
    "Payment Entry",
    "Journal Entry",
    "Stock Entry",
    "Stock Reconciliation",
    "Delivery Note",
    "Batch",
    "Customer",
    "Supplier",
    "POS Invoice",
]


def configure_naming_series(prefix):
    """Prepend branch prefix to all existing naming series options."""
    results = {}
    for doctype in NAMING_SERIES_DOCTYPES:
        try:
            _set_series(doctype, prefix)
            results[doctype] = {"ok": True}
        except Exception as e:
            results[doctype] = {"ok": False, "error": str(e)}
    return results


def _get_current_options(doctype):
    """Return current naming_series options, preferring Property Setter over DocField."""
    ps_name = f"{doctype}-naming_series-options"
    if frappe.db.exists("Property Setter", ps_name):
        val = frappe.db.get_value("Property Setter", ps_name, "value") or ""
    else:
        val = frappe.db.get_value(
            "DocField",
            {"parent": doctype, "fieldname": "naming_series"},
            "options"
        ) or ""
    return [o.strip() for o in val.split("\n") if o.strip()]


def _set_series(doctype, prefix):
    """Prepend prefix to every option that doesn't already have it."""
    options = _get_current_options(doctype)
    if not options:
        return

    new_options = []
    for opt in options:
        if not opt.startswith(prefix + "-"):
            new_options.append(f"{prefix}-{opt}")
        else:
            new_options.append(opt)

    new_options_str = "\n".join(new_options)
    default = new_options[0]

    # Update DocField
    frappe.db.set_value(
        "DocField",
        {"parent": doctype, "fieldname": "naming_series"},
        {"options": new_options_str, "default": default},
    )

    # Update Property Setters if they exist (they override DocField)
    ps_options = f"{doctype}-naming_series-options"
    ps_default = f"{doctype}-naming_series-default"

    if frappe.db.exists("Property Setter", ps_options):
        frappe.db.set_value("Property Setter", ps_options, "value", new_options_str)
    if frappe.db.exists("Property Setter", ps_default):
        frappe.db.set_value("Property Setter", ps_default, "value", default)

    frappe.clear_cache(doctype=doctype)


def validate_branch_prefix(doc, method):
    """Block save if the naming series doesn't start with the branch prefix."""
    settings = frappe.get_cached_doc("Branch Sync Settings")
    if not settings.is_setup_complete:
        return
    prefix = settings.branch_prefix
    if not prefix:
        return
    naming_series = doc.get("naming_series") or ""
    if naming_series and not naming_series.startswith(prefix + "-"):
        frappe.throw(
            f"This branch only allows naming series with prefix <b>{prefix}-</b>.<br>"
            f"Please select a series starting with <b>{prefix}-</b>.",
            title="Invalid Naming Series"
        )
