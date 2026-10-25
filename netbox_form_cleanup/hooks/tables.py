"""
Object lists: hidden columns are removed, empty columns left out.

Wraps NetBoxTable.configure (every core and plugin object list):

- Before NetBox applies the user's column choice, columns of "Always" rules
  with "Object lists" on are added to the table's `exclude`, so they are
  neither drawn nor offered under "Configure table".
- After pagination, with "hide empty columns" on, a column with no value
  on any row of the current page is hidden for this page. Those columns
  still count as selected (BaseTable._get_columns is wrapped), so saving
  "Configure table" keeps them.
"""
import functools

from netbox.tables import BaseTable, NetBoxTable

from ..fields import is_empty
from ..rules import TABLES, hidden_fields, hide_empty, rules_for

#: Never hidden for being empty.
KEEP = {'pk', 'id', 'actions'}

AUTO_HIDDEN = '_form_cleanup_auto_hidden'


def _model_of(table):
    meta = getattr(table, '_meta', None)
    return getattr(meta, 'model', None)


def _record_empty(record, column):
    """Whether this cell has no value. Columns that do not read a field of the record never count as empty."""
    accessor = getattr(column, 'accessor', None)
    if not accessor:
        return False
    first = str(accessor).split('__')[0].split('.')[0]
    if not hasattr(record, first):
        return False
    value = accessor.resolve(record, quiet=True)
    return is_empty(value)


def empty_columns(table):
    """Visible columns with no value on any row of the current page (none if the page has no rows)."""
    page = getattr(table, 'page', None)
    rows = list(page.object_list) if page is not None else list(table.rows)
    records = [getattr(row, 'record', row) for row in rows]
    records = [record for record in records if hasattr(record, 'pk')]
    if not records:
        return set()
    empty = set()
    exempt = set(getattr(table, 'exempt_columns', ()) or ())
    for name, bound in table.columns.items():
        if not bound.visible or name in KEEP or name in exempt:
            continue
        if all(_record_empty(record, bound) for record in records):
            empty.add(name)
    return empty


def _wrap_configure():
    configure = NetBoxTable.configure
    if getattr(configure, '_form_cleanup', False):
        return

    @functools.wraps(configure)
    def wrapped(self, request):
        model = _model_of(self)
        try:
            rules = rules_for(model, TABLES, request)
            if rules:
                hidden = hidden_fields(rules, self.columns.names(), always_only=True)
                hidden -= set(self.exempt_columns or ()) | KEEP
                if hidden:
                    self.exclude = (*(self.exclude or ()), *sorted(hidden))
        except Exception:
            pass
        configure(self, request)
        try:
            if hide_empty(request, 'tables'):
                empty = empty_columns(self)
                for name in empty:
                    self.columns.hide(name)
                setattr(self, AUTO_HIDDEN, empty)
        except Exception:
            pass

    wrapped._form_cleanup = True
    NetBoxTable.configure = wrapped


def _wrap_get_columns():
    get_columns = BaseTable._get_columns
    if getattr(get_columns, '_form_cleanup', False):
        return

    @functools.wraps(get_columns)
    def wrapped(self, visible=True):
        auto = getattr(self, AUTO_HIDDEN, None)
        if not auto:
            return get_columns(self, visible)
        columns = []
        for name, column in self.columns.items():
            shown = column.visible or name in auto
            if shown == visible and name not in self.exempt_columns:
                columns.append((name, column.verbose_name))
        return columns

    wrapped._form_cleanup = True
    BaseTable._get_columns = wrapped


def apply():
    _wrap_configure()
    _wrap_get_columns()
