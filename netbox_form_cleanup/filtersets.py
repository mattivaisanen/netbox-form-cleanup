import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from core.models import ObjectType
from netbox.filtersets import NetBoxModelFilterSet
from users.models import Group

from .models import ConditionChoices, FieldRule

__all__ = ('FieldRuleFilterSet',)


class FieldRuleFilterSet(NetBoxModelFilterSet):
    object_type_id = django_filters.ModelMultipleChoiceFilter(
        queryset=ObjectType.objects.all(),
        label=_('Object type (ID)'),
    )
    object_type = django_filters.CharFilter(method='filter_object_type', label=_('Object type (app_label.model)'))
    global_rule = django_filters.BooleanFilter(
        field_name='object_type', lookup_expr='isnull', label=_('Applies to every object type'),
    )
    field = django_filters.CharFilter(method='filter_field', label=_('Hides field'))
    condition = django_filters.MultipleChoiceFilter(choices=ConditionChoices)
    group_id = django_filters.ModelMultipleChoiceFilter(
        field_name='groups', queryset=Group.objects.all(), label=_('User group (ID)'),
    )
    group = django_filters.ModelMultipleChoiceFilter(
        field_name='groups__name', queryset=Group.objects.all(), to_field_name='name', label=_('User group (name)'),
    )

    class Meta:
        model = FieldRule
        fields = ('id', 'name', 'description', 'enabled', 'condition_field', 'in_forms', 'in_detail', 'in_tables')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value) | Q(fields__contains=[value.strip()])
            | Q(comments__icontains=value)
        )

    def filter_field(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(Q(fields__contains=[value]) | Q(condition_field=value))

    def filter_object_type(self, queryset, name, value):
        try:
            app_label, model = value.lower().split('.')
        except ValueError:
            return queryset.none()
        return queryset.filter(object_type__app_label=app_label, object_type__model=model)
