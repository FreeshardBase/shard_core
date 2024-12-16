from datetime import datetime, timezone
from enum import Enum

import gconf
from common_py import crypto
from common_py import human_encoding
from pydantic import computed_field
from sqlmodel import SQLModel, Field


class Identity(SQLModel, table=True):
	id: str = Field(primary_key=True)
	name: str
	email: str | None = None
	description: str | None = None
	private_key: str
	is_default: bool = False

	class Config:
		fields = {'public_key': {'exclude': True}}

	def __str__(self):
		return f'Identity[{self.short_id}, {self.name}]'

	@classmethod
	def create(cls, name: str, description: str = None, email: str = None) -> 'Identity':
		private_key = crypto.PrivateKey()
		return Identity(
			id=private_key.get_public_key().to_hash_id(),
			name=name,
			description=description,
			email=email,
			private_key=private_key.to_bytes().decode()
		)

	@property
	def short_id(self) -> str:
		return self.id[0:6]

	@property
	def public_key(self) -> crypto.PublicKey:
		return crypto.PrivateKey(self.private_key).get_public_key()

	@computed_field
	@property
	def public_key_pem(self) -> str:
		return self.public_key.to_bytes().decode()

	@computed_field
	@property
	def domain(self) -> str:
		zone = gconf.get('dns.zone')
		prefix_length = gconf.get('dns.prefix length')
		subdomain = self.id[:prefix_length].lower()
		domain = f'{subdomain}.{zone}'
		return domain


class Icon(str, Enum):
	UNKNOWN = 'unknown'
	SMARTPHONE = 'smartphone'
	TABLET = 'tablet'
	NOTEBOOK = 'notebook'
	DESKTOP = 'desktop'

class Terminal(SQLModel, table=True):
	id: str = Field(primary_key=True)
	name: str
	icon: Icon = Icon.UNKNOWN
	last_connection: datetime | None = None

	def __str__(self):
		return f'Terminal[{self.id}, {self.name}]'

	@classmethod
	def create(cls, name: str) -> 'Terminal':
		return Terminal(
			id=human_encoding.random_string(6),
			name=name,
			last_connection=datetime.now(timezone.utc)
		)
