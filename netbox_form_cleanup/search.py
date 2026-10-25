from netbox.search import SearchIndex

from .models import FieldRule


class FieldRuleIndex(SearchIndex):
    model = FieldRule
    fields = (
        ('name', 100),
        ('description', 500),
        ('comments', 5000),
    )
    display_attrs = ('object_type', 'condition', 'description')


indexes = [FieldRuleIndex]
