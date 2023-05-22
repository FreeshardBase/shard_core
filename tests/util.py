import contextlib
import subprocess
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

import gconf
from common_py.crypto import PublicKey
from fastapi import Response
from http_message_signatures import HTTPSignatureKeyResolver, algorithms, VerifyResult
from httpx import URL, Request
from requests import PreparedRequest
from requests_http_signature import HTTPSignatureAuth
from starlette.testclient import TestClient
from tinydb import where

from portal_core.database.database import apps_table
from portal_core.model.app_meta import AppToInstall, InstallationReason
from portal_core.service import app_infra

WAITING_DOCKER_IMAGE = 'nginx:alpine'


def pair_new_terminal(api_client, name='my_terminal', assert_success=True) -> Response:
	pairing_code = get_pairing_code(api_client)
	response = add_terminal(api_client, pairing_code['code'], name)
	if assert_success:
		assert response.status_code == 201
	return response


def get_pairing_code(api_client: TestClient, deadline=None):
	params = {'deadline': deadline} if deadline else {}
	response = api_client.get('protected/terminals/pairing-code', params=params)
	response.raise_for_status()
	return response.json()


def add_terminal(api_client, pairing_code, t_name):
	return api_client.post(
		f'public/pair/terminal?code={pairing_code}',
		json={'name': t_name})


@contextlib.contextmanager
def create_apps_from_docker_compose():
	dc = Path(gconf.get('path_root')) / 'core' / 'docker-compose-apps.yml'
	subprocess.run(
		f'docker-compose -p apps -f {dc.name} up --remove-orphans --no-start',
		cwd=dc.parent,
		shell=True,
		check=True,
	)
	try:
		yield
	finally:
		subprocess.run(
			f'docker-compose -p apps -f {dc.name} down', cwd=dc.parent,
			shell=True,
			check=True,
		)


def verify_signature_auth(request: PreparedRequest, pubkey: PublicKey) -> VerifyResult:
	class KR(HTTPSignatureKeyResolver):
		def resolve_private_key(self, key_id: str):
			pass

		def resolve_public_key(self, key_id: str):
			return pubkey.to_bytes()

	return HTTPSignatureAuth.verify(
		request,
		signature_algorithm=algorithms.RSA_PSS_SHA512,
		key_resolver=KR(),
	)


@contextmanager
def install_test_app():
	with apps_table() as apps:  # type: Table
		apps.truncate()
		apps.insert(AppToInstall(**{
			'description': 'n/a',
			'env_vars': None,
			'image': WAITING_DOCKER_IMAGE,
			'installation_reason': 'config',
			'name': 'myapp',
			'paths': {
				'': {
					'access': 'private',
					'headers': {
						'X-Ptl-Client-Id': '{{ auth.client_id }}',
						'X-Ptl-Client-Name': '{{ auth.client_name }}',
						'X-Ptl-Client-Type': '{{ auth.client_type }}',
						'X-Ptl-ID': '{{ portal.id }}',
						'X-Ptl-Foo': 'bar'
					}
				},
				'/public': {
					'access': 'public',
					'headers': {
						'X-Ptl-Client-Id': '{{ auth.client_id }}',
						'X-Ptl-Client-Name': '{{ auth.client_name }}',
						'X-Ptl-Client-Type': '{{ auth.client_type }}',
						'X-Ptl-ID': '{{ portal.id }}',
						'X-Ptl-Foo': 'baz'
					}
				},
				'/peer': {
					'access': 'peer',
					'headers': {
						'X-Ptl-Client-Id': '{{ auth.client_id }}',
						'X-Ptl-Client-Name': '{{ auth.client_name }}',
						'X-Ptl-Client-Type': '{{ auth.client_type }}',
					}
				}
			},
			'port': 80,
			'services': None,
			'v': '1.0'
		}).dict())
	app_infra.refresh_app_infra()

	with create_apps_from_docker_compose():
		yield

	with apps_table() as apps:
		apps.remove(where('name') == 'myapp')
	app_infra.refresh_app_infra()


def modify_request_like_traefik_forward_auth(request: PreparedRequest) -> Request:
	url = urlparse(request.url)
	netloc_without_subdomain = url.netloc.split('.', maxsplit=1)[1]
	return Request(
		method=request.method,
		url=URL(f'https://{netloc_without_subdomain}/internal/auth'),
		headers={
			'X-Forwarded-Proto': url.scheme,
			'X-Forwarded-Host': url.netloc,
			'X-Forwarded-Uri': url.path,
			'X-Forwarded-Method': request.method,
			'signature-input': request.headers['signature-input'],
			'signature': request.headers['signature'],
			'date': request.headers['date'],
		}
	)


def insert_foo_app():
	app = AppToInstall(**{
		'v': '3.1',
		'name': 'foo-app',
		'image': 'foo',
		'version': '1.2.3',
		'port': 1,
		'paths': {
			'': {'access': 'public'},
		},
		'lifecycle': {'idle_time_for_shutdown': 5},
		'reason': InstallationReason.CUSTOM,
	})
	with apps_table() as apps:  # type: Table
		apps.truncate()
		apps.insert(app.dict())
