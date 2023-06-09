async def test_204_has_empty_body(mock_app_store, api_client):
	delete_response = await api_client.delete('protected/help/tours')
	assert delete_response.status_code == 204, delete_response.text
	assert delete_response.content == b''
