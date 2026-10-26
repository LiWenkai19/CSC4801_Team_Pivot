"""Launch the candidate UI with temporary demo data; Ctrl+C stops both services."""
import argparse
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def ensure_port(port):
    with socket.socket() as listener:
        try:
            listener.bind(('127.0.0.1', port))
        except OSError as error:
            raise RuntimeError(f'Port {port} is in use; stop its owner before previewing.') from error


def wait_ready(url, process, log):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f'Service exited. See {log}')
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError):
            pass
        time.sleep(0.2)
    raise RuntimeError(f'Service did not start: {url}; see {log}')


def stop(process):
    if process.poll() is not None:
        return
    if sys.platform == 'win32':
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke', action='store_true', help='Verify startup and immediately stop.')
    args = parser.parse_args()
    npm = shutil.which('npm.cmd' if sys.platform == 'win32' else 'npm')
    if not npm or not (ROOT / 'frontend/candidate/node_modules').is_dir():
        raise SystemExit('Run npm ci inside frontend/candidate first.')
    for port in (18019, 5173):
        ensure_port(port)
    processes = []
    with tempfile.TemporaryDirectory(prefix='pivot-candidate-preview-', ignore_cleanup_errors=True) as folder:
        log = Path(folder) / 'services.log'
        with log.open('w', encoding='utf-8') as output:
            try:
                hidden = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                api = subprocess.Popen([sys.executable, 'backend/candidate_tests/browser_server.py', '--port', '18019'],
                                       cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, creationflags=hidden)
                processes.append(api)
                wait_ready('http://127.0.0.1:18019/openapi.json', api, log)
                import os
                env = dict(os.environ, VITE_API_BASE_URL='http://127.0.0.1:18019')
                ui = subprocess.Popen([npm, 'run', 'dev', '--', '--host', '127.0.0.1', '--port', '5173', '--strictPort'],
                                      cwd=ROOT / 'frontend/candidate', env=env, stdout=output,
                                      stderr=subprocess.STDOUT, creationflags=hidden)
                processes.append(ui)
                wait_ready('http://127.0.0.1:5173', ui, log)
                print('UI: http://127.0.0.1:5173', flush=True)
                print('API docs: http://127.0.0.1:18019/docs', flush=True)
                print('Demo: alice@example.com / bob@example.com; password: Demo-only-123!', flush=True)
                print('Temporary SQLite data; no business database is used. Ctrl+C stops both services.', flush=True)
                if args.smoke:
                    return 0
                while all(process.poll() is None for process in processes):
                    time.sleep(0.5)
                raise RuntimeError(f'A service stopped. See {log}')
            except KeyboardInterrupt:
                return 0
            except Exception:
                output.flush()
                print(log.read_text(encoding='utf-8', errors='replace')[-3000:], file=sys.stderr)
                raise
            finally:
                for process in reversed(processes):
                    stop(process)


if __name__ == '__main__':
    raise SystemExit(main())
