import frappe
from branch_sync.sync.client import get_settings, center_list, is_center_reachable, write_log

# Master data pulled nightly from center to branch
MASTER_DOCTYPES = [
    {
        "doctype": "Item Group",
        "fields": ["name", "item_group_name", "parent_item_group", "is_group"],
        "filters": [],
    },
    {
        "doctype": "Item",
        "fields": ["name", "item_code", "item_name", "item_group", "description",
                   "stock_uom", "has_batch_no", "has_serial_no",
                   "is_stock_item", "disabled"],
        "filters": [["disabled", "=", 0]],
    },
    {
        "doctype": "Item Price",
        "fields": ["name", "item_code", "price_list", "currency",
                   "price_list_rate", "valid_from", "valid_upto"],
        "filters": [],
    },
    {
        "doctype": "Price List",
        "fields": ["name", "price_list_name", "currency", "enabled"],
        "filters": [["enabled", "=", 1]],
    },
    {
        "doctype": "Customer Group",
        "fields": ["name", "customer_group_name", "parent_customer_group", "is_group"],
        "filters": [],
    },
    {
        "doctype": "Customer",
        "fields": ["name", "customer_name", "customer_group", "customer_type",
                   "territory", "mobile_no", "email_id", "tax_id"],
        "filters": [],
    },
    {
        "doctype": "Supplier",
        "fields": ["name", "supplier_name", "supplier_group", "supplier_type",
                   "country", "mobile_no", "email_id"],
        "filters": [],
    },
    {
        "doctype": "UOM",
        "fields": ["name", "uom_name"],
        "filters": [],
    },
    {
        "doctype": "Mode of Payment",
        "fields": ["name", "mode_of_payment", "type"],
        "filters": [],
    },
]


def sync_master_data():
    """Pull all master data from center. Called nightly by scheduler."""
    settings = get_settings()
    if not settings.is_setup_complete:
        return
    if not is_center_reachable(settings):
        return

    for config in MASTER_DOCTYPES:
        _pull_doctype(config, settings)

    frappe.db.set_value("Branch Sync Settings", None, "last_pull_at", frappe.utils.now())
    frappe.db.commit()


def _pull_doctype(config, settings):
    doctype = config["doctype"]
    try:
        records = center_list(
            settings,
            doctype,
            filters=config.get("filters"),
            fields=config.get("fields"),
            limit_page_length=1000,
        )
        for record in records:
            _upsert(doctype, record)
        write_log("Pull", doctype, f"{len(records)} records", "Success")
    except Exception as e:
        write_log("Pull", doctype, "", "Failed", error_message=str(e))


def _upsert(doctype, data):
    """Insert or update a record locally."""
    name = data.get("name")
    if not name:
        return

    if frappe.db.exists(doctype, name):
        doc = frappe.get_doc(doctype, name)
        for key, val in data.items():
            if key not in ("name", "doctype", "creation", "owner"):
                doc.set(key, val)
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.new_doc(doctype)
        for key, val in data.items():
            if key not in ("doctype", "creation", "owner", "modified", "modified_by"):
                doc.set(key, val)
        doc.insert(ignore_permissions=True)

    frappe.db.commit()
