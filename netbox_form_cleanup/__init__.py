"""
Hide fields from NetBox's web UI: everywhere, per object type, always or
only while they are empty.

Admins add *field rules* (models.FieldRule) in the UI. On add and edit forms
hidden fields move into a collapsed "More fields" section (their values are
still submitted); on object pages they are left out of the attribute panels;
optionally they are removed from object lists. A setting and a per-user
preference also leave out every empty field on object pages and every empty
column on lists. The REST API and the data are never touched. See
DEVELOPER.md for the NetBox internals this wraps.
"""
from netbox.plugins import PluginConfig


class FormCleanupConfig(PluginConfig):
    name = 'netbox_form_cleanup'
    verbose_name = 'Form Cleanup'
    description = 'Hide unused or empty fields from NetBox forms, object pages and lists.'
    version = '0.1.0'
    author = 'Matti'
    base_url = 'form-cleanup'
    # Only claim what CI tests (.github/workflows/test.yml).
    min_version = '4.7.0'

    default_settings = {
        # Superusers see every field unless they switch on "Apply field
        # rules to me" in their preferences.
        'exempt_superusers': True,
        # Defaults for users who leave the preference on "Default".
        'hide_empty_detail': False,
        'hide_empty_tables': False,
    }

    menu = 'navigation.menu'
    template_extensions = 'template_content.template_extensions'
    user_preferences = 'preferences.preferences'
    search_indexes = 'search.indexes'

    def ready(self):
        super().ready()
        from . import hooks

        hooks.apply()


config = FormCleanupConfig
