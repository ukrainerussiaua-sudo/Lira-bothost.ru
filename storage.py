"""
SQLite-based FSM storage for aiogram 3.
Keeps states/data across bot restarts — no more disappearing admin panel.
"""
import json
from typing import Any, Dict, Optional
from aiogram.fsm.storage.base import BaseStorage, StorageKey, StateType
from database.db import fsm_get, fsm_set, fsm_delete, fsm_get_keys


def _state_key(key: StorageKey) -> str:
    return f"fsm:state:{key.bot_id}:{key.chat_id}:{key.user_id}"


def _data_key(key: StorageKey) -> str:
    return f"fsm:data:{key.bot_id}:{key.chat_id}:{key.user_id}"


class SQLiteStorage(BaseStorage):
    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        k = _state_key(key)
        if state is None:
            await fsm_delete(k)
        else:
            state_str = state.state if hasattr(state, "state") else str(state)
            await fsm_set(k, state_str)

    async def get_state(self, key: StorageKey) -> Optional[str]:
        return await fsm_get(_state_key(key))

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        k = _data_key(key)
        if not data:
            await fsm_delete(k)
        else:
            await fsm_set(k, json.dumps(data, ensure_ascii=False))

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        raw = await fsm_get(_data_key(key))
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}

    async def close(self) -> None:
        pass
