import frappe


def after_install():
    """Redirect to setup wizard after app install."""
    frappe.db.commit()
