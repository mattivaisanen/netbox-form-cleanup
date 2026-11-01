"""
Field usage: how many objects of a type have a value in each field.

Shown on the Field Usage page so an admin can spot fields nobody fills in
and hide them with one click. Counts are plain database queries (one per
field), limited to the objects the user may view. "Empty" means the same
as fields.is_empty(): NULL, blank text, empty lists or JSON, no related
objects. Rows that only exist on object pages and whole panels have no
stored value and are not counted.
"""
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.postgres.fields import ArrayField
from django.db import models

from .fields import CF_PREFIX, field_choices
from .rules import rules_for_type

__all__ = ('field_usage',)


def _filled(queryset, model, name):
    """Objects in `queryset` with a value in field `name`, or None when it has no stored value."""
    if name.startswith(CF_PREFIX):
        key = f'custom_field_data__{name[len(CF_PREFIX):]}'
        return (
            queryset.filter(**{f'{key}__isnull': False})  # The key exists...
            .exclude(**{key: None}).exclude(**{key: ''}).exclude(**{key: []})  # ...and holds a value.
            .count()
        )
    try:
        field = model._meta.get_field(name)
    except Exception:
        return None  # A page-only row or a panel.
    if isinstance(field, GenericForeignKey):
        # Assigned object, scope, ...: set when its ID is.
        return queryset.filter(**{f'{field.fk_field}__isnull': False}).count()
    if field.many_to_many:
        return queryset.filter(**{f'{name}__isnull': False}).distinct().count()
    if not getattr(field, 'concrete', False):
        return None
    filled = queryset.filter(**{f'{name}__isnull': False})
    if isinstance(field, (models.CharField, models.TextField)):
        filled = filled.exclude(**{name: ''})
    elif isinstance(field, ArrayField):
        filled = filled.exclude(**{name: []})
    elif isinstance(field, models.JSONField):
        filled = filled.exclude(**{name: {}}).exclude(**{name: []}).exclude(**{name: None})
    return filled.count()


def field_usage(model, queryset):
    """
    One dict per field a rule can name: name, label, filled (objects with a
    value, None when not countable) and rules (the enabled rules that hide
    it on this type, global ones included).
    """
    rules = rules_for_type(model)
    usage = []
    for name, label in field_choices(model):
        try:
            filled = _filled(queryset, model, name)
        except Exception:
            filled = None  # A field the database cannot filter on: show it without a count.
        usage.append({
            'name': name,
            'label': label,
            'filled': filled,
            'rules': [rule for rule in rules if name in rule.fields],
        })
    return usage
