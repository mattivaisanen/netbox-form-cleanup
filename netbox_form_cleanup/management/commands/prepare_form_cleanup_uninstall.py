"""
Remove what would break NetBox pages once this plugin is gone. Run it while
the plugin is still installed, right before taking it out of PLUGINS.

Field rules live in the plugin's own table, but NetBox keeps rows about any
object, field rules included: change log and journal entries, bookmarks,
notifications, tag assignments and the like. Once the plugin's model is
gone, a page listing such a row can't load the rule behind it and fails
with a server error.

So this deletes those rows, takes the plugin's object type off custom
fields, custom links, export templates, saved filters, tags, event rules
and permissions (deleting the ones that were only about field rules),
deletes custom fields whose values are field rules, and removes the
plugin's user preferences.

Field rules and the plugin's own tables are left alone;
`migrate netbox_form_cleanup zero` removes those.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from core.models import Job, ObjectChange
from extras.models import (
    Bookmark,
    CachedValue,
    CustomField,
    CustomLink,
    EventRule,
    ExportTemplate,
    ImageAttachment,
    JournalEntry,
    Notification,
    SavedFilter,
    Subscription,
    TableConfig,
    Tag,
    TaggedItem,
)
from users.models import ObjectPermission, UserConfig

APP_LABEL = 'netbox_form_cleanup'


def _rows():
    """Rows in NetBox's own tables that point at this plugin's objects."""
    ours = {'object_type__app_label': APP_LABEL}
    return {
        'notifications': Notification.objects.filter(**ours),
        'bookmarks': Bookmark.objects.filter(**ours),
        'subscriptions': Subscription.objects.filter(**ours),
        'changelog entries': ObjectChange.objects.filter(
            Q(changed_object_type__app_label=APP_LABEL) | Q(related_object_type__app_label=APP_LABEL)
        ),
        'journal entries': JournalEntry.objects.filter(assigned_object_type__app_label=APP_LABEL),
        'tag assignments': TaggedItem.objects.filter(content_type__app_label=APP_LABEL),
        'image attachments': ImageAttachment.objects.filter(**ours),
        'saved table configs': TableConfig.objects.filter(**ours),
        'search index entries': CachedValue.objects.filter(**ours),
        'background jobs': Job.objects.filter(**ours),
    }


def _object_type_users():
    """
    NetBox objects limited to object types, offered on field rules. Each gets
    this plugin's type removed; the ones left with no object type at all were
    only about field rules and are deleted.
    """
    found = {}
    for label, model in (
        ('custom fields', CustomField), ('custom links', CustomLink), ('export templates', ExportTemplate),
        ('saved filters', SavedFilter), ('tags', Tag), ('event rules', EventRule), ('permissions', ObjectPermission),
    ):
        objects = list(model.objects.filter(object_types__app_label=APP_LABEL).distinct())
        if objects:
            found[label] = objects
    return found


def _only_ours(obj):
    return not obj.object_types.exclude(app_label=APP_LABEL).exists()


def _user_configs():
    """User preferences that hold this plugin's settings (plugins.netbox_form_cleanup.*)."""
    return list(UserConfig.objects.filter(data__plugins__has_key=APP_LABEL))


class Command(BaseCommand):
    help = (
        "Delete NetBox rows that point at this plugin's field rules (changelog and journal entries, bookmarks, "
        'notifications, tag assignments, ...), take its object type off custom fields, tags, event rules, '
        'permissions and the like, and remove its user preferences, so NetBox keeps working after the plugin '
        'is removed.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Only show what would be removed.')
        parser.add_argument('--noinput', '--no-input', action='store_false', dest='interactive',
                            help='Do not ask for confirmation.')

    def handle(self, *args, dry_run=False, interactive=True, **options):
        rows = _rows()
        users = _object_type_users()
        object_fields = list(CustomField.objects.filter(related_object_type__app_label=APP_LABEL))
        configs = _user_configs()

        for name, queryset in rows.items():
            if count := queryset.count():
                self.stdout.write(f'{count} {name} for field rules')
        for label, objects in users.items():
            deleted = [str(obj) for obj in objects if _only_ours(obj)]
            kept = [str(obj) for obj in objects if not _only_ours(obj)]
            if kept:
                self.stdout.write(f'{label} to take the field rule object type off: {", ".join(kept)}')
            if deleted:
                self.stdout.write(f'{label} only for field rules, to delete: {", ".join(deleted)}')
        if object_fields:
            names = ', '.join(str(field) for field in object_fields)
            self.stdout.write(f'custom fields pointing at field rules, to delete: {names}')
        if configs:
            self.stdout.write(f'Form Cleanup preferences of {len(configs)} user(s)')

        if dry_run:
            return
        if interactive and input('Remove these? [y/N] ').strip().lower() not in ('y', 'yes'):
            self.stdout.write('Nothing removed.')
            return

        with transaction.atomic():
            for queryset in rows.values():
                queryset.delete()
            for objects in users.values():
                for obj in objects:
                    if _only_ours(obj):
                        obj.delete()
                    else:
                        obj.object_types.remove(*obj.object_types.filter(app_label=APP_LABEL))
            for field in object_fields:
                field.delete()
            for config in configs:
                config.data['plugins'].pop(APP_LABEL, None)
                config.save()
        self.stdout.write(self.style.SUCCESS(
            'Done. You can now run "migrate netbox_form_cleanup zero", take netbox_form_cleanup out of PLUGINS '
            'and restart NetBox.'
        ))
