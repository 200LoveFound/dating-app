from fastapi import Request, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlmodel import select

from app.dependencies.session import SessionDep
from app.dependencies.auth import AuthDep
from app.models.models import Profile, Match
from app.services.websocket_service import websocket_service
from . import router, templates


@router.get("/chat/{match_id}", response_class=HTMLResponse)
async def chat_page(request: Request, user: AuthDep, db: SessionDep, match_id: int):
    #get user's profile 
    mine = db.exec(select(Profile).where(Profile.user_id == user.id)).one_or_none()
    if not mine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Your profile was not found"
        )

    #get match using a matchid
    match = db.get(Match, match_id)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found"
        )

    #allow only matched users to access this chat/websocket
    if mine.id not in [match.profile1_id, match.profile2_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to access this chat"
        )

    other_profile_id = match.profile2_id if match.profile1_id == mine.id else match.profile1_id
    other_profile = db.get(Profile, other_profile_id)

    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={
            "user": user,
            "mine": mine,
            "match": match,
            "other_profile": other_profile
        }
    )


@router.websocket("/ws/chat/{match_id}/{profile_id}")
async def websocket_chat(websocket: WebSocket, match_id: int, profile_id: int, db: SessionDep):
    match = db.get(Match, match_id)
    if not match:
        await websocket.close(code=1008)
        return

    #to make sure the profile being connected is part of this match
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
            f"System: {profile.username} joined the chat"
        )

        while True:
            data = await websocket.receive_text()
            clean_message = data.strip()
            if not clean_message:
                continue

            await websocket_service.broadcast_to_match(
                match_id,
                f"{profile.username}: {clean_message}"
            )

    except WebSocketDisconnect:
        websocket_service.disconnect(match_id, websocket)
        await websocket_service.broadcast_to_match(
            match_id,
            f"System: {profile.username} left the chat"
        )