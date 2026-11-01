from urllib.parse import urlencode

from django.shortcuts import render
from django.urls import reverse
from django.utils.text import capfirst
from django.views import View

from netbox.ui import layout
from netbox.ui.panels import CommentsPanel
from extras.ui.panels import CustomFieldsPanel, TagsPanel
from netbox.views import generic
from utilities.views import ContentTypePermissionRequiredMixin, register_model_view

from . import filtersets, forms, tables, ui, usage
from .models import FieldRule


@register_model_view(FieldRule, 'list', path='', detail=False)
class FieldRuleListView(generic.ObjectListView):
    queryset = FieldRule.objects.select_related('object_type').prefetch_related('groups', 'except_groups', 'tags')
    table = tables.FieldRuleTable
    filterset = filtersets.FieldRuleFilterSet
    filterset_form = forms.FieldRuleFilterForm


@register_model_view(FieldRule)
class FieldRuleView(generic.ObjectView):
    queryset = FieldRule.objects.select_related('object_type').prefetch_related('groups', 'except_groups', 'tags')
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


class FieldUsageView(ContentTypePermissionRequiredMixin, View):
    """
    Field Usage: for one object type, how many objects have a value in each
    field and which rules hide it, with buttons that open the rule form
    already filled in. Helps find fields nobody uses.
    """
    template_name = 'netbox_form_cleanup/field_usage.html'

    def get_required_permission(self):
        return 'netbox_form_cleanup.view_fieldrule'

    def get(self, request):
        form = forms.FieldUsageForm(request.GET or None)
        context = {'form': form, 'usage': None}
        if form.is_valid() and form.cleaned_data['object_type']:
            object_type = form.cleaned_data['object_type']
            model = object_type.model_class()
            if model is not None:
                # Only objects the user may see are counted.
                queryset = model.objects.all()
                if hasattr(queryset, 'restrict'):
                    queryset = queryset.restrict(request.user, 'view')
                total = queryset.count()
                rows = usage.field_usage(model, queryset)
                type_name = capfirst(str(model._meta.verbose_name))
                for row in rows:
                    counted = total and row['filled'] is not None
                    row['percent'] = round(100 * row['filled'] / total) if counted else None
                    # Opens the rule form filled in for this one field.
                    row['add_query'] = urlencode({
                        'name': f'{type_name}: {row["label"]}'[:100],
                        'object_type': object_type.pk,
                        'fields': row['name'],
                    })
                unused = [row['name'] for row in rows if row['filled'] == 0 and not row['rules']]
                context.update({
                    'object_type': object_type,
                    'model': model,
                    'total': total,
                    'usage': rows,
                    'add_url': reverse('plugins:netbox_form_cleanup:fieldrule_add'),
                    'unused_query': urlencode(
                        {'object_type': object_type.pk, 'fields': unused}, doseq=True,
                    ) if unused and total else '',
                })
        return render(request, self.template_name, context)
