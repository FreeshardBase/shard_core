import logging
from typing import List

from fastapi import APIRouter, HTTPException, status
from tinydb import Query
from tinydb.table import Table

from portal_core.database.database import peers_table
from portal_core.model.peer import Peer
from portal_core.util import signals

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
def get_peer_by_id(id):
	with peers_table() as peers:
		if p := peers.get(Query().id == id):
			return p
		else:
			raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.put('', response_model=Peer)
def put_peer(p: Peer):
	with peers_table() as peers:  # type: Table
		peers.upsert(p.dict(), Query().id == p.id)

	signals.on_peer_write.send(p)
	log.info(f'put {p}')
	return p


@router.delete('/{id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_peer(id):
	with peers_table() as peers:  # type: Table
		deleted = peers.remove(Query().id == id)
		if len(deleted) > 1:
			log.critical(f'during deleting of peer {id}, {len(deleted)} peers were deleted')
		log.info(f'removed peer {deleted[0]}')
