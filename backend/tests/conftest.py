import pytest

from app.services import redis_client


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.expirations: dict[str, int] = {}

    def ping(self) -> bool:
        return True

    def incr(self, key: str) -> int:
        value = int(self.values.get(key, "0")) + 1
        self.values[key] = str(value)
        return value

    def expire(self, key: str, seconds: int) -> bool:
        self.expirations[key] = seconds
        return True

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def set(
        self,
        key: str,
        value: str,
        nx: bool = False,
        ex: int | None = None,
    ) -> bool:
        if nx and key in self.values:
            return False
        self.values[key] = str(value)
        if ex is not None:
            self.expirations[key] = ex
        return True

    def hset(self, key: str, mapping: dict[str, str]) -> int:
        self.hashes.setdefault(key, {}).update({name: str(value) for name, value in mapping.items()})
        return len(mapping)

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes.get(key, {}))

    def delete(self, key: str) -> int:
        existed = key in self.values or key in self.hashes
        self.values.pop(key, None)
        self.hashes.pop(key, None)
        return int(existed)

    def eval(self, script: str, numkeys: int, key: str, owner: str) -> int:
        if self.values.get(key) == owner:
            return self.delete(key)
        return 0


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    client = FakeRedis()
    monkeypatch.setattr(redis_client, "get_redis_client", lambda: client)
    return client


@pytest.fixture(autouse=True)
def use_fake_redis(fake_redis: FakeRedis) -> None:
    pass
