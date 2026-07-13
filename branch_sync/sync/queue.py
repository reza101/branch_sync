import frappe
from branch_sync.sync.client import get_settings, is_center_reachable

MAX_RETRIES = 5


def enqueue_on_submit(doc, method):
    """Hook called when a tracked doctype is submitted."""
    settings = get_settings()
    if not settings.is_setup_complete:
        return

    posting_date = getattr(doc, "posting_date", None)
    posting_time = getattr(doc, "posting_time", None)

    queue_doc = frappe.new_doc("Branch Sync Queue")
    queue_doc.doctype_name = doc.doctype
    queue_doc.document_name = doc.name
    queue_doc.posting_date = posting_date
    queue_doc.posting_time = str(posting_time) if posting_time else None
    queue_doc.status = "Pending"
    queue_doc.queued_at = frappe.utils.now()
    queue_doc.insert(ignore_permissions=True)
    frappe.db.commit()


def process_queue():
    """Called by scheduler every 5 minutes. Pushes pending items to center."""
    settings = get_settings()
    if not settings.is_setup_complete:
        return

    if not is_center_reachable(settings):
        return

    # FIFO order — critical for correct stock valuation
    pending = frappe.get_all(
        "Branch Sync Queue",
        filters={"status": "Pending"},
        fields=["name", "doctype_name", "document_name", "retry_count",
                "posting_date", "posting_time"],
        order_by="posting_date asc, posting_time asc, queued_at asc",
        limit=50,
    )

    for item in pending:
        _process_queue_item(item, settings)

    frappe.db.set_value(
        "Branch Sync Settings", None,
        "last_push_at", frappe.utils.now()
    )
    frappe.db.commit()


def _process_queue_item(item, settings):
    from branch_sync.sync.push import push_document
    try:
        push_document(item.doctype_name, item.document_name, settings)
        frappe.db.set_value("Branch Sync Queue", item.name, {
            "status": "Synced",
            "synced_at": frappe.utils.now(),
        })
    except Exception as e:
        retry_count = (item.retry_count or 0) + 1
        new_status = "Failed" if retry_count >= MAX_RETRIES else "Pending"
        frappe.db.set_value("Branch Sync Queue", item.name, {
            "status": new_status,
            "retry_count": retry_count,
            "error_message": str(e)[:2000],
        })
    frappe.db.commit()
