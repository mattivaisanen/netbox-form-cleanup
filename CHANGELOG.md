# Changelog

## Unreleased

New:

- Rule values match numbers however they are written, so `0` hides a total
  weight of 0.0.
- Rules can hide rows that only exist on object pages, such as a device's
  total weight (the Dimensions panel then disappears) or GPS coordinates.
- Three more conditions: hide fields *while* or *unless another field has
  one of these values* (related objects by name, slug or ID), and *while
  empty or same as another field* (for example show an out-of-band IP only
  when it differs from the primary IP). The rule form shows only the inputs
  the chosen condition needs.
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
