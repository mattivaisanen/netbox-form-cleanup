from rest_framework.routers import APIRootView

from netbox.api.viewsets import NetBoxModelViewSet

from .. import filtersets
from ..models import FieldRule
from . import serializers


class FormCleanupRootView(APIRootView):
    def get_view_name(self):
        return 'Form cleanup'


class FieldRuleViewSet(NetBoxModelViewSet):
    queryset = FieldRule.objects.select_related('object_type').prefetch_related('groups', 'tags')
    serializer_class = serializers.FieldRuleSerializer
    filterset_class = filtersets.FieldRuleFilterSet
