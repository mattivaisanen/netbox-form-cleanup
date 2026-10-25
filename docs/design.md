# netbox-form-cleanup: design

Plan agreed with Matti on 2026-10-25. Kept up to date as the plugin changes.

## Goal

Let NetBox admins remove clutter from the web UI: fields nobody in their
organization uses, or fields that only matter in some situations (an
interface's wireless channel only matters when the interface has a wireless
role). Nothing is ever deleted or blocked: hiding is a display choice, the
REST API and the data are untouched.

## Field rules (UI-managed)

A **field rule** is a NetBox object (NetBoxModel: change log, tags, custom
fields, REST API, permissions, bulk import/edit), under *Plugins → Field
Rules*.

| Field | Meaning |
| --- | --- |
| Name, description | Free text. |
| Enabled | Off keeps the rule without applying it. |
| Object type | One model (e.g. DCIM › Device), or blank for **every** model ("global"). |
| Fields | One or more field names. Per-model rules pick from that model's fields and custom fields; global rules from every field name seen on any model. |
| Condition | **Always**, **While empty**, **While / unless value is one of**, **While value matches a pattern**, **While empty or same as another field** (added 2026-10-25 on Matti's request). Each field is judged by its own value unless another field is picked. The form shows only the inputs a condition needs. |
| Condition values | For *value is one of*: names, slugs or IDs of related objects, choice values, numbers, true/false. |
| Condition pattern | For *matches a pattern*: a regular expression. |
| Condition field | Required for *same as*, optional otherwise: that field's value decides for all listed fields (e.g. hide the wireless channel fields while Wireless role is empty). Blank: each field is judged by its own value. |
| Forms | Apply on add/edit forms (and, for *Always* rules, bulk edit and list filter forms). Default on. |
| Detail pages | Apply on object detail pages. Default on. |
| Tables | Apply to object list columns (*Always* rules only). Default off. |
| User groups | Apply only to members of these groups. Blank: everyone. |

## Where hiding happens

- **Add/edit forms** (any `NetBoxModelForm`, core and plugin): hidden fields
  move into a collapsed **More Fields** section at the bottom of the form.
  Their values are still submitted, so nothing is lost and a field that is
  usually empty can still be filled in. The section opens by itself when one
  of its fields has an error. A required field that is empty is never hidden.
  *When empty* is judged from the form's current value, so after the user
  fills a field it stays visible on the next edit.
- **Bulk edit and filter forms**: *Always* rules move fields into More Fields
  the same way.
- **Detail pages** (NetBox 4.7 panel layouts: every core model and plugins
  that use `ObjectAttributesPanel`): hidden attributes are dropped from
  attribute panels and the custom fields panel; a panel left with nothing to
  show is not rendered. Pages still using hand-written templates are not
  touched (documented limitation).
- **Tables**: hidden columns are removed from the table and from *Configure
  table*.

## Hide empty fields (setting + user preference)

- **Detail pages:** rows with no value (and empty custom fields) are left out.
- **Tables:** columns with no value on any row of the current page are left
  out; they still show as selected under *Configure table*, so saving the
  table configuration does not drop them.

Global default in `PLUGINS_CONFIG` (`hide_empty_detail`, `hide_empty_tables`,
both off); each user can override it under *Preferences* (Default / On /
Off).

## Who sees everything

- **Superusers** see every field by default (`exempt_superusers: True`). A
  superuser can switch on *Apply field rules to me* in Preferences to preview
  what everyone else sees.
- Rules with user groups only apply to members of those groups.

## Not in scope

- REST API, GraphQL, exports and the change log are never filtered.
- Mapping existing devices to the configuration they were imported from
  belongs to netbox-fortigate-importer, not this plugin.

## How it hooks into NetBox

No core templates are overridden. The plugin wraps a few NetBox internals at
startup (listed in DEVELOPER.md, each with a test):

- The `render_field` template tag (every form field NetBox draws, whether
  the form uses fieldsets or a hand-written template like the device form):
  marks hidden fields; a small script moves them into *More Fields*.
- `ObjectAttributesPanel.get_context` / `should_render` and
  `CustomFieldsPanel.get_context`: filter attributes.
- `NetBoxTable.configure`: exclude hidden columns, hide empty ones.
- A `head()` template extension adds the script and style that build the
  collapsed More Fields section.
- Rules are read once per request (current request from
  `netbox.context.current_request`).

## Conventions

Same as Matti's other plugins: no runtime dependencies, no other plugins
required, Apache-2.0, `min_version` = oldest CI release (4.7.0), CI on pull
requests only with two jobs (4.7.0 alone, 4.7.3 next to
netbox-change-approval), docs and CHANGELOG updated with each change.
