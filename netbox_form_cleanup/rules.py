"""
Which fields to hide for the current request.

Rules are read once per request (memoised on the request object) and only
when a form, object page or list is drawn. Superusers are exempt unless they
switch on "Apply field rules to me"; rules with user groups apply only to
members.
"""
import re

from netbox.context import current_request

from .fields import comparable, is_empty, value_labels, wanted_label
from .models import ConditionChoices, FieldRule
from .settings import PLUGIN, get_setting

#: Where a rule applies: the FieldRule flag for each.
FORMS = 'in_forms'
DETAIL = 'in_detail'
TABLES = 'in_tables'

_CACHE_ATTR = '_form_cleanup_rules'

ON, OFF = 'on', 'off'


def get_request():
    return current_request.get()


def preference(request, name):
    """A user's plugin preference ('' when unset or no user)."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return ''
    config = getattr(user, 'config', None)
    if config is None:
        return ''
    return config.get(f'plugins.{PLUGIN}.{name}') or ''


def is_exempt(request):
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_superuser', False):
        return False
    if not get_setting('exempt_superusers'):
        return False
    return preference(request, 'apply_to_me') != ON


def hide_empty(request, where):
    """Whether empty fields are left out on object pages ('detail') or lists ('tables') for this user."""
    if request is None:
        return False
    choice = preference(request, f'hide_empty_{where}')
    if choice == ON:
        return True
    if choice == OFF:
        return False
    return bool(get_setting(f'hide_empty_{where}'))


def active_rules(request=None):
    """The enabled rules that apply to the request's user, read once per request."""
    request = request if request is not None else get_request()
    if request is None:
        return []
    cached = getattr(request, _CACHE_ATTR, None)
    if cached is not None:
        return cached
    if is_exempt(request):
        rules = []
    else:
        user = getattr(request, 'user', None)
        group_ids = set()
        if user is not None and user.is_authenticated:
            group_ids = set(user.groups.values_list('pk', flat=True))
        rules = []
        for rule in FieldRule.objects.filter(enabled=True).prefetch_related('groups'):
            rule_groups = {group.pk for group in rule.groups.all()}
            if rule_groups and not rule_groups & group_ids:
                continue
            rules.append(rule)
    try:
        setattr(request, _CACHE_ATTR, rules)
    except AttributeError:
        pass
    return rules


def rules_for(model, where, request=None):
    """Active rules for `model` (and global ones) that apply in `where` (FORMS, DETAIL or TABLES)."""
    if model is None:
        return []
    from core.models import ObjectType

    rules = [rule for rule in active_rules(request) if getattr(rule, where)]
    if not rules:
        return []
    object_type_id = None
    if any(rule.object_type_id for rule in rules):
        object_type_id = ObjectType.objects.get_for_model(model).pk
    return [rule for rule in rules if rule.object_type_id in (None, object_type_id)]


def hidden_fields(rules, names, value_of=None, always_only=False, model=None):
    """
    The field names among `names` that `rules` hide. `value_of(name)` gives a
    field's current value for conditional rules; without it (or with
    `always_only`) only "Always" rules count. `model` lets "is one of" match
    related objects given by ID (on forms) by name or slug.
    """
    names = set(names)
    hidden = set()
    for rule in rules:
        targets = [name for name in rule.fields if name in names]
        if not targets:
            continue
        if rule.condition == ConditionChoices.ALWAYS:
            hidden.update(targets)
            continue
        if always_only or value_of is None:
            continue
        try:
            hidden.update(_conditional(rule, targets, value_of, model))
        except Exception:
            # A value that cannot be read hides nothing: show the fields.
            continue
    return hidden


def _conditional(rule, targets, value_of, model):
    """
    The targets a conditional rule hides. With a condition field, that one
    field decides for all of them; without, each field is judged by its own
    value ("same as" always needs one).
    """
    condition = rule.condition
    if condition == ConditionChoices.SAME:
        # Shown only while it adds something: set and different from the other field.
        other = comparable(value_of(rule.condition_field))
        return [name for name in targets if (value := comparable(value_of(name))) is None or value == other]
    test = _tests.get(condition)
    if test is None:
        return []
    if rule.condition_field:
        return targets if test(rule, value_of, model, rule.condition_field) else []
    return [name for name in targets if test(rule, value_of, model, name)]


def _test_empty(rule, value_of, model, name):
    return _empty(value_of, name)


def _test_one_of(rule, value_of, model, name):
    wanted = {value.lower() for value in rule.condition_values} | {wanted_label(v) for v in rule.condition_values}
    found = bool(value_labels(model, name, value_of(name)) & wanted)
    return found == (rule.condition == ConditionChoices.IS)


def _test_pattern(rule, value_of, model, name):
    pattern = re.compile(rule.condition_pattern, re.IGNORECASE)
    return any(pattern.search(label) for label in value_labels(model, name, value_of(name)))


_tests = {
    ConditionChoices.EMPTY: _test_empty,
    ConditionChoices.IS: _test_one_of,
    ConditionChoices.IS_NOT: _test_one_of,
    ConditionChoices.REGEX: _test_pattern,
}


def _empty(value_of, name):
    try:
        return is_empty(value_of(name))
    except Exception:
        # A value that cannot be read is not judged empty: show the field.
        return False
