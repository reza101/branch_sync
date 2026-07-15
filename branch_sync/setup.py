import frappe


def after_install():
    frappe.db.commit()


def after_migrate():
    """Re-apply branch naming series prefix after migrate reloads fixtures."""
    try:
        settings = frappe.get_cached_doc("Branch Sync Settings")
    except Exception:
        return
    if not settings.is_setup_complete or not settings.branch_prefix:
        return
    from branch_sync.sync.naming import configure_naming_series
    configure_naming_series(settings.branch_prefix)
    frappe.db.commit()
