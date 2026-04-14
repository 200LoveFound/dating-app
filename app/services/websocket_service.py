# create the websocket service 
# based on the match id when 2 users match

from fastapi import WebSocket


class WebSocketService:
    def __init__(self):
        # match_id which signifies the list of sockets in that chat room (the 2 accounts that matched)
        self.active_connections: dict[int, list[WebSocket]] = {}
        #using match_id for 2 accounts to play tic tac toe game on chat
        self.games: dict[int, dict] = {}

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

    
    #logic to return the number of active chats to the admin dashboard
    def get_active_chat_count(self) -> int:
        return len(self.active_connections)

    
    #logic for the game-tic tac toe
    def start_game(self, match_id: int, player1_id: int, player2_id: int):
        #game info
        self.games[match_id] = {
            "board": ["", "", "", "", "", "", "", "", ""],
            "players": [player1_id, player2_id],
            "turn": player1_id,
            "winner": None,
            "is_draw": False,
        }
        return self.games[match_id]

    def get_game(self, match_id: int):
        return self.games.get(match_id)

    def check_winner(self, board: list[str]):
        win_lines = [
            (0, 1, 2), (3, 4, 5), (6, 7, 8),
            (0, 3, 6), (1, 4, 7), (2, 5, 8),
            (0, 4, 8), (2, 4, 6),
        ]

        for a, b, c in win_lines:
            if board[a] and board[a] == board[b] == board[c]:
                return board[a]

        return None

    #to allow users to play the game while on the chat
    def make_move(self, match_id: int, profile_id: int, index: int):
        game = self.games.get(match_id)
        if not game:
            return {"error": "No active game"}

        if game["winner"] or game["is_draw"]:
            return {"error": "Game already finished"}

        if index < 0 or index > 8:
            return {"error": "Invalid cell"}

        if game["turn"] != profile_id:
            return {"error": "Not your turn"}

        if game["board"][index] != "":
            return {"error": "Cell already taken"}

        symbol = "X" if profile_id == game["players"][0] else "O"
        game["board"][index] = symbol

        winner = self.check_winner(game["board"])
        if winner:
            game["winner"] = winner
        elif all(cell != "" for cell in game["board"]):
            game["is_draw"] = True
        else:
            game["turn"] = (
                game["players"][1]
                if profile_id == game["players"][0]
                else game["players"][0]
            )

        return game

websocket_service = WebSocketService()