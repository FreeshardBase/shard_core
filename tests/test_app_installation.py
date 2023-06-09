import docker
import pytest
from docker.errors import NotFound
from fastapi import status
from httpx import AsyncClient

from tests.util import install_app_and_wait

pytest_plugins = ('pytest_asyncio',)
pytestmark = pytest.mark.asyncio


async def test_get_initial_apps(api_client: AsyncClient):
	response = (await api_client.get('protected/apps')).json()
	assert len(response) == 1
	assert response[0]['name'] == 'filebrowser'


async def test_install_app(api_client: AsyncClient, mock_app_store):
	docker_client = docker.from_env()

	await install_app_and_wait(api_client, 'mock_app')

	docker_client.containers.get('mock_app')

	response = (await api_client.get('protected/apps')).json()
	assert len(response) == 2


async def test_install_app_twice(api_client: AsyncClient, mock_app_store):
	await install_app_and_wait(api_client, 'mock_app')

	response = await api_client.post('protected/apps/mock_app')
	assert response.status_code == status.HTTP_409_CONFLICT


async def test_uninstall_app(api_client: AsyncClient):
	docker_client = docker.from_env()
	docker_client.containers.get('filebrowser')

	response = await api_client.delete('protected/apps/filebrowser')
	assert response.status_code == status.HTTP_204_NO_CONTENT

	response = (await api_client.get('protected/apps')).json()
	assert len(response) == 0

	with pytest.raises(NotFound):
		docker_client.containers.get('filebrowser')
