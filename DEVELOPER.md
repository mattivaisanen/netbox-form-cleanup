# Developer guide

How the plugin works and why, for anyone changing it.

## Rules

`models.FieldRule` is a NetBoxModel (change log, tags, custom fields, REST
API). `fields.py` says which field names a rule may use (`field_choices()`:
a model's forward fields and many-to-many fields, plus `cf_<name>` for
custom fields; `global_field_choices()`: the union over every public model)
and what counts as empty (`is_empty()`: `None`, blank strings, empty
lists, related managers without objects; `False` and `0` are values).
`FieldRule.clean()` checks names against those lists.

`rules.py` decides what applies to the current request:

- `active_rules(request)`: enabled rules whose user groups (if any) include
  the user, read with one query once per request and kept on the request.
  Superusers get none unless `exempt_superusers` is off or their
  `apply_to_me` preference is on. The request comes from
  `netbox.context.current_request`, which NetBox's middleware sets.
- `rules_for(model, where)`: those that are on for forms, object pages or
  lists, and are global or for the model.
- `hidden_fields(rules, names, value_of)`: the names the rules hide.
  `value_of(name)` gives the current value for *When empty* rules; without
  it, or with `always_only`, only *Always* rules count.
- `hide_empty(request, 'detail' | 'tables')`: the user's preference, else
  the setting.

## Wrapped NetBox internals

Everything is wired in `hooks/` from `ready()`. Each wrapper calls
NetBox's own code first, only changes what is drawn, and falls back to
NetBox's result when something unexpected happens (a page never breaks
over cosmetics). Check these on every NetBox upgrade; each has tests.

| NetBox internal | Wrapper | Why |
| --- | --- | --- |
| `utilities.templatetags.form_helpers.render_field` (template tag) | `hooks/forms.py` | Every form field NetBox draws goes through it, in fieldset-based forms and hand-written form templates (the device form is one) alike. The replacement draws the same template and wraps a hidden field in `<div data-form-cleanup-hidden="name">`. It is registered under the same name in NetBox's tag library during `ready()`, before any template is compiled. |
| `netbox.ui.panels.ObjectAttributesPanel.get_context` / `should_render` | `hooks/panels.py` | Object pages: drops attribute rows. Row names come from `panel._attrs` in the order NetBox lists them (respecting `only`/`exclude`); if the counts differ the panel is left alone. A row stands for its own name and, when its accessor is a plain field name, that field too (the device panel's *Parent device* reads `parent_bay`). A panel left without rows is not rendered. |
| `extras.ui.panels.CustomFieldsPanel.get_context` | `hooks/panels.py` | Drops `cf_<name>` fields and empty ones. |
| `CommentsPanel.should_render`, `TagsPanel.should_render` | `hooks/panels.py` | Skips the panel when `comments` / `tags` is hidden, or empty and empty fields are hidden. |
| `netbox.tables.NetBoxTable.configure` | `hooks/tables.py` | Adds rule columns to the table's `exclude` before NetBox applies the user's columns (as NetBox does for custom link columns), and hides columns empty on the current page after pagination. |
| `netbox.tables.BaseTable._get_columns` | `hooks/tables.py` | Columns hidden for being empty still count as selected, so *Configure table* keeps them. |

The "More fields" section itself is built in the browser by
`templates/netbox_form_cleanup/inc/head.html`, added to every page's
`<head>` by a template extension (`template_content.py`). Its CSS hides
marked fields until the script has moved them, so nothing jumps. The
script moves each marked field into one section per form, placed after the
form's last field group (above the buttons), hides groups left with only
their heading, counts the fields, collapses the section unless a field in
it has an error, and runs again after HTMX redraws part of a form. Moving
keeps the field inside its `<form>`, so it is still submitted.

Which fields a form hides is worked out on the first `render_field` of that
form (`hooks.forms.hidden_for()`), after every `__init__` in the form's
class chain has run, and cached on the form. Add and edit forms
(`NetBoxModelForm`) use every rule and judge *When empty* by the field's
current value (submitted data, else initial). Bulk edit and filter forms
(`NetBoxModelBulkEditForm`, `NetBoxModelFilterSetForm`) describe no single
object, so only *Always* rules count. Other forms are never touched.

## Not covered (and why)

- Form fields drawn without `render_field`: the comments box and the
  changelog message (fixed places in NetBox's form template), inline field
  rows, tabbed groups.
- Object pages drawn from hand-written templates.
- The REST API, GraphQL and exports: hiding is a display choice.

## Tests

`netbox_form_cleanup/tests/`, run from a NetBox checkout:

```bash
python manage.py test netbox_form_cleanup
```

`test_rules.py` (validation, matching, groups, superusers, preferences),
`test_ui.py` (forms, object pages, lists) and `test_views.py` (rule pages,
CSV import, REST API). With netbox-change-approval installed the tests
write as an approved change would.

CI (`.github/workflows/test.yml`) runs on pull requests only, two jobs:
the oldest supported NetBox alone and the latest tested one next to
netbox-change-approval.
