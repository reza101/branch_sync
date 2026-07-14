app_name = "branch_sync"
app_title = "Branch Sync"
app_publisher = "webmajors"
app_description = "Branch ↔ Center sync for multi-branch pharmacy"
app_email = "webmajors.com@gmail.com"
app_license = "Proprietary"

after_install = "branch_sync.setup.after_install"

scheduler_events = {
    "cron": {
        # Push queue to center every 5 minutes
        "*/5 * * * *": [
            "branch_sync.sync.queue.process_queue",
        ],
        # Pull master data from center nightly at 02:00
        "0 2 * * *": [
            "branch_sync.sync.pull.sync_master_data",
        ],
        # Push stock reconciliation to center every morning at 06:00
        "0 6 * * *": [
            "branch_sync.sync.push.push_stock_reconciliation",
        ],
    },
}

# Queue submitted docs for push automatically
doc_events = {
    "Sales Invoice": {
        "validate": "branch_sync.sync.naming.validate_branch_prefix",
        "on_submit": "branch_sync.sync.queue.enqueue_on_submit",
    },
    "Purchase Invoice": {
        "validate": "branch_sync.sync.naming.validate_branch_prefix",
        "on_submit": "branch_sync.sync.queue.enqueue_on_submit",
    },
    "Payment Entry": {
        "validate": "branch_sync.sync.naming.validate_branch_prefix",
        "on_submit": "branch_sync.sync.queue.enqueue_on_submit",
    },
    "Stock Entry": {
        "validate": "branch_sync.sync.naming.validate_branch_prefix",
        "on_submit": "branch_sync.sync.queue.enqueue_on_submit",
    },
    "POS Invoice": {
        "validate": "branch_sync.sync.naming.validate_branch_prefix",
        "on_submit": "branch_sync.sync.queue.enqueue_on_submit",
    },
    "POS Opening Entry": {
        "on_submit": "branch_sync.sync.queue.enqueue_on_submit",
    },
    "POS Closing Entry": {
        "on_submit": "branch_sync.sync.queue.enqueue_on_submit",
    },
    # HRMS — submittable
    "Attendance": {
        "on_submit": "branch_sync.sync.queue.enqueue_on_submit",
        "on_cancel": "branch_sync.sync.lifecycle.sync_cancel",
        "on_trash":  "branch_sync.sync.lifecycle.sync_delete",
    },
    "Leave Application": {
        "on_submit": "branch_sync.sync.queue.enqueue_on_submit",
        "on_cancel": "branch_sync.sync.lifecycle.sync_cancel",
        "on_trash":  "branch_sync.sync.lifecycle.sync_delete",
    },
    "Leave Allocation": {
        "on_submit": "branch_sync.sync.queue.enqueue_on_submit",
        "on_cancel": "branch_sync.sync.lifecycle.sync_cancel",
        "on_trash":  "branch_sync.sync.lifecycle.sync_delete",
    },
    "Leave Encashment": {
        "on_submit": "branch_sync.sync.queue.enqueue_on_submit",
        "on_cancel": "branch_sync.sync.lifecycle.sync_cancel",
        "on_trash":  "branch_sync.sync.lifecycle.sync_delete",
    },
    "Salary Slip": {
        "on_submit": "branch_sync.sync.queue.enqueue_on_submit",
        "on_cancel": "branch_sync.sync.lifecycle.sync_cancel",
        "on_trash":  "branch_sync.sync.lifecycle.sync_delete",
    },
    "Additional Salary": {
        "on_submit": "branch_sync.sync.queue.enqueue_on_submit",
        "on_cancel": "branch_sync.sync.lifecycle.sync_cancel",
        "on_trash":  "branch_sync.sync.lifecycle.sync_delete",
    },
    "Expense Claim": {
        "on_submit": "branch_sync.sync.queue.enqueue_on_submit",
        "on_cancel": "branch_sync.sync.lifecycle.sync_cancel",
        "on_trash":  "branch_sync.sync.lifecycle.sync_delete",
    },
    "Employee Advance": {
        "on_submit": "branch_sync.sync.queue.enqueue_on_submit",
        "on_cancel": "branch_sync.sync.lifecycle.sync_cancel",
        "on_trash":  "branch_sync.sync.lifecycle.sync_delete",
    },
    "Payroll Entry": {
        "on_submit": "branch_sync.sync.queue.enqueue_on_submit",
        "on_cancel": "branch_sync.sync.lifecycle.sync_cancel",
        "on_trash":  "branch_sync.sync.lifecycle.sync_delete",
    },
    "Gratuity": {
        "on_submit": "branch_sync.sync.queue.enqueue_on_submit",
        "on_cancel": "branch_sync.sync.lifecycle.sync_cancel",
        "on_trash":  "branch_sync.sync.lifecycle.sync_delete",
    },
    # HRMS — non-submittable
    "Employee": {
        "after_insert": "branch_sync.sync.queue.enqueue_on_save",
        "on_update":    "branch_sync.sync.queue.enqueue_on_save",
        "on_trash":     "branch_sync.sync.lifecycle.sync_delete",
    },
    "Employee Checkin": {
        "after_insert": "branch_sync.sync.queue.enqueue_on_save",
        "on_update":    "branch_sync.sync.queue.enqueue_on_save",
        "on_trash":     "branch_sync.sync.lifecycle.sync_delete",
    },
}

fixtures = [
    {"dt": "Module Def", "filters": [["name", "=", "Branch Sync"]]},
]

doctype_js = {
    "Branch Sync Settings": "public/js/branch_sync_settings.js",
}
