"""
FieldRule: which fields to hide, where, and when.

A NetBoxModel like any NetBox object (tags, change log, custom fields, REST
API, permissions). With an approval plugin installed, changes to rules need
approval like changes to any other object.
"""
import re

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel
from utilities.choices import ChoiceSet

from .fields import PANEL_PREFIX, field_choices, global_field_choices

__all__ = ('ConditionChoices', 'FieldRule')


class ConditionChoices(ChoiceSet):
    ALWAYS = 'always'
    EMPTY = 'empty'
    IS = 'is'
    IS_NOT = 'is_not'
    REGEX = 'regex'
    SAME = 'same'

    CHOICES = (
        (ALWAYS, _('Always'), 'blue'),
        (EMPTY, _('While empty'), 'cyan'),
        (IS, _('While value is one of'), 'purple'),
        (IS_NOT, _('Unless value is one of'), 'purple'),
        (REGEX, _('While value matches a pattern'), 'indigo'),
        (SAME, _('While empty or same as another field'), 'orange'),
    )

    #: Conditions that need a condition field (the others look at each field's own value without one).
    NEEDS_FIELD = (SAME,)
    #: Conditions that compare with values.
    NEEDS_VALUES = (IS, IS_NOT)
    #: Conditions that use a pattern.
    NEEDS_PATTERN = (REGEX,)


class FieldRule(NetBoxModel):
    name = models.CharField(verbose_name=_('name'), max_length=100, unique=True)
    description = models.CharField(verbose_name=_('description'), max_length=200, blank=True)
    enabled = models.BooleanField(verbose_name=_('enabled'), default=True)
    object_type = models.ForeignKey(
        to='core.ObjectType',
        on_delete=models.CASCADE,
        related_name='+',
        blank=True,
        null=True,
        verbose_name=_('object type'),
        help_text=_('Leave blank to apply to every object type that has these fields.'),
    )
    fields = ArrayField(
        base_field=models.CharField(max_length=100),
        verbose_name=_('fields'),
        help_text=_('Custom fields are named cf_<name>.'),
    )
    condition = models.CharField(
        verbose_name=_('condition'),
        max_length=20,
        choices=ConditionChoices,
        default=ConditionChoices.ALWAYS,
    )
    condition_field = models.CharField(
        verbose_name=_('condition field'),
        max_length=100,
        blank=True,
        help_text=_(
            'Another field the condition looks at instead of each hidden field\'s own value (required for '
            '"same as": hide each field while it is empty or has this field\'s value).'
        ),
    )
    condition_values = ArrayField(
        base_field=models.CharField(max_length=200),
        blank=True,
        default=list,
        verbose_name=_('condition values'),
        help_text=_(
            'For "value is one of" / "unless value is one of". Related objects match by name, slug or ID, '
            'choices by value (e.g. active), checkboxes by true or false, numbers by value. Not case sensitive.'
        ),
    )
    in_forms = models.BooleanField(
        verbose_name=_('forms'),
        default=True,
        help_text=_('Move the fields into "More fields" on add and edit forms (bulk edit and filter forms: '
                    '"Always" rules only).'),
    )
    in_detail = models.BooleanField(
        verbose_name=_('object pages'),
        default=True,
        help_text=_('Leave the fields out of object pages.'),
    )
    in_tables = models.BooleanField(
        verbose_name=_('object lists'),
        default=False,
        help_text=_('Remove the fields from object lists ("Always" rules only).'),
    )
    groups = models.ManyToManyField(
        to='users.Group',
        related_name='+',
        blank=True,
        verbose_name=_('user groups'),
        help_text=_('Apply only to members of these groups. Leave blank for everyone.'),
    )
    condition_pattern = models.CharField(
        verbose_name=_('condition pattern'),
        max_length=500,
        blank=True,
        help_text=_('For "matches a pattern": a regular expression, searched anywhere in the value, '
                    'not case sensitive. Related objects match by name, slug or ID.'),
    )
    comments = models.TextField(verbose_name=_('comments'), blank=True)

    clone_fields = ('object_type', 'condition', 'in_forms', 'in_detail', 'in_tables', 'enabled')

    class Meta:
        ordering = ('name',)
        verbose_name = _('field rule')
        verbose_name_plural = _('field rules')

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('plugins:netbox_form_cleanup:fieldrule', args=[self.pk])

    def get_condition_color(self):
        return ConditionChoices.colors.get(self.condition)

    @property
    def model(self):
        """The model the rule is limited to, or None for every model."""
        return self.object_type.model_class() if self.object_type_id else None

    def known_fields(self):
        """Field names this rule may name: the object type's, or any model's for a global rule."""
        model = self.model
        if self.object_type_id and model is None:
            return None  # The model's app is gone: accept what was saved.
        return {name for name, _label in (field_choices(model) if model else global_field_choices())}

    def clean(self):
        super().clean()
        errors = {}
        fields = [f.strip() for f in (self.fields or []) if f and f.strip()]
        self.fields = list(dict.fromkeys(fields))
        if not self.fields:
            errors['fields'] = _('Name at least one field.')
        known = self.known_fields()
        if known is not None:
            unknown = [f for f in self.fields if f not in known]
            if unknown:
                errors['fields'] = _('Unknown field(s): {names}.').format(names=', '.join(unknown))
        self.condition_values = [v.strip() for v in (self.condition_values or []) if v and v.strip()]
        self.condition_pattern = (self.condition_pattern or '').strip()
        if self.condition_field:
            if self.condition == ConditionChoices.ALWAYS:
                errors['condition_field'] = _('"Always" needs no other field.')
            elif known is not None and self.condition_field not in known:
                errors['condition_field'] = _('Unknown field: {name}.').format(name=self.condition_field)
            elif self.condition == ConditionChoices.SAME and self.condition_field in self.fields:
                errors['condition_field'] = _('Pick a field other than the hidden ones.')
        elif self.condition in ConditionChoices.NEEDS_FIELD:
            errors['condition_field'] = _('Pick the other field.')
        if self.condition in ConditionChoices.NEEDS_VALUES:
            if not self.condition_values:
                errors['condition_values'] = _('Enter at least one value.')
        elif self.condition_values:
            errors['condition_values'] = _('Values only work with "value is one of" conditions.')
        if self.condition in ConditionChoices.NEEDS_PATTERN:
            if not self.condition_pattern:
                errors['condition_pattern'] = _('Enter a pattern.')
            else:
                try:
                    re.compile(self.condition_pattern)
                except re.error as e:
                    errors['condition_pattern'] = _('Not a valid pattern: {error}.').format(error=e)
        elif self.condition_pattern:
            errors['condition_pattern'] = _('A pattern only works with "matches a pattern".')
        panels = [name for name in self.fields if name.startswith(PANEL_PREFIX)]
        if panels and self.condition != ConditionChoices.ALWAYS:
            errors['condition'] = _('Whole panels can only be hidden with "Always".')
        if self.in_tables and self.condition != ConditionChoices.ALWAYS:
            errors['in_tables'] = _('Object lists only support "Always" rules.')
        if not (self.in_forms or self.in_detail or self.in_tables):
            errors['in_forms'] = _('Pick at least one place to hide the fields.')
        if errors:
            raise ValidationError(errors)
