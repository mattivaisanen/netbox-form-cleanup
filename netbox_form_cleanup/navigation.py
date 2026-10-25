from django.utils.translation import gettext_lazy as _

from netbox.plugins import PluginMenuButton, PluginMenuItem

# A small plugin: one entry under NetBox's Plugins menu rather than a top-level menu of its own.
menu_items = (
    PluginMenuItem(
        link='plugins:netbox_form_cleanup:fieldrule_list',
        link_text=_('Field Rules'),
        permissions=['netbox_form_cleanup.view_fieldrule'],
        buttons=(
            PluginMenuButton(
                link='plugins:netbox_form_cleanup:fieldrule_add',
                title=_('Add'),
                icon_class='mdi mdi-plus-thick',
                permissions=['netbox_form_cleanup.add_fieldrule'],
            ),
            PluginMenuButton(
                link='plugins:netbox_form_cleanup:fieldrule_bulk_import',
                title=_('Import'),
                icon_class='mdi mdi-upload',
                permissions=['netbox_form_cleanup.add_fieldrule'],
            ),
        ),
    ),
)
