from netbox.ui import layout
from netbox.ui.panels import CommentsPanel
from extras.ui.panels import CustomFieldsPanel, TagsPanel
from netbox.views import generic
from utilities.views import register_model_view

from . import filtersets, forms, tables, ui
from .models import FieldRule


@register_model_view(FieldRule, 'list', path='', detail=False)
class FieldRuleListView(generic.ObjectListView):
    queryset = FieldRule.objects.select_related('object_type').prefetch_related('groups', 'tags')
    table = tables.FieldRuleTable
    filterset = filtersets.FieldRuleFilterSet
    filterset_form = forms.FieldRuleFilterForm


@register_model_view(FieldRule)
class FieldRuleView(generic.ObjectView):
    queryset = FieldRule.objects.select_related('object_type').prefetch_related('groups', 'tags')
    template_name = 'generic/object.html'
    layout = layout.SimpleLayout(
        left_panels=[
            ui.FieldRulePanel(),
            TagsPanel(),
            CommentsPanel(),
        ],
        right_panels=[
            ui.FieldRuleScopePanel(),
            CustomFieldsPanel(),
        ],
    )


@register_model_view(FieldRule, 'add', detail=False)
@register_model_view(FieldRule, 'edit')
class FieldRuleEditView(generic.ObjectEditView):
    queryset = FieldRule.objects.all()
    form = forms.FieldRuleForm


@register_model_view(FieldRule, 'delete')
class FieldRuleDeleteView(generic.ObjectDeleteView):
    queryset = FieldRule.objects.all()


@register_model_view(FieldRule, 'bulk_import', path='import', detail=False)
class FieldRuleBulkImportView(generic.BulkImportView):
    queryset = FieldRule.objects.all()
    model_form = forms.FieldRuleImportForm


@register_model_view(FieldRule, 'bulk_edit', path='edit', detail=False)
class FieldRuleBulkEditView(generic.BulkEditView):
    queryset = FieldRule.objects.all()
    filterset = filtersets.FieldRuleFilterSet
    table = tables.FieldRuleTable
    form = forms.FieldRuleBulkEditForm


@register_model_view(FieldRule, 'bulk_delete', path='delete', detail=False)
class FieldRuleBulkDeleteView(generic.BulkDeleteView):
    queryset = FieldRule.objects.all()
    filterset = filtersets.FieldRuleFilterSet
    table = tables.FieldRuleTable
