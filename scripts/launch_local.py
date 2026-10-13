"""Local desktop launcher. Never use this development server for public hosting."""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import venv
import webbrowser

ROOT = Path(__file__).resolve().parent.parent

def prepare():
    if not (3, 12) <= sys.version_info[:2] <= (3, 14):
        raise RuntimeError('Install Python 3.12 or 3.13 from python.org, then launch again.')
    os.chdir(ROOT)
    env = os.environ.copy()
    # A desktop trial must not modify an inherited production database.
    env.pop('DATABASE_URL', None)
    env.pop('MEDIA_ROOT', None)
    env.pop('TRUST_PROXY', None)
    env.update(DEBUG='1', PYTHONUTF8='1', PYTHONIOENCODING='utf-8', ALLOWED_HOSTS='localhost,127.0.0.1,[::1]', CSRF_TRUSTED_ORIGINS='')
    python = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        print('Preparing Python environment. Please wait...', flush=True)
        venv.EnvBuilder(with_pip=True).create(ROOT / '.venv')
    def run(*args):
        subprocess.run([str(python), *args], cwd=ROOT, env=env, check=True)
    print('Installing dependencies and preparing your store...', flush=True)
    run('-m', 'pip', 'install', '--disable-pip-version-check', '-r', 'requirements.txt')
    for args in [('migrate', '--noinput'), ('createcachetable',), ('bootstrap_store',), ('collectstatic', '--noinput'), ('check',)]:
        run('manage.py', *args)
    return python, env, run

def free_port():
    for port in range(8000, 8021):
        with socket.socket() as sock:
            try:
                sock.bind(('127.0.0.1', port))
                return port
            except OSError:
                pass
    raise RuntimeError('Ports 8000-8020 are busy. Close the previous store window and try again.')

def open_when_ready(port, stop):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    address = f'http://127.0.0.1:{port}/'
    deadline = time.monotonic() + 45
    while not stop.is_set() and time.monotonic() < deadline:
        try:
            with opener.open(address + 'health/', timeout=2) as response:
                if response.status == 200:
                    webbrowser.open(address)
                    return
        except OSError:
            pass
        stop.wait(0.5)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare-only', action='store_true', help='Install/migrate only; no account prompt, browser or server.')
    options = parser.parse_args()
    python, env, run = prepare()
    if options.prepare_only:
        print('Preparation complete. No account was created and no browser or server was opened.')
        return
    result = subprocess.run([str(python), '-c', "import os;os.environ['DJANGO_SETTINGS_MODULE']='config.settings';import django;django.setup();from shop.models import User;raise SystemExit(0 if User.objects.filter(is_active=True,is_superuser=True).exists() else 3)"], cwd=ROOT, env=env)
    if result.returncode == 3:
        print('\nCreate your administrator account. Enter your email and a strong password.')
        print('Password characters will not appear while typing. This is normal.\n', flush=True)
        run('manage.py', 'createsuperuser')
    elif result.returncode:
        raise RuntimeError('Could not check the administrator account. Read the error above.')
    port = free_port()
    print(f'\nStore: localhost:{port}\nAdministrator: localhost:{port}/admin/\nWorker: localhost:{port}/worker/login/')
    print('Keep this window open while using the store. Press Ctrl+C to stop.\n', flush=True)
    stop = threading.Event()
    browser_thread = threading.Thread(target=open_when_ready, args=(port, stop), daemon=True)
    process = subprocess.Popen([str(python), 'manage.py', 'runserver', f'127.0.0.1:{port}', '--noreload'], cwd=ROOT, env=env)
    browser_thread.start()
    try:
        code = process.wait()
        if code:
            raise RuntimeError('The development server could not start. Read the error above.')
    finally:
        stop.set()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nStore stopped. Your saved data is preserved.')
    except (RuntimeError, subprocess.CalledProcessError, OSError) as error:
        print('\nLaunch failed:', error, file=sys.stderr)
        raise SystemExit(1)
