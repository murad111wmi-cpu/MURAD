#!/usr/bin/env python3
"""Generate a private local production env file; never display credential values."""
import os,secrets
from pathlib import Path
root=Path(__file__).resolve().parent.parent
path=root/'.env'
if path.exists(): raise SystemExit('.env exists; preserved. Edit it locally to set your domain.')
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:
    f.write('DEBUG=0\nDJANGO_SECRET_KEY='+secrets.token_urlsafe(64)+'\nPOSTGRES_PASSWORD='+secrets.token_urlsafe(32)+'\nALLOWED_HOSTS=localhost,127.0.0.1\nCSRF_TRUSTED_ORIGINS=\nDOMAIN=\n')
print('Created private .env. Configure DOMAIN, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS before public launch.')
