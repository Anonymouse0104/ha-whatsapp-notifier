"""Client for the WhatsApp bridge add-on: REST for sending, WebSocket for status + incoming."""
from __future__ import annotations

import asyncio
import logging

from aiohttp import ClientError, ClientSession, ClientTimeout, WSMsgType
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .chat_id import normalize
from .const import DOMAIN, EVENT_MESSAGE, SIGNAL_STATUS

_LOGGER = logging.getLogger(__name__)


class Bridge:
    def __init__(self, hass: HomeAssistant, session: ClientSession, host: str, port: int, token: str) -> None:
        self.hass = hass
        self.session = session
        self.base = f"http://{host}:{port}"
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.status = "bridge_unreachable"
        self.attrs: dict = {}
        self.default_chat = lambda: ""
        self.forward_chats = lambda: []
        self._task: asyncio.Task | None = None

    def _set(self, status: str, attrs: dict | None = None) -> None:
        self.status, self.attrs = status, attrs or {}
        async_dispatcher_send(self.hass, SIGNAL_STATUS)

    async def send(self, chat_id: str, message: str) -> str:
        try:
            body = {"chat_id": normalize(chat_id), "message": message}
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        try:
            async with self.session.post(self.base + "/send", json=body, headers=self.headers, timeout=ClientTimeout(total=20)) as r:
                data = await r.json()
                if r.status >= 400:
                    raise HomeAssistantError(f"WhatsApp send failed: {data.get('error', r.status)}")
                return data["id"]
        except (ClientError, asyncio.TimeoutError) as err:
            raise HomeAssistantError(f"WhatsApp bridge unreachable: {err}") from err

    def start(self) -> None:
        self._task = self.hass.async_create_background_task(self._listen(), f"{DOMAIN}_ws")

    def stop(self) -> None:
        if self._task:
            self._task.cancel()

    async def _listen(self) -> None:
        while True:
            try:
                async with self.session.ws_connect(self.base + "/ws", headers=self.headers, heartbeat=30) as ws:
                    # the bridge forgets nothing, but HA is the source of truth for this list
                    async with self.session.post(
                        self.base + "/forward", json={"chats": self.forward_chats()},
                        headers=self.headers, timeout=ClientTimeout(total=10),
                    ):
                        pass
                    async for msg in ws:
                        if msg.type != WSMsgType.TEXT:
                            continue
                        data = msg.json()
                        if data.pop("type", None) == "status":
                            self._set(data.pop("status"), data)
                        else:
                            self.hass.bus.async_fire(EVENT_MESSAGE, data)
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 - any failure means: retry and show unreachable
                _LOGGER.debug("bridge websocket error: %s", err)
            self._set("bridge_unreachable")
            await asyncio.sleep(10)
