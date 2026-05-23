from redis.exceptions import RedisError

from app.services import redis_client

RELEASE_LOCK_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


def acquire_lock(
    key: str,
    owner: str,
    ttl_seconds: int = 300,
) -> bool:
    try:
        return bool(redis_client.get_redis_client().set(key, owner, nx=True, ex=ttl_seconds))
    except RedisError:
        return False


def release_lock(
    key: str,
    owner: str,
) -> None:
    try:
        redis_client.get_redis_client().eval(RELEASE_LOCK_SCRIPT, 1, key, owner)
    except RedisError:
        return
