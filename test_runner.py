import concurrent.futures
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from runner import Store


def payload(**changes):
    return dict(value=12, failures=0, permanent=False, max_attempts=3) | changes


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.path = Path(self.tmp.name) / 'test.sqlite'
        self.store = Store(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def ready(self):
        with self.store.db() as c:
            c.execute('UPDATE jobs SET due=0')

    def test_concurrent_duplicates(self):
        with concurrent.futures.ThreadPoolExecutor(8) as pool:
            results = list(pool.map(lambda _: self.store.submit('same', payload()), range(16)))
        self.assertEqual(len({r[0] for r in results}), 1)
        self.assertEqual(sum(r[1] for r in results), 1)

    def test_payload_conflict_and_validation(self):
        self.store.submit('same', payload())
        with self.assertRaises(ValueError):
            self.store.submit('same', payload(value=13))
        for p in (payload(value=True), payload(max_attempts=6), payload(extra=1)):
            with self.assertRaises(ValueError):
                self.store.submit('invalid', p)

    def test_competing_claims(self):
        self.store.submit('one', payload())
        with concurrent.futures.ThreadPoolExecutor(8) as pool:
            results = list(pool.map(lambda _: self.store.claim(), range(8)))
        self.assertEqual(sum(r is not None for r in results), 1)

    def test_transient_then_success(self):
        self.store.submit('transient', payload(failures=2))
        for _ in range(3):
            self.ready()
            self.assertTrue(self.store.finish(self.store.claim()))
        h = self.store.history()
        self.assertEqual(h['jobs'][0]['state'], 'succeeded')
        self.assertEqual([a['outcome'] for a in h['attempts']], ['transient_failure'] * 2 + ['succeeded'])
        self.assertEqual(h['effects'][0]['result'], '144')

    def test_permanent_failure(self):
        self.store.submit('permanent', payload(permanent=True))
        self.store.finish(self.store.claim())
        self.assertEqual(self.store.history()['jobs'][0]['state'], 'failed')
        self.assertEqual(len(self.store.history()['attempts']), 1)

    def test_retry_exhaustion_and_backoff(self):
        self.store.submit('exhaust', payload(failures=5))
        for _ in range(3):
            self.ready()
            self.store.finish(self.store.claim())
            self.assertIsNone(self.store.claim())
        self.assertEqual(self.store.history()['jobs'][0]['state'], 'failed')
        self.assertEqual(self.store.history()['effects'], [])

    def test_stale_worker_is_fenced(self):
        self.store.submit('stale', payload())
        old = self.store.claim(0.01)
        time.sleep(0.03)
        self.store.claim()
        self.ready()
        new = self.store.claim()
        self.assertFalse(self.store.finish(old))
        self.assertTrue(self.store.finish(new))
        self.assertEqual(len(self.store.history()['effects']), 1)

    def test_crash_exhausts_attempt_budget(self):
        self.store.submit('last-crash', payload(max_attempts=1))
        self.store.claim(0.01)
        time.sleep(0.03)
        self.assertIsNone(self.store.claim())
        h = self.store.history()
        self.assertEqual(h['jobs'][0]['state'], 'failed')
        self.assertEqual(h['attempts'][0]['outcome'], 'lease_expired')
        self.assertEqual(h['effects'], [])

    def crash(self, flag):
        proc = subprocess.Popen([sys.executable, str(Path(__file__).with_name('runner.py')), 'worker', '--db', str(self.path), '--once', '--lease-seconds', '0.2', flag, '30'], stdout=subprocess.PIPE, text=True)
        try:
            self.assertIn('claimed', proc.stdout.readline())
            if flag == '--pause-after-commit':
                self.assertIn('finished', proc.stdout.readline())
            proc.kill()
            proc.wait(timeout=5)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
            proc.stdout.close()

    def test_real_worker_crash_before_commit(self):
        self.store.submit('crash-before', payload())
        self.crash('--pause-after-claim')
        time.sleep(0.25)
        self.store.claim()
        self.ready()
        self.store.finish(self.store.claim())
        h = self.store.history()
        self.assertEqual(h['jobs'][0]['state'], 'succeeded')
        self.assertEqual([a['outcome'] for a in h['attempts']], ['lease_expired', 'succeeded'])
        self.assertEqual(len(h['effects']), 1)

    def test_real_worker_crash_after_commit(self):
        self.store.submit('crash-after', payload())
        self.crash('--pause-after-commit')
        time.sleep(0.25)
        self.assertIsNone(self.store.claim())
        self.assertEqual(len(self.store.history()['effects']), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
