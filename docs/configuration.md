# Configuration

Settings go in NetBox's `configuration.py`:

```python
PLUGINS_CONFIG = {
    'netbox_form_cleanup': {
        'exempt_superusers': True,
        'hide_empty_detail': False,
        'hide_empty_tables': False,
    },
}
```

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `exempt_superusers` | bool | `True` | Superusers see every field unless they switch on *Apply field rules to me* in their preferences. `False` applies rules to superusers too. |
| `hide_empty_detail` | bool | `False` | Leave out fields without a value on object pages, for users whose preference is *Default*. |
| `hide_empty_tables` | bool | `False` | Leave out columns without a value on the current page of object lists, for users whose preference is *Default*. |

Everything else is set per rule under **Form Cleanup → Field rules** (see
the README).

## User preferences

Under the user menu → *Preferences* → *Plugins*:

| Preference | Choices | Effect |
| --- | --- | --- |
| Hide empty fields on object pages | Default / On / Off | Overrides `hide_empty_detail` for this user. |
| Hide empty columns in object lists | Default / On / Off | Overrides `hide_empty_tables` for this user. |
| Apply field rules to me (superusers) | Off / On | A superuser sees what other users see. No effect for other users. |

Admins can set defaults for everyone with NetBox's own
`DEFAULT_USER_PREFERENCES`, for example
`{'plugins': {'netbox_form_cleanup': {'hide_empty_detail': 'on'}}}`.

## Field rules

| Field | Meaning |
| --- | --- |
| Object type | One object type, or blank for every type that has the fields. |
| Fields | The fields to hide, by name as on the object's form (`serial`, `tenant`). Custom fields are `cf_<name>`. Rows that only exist on the object page (a device's `total_weight`, `gps_coordinates`) are offered too, marked *object page only*; they have no form field or column. Whole panels of the object page are offered as `panel:<app.model>` for tables of related objects (a device's `panel:dcim.virtualdevicecontext`) and `panel:<title>` for others (`panel:management`); they can only be hidden with *Always*. The form offers the object type's fields, or every field name of every type when blank. |
| Condition | *Always*; *While empty*; *While value is one of*; *Unless value is one of*; *While value matches a pattern*; *While empty or same as another field*. The form shows only the inputs the chosen condition needs. |
| Condition field (form: *Look at another field* / *Other field*) | Optional except for *same as*. Blank: each hidden field is judged by its own value. Set: that field's value decides for all the hidden fields. *Same as*: each field shows only when it has a value that differs from this one. |
| Condition values (form: *Values*) | *Value is one of* / *unless value is one of* only. Related objects match by name, slug, model (device types) or ID; choices by value (`active`); checkboxes by `true` / `false`; numbers by value (`0` matches 0.0); anything else by its text. Not case sensitive. A field without a value matches nothing, so *unless* hides empty fields too. |
| Condition pattern (form: *Pattern*) | *Matches a pattern* only. A Python regular expression, searched anywhere in the value, not case sensitive; related objects match by name, slug or ID, numbers as written without trailing zeros (`^0$` matches 0.0). An empty value matches nothing. |
| Forms | Move the fields into *More fields* on add and edit forms; bulk edit and filter forms with *Always* rules. On by default. |
| Object pages | Leave the fields out of object pages. On by default. |
| Object lists | Remove the fields' columns from object lists. *Always* rules only. Off by default. |
| User groups | Apply only to members of these groups. Blank: everyone. |

CSV import columns: `name`, `description`, `enabled`, `object_type`
(`app_label.model`, blank for every type), `fields` (comma separated, in
double quotes when more than one), `condition` (`always`, `empty`, `is`,
`is_not`, `regex` or `same`), `condition_field`, `condition_values` (comma
separated, like `fields`), `condition_pattern`, `in_forms`, `in_detail`, `in_tables`, `groups` (group
names), `tags`, `comments`. Columns left out take the defaults above.

REST API: `/api/plugins/form-cleanup/rules/`, with `object_type` as
`app_label.model` (or `null`), and `fields` and `condition_values` as lists.

## Permissions

| Permission | Allows |
| --- | --- |
| `netbox_form_cleanup.view_fieldrule` | Seeing rules |
| `netbox_form_cleanup.add_fieldrule`, `change_fieldrule`, `delete_fieldrule` | Managing rules |

Rules apply to everyone who opens a form, object page or list, whatever
their permissions; they need no permission of their own.
