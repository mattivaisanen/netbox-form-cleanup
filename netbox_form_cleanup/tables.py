import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable, columns

from .models import FieldRule

__all__ = ('FieldRuleTable',)


class FieldRuleTable(NetBoxTable):
    name = tables.Column(verbose_name=_('Name'), linkify=True)
    enabled = columns.BooleanColumn(verbose_name=_('Enabled'))
    object_type = columns.ContentTypeColumn(verbose_name=_('Object type'), default=_('Every type'))
    fields = columns.ArrayColumn(verbose_name=_('Fields'))
    condition = columns.ChoiceFieldColumn(verbose_name=_('Condition'))
    condition_field = tables.Column(verbose_name=_('Condition field'))
    in_forms = columns.BooleanColumn(verbose_name=_('Forms'))
    in_detail = columns.BooleanColumn(verbose_name=_('Object pages'))
    in_tables = columns.BooleanColumn(verbose_name=_('Object lists'))
    groups = columns.ManyToManyColumn(verbose_name=_('User groups'), linkify_item=True)
    comments = columns.MarkdownColumn(verbose_name=_('Comments'))
    tags = columns.TagColumn(url_name='plugins:netbox_form_cleanup:fieldrule_list')

    class Meta(NetBoxTable.Meta):
        model = FieldRule
        fields = (
            'pk', 'id', 'name', 'enabled', 'object_type', 'fields', 'condition', 'condition_field', 'in_forms',
            'in_detail', 'in_tables', 'groups', 'description', 'comments', 'tags', 'created', 'last_updated',
        )
        default_columns = (
            'pk', 'name', 'enabled', 'object_type', 'fields', 'condition', 'in_forms', 'in_detail', 'in_tables',
            'groups',
        )
