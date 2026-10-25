from rest_framework import serializers

from core.models import ObjectType
from netbox.api.fields import ChoiceField, ContentTypeField, SerializedPKRelatedField
from netbox.api.serializers import NetBoxModelSerializer
from users.api.serializers import GroupSerializer
from users.models import Group

from ..models import ConditionChoices, FieldRule


class FieldRuleSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='plugins-api:netbox_form_cleanup-api:fieldrule-detail')
    object_type = ContentTypeField(queryset=ObjectType.objects.public(), required=False, allow_null=True)
    fields = serializers.ListField(child=serializers.CharField(max_length=100), allow_empty=False)
    condition = ChoiceField(choices=ConditionChoices, required=False)
    groups = SerializedPKRelatedField(
        queryset=Group.objects.all(), serializer=GroupSerializer, nested=True, required=False, many=True,
    )

    class Meta:
        model = FieldRule
        fields = (
            'id', 'url', 'display_url', 'display', 'name', 'description', 'enabled', 'object_type', 'fields',
            'condition', 'condition_field', 'in_forms', 'in_detail', 'in_tables', 'groups', 'comments', 'tags',
            'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'name', 'description')
