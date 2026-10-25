# netbox-form-cleanup

A NetBox plugin that hides the fields your organization doesn't use from
NetBox's web UI: on add and edit forms, on object pages and in object lists.
Hide a field everywhere, only for one object type, or only while it is
empty. Nothing is deleted and nothing is blocked: hiding only changes what
the web UI draws. The REST API, GraphQL, exports and the data stay exactly
as they are.

## What it does

- **Field rules, managed in the UI.** *Plugins → Field Rules* lists the
  rules. A rule names one or more fields (custom fields too) and either one
  object type or every object type that has those fields. Rules are normal
  NetBox objects: change log, tags, custom fields, CSV import, bulk edit,
  REST API and permissions all work as for any other object. Besides real
  fields, a rule can name rows that only exist on an object page (a
  device's *Total weight*, *GPS coordinates*, *Region*...); hiding the only
  row of a panel removes the panel. Whole panels can be hidden too
  (*Virtual Device Contexts panel*, *Management panel*...), with *Always*.
- **Always, or on a condition.** An *Always* rule hides its fields for
  good. Conditional rules look at each field's own value, or at another
  field you pick, which then decides for all of them:
  - *While empty*. Example: hide an interface's wireless channel,
    frequency, width and power while its *Wireless role* is empty, so they
    only show on radios.
  - *While value is one of* / *Unless value is one of* some values.
    Related objects match by name, slug or ID, numbers by value. Example:
    hide a device's total weight while it is `0`.
  - *While value matches a pattern* (a regular expression). Example: hide
    serial numbers that start with `TEMP-`.
  - *While empty or same as another field*: each field shows only when it
    has a value that differs from the other field. Example: a circuit
    termination's upstream speed only when it differs from the port speed.
  The rule form only shows the inputs the chosen condition needs.
- **Forms keep working.** On add and edit forms hidden fields are not
  removed: they move into a collapsed **More Fields** section at the bottom
  of the form. Open it to fill one in; its value is saved as usual. The
  section opens by itself when one of its fields has an error. A required
  field that has no value yet is never hidden. Bulk edit forms and the
  filter forms of object lists use *Always* rules the same way.
- **Object pages.** Hidden fields are left out of the attribute panels and
  the custom fields panel. A panel left with nothing to show is not drawn.
- **Object lists (optional per rule).** With *Object lists* on, an *Always*
  rule's columns are removed from the list and from *Configure table*.
- **Hide empty fields.** A setting, which each user can override in their
  preferences, leaves out every field without a value on object pages, and
  every column without a value on the current page of an object list.
  Columns hidden this way stay selected under *Configure table*, so saving
  the table configuration keeps them.
- **Superusers see everything** unless they switch on *Apply field rules to
  me* in their preferences, which shows them what everyone else sees.
- **Per group.** A rule can be limited to members of some user groups.

## What it does not do

- Change the REST API, GraphQL, exports, the change log or permissions. A
  hidden field is still readable and writable everywhere else.
- Touch pages NetBox draws from hand-written templates instead of its panel
  layouts (all core object pages in NetBox 4.7 use the layouts; some
  plugins may not). Forms are covered whatever template draws them.
- Move a form's comments box or changelog message (NetBox draws them in
  fixed places), or fields inside tabbed groups.

## Requirements

- NetBox **4.7** or later. Tested with NetBox 4.7.3.
- No other NetBox plugins. Works next to netbox-change-approval (rule
  changes then need approval like any other change).

## Installation

```bash
pip install git+https://github.com/mattivaisanen/netbox-form-cleanup.git
```

Add it to `configuration.py` and run the migrations:

```python
PLUGINS = ['netbox_form_cleanup']
```

```bash
python manage.py migrate
```

## Upgrading

```bash
pip install --upgrade git+https://github.com/mattivaisanen/netbox-form-cleanup.git
python manage.py migrate
```

Then restart NetBox and its worker. See [CHANGELOG.md](CHANGELOG.md) for
what changed; upgrades never touch your rules except where the changelog
says so.

Settings and permissions: [docs/configuration.md](docs/configuration.md).
How it works inside: [DEVELOPER.md](DEVELOPER.md).

## License

Apache-2.0, see [LICENSE](LICENSE).
