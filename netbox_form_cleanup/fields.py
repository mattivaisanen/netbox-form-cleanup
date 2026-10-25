"""
Field names a rule can use, and what counts as an empty value.

Names are the model's own field names (as on its edit form and in its
table), and cf_<name> for custom fields (as NetBox names them on forms and
tables).
"""
from decimal import Decimal, InvalidOperation

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
    known = {name for name, _label in choices}
    for name, label in page_attributes(model):
        if name not in known:
            choices.append((name, f'{label} (object page only)'))
            known.add(name)
    return choices


def _panels(item):
    """Every panel in a layout (rows → columns → panels)."""
    from netbox.ui.layout import Column, Layout, Row

    if isinstance(item, (Layout, Row, Column)):
        for child in item:
            yield from _panels(child)
    else:
        yield item


#: Prefix of rule field names that stand for a whole panel of an object page.
PANEL_PREFIX = 'panel:'


def panel_key(panel):
    """
    The rule field name of an object page panel: panel:<app.model> for a
    table of related objects, panel:<title> (slugified) for others, None
    for panels without a fixed title (plugin content, templates).
    """
    from django.utils.text import slugify
    from netbox.ui.panels import ObjectsTablePanel

    if isinstance(panel, ObjectsTablePanel):
        return f'{PANEL_PREFIX}{panel.model_label.lower()}'
    title = getattr(panel, 'title', None)
    if not title:
        return None
    return f'{PANEL_PREFIX}{slugify(str(title))}'


def panel_label(panel):
    from netbox.ui.panels import ObjectsTablePanel

    if isinstance(panel, ObjectsTablePanel) and not panel.title:
        try:
            return capfirst(str(panel.model._meta.verbose_name_plural))
        except Exception:
            return panel.model_label
    return capfirst(str(panel.title))


def _page_panels(model):
    """Every panel of the model's object page (its registered detail view's layout)."""
    from netbox.registry import registry

    views = registry['views'].get(model._meta.app_label, {}).get(model._meta.model_name, [])
    for entry in views:
        layout = getattr(entry['view'], 'layout', None)
        if entry.get('name') != '' or not entry.get('detail', True) or layout is None:
            continue
        try:
            yield from list(_panels(layout))
        except Exception:
            continue


def page_attributes(model):
    """
    (name, label) of what a rule can hide on the model's object page beyond
    its fields: rows that are no field of their own (a device's total
    weight, GPS coordinates) and whole panels (panel:<...>, e.g. a device's
    Virtual Device Contexts table).
    """
    from netbox.ui.panels import ObjectAttributesPanel

    rows, panels = [], []
    for panel in _page_panels(model):
        key = panel_key(panel)
        if key:
            panels.append((key, f'{panel_label(panel)} panel'))
        if isinstance(panel, ObjectAttributesPanel):
            for name, attr in panel._attrs.items():
                label = attr.label or ObjectAttributesPanel._name_to_label(name)
                rows.append((name, capfirst(str(label))))
    return rows + panels


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


def _related_model(model, name):
    if model is None or name.startswith(CF_PREFIX):
        return None
    try:
        field = model._meta.get_field(name)
    except Exception:
        return None
    return field.related_model if field.is_relation else None


def _labels_of(obj):
    """What a related object can be named by in a rule: ID, name, slug, model (device types), display."""
    labels = {str(obj.pk), str(obj)}
    for attr in ('name', 'slug', 'model'):
        value = getattr(obj, attr, None)
        if isinstance(value, str) and value:
            labels.add(value)
    return labels


def value_labels(model, name, value):
    """
    Every text a field's value matches in a rule's "is one of" list, lower
    case. Related objects (as objects, IDs or lists of either) give their
    ID, name, slug and display; True/False give "true"/"false"; anything
    else its text.
    """
    if is_empty(value):
        return set()
    if hasattr(value, 'all') and callable(value.all):
        value = list(value.all())
    items = value if isinstance(value, (list, tuple, set)) else [value]
    related = _related_model(model, name)
    labels = set()
    pks = []
    for item in items:
        if hasattr(item, '_meta') and hasattr(item, 'pk'):
            labels |= _labels_of(item)
        elif isinstance(item, bool):
            labels.add('true' if item else 'false')
        elif related is not None and str(item).strip().isdigit():
            pks.append(int(str(item).strip()))
            labels.add(str(item).strip())
        elif isinstance(item, (int, float, Decimal)):
            labels.add(number_label(item))
        else:
            labels.add(str(item).strip())
    if pks:
        for obj in related.objects.filter(pk__in=pks):
            labels |= _labels_of(obj)
    return {label.lower() for label in labels}


def comparable(value):
    """A value in a form both a saved object and a form give for the same thing (related objects by ID)."""
    if is_empty(value):
        return None
    if hasattr(value, 'all') and callable(value.all):
        value = list(value.all())
    if isinstance(value, (list, tuple, set)):
        return tuple(sorted(str(comparable(item)) for item in value))
    if hasattr(value, '_meta') and hasattr(value, 'pk'):
        return str(value.pk)
    return str(value).strip()


def number_label(value):
    """A number as text without trailing zeros, so 0, 0.0 and 0.00 all read "0"."""
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return str(value).strip()
    if not number.is_finite():
        return str(value).strip()
    text = format(number.normalize(), 'f')
    return '0' if text in ('-0', '') else text


def wanted_label(value):
    """A rule's value as value_labels() writes it: numbers normalized, lower case."""
    text = value.strip()
    try:
        Decimal(text)
    except (InvalidOperation, ValueError):
        return text.lower()
    return number_label(text).lower() if any(ch.isdigit() for ch in text) else text.lower()
