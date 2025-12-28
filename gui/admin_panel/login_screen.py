# gui/admin_panel/login_screen.py

"""
Compatibility wrapper:
Old code imports `AdminPanel` from here with (back_callback, stack).
We now delegate to the new AdminLogin class.
"""

from .admin_login import AdminLogin


class AdminPanel(AdminLogin):
    def __init__(self, back_callback, *args, **kwargs):
        # args may contain `stack`, we just ignore it here
        
        super().__init__(back_callback)
