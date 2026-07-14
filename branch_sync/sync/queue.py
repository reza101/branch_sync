import frappe
from branch_sync.sync.client import get_settings, is_center_reachable

MAX_RETRIES = 5


def _enqueue(doctype, name, action="Push", posting_date=None, posting_time=None):
    """Add a document to the sync queue."""
    queue_doc = frappe.new_doc("Branch Sync Queue")
    queue_doc.action = action
    queue_doc.doctype_name = doctype
    queue_doc.document_name = name
    queue_doc.posting_date = posting_date
    queue_doc.posting_time = str(posting_time) if posting_time else None
    queue_doc.status = "Pending"
    queue_doc.queued_at = frappe.utils.now()
    queue_doc.insert(ignore_permissions=True)
    frappe.db.commit()


def enqueue_on_submit(doc, method):
    """Hook called when a tracked doctype is submitted."""
    settings = get_settings()
    if not settings.is_setup_complete:
        return
    _enqueue(
        doc.doctype, doc.name,
        getattr(doc, "posting_date", None),
        getattr(doc, "posting_time", None),
    )


def enqueue_on_save(doc, method):
    """Hook for non-submittable doctypes (e.g. Employee) — enqueue on insert/update."""
    settings = get_settings()
    if not settings.is_setup_complete:
        return
    # Avoid duplicate pending Push entries for the same document
    if frappe.db.exists("Branch Sync Queue", {
        "action": "Push",
        "doctype_name": doc.doctype,
        "document_name": doc.name,
        "status": "Pending",
    }):
        return
    _enqueue(doc.doctype, doc.name, action="Push")


def enqueue_on_cancel(doc, method):
    """Hook called on cancel — queue a Cancel action."""
    settings = get_settings()
    if not settings.is_setup_complete:
        return
    _enqueue(doc.doctype, doc.name, action="Cancel")


def enqueue_on_trash(doc, method):
    """Hook called on delete — queue a Delete action (doc still exists at this point)."""
    settings = get_settings()
    if not settings.is_setup_complete:
        return
    _enqueue(doc.doctype, doc.name, action="Delete")


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
    import time
    from branch_sync.sync.push import push_document
    from branch_sync.sync.lifecycle import cancel_on_center, delete_on_center
    from branch_sync.sync.client import write_log
    start = time.time()
    try:
        action = item.get("action") or "Push"
        if action == "Push":
            # push_document writes its own log
            push_document(item.doctype_name, item.document_name, settings)
        elif action == "Cancel":
            cancel_on_center(item.doctype_name, item.document_name, settings)
            write_log("Cancel", item.doctype_name, item.document_name, "Success",
                      duration=time.time() - start)
        elif action == "Delete":
            delete_on_center(item.doctype_name, item.document_name, settings)
            write_log("Delete", item.doctype_name, item.document_name, "Success",
                      duration=time.time() - start)

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
        action = item.get("action") or "Push"
        if action in ("Cancel", "Delete"):
            write_log(action, item.doctype_name, item.document_name, "Failed",
                      error_message=str(e), duration=time.time() - start)
    frappe.db.commit()
