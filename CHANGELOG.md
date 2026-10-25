# Changelog

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
