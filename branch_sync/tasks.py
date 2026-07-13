import frappe


def process_queue():
    from branch_sync.sync.queue import process_queue as _process_queue
    _process_queue()


def sync_master_data():
    from branch_sync.sync.pull import sync_master_data as _sync_master_data
    _sync_master_data()


def push_stock_reconciliation():
    from branch_sync.sync.push import push_stock_reconciliation as _push
    _push()
