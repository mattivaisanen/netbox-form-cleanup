"""What users see: forms, object pages and lists."""
from django.template import Context, Template
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import ObjectType
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

    def test_is_not_one_of_on_form(self):
        self.rule(['cluster'], model=Device, condition=ConditionChoices.IS_NOT,
                  condition_field='device_type', condition_values=['vm-host'])
        page = self.client.get(reverse('dcim:device_edit', args=[self.plain.pk]))
        self.assertContains(page, MARK.format('cluster'))
        page = self.client.get(reverse('dcim:device_add'))  # no device type yet: not "vm-host" either
        self.assertContains(page, MARK.format('cluster'))

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

    def test_same_as_primary_ip(self):
        from ipam.models import IPAddress

        ip = IPAddress.objects.create(address='192.0.2.10/24')
        Device.objects.filter(pk=self.plain.pk).update(primary_ip4=ip, oob_ip=ip)
        self.rule(['oob_ip'], model=Device, condition=ConditionChoices.SAME, condition_field='primary_ip4')
        page = self.client.get(self.plain.get_absolute_url())
        self.assertContains(page, 'Primary IPv4</th>')
        self.assertNotContains(page, 'Out-of-band IP</th>')

    def test_page_only_attribute(self):
        """Total weight is no field, only a row on the device page; hiding it drops the whole Dimensions panel."""
        page = self.client.get(self.plain.get_absolute_url())
        self.assertContains(page, 'Total weight</th>')
        self.rule(['total_weight'], model=Device)
        page = self.client.get(self.plain.get_absolute_url())
        self.assertNotContains(page, 'Total weight</th>')
        self.assertNotContains(page, '>Dimensions<')

    def test_whole_panel(self):
        # (The sidebar menu names Virtual Device Contexts too: count the page's own mentions.)
        before = self.client.get(self.plain.get_absolute_url()).content.decode().count('Virtual Device Contexts')
        self.rule(['panel:dcim.virtualdevicecontext', 'panel:management'], model=Device)
        page = self.client.get(self.plain.get_absolute_url())
        self.assertEqual(page.status_code, 200)
        self.assertLess(page.content.decode().count('Virtual Device Contexts'), before)
        self.assertNotContains(page, 'device_id={}'.format(self.plain.pk) + '&amp;exclude_columns=device')
        self.assertNotContains(page, '>Management<')
        self.assertContains(page, 'Site</th>')

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

    def render_included(self, obj):
        """NetBox's shared panels as a hand-written (plugin) object page includes them."""
        from netbox.context import current_request

        token = current_request.set(self.request_for(self.user))
        try:
            return Template(
                "{% include 'inc/panels/tags.html' %}{% include 'inc/panels/comments.html' %}"
                "{% include 'inc/panels/custom_fields.html' %}"
            ).render(Context({'object': obj}))
        finally:
            current_request.reset(token)

    def test_included_panels(self):
        from extras.models import CustomField, Tag

        field = CustomField.objects.create(name='rack_note', type='text')
        field.object_types.set([ObjectType.objects.get_for_model(Device)])
        Device.objects.filter(pk=self.stacked.pk).update(
            comments='Stacked', custom_field_data={'rack_note': 'Note 1'},
        )
        self.stacked.refresh_from_db()
        self.stacked.tags.add(Tag.objects.create(name='Core', slug='core'))
        self.rule(['tags'], model=Device, condition=ConditionChoices.EMPTY, in_forms=False)
        self.set_pref(self.user, 'hide_empty_detail', 'on')

        html = self.render_included(self.plain)  # No tags, comments or custom field values.
        self.assertNotIn('>Tags<', html)
        self.assertNotIn('>Comments<', html)
        self.assertNotIn('>Custom Fields<', html)
        html = self.render_included(self.stacked)
        self.assertIn('Core', html)
        self.assertIn('Stacked', html)
        self.assertIn('Note 1', html)

        self.rule(['cf_rack_note', 'comments'], model=Device, in_forms=False)
        html = self.render_included(self.stacked)
        self.assertNotIn('Note 1', html)
        self.assertNotIn('>Comments<', html)
        self.assertIn('Core', html)


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

    def test_export_keeps_hidden_column(self):
        self.rule(['serial'], model=Device, in_tables=True)
        page = self.client.get(reverse('dcim:device_list') + '?export')
        self.assertIn(b'SER-1', page.content)

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
