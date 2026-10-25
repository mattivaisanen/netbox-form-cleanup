"""Shared test data and helpers."""
from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from core.models import ObjectType
from dcim.models import Device, DeviceRole, DeviceType, Manufacturer, Site, VirtualChassis
from netbox.context import current_request

from ..models import FieldRule

PLUGIN = 'netbox_form_cleanup'


def has_change_approval():
    return apps.is_installed('netbox_change_approval')


class NetBoxData:
    """
    Test data and helpers. With netbox-change-approval installed, the tests
    write as an approved change would, so its gate stays out of the way.
    """
    @classmethod
    def setUpClass(cls):
        cls._ungated = None
        if has_change_approval():
            from netbox_change_approval.context import applying_change_on

            cls._ungated = applying_change_on()
            cls._ungated.__enter__()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if cls._ungated is not None:
            cls._ungated.__exit__(None, None, None)

    @classmethod
    def make_netbox(cls):
        cls.site = Site.objects.create(name='Site 1', slug='site-1')
        cls.role = DeviceRole.objects.create(name='Switch', slug='switch')
        maker = Manufacturer.objects.create(name='Maker', slug='maker')
        cls.device_type = DeviceType.objects.create(manufacturer=maker, model='Model 1', slug='model-1')
        cls.vc = VirtualChassis.objects.create(name='Stack 1')
        cls.plain = Device.objects.create(
            name='plain', site=cls.site, role=cls.role, device_type=cls.device_type, serial='SER-1',
        )
        cls.stacked = Device.objects.create(
            name='stacked', site=cls.site, role=cls.role, device_type=cls.device_type,
            virtual_chassis=cls.vc, vc_position=1,
        )
        User = get_user_model()
        cls.admin = User.objects.create(username='admin', is_superuser=True)
        cls.user = User.objects.create(username='user')

    @staticmethod
    def rule(fields, model=None, **kwargs):
        kwargs.setdefault('name', f'Rule {FieldRule.objects.count() + 1}')
        if model is not None:
            kwargs['object_type'] = ObjectType.objects.get_for_model(model)
        rule = FieldRule(fields=list(fields), **kwargs)
        rule.full_clean()
        rule.save()
        return rule

    @staticmethod
    def set_pref(user, name, value):
        user.config.set(f'plugins.{PLUGIN}.{name}', value, commit=True)

    @staticmethod
    def request_for(user):
        """A request as `user`, made current like NetBox's middleware does."""
        request = RequestFactory().get('/')
        request.user = user
        return request

    def as_current(self, user):
        request = self.request_for(user)
        token = current_request.set(request)
        self.addCleanup(current_request.reset, token)
        return request
