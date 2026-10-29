from unittest import TestCase
from unittest.mock import patch
from main.apps.physics_client.services.optional.channel_cache import ChannelCache


class CacheLifetimeTest(TestCase):
    def test_moving_keys_are_expired_before_256_writes(self):
        cache = ChannelCache(ttl_sec=0.5)
        with patch('main.apps.physics_client.services.optional.channel_cache.time.monotonic') as now:
            for i in range(200):
                now.return_value = float(i)
                cache.set((i,), {'sample': 'channel'})
                self.assertEqual(len(cache), 1)

    def test_memory_budget_evicts_old_values_and_rejects_oversized_value(self):
        cache = ChannelCache(ttl_sec=60, max_bytes=1000)
        cache.set(('a',), b'a' * 600)
        cache.set(('b',), b'b' * 600)
        self.assertIsNone(cache.get(('a',)))
        self.assertIsNotNone(cache.get(('b',)))
        cache.set(('too-big',), b'x' * 2000)
        self.assertIsNone(cache.get(('too-big',)))
        self.assertLessEqual(cache._bytes, 1000)
        cache.clear()
        self.assertEqual(cache._bytes, 0)
