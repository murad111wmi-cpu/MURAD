#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export DEBUG=1
bash scripts/setup.sh
if ! .venv/bin/python -c "import os;os.environ['DJANGO_SETTINGS_MODULE']='config.settings';import django;django.setup();from shop.models import User;raise SystemExit(0 if User.objects.filter(is_superuser=True,is_active=True).exists() else 1)"; then
  echo 'أنشئ حساب المدير. أدخل بريدك وكلمة مرور قوية. كلمة المرور لن تظهر أثناء الكتابة.'
  .venv/bin/python manage.py createsuperuser
fi
exec bash scripts/start.sh
