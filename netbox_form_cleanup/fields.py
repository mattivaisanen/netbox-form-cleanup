"""
Field names a rule can use, and what counts as an empty value.

Names are the model's own field names (as on its edit form and in its
table), and cf_<name> for custom fields (as NetBox names them on forms and
tables).
"""
from django.db import models
from django.db.models.fields.related import ForeignObjectRel
from django.utils.text import capfirst

#: Never offered: bookkeeping NetBox fills in itself.
SKIP_FIELDS = {'id', 'created', 'last_updated', 'custom_field_data'}

CF_PREFIX = 'cf_'


def _label(field):
    return capfirst(str(getattr(field, 'verbose_name', None) or field.name.replace('_', ' ')))


def field_choices(model):
    """(name, label) for each field of `model` a rule can hide, custom fields last."""
    from extras.models import CustomField

    choices = []
    for field in model._meta.get_fields():
        if isinstance(field, ForeignObjectRel):
            continue  # Reverse relations: other objects pointing here.
        if field.name in SKIP_FIELDS or field.name.startswith('_'):
            continue
        if isinstance(field, models.Field) and not field.editable and not field.is_relation:
            continue
        choices.append((field.name, _label(field)))
    for cf in CustomField.objects.get_for_model(model):
        choices.append((f'{CF_PREFIX}{cf.name}', f'{cf.label or cf.name} (custom field)'))
    return choices


def public_models():
    from core.models import ObjectType

    for object_type in ObjectType.objects.public().order_by('app_label', 'model'):
        if (model := object_type.model_class()) is not None:
            yield model


def global_field_choices():
    """Every field name any public model has, for rules without an object type."""
    seen = {}
    for model in public_models():
        for name, label in field_choices(model):
            seen.setdefault(name, label)
    return sorted(seen.items(), key=lambda item: str(item[1]).lower())


def is_empty(value):
    """True for None, '', empty lists and related managers without objects. False and 0 are values."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ''
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    if hasattr(value, 'all') and callable(value.all):
        # A related manager or queryset (prefetched where NetBox prefetches).
        try:
            return not value.all()
        except Exception:
            return False
    return False


def object_value(obj, name):
    """The value of field `name` (or cf_<name>) on a saved or unsaved object."""
    if name.startswith(CF_PREFIX):
        data = getattr(obj, 'custom_field_data', None) or {}
        if name[len(CF_PREFIX):] in data or not hasattr(obj, name):
            return data.get(name[len(CF_PREFIX):])
    try:
        field = obj._meta.get_field(name)
    except Exception:
        field = None
    if field is not None and field.many_to_many and obj.pk is None:
        return None
    if field is not None and field.is_relation and (field.many_to_one or field.one_to_one) and field.concrete:
        # The id, so an unsaved object does not query its relation.
        return getattr(obj, field.attname, None)
    return getattr(obj, name, None)
