"""Rule validation, matching and who the rules apply to."""
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from dcim.models import Device, Site
from users.models import Group

from .. import rules
from ..fields import field_choices, global_field_choices, is_empty, object_value
from ..models import ConditionChoices, FieldRule
from .utils import NetBoxData


class EmptyTests(TestCase):
    def test_empty_values(self):
        for value in (None, '', '   ', [], (), {}, set()):
            self.assertTrue(is_empty(value), value)
        for value in (0, False, 'x', [0], {'a': 1}):
            self.assertFalse(is_empty(value), value)


class RuleValidationTests(NetBoxData, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.make_netbox()

    def test_known_fields(self):
        names = {name for name, _label in field_choices(Device)}
        self.assertIn('virtual_chassis', names)
        self.assertIn('asset_tag', names)
        self.assertNotIn('id', names)
        self.assertNotIn('interfaces', names)  # reverse relation
        self.assertIn('asset_tag', {name for name, _label in global_field_choices()})

    def test_unknown_field_refused(self):
        with self.assertRaises(ValidationError) as cm:
            self.rule(['no_such_field'], model=Device)
        self.assertIn('fields', cm.exception.message_dict)

    def test_condition_field_needs_when_empty(self):
        with self.assertRaises(ValidationError) as cm:
            self.rule(['vc_position'], model=Device, condition_field='virtual_chassis')
        self.assertIn('condition_field', cm.exception.message_dict)

    def test_tables_need_always(self):
        with self.assertRaises(ValidationError) as cm:
            self.rule(['serial'], model=Device, condition=ConditionChoices.EMPTY, in_tables=True)
        self.assertIn('in_tables', cm.exception.message_dict)

    def test_needs_a_place(self):
        with self.assertRaises(ValidationError) as cm:
            self.rule(['serial'], model=Device, in_forms=False, in_detail=False)
        self.assertIn('in_forms', cm.exception.message_dict)

    def test_duplicates_dropped(self):
        rule = self.rule(['serial', 'serial', ' asset_tag '], model=Device)
        self.assertEqual(rule.fields, ['serial', 'asset_tag'])


class MatchingTests(NetBoxData, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.make_netbox()

    def test_always_and_global(self):
        self.rule(['asset_tag'])  # every type
        self.rule(['serial'], model=Device)
        self.rule(['facility'], model=Site)
        request = self.request_for(self.user)
        device_rules = rules.rules_for(Device, rules.DETAIL, request)
        hidden = rules.hidden_fields(device_rules, ['asset_tag', 'serial', 'facility', 'name'])
        self.assertEqual(hidden, {'asset_tag', 'serial'})

    def test_when_empty_each_field(self):
        rule = self.rule(['serial', 'asset_tag'], model=Device, condition=ConditionChoices.EMPTY)
        hidden = rules.hidden_fields([rule], ['serial', 'asset_tag'], lambda n: object_value(self.plain, n))
        self.assertEqual(hidden, {'asset_tag'})  # plain has a serial

    def test_when_empty_condition_field(self):
        rule = self.rule(
            ['virtual_chassis', 'vc_position', 'vc_priority'], model=Device,
            condition=ConditionChoices.EMPTY, condition_field='virtual_chassis',
        )
        names = ['virtual_chassis', 'vc_position', 'vc_priority']
        plain = rules.hidden_fields([rule], names, lambda n: object_value(self.plain, n))
        stacked = rules.hidden_fields([rule], names, lambda n: object_value(self.stacked, n))
        self.assertEqual(plain, set(names))
        self.assertEqual(stacked, set())

    def test_always_only(self):
        rule = self.rule(['serial'], model=Device, condition=ConditionChoices.EMPTY)
        self.assertEqual(rules.hidden_fields([rule], ['serial'], lambda n: None, always_only=True), set())

    def test_custom_field_value(self):
        self.plain.custom_field_data = {'owner': 'x'}
        self.assertEqual(object_value(self.plain, 'cf_owner'), 'x')
        self.assertIsNone(object_value(self.plain, 'cf_missing'))

    def test_disabled_rule_ignored(self):
        self.rule(['serial'], model=Device, enabled=False)
        self.assertEqual(rules.active_rules(self.request_for(self.user)), [])

    def test_groups(self):
        team = Group.objects.create(name='Team')
        rule = self.rule(['serial'], model=Device)
        rule.groups.set([team])
        self.assertEqual(rules.active_rules(self.request_for(self.user)), [])
        self.user.groups.add(team)
        self.assertEqual(rules.active_rules(self.request_for(self.user)), [rule])

    def test_rules_read_once_per_request(self):
        self.rule(['serial'], model=Device)
        request = self.request_for(self.user)
        rules.active_rules(request)
        with self.assertNumQueries(0):
            rules.active_rules(request)


class ExemptionTests(NetBoxData, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.make_netbox()
        cls.rule(['serial'], model=Device)

    def test_superuser_exempt_by_default(self):
        self.assertEqual(rules.active_rules(self.request_for(self.admin)), [])

    def test_superuser_opts_in(self):
        self.set_pref(self.admin, 'apply_to_me', 'on')
        self.assertEqual(len(rules.active_rules(self.request_for(self.admin))), 1)

    @override_settings(PLUGINS_CONFIG={'netbox_form_cleanup': {'exempt_superusers': False}})
    def test_exemption_off(self):
        self.assertEqual(len(rules.active_rules(self.request_for(self.admin))), 1)

    def test_no_request(self):
        self.assertEqual(rules.active_rules(None), [])

    def test_hide_empty_preference(self):
        request = self.request_for(self.user)
        self.assertFalse(rules.hide_empty(request, 'detail'))
        self.set_pref(self.user, 'hide_empty_detail', 'on')
        self.assertTrue(rules.hide_empty(self.request_for(self.user), 'detail'))

    @override_settings(PLUGINS_CONFIG={'netbox_form_cleanup': {'hide_empty_tables': True}})
    def test_hide_empty_setting_and_override(self):
        self.assertTrue(rules.hide_empty(self.request_for(self.user), 'tables'))
        self.set_pref(self.user, 'hide_empty_tables', 'off')
        self.assertFalse(rules.hide_empty(self.request_for(self.user), 'tables'))


class RuleModelTests(NetBoxData, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.make_netbox()

    def test_str_and_url(self):
        rule = self.rule(['serial'], model=Device, name='Serials')
        self.assertEqual(str(rule), 'Serials')
        self.assertEqual(rule.model, Device)
        self.assertTrue(rule.get_absolute_url().endswith(f'/rules/{rule.pk}/'))
        self.assertIsNone(FieldRule(fields=['x']).model)
