"""Optional browser QA with existing Playwright; never controls an open browser."""
import json
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from runner import Store


def main():
    root = Path(__file__).parent
    with tempfile.TemporaryDirectory(dir=root) as tmp:
        db = Path(tmp) / 'qa.sqlite'
        api = subprocess.Popen([sys.executable, str(root / 'runner.py'), 'api', '--db', str(db), '--port', '8766'], stdout=subprocess.PIPE)
        worker = None
        try:
            url = 'http://127.0.0.1:8766'
            for _ in range(50):
                try:
                    urllib.request.urlopen(url, timeout=1).close()
                    break
                except urllib.error.URLError:
                    time.sleep(0.1)
            def submit(key, failures=0, permanent=False, value=12):
                body = json.dumps({'key': key, 'payload': {'value': value, 'failures': failures, 'permanent': permanent, 'max_attempts': 3}}).encode()
                req = urllib.request.Request(url + '/api/jobs', data=body, headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=3) as r:
                    return r.status, json.load(r)
            assert submit('immediate')[0] == 201
            assert submit('immediate')[0] == 200
            try:
                submit('immediate', value=13)
                raise AssertionError('conflict accepted')
            except urllib.error.HTTPError as e:
                assert e.code == 409
            submit('recovered', failures=2)
            submit('exhausted', failures=5)
            submit('permanent', permanent=True)
            worker = subprocess.Popen([sys.executable, str(root / 'runner.py'), 'worker', '--db', str(db)], stdout=subprocess.DEVNULL)
            for _ in range(100):
                h = Store(db).history()
                if all(j['state'] in ('succeeded', 'failed') for j in h['jobs']):
                    break
                time.sleep(0.1)
            assert sorted(j['state'] for j in h['jobs']) == ['failed', 'failed', 'succeeded', 'succeeded']
            assert len(h['effects']) == 2
            print('HTTP end-to-end: PASS (create, duplicate, conflict, worker, retry, exhaustion, permanent)')
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 1280, 'height': 1000})
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(url)
                page.wait_for_function("document.getElementById('summary').textContent === '4 jobs · 2 committed effects'")
                assert page.locator('#jobs tr').count() == 4
                page.locator('#key').fill('browser-submit')
                page.locator('button').click()
                page.wait_for_function("document.getElementById('message').textContent.startsWith('Created job')")
                page.wait_for_function("document.getElementById('summary').textContent === '5 jobs · 3 committed effects'")
                assert not errors, errors
                (root / 'docs').mkdir(exist_ok=True)
                page.screenshot(path=str(root / 'docs' / 'dashboard.png'), full_page=True)
                page.set_viewport_size({'width': 390, 'height': 844})
                page.screenshot(path=str(root / 'docs' / 'dashboard-mobile.png'), full_page=True)
                browser.close()
            print('Headless dashboard: PASS (render, submit, refresh, no JS errors; screenshots saved)')
        finally:
            for process in (worker, api):
                if process:
                    process.kill()
                    process.wait(timeout=5)
            api.stdout.close()


if __name__ == '__main__':
    main()
