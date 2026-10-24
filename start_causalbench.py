"""Start the local laboratory independently of a terminal, then open it."""
from pathlib import Path
import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
URL = 'http://127.0.0.1:8767/'

def healthy():
    try:
        with urllib.request.urlopen(URL + 'api/health', timeout=1) as response:
            result = json.load(response)
            return result.get('status') == 'ok' and result.get('mode') == 'simulation' and 'engine' in result
    except (OSError, ValueError):
        return False

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if not healthy():
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1', 8767)) == 0:
                raise SystemExit('Port 8767 is in use by another service. CausalBench was not started.')
        (ROOT / 'data').mkdir(exist_ok=True)
        options = {'cwd': str(ROOT), 'stdin': subprocess.DEVNULL, 'close_fds': True}
        if os.name == 'nt':
            options['creationflags'] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            options['start_new_session'] = True
        with (ROOT / 'data' / 'server.log').open('ab') as log:
            process = subprocess.Popen([sys.executable, '-u', '-m', 'causalbench.server', '--port', '8767'], stdout=log, stderr=log, **options)
        for _ in range(40):
            if healthy():
                break
            if process.poll() is not None:
                raise SystemExit('Server exited. See data/server.log for details.')
            time.sleep(.25)
        else:
            raise SystemExit('Server did not become ready. See data/server.log for details.')
    print('CausalBench is ready: ' + URL)
    if not args.no_browser:
        webbrowser.open(URL)

if __name__ == '__main__':
    main()
