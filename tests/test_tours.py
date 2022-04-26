def test_add(api_client):
	tour = {
		'name': 'foo',
		'status': 'seen'
	}
	put_response = api_client.put('protected/help/tours', json=tour)
	assert put_response.status_code == 204, put_response.text

	get_response = api_client.get('protected/help/tours/foo')
	assert get_response.status_code == 200, get_response.text
	assert get_response.json() == tour


def test_update(api_client):
	tour1 = {
		'name': 'foo',
		'status': 'seen'
	}
	put_response1 = api_client.put('protected/help/tours', json=tour1)
	assert put_response1.status_code == 204, put_response1.text

	tour2 = {
		'name': 'foo',
		'status': 'unseen'
	}
	put_response2 = api_client.put('protected/help/tours', json=tour2)
	assert put_response2.status_code == 204, put_response2.text

	get_response = api_client.get('protected/help/tours/foo')
	assert get_response.status_code == 200, get_response.text
	assert get_response.json() == tour2


def test_list(api_client):
	tour1 = {
		'name': 'foo',
		'status': 'seen'
	}
	put_response1 = api_client.put('protected/help/tours', json=tour1)
	assert put_response1.status_code == 204, put_response1.text

	tour2 = {
		'name': 'bar',
		'status': 'unseen'
	}
	put_response2 = api_client.put('protected/help/tours', json=tour2)
	assert put_response2.status_code == 204, put_response2.text

	get_response = api_client.get('protected/help/tours')
	assert get_response.status_code == 200, get_response.text
	assert len(get_response.json()) == 2
	assert tour1 in get_response.json()
	assert tour2 in get_response.json()


def test_reset(api_client):
	tour = {
		'name': 'foo',
		'status': 'seen'
	}
	put_response = api_client.put('protected/help/tours', json=tour)
	assert put_response.status_code == 204, put_response.text

	delete_response = api_client.delete('protected/help/tours')
	assert delete_response.status_code == 204, delete_response.text

	get_response = api_client.get('protected/help/tours')
	assert get_response.status_code == 200, get_response.text
	assert len(get_response.json()) == 0
