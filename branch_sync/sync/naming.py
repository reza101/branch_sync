import frappe

SERIES_MAP = {
    "Sales Invoice":     "{prefix}-SINV-.YYYY.-",
    "Purchase Invoice":  "{prefix}-PINV-.YYYY.-",
    "Payment Entry":     "{prefix}-PAY-.YYYY.-",
    "Stock Entry":       "{prefix}-STE-.YYYY.-",
    "Batch":             "{prefix}-BATCH-.YYYY.-",
    "Customer":          "{prefix}-CUST-.YYYY.-",
    "Supplier":          "{prefix}-SUPP-.YYYY.-",
}


def configure_naming_series(prefix):
    """Set naming series for all branch doctypes with given prefix."""
    results = {}
    for doctype, template in SERIES_MAP.items():
        series = template.format(prefix=prefix)
        try:
            _set_series(doctype, series)
            results[doctype] = {"series": series, "ok": True}
        except Exception as e:
            results[doctype] = {"series": series, "ok": False, "error": str(e)}
    return results


def _set_series(doctype, series):
    """Add the series to the doctype's naming_series options and set as default."""
    meta = frappe.get_meta(doctype)
    field = meta.get_field("naming_series")
    if not field:
        return

    current_options = field.options or ""
    options_list = [o.strip() for o in current_options.split("\n") if o.strip()]

    if series not in options_list:
        options_list.insert(0, series)
        new_options = "\n".join(options_list)
        frappe.db.set_value("DocField",
            {"parent": doctype, "fieldname": "naming_series"},
            "options", new_options)

    # Set as default
    frappe.db.set_value("DocField",
        {"parent": doctype, "fieldname": "naming_series"},
        "default", series)

    frappe.clear_cache(doctype=doctype)
