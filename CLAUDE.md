# Working on this repo

NetBox plugin that hides fields from NetBox's web UI (forms, object pages,
object lists) by rules managed in the UI. Follows the conventions of
mattivaisanen/netbox-change-approval, netbox-fortigate-importer and
netbox-naming-convention.

## Rules

- **Display only.** Hiding never changes data, what a form saves, the REST
  API, GraphQL, exports or permissions. Hidden form fields stay inside the
  form (moved, not removed) so their values are submitted.
- **Never break a page.** Every wrapper of a NetBox internal (hooks/) calls
  NetBox first and falls back to NetBox's own result on anything
  unexpected. Each wrapped internal is listed in DEVELOPER.md and tested.
- **No dependencies on other plugins.** netbox-change-approval is only
  detected in tests (`tests/utils.has_change_approval()`).
- **Matti's NetBox:** netbox-docker in ~/netbox-docker, plugin source
  bind-mounted into the netbox and netbox-worker containers. Matti restarts
  NetBox. Keep test runs minimal (token cost); the test DB is shared, so
  don't run tests while another thread does. Run tests in the container
  with separate Redis DBs, or their jobs leak into the live DB and crash
  the worker: `sudo -n docker compose exec -T -e REDIS_DATABASE=2
  -e REDIS_CACHE_DATABASE=3 netbox /opt/netbox/venv/bin/python
  /opt/netbox/netbox/manage.py test netbox_form_cleanup --keepdb --noinput`.
- **NetBox support:** only claim what CI tests. `min_version` is the oldest
  release in the CI matrix; keep README "Requirements" in sync. Migrations
  depend only on migrations that exist in that oldest release.
- **Python:** `requires-python >= 3.10`; CI runs 3.12.
- **Packaging:** setuptools via `pyproject.toml`, no runtime dependencies.
  Keep `version` in `pyproject.toml` and `FormCleanupConfig.version` the
  same. Non-`.py` files must be listed in package-data.
- **Tests:** Django tests in `netbox_form_cleanup/tests/`, run with
  `python manage.py test netbox_form_cleanup` from a NetBox checkout.
  Every behaviour change gets a test. Never skip or weaken a test to get CI
  green.
- **Docs:** update in the same commit as the change: README.md,
  DEVELOPER.md (every wrapped NetBox internal), docs/configuration.md
  (every setting and preference), CHANGELOG.md (`## Unreleased` on top,
  `New:` / `Fixed:` lists written for NetBox users).
- **UI labels:** concise nouns like NetBox's own, never question words.
- **Commits:** subject says what changes for the user, in plain words. Body
  explains the problem, then the fix, in plain language. Never commit
  Claude conversation files.
