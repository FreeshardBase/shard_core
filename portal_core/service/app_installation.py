import asyncio
import datetime
import logging
import shutil
from contextlib import suppress
from pathlib import Path
from typing import Optional, Dict

import gconf
import jinja2
import pydantic
import yaml
from azure.storage.blob.aio import ContainerClient
from pydantic import BaseModel
from tinydb import Query

from portal_core.database.database import apps_table, identities_table
from portal_core.model.app_meta import InstalledApp, InstallationReason, Status
from portal_core.model.identity import SafeIdentity, Identity
from portal_core.service.app_tools import docker_create_app, get_installed_apps_path, get_installed_apps, \
	get_app_metadata, docker_shutdown_app
from portal_core.service.traefik_dynamic_config import compile_config, AppInfo
from portal_core.util import signals
from portal_core.util.subprocess import subprocess

log = logging.getLogger(__name__)

install_lock = asyncio.Lock()
installation_tasks: Dict[str, asyncio.Task] = {}


class AppStoreStatus(BaseModel):
	current_branch: str
	commit_id: str
	last_update: Optional[datetime.datetime]


async def install_store_app(
		name: str,
		installation_reason: InstallationReason = InstallationReason.STORE,
		store_branch: Optional[str] = 'feature-docker-compose',  # todo: change back to master
):
	with apps_table() as apps:
		if apps.contains(Query().name == name):
			raise AppAlreadyInstalled(name)
		installed_app = InstalledApp(
			name=name,
			installation_reason=installation_reason,
			status=Status.INSTALLATION_QUEUED,
			from_branch=store_branch,
		)
		apps.insert(installed_app.dict())

	task = asyncio.create_task(_install_app_task(installed_app))
	installation_tasks[name] = task
	signals.on_apps_update.send()
	log.info(f'created installation task for {name}')
	log.debug(f'installation tasks: {installation_tasks.keys()}')


async def _install_app_task(installed_app: InstalledApp):
	await asyncio.sleep(10)
	async with install_lock:
		log.info(f'starting installation of {installed_app.name}')
		with apps_table() as apps:
			apps.update({'status': Status.INSTALLING}, Query().name == installed_app.name)
		signals.on_apps_update.send()
		try:
			log.debug(f'downloading app {installed_app.name} from store')
			await _download_azure_blob_directory(
				f'{installed_app.from_branch}/all_apps/{installed_app.name}',
				get_installed_apps_path() / installed_app.name,
			)
			log.debug('updating traefik dynamic config')
			_write_traefik_dyn_config()
			log.debug(f'creating docker-compose.yml for app {installed_app.name}')
			await _render_docker_compose_template(installed_app)
			log.debug(f'creating containers for app {installed_app.name}')
			await docker_create_app(installed_app.name)
			log.info(f'finished installation of {installed_app.name}')
		except Exception as e:
			log.error(f'Error while installing app {installed_app.name}: {e!r}')
			with apps_table() as apps:
				apps.update({'status': Status.ERROR}, Query().name == installed_app.name)
			signals.on_apps_update.send()
		finally:
			del installation_tasks[installed_app.name]


async def cancel_all_installations(wait=False):
	for name in list(installation_tasks.keys()):
		await cancel_installation(name)
	if wait:
		for task in list(installation_tasks.values()):
			with suppress(asyncio.CancelledError):
				await task


async def cancel_installation(name: str):
	if name not in installation_tasks:
		raise AppNotInstalled(name)
	installation_tasks[name].cancel()
	with apps_table() as apps:
		apps.update({'status': Status.ERROR}, Query().name == name)
	signals.on_apps_update.send()
	log.debug(f'cancelled installation of {name}')


async def uninstall_app(name: str):
	async with install_lock:
		log.debug(f'starting uninstallation of {name}')
		with apps_table() as apps:
			if not apps.contains(Query().name == name):
				raise AppNotInstalled(name)
		log.debug(f'shutting down docker container for app {name}')
		await docker_shutdown_app(name)
		log.debug(f'deleting app data for {name}')
		shutil.rmtree(Path(get_installed_apps_path() / name))
		log.debug(f'removing app {name} from database')
		with apps_table() as apps:
			apps.remove(Query().name == name)
		log.debug('updating traefik dynamic config')
		_write_traefik_dyn_config()
		signals.on_apps_update.send()
		log.debug(f'finished uninstallation of {name}')


class AppAlreadyInstalled(Exception):
	pass


class AppNotInstalled(Exception):
	pass


async def _download_azure_blob_directory(directory_name: str, target_dir: Path):
	async with ContainerClient(
			account_url=gconf.get('apps.app_store.base_url'),
			container_name=gconf.get('apps.app_store.container_name'),
	) as container_client:

		directory_name = directory_name.rstrip('/')
		async for blob in container_client.list_blobs(name_starts_with=directory_name):
			if blob.name.endswith('/'):
				continue
			target_file = target_dir / blob.name[len(directory_name) + 1:]
			target_file.parent.mkdir(exist_ok=True, parents=True)
			with open(target_file, 'wb') as f:
				download_blob = await container_client.download_blob(blob)
				f.write(await download_blob.readall())


async def _render_docker_compose_template(app: InstalledApp):
	fs = {
		'app_data': (Path(gconf.get('path_root')) / 'user_data' / 'app_data' / app.name).absolute(),
		'shared_documents': (Path(gconf.get('path_root')) / 'user_data' / 'shared' / 'documents').absolute(),
		'shared_media': (Path(gconf.get('path_root')) / 'user_data' / 'shared' / 'media').absolute(),
		'shared_music': (Path(gconf.get('path_root')) / 'user_data' / 'shared' / 'music').absolute(),
	}

	with identities_table() as identities:
		default_identity = Identity(**identities.get(Query().is_default == True))  # noqa: E712
	portal = SafeIdentity.from_identity(default_identity)

	app_dir = get_installed_apps_path() / app.name
	template = jinja2.Template((app_dir / 'docker-compose.yml.template').read_text())
	(app_dir / 'docker-compose.yml').write_text(template.render(
		fs=fs, portal=portal,
	))


async def refresh_init_apps():
	configured_init_apps = set(gconf.get('apps.initial_apps'))
	installed_apps = get_installed_apps()

	for app_name in configured_init_apps - installed_apps:
		await install_store_app(app_name, InstallationReason.CONFIG)


def _write_traefik_dyn_config():
	with apps_table() as apps:
		apps = [InstalledApp(**a) for a in apps.all() if a['status'] != Status.INSTALLATION_QUEUED]
	app_infos = [AppInfo(get_app_metadata(a.name), installed_app=a) for a in apps]

	with identities_table() as identities:
		default_identity = Identity(**identities.get(Query().is_default == True))  # noqa: E712
	portal = SafeIdentity.from_identity(default_identity)

	traefik_dyn_filename = Path(gconf.get('path_root')) / 'core' / 'traefik_dyn' / 'traefik_dyn.yml'
	_write_to_yaml(compile_config(app_infos, portal), traefik_dyn_filename)


def _write_to_yaml(spec: pydantic.BaseModel, output_path: Path):
	output_path.parent.mkdir(exist_ok=True, parents=True)
	with open(output_path, 'w') as f:
		f.write('# == DO NOT MODIFY ==\n# this file is auto-generated\n\n')
		f.write(yaml.dump(spec.dict(exclude_none=True)))


async def login_docker_registries():
	registries = gconf.get('apps.registries')
	for r in registries:
		await subprocess('docker', 'login', '-u', r['username'], '-p', r['password'], r['uri'])
		log.debug(f'logged in to registry {r["uri"]}')
