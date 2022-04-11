from enum import Enum
from typing import Optional, List, Dict, Union

from pydantic import BaseModel, root_validator

from portal_core.model import app_migration

CURRENT_VERSION = '3.0'


class InstallationReason(str, Enum):
	UNKNOWN = 'unknown'
	CONFIG = 'config'
	CUSTOM = 'custom'
	STORE = 'store'


class Access(str, Enum):
	PUBLIC = 'public'
	PRIVATE = 'private'


class Status(str, Enum):
	UNKNOWN = 'unknown'
	RUNNING = 'running'


class Service(str, Enum):
	POSTGRES = 'postgres'


class StoreInfo(BaseModel):
	description_short: Optional[str]
	description_long: Optional[Union[str, List[str]]]
	hint: Optional[Union[str, List[str]]]
	is_featured: Optional[bool]


class Postgres(BaseModel):
	connection_string: str
	userspec: str
	user: str
	password: str
	hostspec: str
	host: str
	port: int


class DataDir(BaseModel):
	path: str
	uid: int
	gid: int


class Path(BaseModel):
	access: Access
	headers: Optional[Dict[str, str]]


class App(BaseModel):
	v: str
	name: str
	image: str
	port: int
	data_dirs: Optional[List[Union[str, DataDir]]]
	env_vars: Optional[Dict[str, str]]
	services: Optional[List[Service]]
	paths: Dict[str, Path]
	store_info: Optional[StoreInfo]

	@root_validator(pre=True)
	def migrate(cls, values):
		if 'v' not in values:
			values['v'] = '0.0'
		while values['v'] != CURRENT_VERSION:
			migrate = app_migration.migrations[values['v']]
			values = migrate(values)
		return values


class AppToInstall(App):
	installation_reason: InstallationReason = InstallationReason.UNKNOWN


class InstalledApp(AppToInstall):
	status: str = Status.UNKNOWN
	postgres: Union[Postgres, None]


class StoreApp(App):
	is_installed: bool
