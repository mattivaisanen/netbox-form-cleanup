"""
The NetBox internals this plugin wraps (see DEVELOPER.md). Each wrapper
calls NetBox's own code first and only changes what is drawn; it never
changes data or what a form saves. `apply()` runs once from ready().
"""
_applied = False


def apply():
    global _applied
    if _applied:
        return
    from . import forms, panels, tables

    forms.apply()
    panels.apply()
    tables.apply()
    _applied = True
