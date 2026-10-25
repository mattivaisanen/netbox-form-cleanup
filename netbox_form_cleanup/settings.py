"""Plugin settings: PLUGINS_CONFIG['netbox_form_cleanup'], with defaults
from FormCleanupConfig.default_settings."""
from netbox.plugins.utils import get_plugin_config

PLUGIN = 'netbox_form_cleanup'


def get_setting(key):
    return get_plugin_config(PLUGIN, key)
