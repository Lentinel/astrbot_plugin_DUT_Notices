from collections.abc import Awaitable, Callable

from sources import SOURCES

GetKV = Callable[[str, object], Awaitable[object]]
PutKV = Callable[[str, object], Awaitable[None]]


class SubscriptionStore:
    def __init__(self, get_kv_data: GetKV, put_kv_data: PutKV):
        self._get_kv_data = get_kv_data
        self._put_kv_data = put_kv_data

    async def get_global_sessions(self) -> list[str]:
        sessions = await self._get_kv_data("subscribed_sessions", [])
        if not isinstance(sessions, list):
            return []
        return [str(session) for session in sessions]

    async def save_global_sessions(self, sessions: list[str]):
        await self._put_kv_data("subscribed_sessions", sessions)

    async def get_source_subscriptions(self) -> dict[str, list[str]]:
        raw_data = await self._get_kv_data("source_subscriptions", {})
        if not isinstance(raw_data, dict):
            return {}

        cleaned: dict[str, list[str]] = {}
        valid_keys = {source["key"] for source in SOURCES}
        for session, keys in raw_data.items():
            if not isinstance(keys, list):
                continue
            normalized = [str(key) for key in keys if str(key) in valid_keys]
            if normalized:
                cleaned[str(session)] = sorted(set(normalized))
        return cleaned

    async def save_source_subscriptions(self, subscriptions: dict[str, list[str]]):
        await self._put_kv_data("source_subscriptions", subscriptions)
