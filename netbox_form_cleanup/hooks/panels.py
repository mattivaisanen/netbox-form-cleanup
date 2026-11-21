"""
Object pages: hidden (and, by preference, empty) attributes are left out.

Wraps NetBox 4.7's panel classes, which every core object page and plugins
using NetBox's layouts are built from:

- ObjectAttributesPanel.get_context: drop rows; should_render: skip a panel
  left with no rows.
- CommentsPanel / TagsPanel should_render: skip when hidden or empty.
- Panel.render: skip a whole panel a rule names as panel:<...>.

Pages drawn from hand-written templates (most plugins' own object pages)
show tags, comments and custom fields by including NetBox's shared panel
templates instead, so those are covered too:

- IncludeNode.render: skip {% include 'inc/panels/tags.html' %} and
  'inc/panels/comments.html' when hidden or empty.
- CustomFieldsMixin.get_custom_fields_by_group: the custom fields both
  'inc/panels/custom_fields.html' and CustomFieldsPanel list, without
  hidden (and, by preference, empty) ones.
"""
import functools
import logging

from django.template.loader_tags import IncludeNode

from extras.ui.panels import TagsPanel
from netbox.models.features import CustomFieldsMixin
from netbox.ui.panels import CommentsPanel, ObjectAttributesPanel, Panel

from ..fields import CF_PREFIX, is_empty, object_value, panel_key
from ..rules import DETAIL, get_request, hidden_fields, hide_empty, rules_for

logger = logging.getLogger('netbox_form_cleanup')

#: Set in a panel's context when every row was left out.
EMPTIED = 'form_cleanup_emptied'

#: NetBox's shared panel templates for hand-written object pages, and the field each shows.
INCLUDED_PANELS = {
    'inc/panels/tags.html': 'tags',
    'inc/panels/comments.html': 'comments',
}


def _detail_state(obj):
    """(hidden field names getter, hide empty?) for `obj` on the current page."""
    request = get_request()
    rules = rules_for(type(obj), DETAIL, request)
    return rules, hide_empty(request, 'detail')


def _hidden(rules, obj, names):
    if not rules:
        return set()
    return hidden_fields(rules, names, value_of=functools.partial(object_value, obj), model=type(obj))


def _attr_keys(name, attr):
    """The field names a panel row stands for: its own name, and its accessor when that is a plain field."""
    keys = {name}
    accessor = getattr(attr, 'accessor', None)
    if isinstance(accessor, str) and accessor and '.' not in accessor:
        keys.add(accessor)
    return keys


def _attr_empty(attr, obj):
    try:
        return is_empty(attr.get_value(obj))
    except Exception:
        return False


def _shown_names(panel):
    """The panel's row names, in the order NetBox's get_context lists them."""
    names = set(panel._attrs)
    if panel.only:
        names &= set(panel.only)
    elif panel.exclude:
        names -= set(panel.exclude)
    return [name for name in panel._attrs if name in names]


def _wrap_attributes():
    get_context = ObjectAttributesPanel.get_context
    should_render = ObjectAttributesPanel.should_render
    if getattr(get_context, '_form_cleanup', False):
        return

    @functools.wraps(get_context)
    def wrapped_get_context(self, context):
        ctx = get_context(self, context)
        obj = ctx.get('object')
        if obj is None or not hasattr(obj, '_meta'):
            return ctx
        try:
            names = _shown_names(self)
            rows = ctx.get('attrs') or []
            if len(names) != len(rows):
                return ctx  # Not the layout we know: leave it alone.
            rules, drop_empty = _detail_state(obj)
            if not rules and not drop_empty:
                return ctx
            all_keys = set().union(*(_attr_keys(name, self._attrs[name]) for name in names)) if names else set()
            hidden = _hidden(rules, obj, all_keys)
            kept = []
            for name, row in zip(names, rows):
                attr = self._attrs[name]
                if _attr_keys(name, attr) & hidden:
                    continue
                if drop_empty and _attr_empty(attr, obj):
                    continue
                kept.append(row)
            if len(kept) != len(rows):
                ctx = {**ctx, 'attrs': kept, EMPTIED: not kept}
        except Exception:  # Never break a page over cosmetics.
            logger.exception('Could not leave out attributes of %s', type(self).__name__)
            return ctx
        return ctx

    @functools.wraps(should_render)
    def wrapped_should_render(self, context):
        if context.get(EMPTIED):
            return False
        return should_render(self, context)

    wrapped_get_context._form_cleanup = True
    ObjectAttributesPanel.get_context = wrapped_get_context
    ObjectAttributesPanel.should_render = wrapped_should_render


def _wrap_custom_fields():
    """
    Custom fields left out on object pages. NetBox only calls this method to
    draw them (CustomFieldsPanel and inc/panels/custom_fields.html), never to
    read or save data. Outside a request no rules apply, so nothing changes.
    """
    get_groups = CustomFieldsMixin.get_custom_fields_by_group
    if getattr(get_groups, '_form_cleanup', False):
        return

    @functools.wraps(get_groups)
    def wrapped(self):
        groups = get_groups(self)
        if not groups:
            return groups
        try:
            rules, drop_empty = _detail_state(self)
            if not rules and not drop_empty:
                return groups
            names = {f'{CF_PREFIX}{cf.name}' for fields in groups.values() for cf in fields}
            hidden = _hidden(rules, self, names)
            cleaned = {}
            for group, fields in groups.items():
                kept = {
                    cf: value for cf, value in fields.items()
                    if f'{CF_PREFIX}{cf.name}' not in hidden and not (drop_empty and is_empty(value))
                }
                if kept:
                    cleaned[group] = kept
            return cleaned
        except Exception:
            logger.exception('Could not leave out custom fields of %s', type(self).__name__)
            return groups

    wrapped._form_cleanup = True
    CustomFieldsMixin.get_custom_fields_by_group = wrapped


def _field_left_out(obj, name):
    """Whether the object page leaves out field `name` of `obj`: hidden by a rule, or empty while empty fields are."""
    rules, drop_empty = _detail_state(obj)
    if name in _hidden(rules, obj, {name}):
        return True
    return drop_empty and is_empty(object_value(obj, name))


def _wrap_single_field(panel_class, field_of):
    """Comments and tags panels: skipped when their field is hidden, or empty and empty fields are left out."""
    should_render = panel_class.should_render
    if getattr(should_render, '_form_cleanup', False):
        return

    @functools.wraps(should_render)
    def wrapped(self, context):
        obj = context.get('object')
        if obj is not None and hasattr(obj, '_meta'):
            try:
                if _field_left_out(obj, field_of(self)):
                    return False
            except Exception:  # Never break a page over cosmetics.
                logger.exception('Could not check %s', panel_class.__name__)
        return should_render(self, context)

    wrapped._form_cleanup = True
    panel_class.should_render = wrapped


def _wrap_whole_panels():
    """Any panel a rule names as panel:<...> (fields.panel_key) is not drawn."""
    render = Panel.render
    if getattr(render, '_form_cleanup', False):
        return

    @functools.wraps(render)
    def wrapped(self, context):
        obj = context.get('object')
        if obj is not None and hasattr(obj, '_meta'):
            try:
                key = panel_key(self)
                if key:
                    rules, _drop_empty = _detail_state(obj)
                    if key in _hidden(rules, obj, {key}):
                        return ''
            except Exception:  # Never break a page over cosmetics.
                logger.exception('Could not check panel %s', type(self).__name__)
        return render(self, context)

    wrapped._form_cleanup = True
    Panel.render = wrapped


def _wrap_included_panels():
    """
    {% include 'inc/panels/tags.html' %} and the comments one draw nothing
    when the page's object leaves that field out. Every other include is
    passed straight to Django.
    """
    render = IncludeNode.render
    if getattr(render, '_form_cleanup', False):
        return

    @functools.wraps(render)
    def wrapped(self, context):
        try:
            # Only a fixed template name ('inc/panels/tags.html') is looked at.
            name = getattr(self.template, 'var', None)
            field = INCLUDED_PANELS.get(name) if isinstance(name, str) else None
            if field:
                obj = self.extra_context['object'].resolve(context) if 'object' in self.extra_context \
                    else context.get('object')
                if obj is not None and hasattr(obj, '_meta') and _field_left_out(obj, field):
                    return ''
        except Exception:  # Never break a page over cosmetics.
            logger.exception('Could not check included template %r', getattr(self.template, 'var', None))
        return render(self, context)

    wrapped._form_cleanup = True
    IncludeNode.render = wrapped


def apply():
    _wrap_whole_panels()
    _wrap_attributes()
    _wrap_custom_fields()
    _wrap_single_field(CommentsPanel, lambda panel: panel.field_name)
    _wrap_single_field(TagsPanel, lambda panel: 'tags')
    _wrap_included_panels()
