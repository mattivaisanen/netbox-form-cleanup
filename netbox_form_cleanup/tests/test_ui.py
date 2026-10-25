"""What users see: forms, object pages and lists."""
from django.test import TestCase, override_settings
from django.urls import reverse

from dcim.forms import DeviceBulkEditForm, DeviceFilterForm, DeviceForm, SiteForm
from dcim.models import Device, Site
from dcim.tables import DeviceTable

from ..hooks.forms import hidden_for
from ..hooks.tables import AUTO_HIDDEN
from ..models import ConditionChoices
from .utils import NetBoxData

MARK = 'data-form-cleanup-hidden="{}"'
VC_FIELDS = ['virtual_chassis', 'vc_position', 'vc_priority']


@override_settings(LOGIN_REQUIRED=True, EXEMPT_VIEW_PERMISSIONS=['*'])
class FormTests(NetBoxData, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.make_netbox()
        cls.rule(['asset_tag'])
        cls.rule(VC_FIELDS, model=Device, condition=ConditionChoices.EMPTY, condition_field='virtual_chassis')

    def setUp(self):
        self.set_pref(self.admin, 'apply_to_me', 'on')
        self.client.force_login(self.admin)

    def test_add_form_marks_hidden_fields(self):
        page = self.client.get(reverse('dcim:device_add'))
        self.assertEqual(page.status_code, 200)
        for name in ['asset_tag', *VC_FIELDS]:
            self.assertContains(page, MARK.format(name))
        self.assertNotContains(page, MARK.format('serial'))
        self.assertContains(page, 'form-cleanup-more')  # the script that moves them

    def test_edit_form_shows_filled_condition(self):
        page = self.client.get(reverse('dcim:device_edit', args=[self.stacked.pk]))
        for name in VC_FIELDS:
            self.assertNotContains(page, MARK.format(name))
        self.assertContains(page, MARK.format('asset_tag'))

    def test_superuser_sees_everything_by_default(self):
        self.set_pref(self.admin, 'apply_to_me', 'off')
        page = self.client.get(reverse('dcim:device_add'))
        self.assertNotContains(page, 'data-form-cleanup-hidden=')

    def test_hidden_values_still_saved(self):
        self.rule(['facility'], model=Site)
        response = self.client.post(reverse('dcim:site_add'), {
            'name': 'Site 2', 'slug': 'site-2', 'status': 'active', 'facility': 'FAC-1',
        })
        self.assertEqual(response.status_code, 302, response.content[:2000])
        self.assertEqual(Site.objects.get(slug='site-2').facility, 'FAC-1')

    def test_required_empty_field_stays(self):
        self.rule(['name'], model=Site)
        self.as_current(self.admin)
        self.assertNotIn('name', hidden_for(SiteForm()))
        self.assertIn('name', hidden_for(SiteForm(instance=Site.objects.get(pk=self.site.pk))))

    def test_bulk_edit_and_filter_forms_use_always_rules_only(self):
        self.rule(['airflow', 'serial'], model=Device, condition=ConditionChoices.EMPTY)
        self.rule(['airflow'], model=Device)
        self.as_current(self.admin)
        for form in (DeviceFilterForm(), DeviceBulkEditForm()):
            hidden = hidden_for(form)
            self.assertIn('airflow', hidden)
            self.assertFalse(hidden & {'serial', *VC_FIELDS}, type(form).__name__)

    def test_other_forms_untouched(self):
        self.as_current(self.admin)
        page = self.client.get(reverse('account:preferences'))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'data-form-cleanup-hidden=')

    def test_form_without_request(self):
        self.assertEqual(hidden_for(DeviceForm()), frozenset())


@override_settings(LOGIN_REQUIRED=True, EXEMPT_VIEW_PERMISSIONS=['*'])
class DetailTests(NetBoxData, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.make_netbox()
        cls.rule(VC_FIELDS, model=Device, condition=ConditionChoices.EMPTY, condition_field='virtual_chassis')
        cls.rule(['serial'], model=Device, in_forms=False)

    def setUp(self):
        self.client.force_login(self.user)

    def test_hidden_rows_left_out(self):
        page = self.client.get(self.plain.get_absolute_url())
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'Virtual chassis</th>')
        self.assertNotContains(page, 'SER-1')
        self.assertContains(page, 'Airflow</th>')
        page = self.client.get(self.stacked.get_absolute_url())
        self.assertContains(page, 'Stack 1')

    def test_hide_empty(self):
        self.set_pref(self.user, 'hide_empty_detail', 'on')
        page = self.client.get(self.plain.get_absolute_url())
        self.assertNotContains(page, 'Airflow</th>')
        self.assertContains(page, 'Site</th>')

    def test_empty_panel_not_drawn(self):
        self.set_pref(self.user, 'hide_empty_detail', 'on')
        page = self.client.get(self.site.get_absolute_url())
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, '<h2 class="card-header">Comments')


@override_settings(LOGIN_REQUIRED=True, EXEMPT_VIEW_PERMISSIONS=['*'])
class TableTests(NetBoxData, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.make_netbox()

    def setUp(self):
        self.client.force_login(self.user)

    def table(self):
        request = self.as_current(self.user)
        table = DeviceTable(Device.objects.all())
        table.configure(request)
        return table

    def test_rule_removes_column(self):
        self.rule(['serial'], model=Device, in_tables=True)
        table = self.table()
        self.assertNotIn('serial', table.columns.names())
        self.assertNotIn('serial', [name for name, _label in table.available_columns])

    def test_form_only_rule_keeps_column(self):
        self.rule(['serial'], model=Device)
        self.assertIn('serial', self.table().columns.names())

    def test_empty_columns_hidden_but_still_selected(self):
        self.set_pref(self.user, 'hide_empty_tables', 'on')
        table = self.table()
        self.assertIn('rack', getattr(table, AUTO_HIDDEN))
        self.assertFalse(table.columns['rack'].visible)
        self.assertTrue(table.columns['name'].visible)
        self.assertIn('rack', [name for name, _label in table.selected_columns])

    def test_list_page(self):
        self.rule(['serial'], model=Device, in_tables=True)
        self.set_pref(self.user, 'hide_empty_tables', 'on')
        page = self.client.get(reverse('dcim:device_list'))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'plain')
