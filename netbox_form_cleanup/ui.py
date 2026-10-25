"""Panels of the field rule page (NetBox 4.7 layouts)."""
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from netbox.ui import attrs, panels
from utilities.object_types import object_type_name


class ObjectTypeAttr(attrs.ObjectAttribute):
    """The rule's object type, or "Every object type" when blank."""
    def render(self, obj, context):
        object_type = self.get_value(obj)
        if object_type is None:
            return format_html('<span class="text-muted">{}</span>', _('Every object type'))
        return format_html('{}', object_type_name(object_type))


class FieldRulePanel(panels.ObjectAttributesPanel):
    title = _('Field rule')

    name = attrs.TextAttr('name')
    description = attrs.TextAttr('description')
    enabled = attrs.BooleanAttr('enabled')
    object_type = ObjectTypeAttr('object_type', label=_('Object type'))
    fields = attrs.ArrayAttr('fields', style='font-monospace')
    condition = attrs.ChoiceAttr('condition')
    condition_field = attrs.TextAttr('condition_field', style='font-monospace')
    condition_values = attrs.ArrayAttr('condition_values')


class FieldRuleScopePanel(panels.ObjectAttributesPanel):
    title = _('Scope')

    in_forms = attrs.BooleanAttr('in_forms', label=_('Forms'))
    in_detail = attrs.BooleanAttr('in_detail', label=_('Object pages'))
    in_tables = attrs.BooleanAttr('in_tables', label=_('Object lists'))
    groups = attrs.RelatedObjectListAttr('groups', label=_('User groups'), linkify=True)
