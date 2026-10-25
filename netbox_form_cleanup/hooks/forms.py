"""
Forms: hidden fields are marked when drawn and moved into a collapsed
"More fields" section at the end of the form (inc/head.html).

NetBox draws every form field, whether the form uses fieldsets or a
hand-written template (the device form does), through the `render_field`
template tag. That tag is swapped for one that draws the same thing and,
for a field the rules hide, wraps it in <div data-form-cleanup-hidden>. The
field stays inside the <form>, so its value is still submitted and nothing
a form saves changes; only where it sits on the page changes.

Which fields a form hides is worked out the first time one of its fields
is drawn, after the form's __init__ (and its subclasses') has finished, and
remembered on the form. Add and edit forms (NetBoxModelForm) use every
rule; bulk edit and filter forms describe no single object, so only
"Always" rules count there. Other forms (login, preferences, scripts, ...)
are never touched.
"""
import logging

from netbox.forms import NetBoxModelBulkEditForm, NetBoxModelFilterSetForm, NetBoxModelForm
from utilities.templatetags import form_helpers

from ..fields import is_empty
from ..rules import FORMS, hidden_fields, rules_for

logger = logging.getLogger('netbox_form_cleanup')

#: Cache of a form's hidden field names.
HIDDEN_ATTR = '_form_cleanup_hidden'

#: Never moved: NetBox draws these in fixed places of its own.
NEVER_MOVED = {'changelog_message'}


def _model_of(form):
    meta = getattr(form, '_meta', None)
    return getattr(meta, 'model', None) or getattr(form, 'model', None)


def _kind(form):
    """'object' for add/edit forms, 'always' for bulk edit and filter forms, None for other forms."""
    if isinstance(form, NetBoxModelForm):
        return 'object'
    if isinstance(form, (NetBoxModelBulkEditForm, NetBoxModelFilterSetForm)):
        return 'always'
    return None


def _value(form, name):
    """The field's value as the form draws it (submitted data, else initial)."""
    return form[name].value()


def compute_hidden(form):
    """The names of the form's fields the current user's rules hide."""
    kind = _kind(form)
    if kind is None:
        return frozenset()
    rules = rules_for(_model_of(form), FORMS)
    if not rules:
        return frozenset()
    always_only = kind != 'object'
    hidden = hidden_fields(rules, form.fields, value_of=lambda name: _value(form, name), always_only=always_only)
    out = set()
    for name in hidden:
        if name in NEVER_MOVED or name not in form.fields:
            continue
        if not always_only and form.fields[name].required:
            # A required field without a value must stay in sight.
            try:
                if is_empty(_value(form, name)):
                    continue
            except Exception:
                continue
        out.add(name)
    return frozenset(out)


def hidden_for(form):
    """compute_hidden(), once per form."""
    cached = getattr(form, HIDDEN_ATTR, None)
    if cached is None:
        try:
            cached = compute_hidden(form)
        except Exception:  # Never break a form over cosmetics.
            logger.exception('Could not work out hidden fields of %s', type(form).__name__)
            cached = frozenset()
        try:
            setattr(form, HIDDEN_ATTR, cached)
        except AttributeError:
            pass
    return cached


def is_hidden(bound_field):
    form = getattr(bound_field, 'form', None)
    if form is None:
        return False
    return bound_field.name in hidden_for(form)


def apply():
    original = form_helpers.render_field
    if getattr(original, '_form_cleanup', False):
        return

    def render_field(field, bulk_nullable=False, label=None):
        context = original(field, bulk_nullable=bulk_nullable, label=label)
        context['form_cleanup_hidden'] = is_hidden(field)
        return context

    render_field._form_cleanup = True
    render_field.__doc__ = original.__doc__
    # Registering under the same name replaces the tag in NetBox's form_helpers
    # library; templates are compiled after ready(), so they all get this one.
    form_helpers.register.inclusion_tag('netbox_form_cleanup/render_field.html', name='render_field')(render_field)
    form_helpers.render_field = render_field
