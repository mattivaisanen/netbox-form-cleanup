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
        self.assertIn('total_weight', names)  # a row on the device page, not a field
        self.assertIn('panel:dcim.virtualdevicecontext', names)  # a whole panel
        with self.assertRaises(ValidationError) as cm:
            self.rule(['panel:dcim.virtualdevicecontext'], model=Device, condition=ConditionChoices.EMPTY)
        self.assertIn('condition', cm.exception.message_dict)
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


class ValueConditionTests(NetBoxData, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.make_netbox()
        from ipam.models import IPAddress

        cls.ip1 = IPAddress.objects.create(address='192.0.2.1/24')
        cls.ip2 = IPAddress.objects.create(address='192.0.2.2/24')

    def hidden(self, rule, obj, names, model=Device, value_of=None):
        return rules.hidden_fields([rule], names, value_of or (lambda n: object_value(obj, n)), model=model)

    def test_is_one_of_matches_name_slug_or_id(self):
        for value in ('Model 1', 'model-1', str(self.device_type.pk), 'MODEL 1'):
            FieldRule.objects.all().delete()
            rule = self.rule(['cluster'], model=Device, condition=ConditionChoices.IS,
                             condition_field='device_type', condition_values=[value])
            self.assertEqual(self.hidden(rule, self.plain, ['cluster']), {'cluster'}, value)

    def test_is_not_one_of(self):
        rule = self.rule(['cluster'], model=Device, condition=ConditionChoices.IS_NOT,
                         condition_field='device_type', condition_values=['vm-type', 'Other'])
        self.assertEqual(self.hidden(rule, self.plain, ['cluster']), {'cluster'})
        rule.condition_values = ['model-1']
        self.assertEqual(self.hidden(rule, self.plain, ['cluster']), set())

    def test_is_one_of_on_form_values(self):
        """Forms give related objects as IDs (text): they still match by name."""
        rule = self.rule(['cluster'], model=Device, condition=ConditionChoices.IS,
                         condition_field='device_type', condition_values=['Model 1'])
        values = {'device_type': str(self.device_type.pk), 'cluster': ''}
        self.assertEqual(self.hidden(rule, None, ['cluster'], value_of=values.get), {'cluster'})

    def test_is_one_of_choice_and_boolean(self):
        rule = self.rule(['serial'], model=Device, condition=ConditionChoices.IS,
                         condition_field='status', condition_values=['active'])
        self.assertEqual(self.hidden(rule, self.plain, ['serial']), {'serial'})
        rule = self.rule(['facility'], model=Site, condition=ConditionChoices.IS_NOT,
                         condition_field='status', condition_values=['planned'])
        self.assertEqual(self.hidden(rule, self.site, ['facility'], model=Site), {'facility'})
        values = {'facility': '', 'status': 'planned'}
        self.assertEqual(self.hidden(rule, None, ['facility'], model=Site, value_of=values.get), set())

    def test_own_value_without_other_field(self):
        """Without another field, each field is judged by its own value."""
        rule = self.rule(['serial', 'asset_tag'], model=Device, condition=ConditionChoices.IS_NOT,
                         condition_values=['SER-1'])
        self.assertEqual(self.hidden(rule, self.plain, ['serial', 'asset_tag']), {'asset_tag'})

    def test_pattern(self):
        rule = self.rule(['serial'], model=Device, condition=ConditionChoices.REGEX, condition_pattern='^ser-')
        self.assertEqual(self.hidden(rule, self.plain, ['serial']), {'serial'})
        rule.condition_pattern = '^xyz'
        self.assertEqual(self.hidden(rule, self.plain, ['serial']), set())
        # Related objects match by name; with another field it decides for all fields.
        rule = self.rule(['cluster', 'serial'], model=Device, condition=ConditionChoices.REGEX,
                         condition_field='device_type', condition_pattern='model \\d')
        self.assertEqual(self.hidden(rule, self.plain, ['cluster', 'serial']), {'cluster', 'serial'})
        # Zero, however written.
        rule = self.rule(['total_weight'], model=Device, condition=ConditionChoices.REGEX,
                         condition_pattern='^0$')
        self.assertEqual(self.hidden(rule, Device.objects.get(pk=self.plain.pk), ['total_weight']),
                         {'total_weight'})

    def test_numbers_match_however_written(self):
        """A device's total weight is 0.0 without weights: "0" in the rule matches it."""
        rule = self.rule(['total_weight'], model=Device, condition=ConditionChoices.IS, condition_values=['0'])
        self.assertEqual(self.hidden(rule, Device.objects.get(pk=self.plain.pk), ['total_weight']), {'total_weight'})
        rule.condition_values = ['0.00']
        self.assertEqual(self.hidden(rule, None, ['total_weight'], value_of={'total_weight': 0}.get), {'total_weight'})
        self.assertEqual(self.hidden(rule, None, ['total_weight'], value_of={'total_weight': 1.5}.get), set())

    def test_same_as(self):
        rule = self.rule(['oob_ip'], model=Device, condition=ConditionChoices.SAME, condition_field='primary_ip4')
        Device.objects.filter(pk=self.plain.pk).update(primary_ip4=self.ip1, oob_ip=self.ip1)
        same = Device.objects.get(pk=self.plain.pk)
        self.assertEqual(self.hidden(rule, same, ['oob_ip']), {'oob_ip'})
        # An empty field adds nothing either.
        Device.objects.filter(pk=self.plain.pk).update(oob_ip=None)
        self.assertEqual(self.hidden(rule, Device.objects.get(pk=self.plain.pk), ['oob_ip']), {'oob_ip'})
        Device.objects.filter(pk=self.plain.pk).update(oob_ip=self.ip2)
        other = Device.objects.get(pk=self.plain.pk)
        self.assertEqual(self.hidden(rule, other, ['oob_ip']), set())
        # On a form: the same IDs as text.
        values = {'oob_ip': str(self.ip1.pk), 'primary_ip4': self.ip1.pk}
        self.assertEqual(self.hidden(rule, None, ['oob_ip'], value_of=values.get), {'oob_ip'})

    def test_validation(self):
        with self.assertRaises(ValidationError) as cm:
            self.rule(['cluster'], model=Device, condition=ConditionChoices.IS, condition_field='device_type')
        self.assertIn('condition_values', cm.exception.message_dict)
        with self.assertRaises(ValidationError) as cm:
            self.rule(['oob_ip'], model=Device, condition=ConditionChoices.SAME)
        self.assertIn('condition_field', cm.exception.message_dict)
        with self.assertRaises(ValidationError) as cm:
            self.rule(['serial'], model=Device, condition=ConditionChoices.REGEX)
        self.assertIn('condition_pattern', cm.exception.message_dict)
        with self.assertRaises(ValidationError) as cm:
            self.rule(['serial'], model=Device, condition=ConditionChoices.REGEX, condition_pattern='(')
        self.assertIn('condition_pattern', cm.exception.message_dict)
        with self.assertRaises(ValidationError) as cm:
            self.rule(['serial'], model=Device, condition_pattern='x')
        self.assertIn('condition_pattern', cm.exception.message_dict)
        with self.assertRaises(ValidationError) as cm:
            self.rule(['serial'], model=Device, condition_values=['x'])
        self.assertIn('condition_values', cm.exception.message_dict)
        with self.assertRaises(ValidationError) as cm:
            self.rule(['oob_ip'], model=Device, condition=ConditionChoices.SAME, condition_field='oob_ip')
        self.assertIn('condition_field', cm.exception.message_dict)
        with self.assertRaises(ValidationError) as cm:
            self.rule(['serial'], model=Device, condition_field='asset_tag')
        self.assertIn('condition_field', cm.exception.message_dict)


class MigrationTests(NetBoxData, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.make_netbox()

    def test_rule_naming_its_own_field_twice_is_simplified(self):
        from importlib import import_module

        from django.apps import apps as django_apps

        migration = import_module('netbox_form_cleanup.migrations.0003_condition_pattern')
        twice = self.rule(['total_weight'], model=Device, condition=ConditionChoices.IS,
                          condition_field='total_weight', condition_values=['0'])
        other = self.rule(['cluster'], model=Device, condition=ConditionChoices.IS,
                          condition_field='device_type', condition_values=['x'])
        migration.drop_self_condition_field(django_apps, None)
        twice.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(twice.condition_field, '')
        self.assertEqual(other.condition_field, 'device_type')
