"""Allow pure-unit tests without requiring a running Redis server/library."""
import sys
import types
if 'redis' not in sys.modules:
    try:
        import redis  # noqa: F401
    except ImportError:
        stub = types.ModuleType('redis')
        class Redis:
            @staticmethod
            def from_url(*args, **kwargs):
                raise RuntimeError('Redis client is not installed')
        stub.Redis = Redis
        sys.modules['redis'] = stub
