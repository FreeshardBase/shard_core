import logging
import zipfile
from datetime import datetime
from itertools import chain
from pathlib import Path

import gconf
import zipfly
from fastapi import APIRouter
from starlette.responses import StreamingResponse
from tinydb import Query

from portal_core.model.identity import Identity
from portal_core.database.database import identities_table

log = logging.getLogger(__name__)

router = APIRouter(
	prefix='/backup',
)


@router.get('/export')
def export_backup():
	with identities_table() as identities:
		default_identity = Identity(**identities.get(Query().is_default == True))

	included_dirs = gconf.get('services.backup.included_dirs')
	all_paths = chain.from_iterable(Path(d).rglob('*') for d in included_dirs)
	zip_paths = [{
		'fs': str(p.absolute()),
		'n': p.absolute().relative_to(Path.cwd()),
	} for p in all_paths if not p.is_dir()]

	zfly = zipfly.ZipFly(paths=zip_paths, compression=zipfile.ZIP_STORED)

	filename = f'Backup of Portal {default_identity.short_id} - {datetime.now().strftime("%Y-%m-%d %H-%M")}.zip'

	log.info('exported full backup')

	return StreamingResponse(
		zfly.generator(),
		media_type='application/zip',
		headers={'Content-Disposition': f'attachment; filename={filename}'}
	)
