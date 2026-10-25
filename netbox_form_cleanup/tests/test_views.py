"""The plugin's own pages and REST API."""
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import ObjectType
from dcim.models import Device

from ..models import FieldRule
from .utils import NetBoxData

URL = 'plugins:netbox_form_cleanup:'
API = '/api/plugins/form-cleanup/rules/'


@override_settings(LOGIN_REQUIRED=True, EXEMPT_VIEW_PERMISSIONS=['*'])
class RulePageTests(NetBoxData, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.make_netbox()
        cls.vc_rule = cls.rule(['vc_position'], model=Device, name='VC position')

    def setUp(self):
        self.client.force_login(self.admin)

    def test_pages(self):
        for url in (
            reverse(URL + 'fieldrule_list'), self.vc_rule.get_absolute_url(), reverse(URL + 'fieldrule_add'),
            reverse(URL + 'fieldrule_edit', args=[self.vc_rule.pk]), reverse(URL + 'fieldrule_bulk_import'),
        ):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_form_offers_the_types_fields(self):
        object_type = ObjectType.objects.get_for_model(Device)
        page = self.client.get(reverse(URL + 'fieldrule_add') + f'?object_type={object_type.pk}')
        self.assertContains(page, 'value="virtual_chassis"')

    def test_add_through_form(self):
        object_type = ObjectType.objects.get_for_model(Device)
        response = self.client.post(reverse(URL + 'fieldrule_add'), {
            'name': 'Asset tags', 'object_type': object_type.pk, 'fields': ['asset_tag'],
            'condition': 'always', 'in_forms': 'on', 'in_detail': 'on', 'enabled': 'on',
        })
        self.assertEqual(response.status_code, 302, response.content[:3000])
        self.assertEqual(FieldRule.objects.get(name='Asset tags').fields, ['asset_tag'])

    def test_csv_import(self):
        response = self.client.post(reverse(URL + 'fieldrule_bulk_import'), {
            'data': 'name,object_type,fields,condition,in_tables\n'
                    'Imported,dcim.device,"serial,asset_tag",always,true\n'
                    'Everywhere,,description,,false\n',
            'format': 'csv', 'csv_delimiter': ',',
        })
        import re; self.assertEqual(response.status_code, 302, re.findall(r'(?s)(?:alert|text-danger|errorlist)[^>]*>(.{0,300})', response.content.decode())[:5])
        imported = FieldRule.objects.get(name='Imported')
        self.assertEqual(imported.fields, ['serial', 'asset_tag'])
        self.assertTrue(imported.in_tables)
        self.assertIsNone(FieldRule.objects.get(name='Everywhere').object_type)


@override_settings(LOGIN_REQUIRED=True)
class ApiTests(NetBoxData, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.make_netbox()

    def setUp(self):
        self.client.force_login(self.admin)

    def test_create_and_validate(self):
        response = self.client.post(API, {
            'name': 'VC', 'object_type': 'dcim.device', 'fields': ['virtual_chassis', 'vc_position'],
            'condition': 'empty', 'condition_field': 'virtual_chassis',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['object_type'], 'dcim.device')
        response = self.client.post(API, {'name': 'Bad', 'object_type': 'dcim.device', 'fields': ['nope']},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('fields', response.json())

    def test_rules_never_change_the_api(self):
        self.rule(['serial'], model=Device, in_tables=True)
        self.set_pref(self.admin, 'apply_to_me', 'on')
        response = self.client.get(f'/api/dcim/devices/{self.plain.pk}/')
        self.assertEqual(response.json()['serial'], 'SER-1')
