import frappe
from frappe.model.document import Document


class BranchSyncSettings(Document):
    def get_auth_headers(self):
        return {
            "Authorization": f"token {self.center_api_key}:{self.get_password('center_api_secret')}",
            "Content-Type": "application/json",
        }
