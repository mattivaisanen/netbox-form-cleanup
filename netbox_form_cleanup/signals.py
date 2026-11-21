"""
Keep rules from widening by themselves. A rule with no user groups applies
to everyone, so when the last of its user groups is deleted the rule is
disabled first, with a change log entry saying why.

Two ways a deletion reaches a rule:
- With a request (UI, API), NetBox's own pre_delete handler removes the
  group from each rule first (an m2m "post_remove"), so group_deleting()
  finds no rule any more. rule_groups_changed() catches that case.
- Without one (scripts, shell), the m2m rows just go with the group:
  group_deleting() notes the rules before, group_deleted() checks them after.

Except user groups need nothing: losing one only stops an exception for
members of a group that no longer exists.
"""
from threading import local

from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import m2m_changed, post_delete, pre_delete
from django.utils.translation import gettext as _

from users.models import Group

try:
    # NetBox internal: the objects whose pre_delete it is handling in this thread.
    from core.signals import _signals_received
except ImportError:  # A later NetBox renamed it: only the delete receivers are left.
    _signals_received = None

from .models import FieldRule

# Rules that list a group being deleted, per thread: (group pk, rule pk).
_pending = local()


def connect():
    """Called once from FormCleanupConfig.ready()."""
    pre_delete.connect(group_deleting, sender=Group, dispatch_uid='netbox_form_cleanup:group_deleting')
    post_delete.connect(group_deleted, sender=Group, dispatch_uid='netbox_form_cleanup:group_deleted')
    m2m_changed.connect(
        rule_groups_changed, sender=FieldRule.groups.through, dispatch_uid='netbox_form_cleanup:rule_groups',
    )


def group_deleting(sender, instance, **kwargs):
    """Note the enabled rules limited to instance; group_deleted() checks them once the rows are gone."""
    pending = _pending.__dict__.setdefault('rules', set())
    for pk in FieldRule.objects.filter(enabled=True, groups=instance).values_list('pk', flat=True):
        pending.add((instance.pk, pk))


def group_deleted(sender, instance, **kwargs):
    """
    Disable the noted rules left with no user groups. Checked after the
    delete, so deleting all of a rule's groups at once is caught too.
    """
    pending = _pending.__dict__.setdefault('rules', set())
    entries = {entry for entry in pending if entry[0] == instance.pk}
    pending.difference_update(entries)
    noted = {rule_pk for _group_pk, rule_pk in entries}
    for rule in FieldRule.objects.filter(pk__in=noted, enabled=True):
        if not rule.groups.exists():
            disable(rule, instance)


def rule_groups_changed(sender, instance, action, reverse, pk_set, **kwargs):
    """A rule lost its last user group because that group is being deleted (not because of an edit)."""
    if action != 'post_remove' or reverse or not isinstance(instance, FieldRule) or not instance.enabled:
        return
    if instance.groups.exists():
        return  # Other groups are left, so the rule does not widen.
    deleting = getattr(_signals_received, 'pre_delete', None) or set()
    object_type = ContentType.objects.get_for_model(Group)
    deleted = [pk for pk in pk_set or () if (object_type, pk) in deleting]
    if deleted:
        disable(instance, Group.objects.filter(pk=deleted[0]).first() or deleted[0])


def disable(rule, group):
    """Disable rule, with a change log message naming the deleted group."""
    if getattr(rule, '_prechange_snapshot', None) is None:
        # NetBox's delete handler took one before removing the group; keep it so "before" lists it.
        rule.snapshot()
    rule.enabled = False
    rule._changelog_message = _('Form Cleanup: disabled, its only user group {name} was deleted').format(name=group)
    rule.save()
