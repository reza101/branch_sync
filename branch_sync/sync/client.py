import requests
import frappe


def get_settings():
    return frappe.get_single("Branch Sync Settings")


def is_center_reachable(settings=None):
    if not settings:
        settings = get_settings()
    try:
        r = requests.get(
            f"{_base_url(settings)}/api/method/frappe.ping",
            timeout=5,
        )
        reachable = r.ok
    except Exception:
        reachable = False

    status = "Online" if reachable else "Offline"
    frappe.db.set_value("Branch Sync Settings", None, "last_connection_status", status)
    frappe.db.commit()
    return reachable


def _base_url(settings):
    return settings.center_url.rstrip("/")


def _resource_url(settings, doctype, name=None):
    """Build a properly URL-encoded resource URL."""
    from urllib.parse import quote
    base = f"{_base_url(settings)}/api/resource/{quote(doctype, safe='')}"
    if name is not None:
        base += f"/{quote(name, safe='')}"
    return base


def center_get(settings, doctype, name):
    """Fetch a single document from center. Returns dict or None."""
    r = requests.get(
        _resource_url(settings, doctype, name),
        headers=settings.get_auth_headers(),
        timeout=15,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json().get("data")


def center_exists(settings, doctype, name):
    return center_get(settings, doctype, name) is not None


def center_insert(settings, doctype, data):
    """Insert a new document on center."""
    r = requests.post(
        _resource_url(settings, doctype),
        json=data,
        headers=settings.get_auth_headers(),
        timeout=30,
    )
    if not r.ok:
        raise Exception(f"HTTP {r.status_code}: {r.text[:500]}")
    return r.json().get("data")


def center_list(settings, doctype, filters=None, fields=None, limit_page_length=500):
    """Fetch a list of documents from center."""
    params = {"limit_page_length": limit_page_length}
    if filters:
        import json
        params["filters"] = json.dumps(filters)
    if fields:
        import json
        params["fields"] = json.dumps(fields)

    r = requests.get(
        f"{_base_url(settings)}/api/resource/{doctype}",
        params=params,
        headers=settings.get_auth_headers(),
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("data", [])


def write_log(sync_type, doctype_name, document_name, status, error_message=None, duration=None):
    log = frappe.new_doc("Branch Sync Log")
    log.sync_type = sync_type
    log.doctype_name = doctype_name
    log.document_name = document_name
    log.status = status
    log.timestamp = frappe.utils.now()
    if error_message:
        log.error_message = str(error_message)[:2000]
    if duration is not None:
        log.duration_seconds = duration
    log.insert(ignore_permissions=True)
    frappe.db.commit()
