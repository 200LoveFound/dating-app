from fastapi import Request, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlmodel import select
import json
from app.dependencies.session import SessionDep
from app.dependencies.auth import AuthDep
from app.models.models import Profile, Match, Message
from app.services.websocket_service import websocket_service
from . import router, templates

##rock, paper, scissors store to keep track of each player's move per match
rps_store={}

def determine_rps_winner(move1: str, move2: str):
    if move1==move2:
        return "draw"
    if move1=="rock" and move2=="scissors":
        return "player1"
    if move1=="paper" and move2=="rock":
        return "player1"
    if move1=="scissors" and move2=="paper":
        return "player1"
    return "player2"


@router.get("/chat/{match_id}", response_class=HTMLResponse)
async def chat_page(request: Request, user: AuthDep, db: SessionDep, match_id: int):

    mine = db.exec(select(Profile).where(Profile.user_id == user.id)).one_or_none()

    if not mine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Your profile was not found")

    match = db.get(Match, match_id)

    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    if mine.id not in [match.profile1_id, match.profile2_id]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not allowed to access this chat")

    other_profile_id = match.profile2_id if match.profile1_id == mine.id else match.profile1_id
    other_profile = db.get(Profile, other_profile_id)

    previous_messages = db.exec(
        select(Message).where(Message.match_id == match_id).order_by(Message.sent_at)
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={
            "user": user,
            "mine": mine,
            "match": match,
            "other_profile": other_profile,
            "previous_messages": previous_messages
        }
    )


@router.websocket("/ws/chat/{match_id}/{profile_id}")
async def websocket_chat(websocket: WebSocket, match_id: int, profile_id: int, db: SessionDep):
    match = db.get(Match, match_id)
    if not match:
        await websocket.close(code=1008)
        return

    if profile_id not in [match.profile1_id, match.profile2_id]:
        await websocket.close(code=1008)
        return

    profile = db.get(Profile, profile_id)
    if not profile:
        await websocket.close(code=1008)
        return

    await websocket_service.connect(match_id, websocket)

    try:
        await websocket_service.broadcast_to_match(
            match_id,
            json.dumps({"type": "system", "text": f"{profile.username} joined the chat"})
        )
        

        while True:
            raw_data = await websocket.receive_text()

            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                data = {"type": "message", "text": raw_data}

            msg_type = data.get("type")

            if msg_type == "message":
                clean_message = (data.get("text") or "").strip()
                if not clean_message:
                    continue

                msg = Message(
                match_id=match_id,
                sender_profile_id=profile_id,
                content=clean_message
                )
                db.add(msg)
                db.commit()

                await websocket_service.broadcast_to_match(
                    match_id,
                    json.dumps({
                        "type": "message",
                        "sender_id": profile_id,
                        "sender": profile.username,
                        "text": clean_message
                    })
                )

            ##when one player clicks "Play Rock Paper Scissors", the other player is also invited to play it
            elif msg_type == "rps_invite":

                await websocket_service.broadcast_to_match(
                    match_id,
                    json.dumps({
                        "type": "rps_invite",
                        "sender_id": profile_id,
                        "sender": profile.username,
                        "text": f"{profile.username} wants to play Rock Paper Scissors! Choose your move."
                    })
                )

                   
            ##for rock, paper, scissors move
            elif msg_type=="rps_move":
                move=data.get("move")

                if move not in ["rock", "paper", "scissors"]:
                    continue

                if match_id not in rps_store:
                    rps_store[match_id]={}
                    
                ##save the user's move
                rps_store[match_id][profile_id]=move

                ##to notify the player that a move was submitted:
                await websocket_service.broadcast_to_match(
                    match_id,
                    json.dumps({
                        "type": "rps_status",
                        "text": f"{profile.username} submitted a move!"
                    })
                )

                ##calculate  the winner once both players submit a move
                if match.profile1_id in rps_store[match_id] and match.profile2_id in rps_store[match_id]:
                    p1_move=rps_store[match_id][match.profile1_id]
                    p2_move=rps_store[match_id][match.profile2_id]

                    winner=determine_rps_winner(p1_move, p2_move)
                    if winner=="draw":
                        result_text=f"Draw! Both players chose {p1_move.upper()}"

                    elif winner=="player1":
                        p1=db.get(Profile,match.profile1_id)
                        result_text=f"{p1.username} wins! ({p1_move.upper()} beats {p2_move.upper()})"


                    else:
                        p2=db.get(Profile,match.profile2_id)
                        result_text=f"{p2.username} wins! ({p2_move.upper()} beats {p1_move.upper()})"

                    ##broadcast the result of the match
                    await websocket_service.broadcast_to_match(
                        match_id,
                        json.dumps({
                            "type": "rps_result",
                            "p1_move": p1_move,
                            "p2_move": p2_move,
                            "result": result_text
                        })
                    )

                    ##reset the game
                    rps_store[match_id]={}
           

            elif msg_type == "start_game":
                game = websocket_service.start_game(match_id=match_id, player1_id=match.profile1_id, player2_id=match.profile2_id)

                await websocket_service.broadcast_to_match(
                    match_id,
                    json.dumps({
                        "type": "game_started",
                        "board": game["board"],
                        "turn": game["turn"],
                        "players": game["players"],
                        "winner": game["winner"],
                        "is_draw": game["is_draw"]
                    })
                )

            elif msg_type == "move":
                index = data.get("index")
                if index is None:
                    continue

                result = websocket_service.make_move(match_id=match_id, profile_id=profile_id, index=int(index))

                if "error" in result:
                    await websocket.send_text(json.dumps({
                        "type": "game_error",
                        "text": result["error"]
                    }))
                    continue

                await websocket_service.broadcast_to_match(
                    match_id,
                    json.dumps({
                        "type": "game_update",
                        "board": result["board"],
                        "turn": result["turn"],
                        "winner": result["winner"],
                        "is_draw": result["is_draw"]
                    })
                )


    except WebSocketDisconnect:
        websocket_service.disconnect(match_id, websocket)
        await websocket_service.broadcast_to_match(
            match_id,
            json.dumps({"type": "system", "text": f"{profile.username} left the chat"})
        )