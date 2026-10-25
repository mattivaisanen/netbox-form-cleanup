# Changelog

## Unreleased

New:

- Field rules (*Form Cleanup → Field rules*): hide fields for one object
  type or every type, always or only while empty, optionally only while a
  *condition field* is empty, optionally only for some user groups.
- Hidden fields move into a collapsed *More fields* section on add and edit
  forms (also bulk edit and list filter forms for *Always* rules); their
  values are still saved.
- Hidden fields are left out of object pages, and with *Object lists* on,
  out of object lists and *Configure table*.
- Setting and user preference to hide empty fields on object pages and
  empty columns in object lists.
- Superusers see every field unless they switch on *Apply field rules to
  me* in their preferences.
- Rules have a REST API, CSV import, bulk edit, change log, tags and search.
