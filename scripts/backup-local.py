#!/usr/bin/env python3
import sqlite3,tarfile,os
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parent.parent
src=root/'data/store.sqlite3'
if not src.exists(): raise SystemExit('No SQLite database found. Use backup.sh for PostgreSQL.')
folder=root/'.backups'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
folder.mkdir(parents=True,mode=0o700)
path=folder/'database.sqlite3'
with sqlite3.connect(src) as source, sqlite3.connect(path) as target: source.backup(target)
path.chmod(0o600)
if (root/'media').exists():
    archive=folder/'media.tar.gz'
    with tarfile.open(archive,'w:gz') as tar: tar.add(root/'media',arcname='media')
    archive.chmod(0o600)
print('Local backup created:',folder.relative_to(root))
