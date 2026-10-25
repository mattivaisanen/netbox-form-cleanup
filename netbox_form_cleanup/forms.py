from django import forms
from django.utils.translation import gettext_lazy as _

from core.models import ObjectType
from netbox.forms import NetBoxModelBulkEditForm, NetBoxModelFilterSetForm, NetBoxModelForm, NetBoxModelImportForm
from users.models import Group
from utilities.forms import BOOLEAN_WITH_BLANK_CHOICES
from utilities.forms.fields import (
    CommentField, ContentTypeChoiceField, CSVChoiceField, CSVContentTypeField, CSVModelMultipleChoiceField,
    DynamicModelMultipleChoiceField, TagFilterField,
)
from utilities.forms.rendering import FieldSet, InlineFields
from utilities.forms.utils import get_field_value
from utilities.forms.widgets import BulkEditNullBooleanSelect, HTMXSelect

from .fields import field_choices, global_field_choices
from .models import ConditionChoices, FieldRule

__all__ = ('FieldRuleBulkEditForm', 'FieldRuleFilterForm', 'FieldRuleForm', 'FieldRuleImportForm')


def _object_types():
    return ObjectType.objects.public()


def _choices_for(object_type):
    model = object_type.model_class() if object_type else None
    if model is not None:
        return [(name, f'{label} ({name})') for name, label in field_choices(model)]
    return [(name, f'{label} ({name})') for name, label in global_field_choices()]


class FieldRuleForm(NetBoxModelForm):
    """
    The rule form. Changing the object type draws the form again (HTMXSelect)
    so the field lists offer that type's fields, or every type's when blank.
    """
    object_type = ContentTypeChoiceField(
        label=_('Object type'),
        queryset=_object_types(),
        required=False,
        widget=HTMXSelect(),
        help_text=FieldRule._meta.get_field('object_type').help_text,
    )
    fields = forms.MultipleChoiceField(
        label=_('Fields'),
        help_text=_('Fields to hide.'),
    )
    condition_field = forms.ChoiceField(
        label=_('Condition field'),
        required=False,
        help_text=FieldRule._meta.get_field('condition_field').help_text,
    )
    groups = DynamicModelMultipleChoiceField(
        label=_('User groups'),
        queryset=Group.objects.all(),
        required=False,
        help_text=FieldRule._meta.get_field('groups').help_text,
    )
    comments = CommentField()

    fieldsets = (
        FieldSet('name', 'description', 'enabled', 'tags', name=_('Field rule')),
        FieldSet('object_type', 'fields', name=_('Fields')),
        FieldSet('condition', 'condition_field', 'condition_values', name=_('Condition')),
        FieldSet(
            InlineFields('in_forms', 'in_detail', 'in_tables', label=_('Hide on')),
            name=_('Scope'),
        ),
        FieldSet('groups', name=_('Users')),
    )

    class Meta:
        model = FieldRule
        fields = (
            'name', 'description', 'enabled', 'object_type', 'fields', 'condition', 'condition_field',
            'condition_values', 'in_forms', 'in_detail', 'in_tables', 'groups', 'tags', 'comments',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        object_type = None
        value = get_field_value(self, 'object_type')
        if value:
            object_type = value if isinstance(value, ObjectType) else (
                ObjectType.objects.filter(pk=value).first()
            )
        choices = _choices_for(object_type)
        # Keep saved names a model no longer has, so editing does not drop them silently.
        known = {name for name, _label in choices}
        saved = list(self.initial.get('fields') or []) if not self.is_bound else []
        choices += [(name, name) for name in saved if name not in known]
        self.fields['fields'].choices = choices
        self.fields['condition_field'].choices = [('', '---------'), *choices]


class FieldRuleImportForm(NetBoxModelImportForm):
    object_type = CSVContentTypeField(
        label=_('Object type'),
        queryset=_object_types(),
        required=False,
        help_text=_("Object type as app_label.model, e.g. dcim.site. Blank for every type."),
    )
    condition = CSVChoiceField(label=_('Condition'), choices=ConditionChoices, required=False)
    groups = CSVModelMultipleChoiceField(
        label=_('User groups'),
        queryset=Group.objects.all(),
        required=False,
        to_field_name='name',
        help_text=_('Group names separated by commas, in double quotes.'),
    )

    # Left out of the CSV: the model's default (on, on, off, on), not off.
    enabled = forms.NullBooleanField(label=_('Enabled'), required=False)
    in_forms = forms.NullBooleanField(label=_('Forms'), required=False)
    in_detail = forms.NullBooleanField(label=_('Object pages'), required=False)
    in_tables = forms.NullBooleanField(label=_('Object lists'), required=False)

    class Meta:
        model = FieldRule
        fields = (
            'name', 'description', 'enabled', 'object_type', 'fields', 'condition', 'condition_field',
            'condition_values', 'in_forms', 'in_detail', 'in_tables', 'groups', 'tags', 'comments',
        )

    def clean(self):
        super().clean()
        for name in ('enabled', 'in_forms', 'in_detail', 'in_tables'):
            if self.cleaned_data.get(name) is None:
                self.cleaned_data[name] = FieldRule._meta.get_field(name).default
        return self.cleaned_data

    def clean_condition(self):
        return self.cleaned_data.get('condition') or ConditionChoices.ALWAYS


class FieldRuleBulkEditForm(NetBoxModelBulkEditForm):
    model = FieldRule
    enabled = forms.NullBooleanField(label=_('Enabled'), required=False, widget=BulkEditNullBooleanSelect())
    in_forms = forms.NullBooleanField(label=_('Forms'), required=False, widget=BulkEditNullBooleanSelect())
    in_detail = forms.NullBooleanField(label=_('Object pages'), required=False, widget=BulkEditNullBooleanSelect())
    in_tables = forms.NullBooleanField(label=_('Object lists'), required=False, widget=BulkEditNullBooleanSelect())
    groups = DynamicModelMultipleChoiceField(label=_('User groups'), queryset=Group.objects.all(), required=False)
    description = forms.CharField(label=_('Description'), max_length=200, required=False)
    comments = CommentField()

    fieldsets = (
        FieldSet('enabled', 'description', name=_('Field rule')),
        FieldSet('in_forms', 'in_detail', 'in_tables', name=_('Scope')),
        FieldSet('groups', name=_('Users')),
    )
    nullable_fields = ('description', 'groups', 'comments')


class FieldRuleFilterForm(NetBoxModelFilterSetForm):
    model = FieldRule
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('enabled', 'object_type_id', 'field', 'condition', name=_('Rule')),
        FieldSet('in_forms', 'in_detail', 'in_tables', name=_('Scope')),
        FieldSet('group_id', name=_('Users')),
    )
    enabled = forms.NullBooleanField(
        label=_('Enabled'), required=False, widget=forms.Select(choices=BOOLEAN_WITH_BLANK_CHOICES),
    )
    object_type_id = forms.ModelMultipleChoiceField(
        label=_('Object type'), queryset=_object_types(), required=False,
    )
    field = forms.CharField(label=_('Field'), required=False)
    condition = forms.MultipleChoiceField(label=_('Condition'), choices=ConditionChoices, required=False)
    in_forms = forms.NullBooleanField(
        label=_('Forms'), required=False, widget=forms.Select(choices=BOOLEAN_WITH_BLANK_CHOICES),
    )
    in_detail = forms.NullBooleanField(
        label=_('Object pages'), required=False, widget=forms.Select(choices=BOOLEAN_WITH_BLANK_CHOICES),
    )
    in_tables = forms.NullBooleanField(
        label=_('Object lists'), required=False, widget=forms.Select(choices=BOOLEAN_WITH_BLANK_CHOICES),
    )
    group_id = DynamicModelMultipleChoiceField(label=_('User group'), queryset=Group.objects.all(), required=False)
    tag = TagFilterField(model)
