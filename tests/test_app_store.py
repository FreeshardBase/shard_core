from portal_core.service import app_store


def test_install(api_client):
	app_store.refresh_app_store(ref='develop')

	app_template_pathon_details = next(a for a in (app_store.get_store_apps()) if a.name == 'app-template-python')
	assert not app_template_pathon_details.is_installed

	app_store.install_store_app('app-template-python')

	app_template_pathon_details = next(a for a in (app_store.get_store_apps()) if a.name == 'app-template-python')
	assert app_template_pathon_details.is_installed
