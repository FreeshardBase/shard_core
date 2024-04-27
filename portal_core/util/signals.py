from blinker import Signal

on_terminals_update = Signal()
async_on_first_terminal_add = Signal()
on_terminal_add = Signal()
on_terminal_auth = Signal()

on_apps_update = Signal()
async_on_request_to_app = Signal()  # todo: make sync
on_app_install_error = Signal()

async_on_peer_write = Signal()
on_peer_auth = Signal()

on_backup_update = Signal()
