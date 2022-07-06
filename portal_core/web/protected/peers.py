import logging
from typing import List

from fastapi import APIRouter, HTTPException, status
from tinydb import Query
from tinydb.table import Table

from portal_core.database.database import peers_table
from portal_core.model.peer import Peer

log = logging.getLogger(__name__)

router = APIRouter(
	prefix='/peers',
)


@router.get('', response_model=List[Peer])
def list_all_peers(name: str = None):
	with peers_table() as peers:  # type: Table
		if name:
			return peers.search(Query().name.search(name))
		else:
			return peers.all()


@router.get('/{id}', response_model=Peer)
def get_peer_by_id(id_):
	with peers_table() as peers:
		if p := peers.get(Query().id == id_):
			return p
		else:
			raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.post('', response_model=Peer, status_code=status.HTTP_201_CREATED)
def add_peer(p: Peer):
	with peers_table() as peers:  # type: Table
		if peers.get(Query().id == p.id):
			raise HTTPException(status_code=status.HTTP_409_CONFLICT)
		else:
			peers.insert(p.dict())
			log.info(f'added {p}')
			return p
