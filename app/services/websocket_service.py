# create the websocket service 
# based on the match id when 2 users match

from fastapi import WebSocket


class WebSocketService:
    def __init__(self):
        # match_id which signifies the list of sockets in that chat room (the 2 accounts that matched)
        self.active_connections: dict[int, list[WebSocket]] = {}

    #connect
    async def connect(self, match_id: int, websocket: WebSocket):
        await websocket.accept()
        if match_id not in self.active_connections:
            self.active_connections[match_id] = []
        self.active_connections[match_id].append(websocket)

    #disconnect
    def disconnect(self, match_id: int, websocket: WebSocket):
        if match_id in self.active_connections:
            if websocket in self.active_connections[match_id]:
                self.active_connections[match_id].remove(websocket)

            if len(self.active_connections[match_id]) == 0:
                del self.active_connections[match_id]

    #send message
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    
    async def broadcast_to_match(self, match_id: int, message: str):
        if match_id not in self.active_connections:
            return

        dead_connections = []
        for connection in self.active_connections[match_id]:
            try:
                await connection.send_text(message)
            except Exception:
                dead_connections.append(connection)

        for connection in dead_connections:
            self.disconnect(match_id, connection)


websocket_service = WebSocketService()