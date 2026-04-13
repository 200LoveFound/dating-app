from fastapi import Request, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlmodel import select
import json
from app.dependencies.session import SessionDep
from app.dependencies.auth import AuthDep
from app.models.models import Profile, Match, Message
from app.services.websocket_service import websocket_service
from . import router, templates


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
            data = await websocket.receive_text()
            clean_message = data.strip()
            if not clean_message:
                continue

            # Save to DB
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

    except WebSocketDisconnect:
        websocket_service.disconnect(match_id, websocket)
        await websocket_service.broadcast_to_match(
            match_id,
            json.dumps({"type": "system", "text": f"{profile.username} left the chat"})
        )