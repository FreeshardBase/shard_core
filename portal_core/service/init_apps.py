import gconf
from tinydb import where
from tinydb.table import Table

from portal_core.database.database import apps_table
from portal_core.model.app import InstallationReason, InstalledApp, AppToInstall


def refresh_init_apps():
	configured_init_apps = {k: v for k, v in gconf.get('apps.initial_apps').items() if v}
	with apps_table() as apps:  # type: Table
		installed_init_apps = [InstalledApp(**a) for a
			in apps.search(where('installation_reason') == InstallationReason.CONFIG)]

	to_add = set(configured_init_apps.keys()) - {a.name for a in installed_init_apps}
	to_remove = {a.name for a in installed_init_apps} - set(configured_init_apps.keys())

	with apps_table() as apps:
		for app_name in to_add:
			app = AppToInstall(
				name=app_name,
				**gconf.get('apps.initial_apps', app_name),
				installation_reason=InstallationReason.CONFIG,
			)
			apps.insert(app.dict())

		for app_name in to_remove:
			apps.remove(where('name') == app_name)
