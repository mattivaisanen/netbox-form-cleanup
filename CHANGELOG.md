# Changelog

## Unreleased

## 0.2.0 (2026-11-21)

Supports NetBox 4.7 only (`max_version` 4.7.99), as the plugin wraps
NetBox 4.7 internals.

New:

- *Except user groups* on field rules: the rule never applies to members
  of these groups, even when they are in the rule's own user groups.
- `prepare_form_cleanup_uninstall` command and an *Uninstalling* section in
  the README.
- *Plugins → Field Usage*: pick an object type to see how many objects
  have a value in each field and which rules hide it, then add a rule for
  one field or for every unused field in one click.

Fixed:

- Empty (or hidden) tags, comments and custom fields are now left out on
  object pages drawn from their own templates, as most plugins' pages
  are. Before, only NetBox's core object pages left them out.
- The rule form no longer offers *Tagged items* and other generic reverse
  relations. They are no fields of the form or the page, so a rule for
  them hid nothing; use *Tags*.
- CSV exports of object lists keep columns that a rule removes from the
  list, as exports are never filtered.
- Field rules no longer apply to the field rule pages themselves, so a
  rule for every object type cannot hide parts of the rule form. Rules
  cannot be limited to the field rule type any more.
- *Clone* on a field rule keeps its fields, condition, user groups and
  except user groups.
- Deleting the last user group of a rule disables the rule, with a change
  log message, instead of leaving it to apply to everyone.
- Unexpected errors while hiding fields are logged (`netbox_form_cleanup`
  logger) instead of passing silently; the page still shows NetBox's own
  result.

## 0.1.0 (2026-10-26)

First release.

New:

- Field rules (*Plugins → Field Rules*): hide fields for one object type
  or every type, optionally only for some user groups. Rules have a REST
  API, CSV import, bulk edit, change log, tags and search.
- Conditions: *Always*, *While empty*, *While value is one of*, *Unless
  value is one of*, *While value matches a pattern* (regular expression)
  and *While empty or same as another field* (for example show an
  out-of-band IP only when it differs from the primary IP). Each field is
  judged by its own value unless another field is picked. Values match
  related objects by name, slug or ID and numbers by value (`0` matches
  0.0). The rule form shows only the inputs the chosen condition needs.
- Hidden fields move into a collapsed *More Fields* section on add and edit
  forms (also bulk edit and list filter forms for *Always* rules); their
  values are still saved.
- Hidden fields are left out of object pages, and with *Object lists* on,
  out of object lists and *Configure table*.
- Rules can hide rows that only exist on object pages (a device's total
  weight, GPS coordinates) and whole panels (a device's Virtual Device
  Contexts table).
- Setting and user preference to hide empty fields on object pages and
  empty columns in object lists.
- Superusers see every field unless they switch on *Apply field rules to
  me* in their preferences.
