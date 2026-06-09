from typing import Dict, List

from fastapi import WebSocket


class LocationConnectionManager:
    """
    Manages per-incident WebSocket rooms.
    Each room has one broadcaster (technician) and any number of viewers.
    """

    def __init__(self) -> None:
        # incident_id -> {"technician": WebSocket | None, "viewers": list[WebSocket]}
        self._rooms: Dict[str, dict] = {}

    async def connect_technician(self, ws: WebSocket, incident_id: str) -> None:
        await ws.accept()
        if incident_id not in self._rooms:
            self._rooms[incident_id] = {"technician": None, "viewers": []}
        self._rooms[incident_id]["technician"] = ws

    async def connect_viewer(self, ws: WebSocket, incident_id: str) -> None:
        await ws.accept()
        if incident_id not in self._rooms:
            self._rooms[incident_id] = {"technician": None, "viewers": []}
        self._rooms[incident_id]["viewers"].append(ws)

    def disconnect_technician(self, incident_id: str) -> None:
        if incident_id in self._rooms:
            self._rooms[incident_id]["technician"] = None

    def disconnect_viewer(self, ws: WebSocket, incident_id: str) -> None:
        if incident_id in self._rooms:
            try:
                self._rooms[incident_id]["viewers"].remove(ws)
            except ValueError:
                pass

    async def broadcast_location(self, incident_id: str, payload: dict) -> None:
        if incident_id not in self._rooms:
            return
        dead: List[WebSocket] = []
        for ws in list(self._rooms[incident_id]["viewers"]):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect_viewer(ws, incident_id)


location_manager = LocationConnectionManager()
