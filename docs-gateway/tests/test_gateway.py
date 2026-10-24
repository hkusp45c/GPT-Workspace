import concurrent.futures
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import server as g

class MeterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = patch.object(g, 'DATA', Path(self.tmp.name))
        self.p.start()
        self.addCleanup(self.p.stop)
        self.clock = patch.object(g.time, 'time', return_value=1792800000.0)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.used = 0
        self.searches = 0
        self.fail = False
        self.reset = '2026-11-01T00:00:00.000Z'
        self.up = patch.object(g, 'upstream', side_effect=self.upstream)
        self.up.start()
        self.addCleanup(self.up.stop)

    def upstream(self, path, params=None):
        if path == 'v2/usage':
            return {'usageResetsAt': self.reset,
                    'member': {'requests': self.used, 'includedInPlan': 1000}}
        self.searches += 1
        if self.fail:
            raise g.Blocked('simulated timeout')
        return {'infoSnippets': [{'content': 'example', 'source': 'https://example.org'}]}

    def test_locked_by_default(self):
        with self.assertRaises(g.Blocked):
            g.search({'query': 'test'})
        self.assertEqual(self.searches, 0)

    def test_cache_persists_after_revoke(self):
        g.authorize(60, 1)
        first = g.search({'query': 'test'})
        g.revoke()
        second = g.search({'query': 'test'})
        self.assertFalse(first['cached'])
        self.assertTrue(second['cached'])
        self.assertEqual(self.searches, 1)
        self.assertEqual(g.read_cache(first['cache_id'])['documentation'], first['documentation'])

    def test_failure_still_consumes_reservation(self):
        g.authorize(60, 1)
        self.fail = True
        with self.assertRaises(g.Blocked):
            g.search({'query': 'test'})
        self.assertEqual(g.status()['spent'], 1)
        self.assertEqual(g.status()['calls'], 0)

    def test_provider_usage_counts_toward_ceiling(self):
        g.authorize(60, 10)
        self.used = 900
        with self.assertRaises(g.Blocked):
            g.search({'query': 'test'})
        self.assertEqual(self.searches, 0)

    def test_stale_provider_counter_cannot_undo_local_reservations(self):
        g.authorize(60, 10)
        self.used = 899
        g.search({'query': 'first'})
        with self.assertRaises(g.Blocked):
            g.search({'query': 'second'})
        self.assertEqual(self.searches, 1)

    def test_concurrent_calls_share_grant(self):
        g.authorize(60, 1)
        def run(i):
            try:
                return g.search({'query': str(i)})
            except g.Blocked:
                return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(run, range(4)))
        self.assertEqual(sum(x is not None for x in results), 1)
        self.assertEqual(self.searches, 1)

    def test_expiry(self):
        g.authorize(1, 10)
        with patch.object(g.time, 'time', return_value=1792800061):
            with self.assertRaises(g.Blocked):
                g.search({'query': 'test'})

    def test_version_partitions_cache(self):
        g.authorize(60, 10)
        g.search({'query': 'test', 'library': 'python', 'version': '3.12'})
        g.search({'query': 'test', 'library': 'python', 'version': '3.13'})
        self.assertEqual(self.searches, 2)

    def test_bad_usage_fails_closed(self):
        g.authorize(60, 10)
        self.reset = 'bad'
        with self.assertRaises(g.Blocked):
            g.search({'query': 'test'})
        self.assertEqual(self.searches, 0)

    def test_usage_outage_fails_closed(self):
        g.authorize(60, 10)
        with patch.object(g, 'upstream', side_effect=g.Blocked('outage')):
            with self.assertRaises(g.Blocked):
                g.search({'query': 'test'})
        self.assertEqual(self.searches, 0)

    def test_expired_cache_does_not_silently_serve_stale(self):
        g.authorize(60, 10)
        first = g.search({'query': 'test'})
        with patch.object(g.time, 'time', return_value=1792800000 + g.TTL + 1):
            with self.assertRaises(g.Blocked):
                g.search({'query': 'test'})
            self.assertTrue(g.read_cache(first['cache_id'])['stale'])

    def test_rollover_resets_month_only(self):
        g.authorize(60, 10)
        self.used = 899
        g.search({'query': 'first'})
        with patch.object(g.time, 'time', return_value=1793577601):
            self.reset = '2026-12-01T00:00:00.000Z'
            self.used = 0
            g.authorize(60, 1)
            g.search({'query': 'second'})
            self.assertEqual(g.status()['spent'], 1)

if __name__ == '__main__':
    unittest.main()
