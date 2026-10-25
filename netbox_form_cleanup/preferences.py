"""User preferences (shown under the user's Preferences page). Read with rules.preference()."""
from django.utils.translation import gettext_lazy as _

from users.preferences import UserPreference

_DEFAULT_ON_OFF = (
    ('', _('Default')),
    ('on', _('On')),
    ('off', _('Off')),
)

preferences = {
    'hide_empty_detail': UserPreference(
        label=_('Hide empty fields on object pages'),
        choices=_DEFAULT_ON_OFF,
        default='',
        description=_('Leave out fields that have no value. Default: as the administrator set it.'),
    ),
    'hide_empty_tables': UserPreference(
        label=_('Hide empty columns in object lists'),
        choices=_DEFAULT_ON_OFF,
        default='',
        description=_('Leave out columns with no value on the current page. Default: as the administrator set it.'),
    ),
    'apply_to_me': UserPreference(
        label=_('Apply field rules to me (superusers)'),
        choices=(
            ('off', _('Off: show me every field')),
            ('on', _('On: show me what other users see')),
        ),
        default='off',
        description=_('Superusers see every field unless this is on. No effect for other users.'),
    ),
}
