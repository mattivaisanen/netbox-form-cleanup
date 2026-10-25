"""
Object pages: hidden (and, by preference, empty) attributes are left out.

Wraps NetBox 4.7's panel classes, which every core object page and plugins
using NetBox's layouts are built from:

- ObjectAttributesPanel.get_context: drop rows; should_render: skip a panel
  left with no rows.
- CustomFieldsPanel.get_context: drop custom fields (cf_<name>).
- CommentsPanel / TagsPanel should_render: skip when hidden or empty.
- Panel.render: skip a whole panel a rule names as panel:<...>.

Pages drawn from hand-written templates are not touched.
"""
import functools

from extras.ui.panels import CustomFieldsPanel, TagsPanel
from netbox.ui.panels import CommentsPanel, ObjectAttributesPanel, Panel

from ..fields import CF_PREFIX, is_empty, object_value, panel_key
from ..rules import DETAIL, get_request, hidden_fields, hide_empty, rules_for

#: Set in a panel's context when every row was left out.
EMPTIED = 'form_cleanup_emptied'


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
    get_context = CustomFieldsPanel.get_context
    if getattr(get_context, '_form_cleanup', False):
        return

    @functools.wraps(get_context)
    def wrapped(self, context):
        ctx = get_context(self, context)
        obj = ctx.get('object')
        groups = ctx.get('custom_fields')
        if obj is None or not groups:
            return ctx
        try:
            rules, drop_empty = _detail_state(obj)
            if not rules and not drop_empty:
                return ctx
            names = {f'{CF_PREFIX}{cf.name}' for fields in groups.values() for cf in fields}
            hidden = _hidden(rules, obj, names)
            cleaned = {}
            for group, fields in groups.items():
                kept = {
                    cf: value for cf, value in fields.items()
                    if f'{CF_PREFIX}{cf.name}' not in hidden and not (drop_empty and is_empty(value))
                }
                if kept:
                    cleaned[group] = kept
            ctx = {**ctx, 'custom_fields': cleaned}
        except Exception:
            return ctx
        return ctx

    wrapped._form_cleanup = True
    CustomFieldsPanel.get_context = wrapped


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
                name = field_of(self)
                rules, drop_empty = _detail_state(obj)
                if name in _hidden(rules, obj, {name}):
                    return False
                if drop_empty and is_empty(object_value(obj, name)):
                    return False
            except Exception:
                pass
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
            except Exception:
                pass
        return render(self, context)

    wrapped._form_cleanup = True
    Panel.render = wrapped


def apply():
    _wrap_whole_panels()
    _wrap_attributes()
    _wrap_custom_fields()
    _wrap_single_field(CommentsPanel, lambda panel: panel.field_name)
    _wrap_single_field(TagsPanel, lambda panel: 'tags')
