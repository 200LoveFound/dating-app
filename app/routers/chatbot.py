from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv
from pydantic import BaseModel
from fastapi import HTTPException
from sqlmodel import select
import asyncio
from functools import partial
import os
from app.models.models import Profile, Match, Message
from app.dependencies import AuthDep, SessionDep
from . import api_router 
from app.config import get_settings

settings = get_settings()

llm = ChatOpenAI(
    api_key=settings.api_key,
    base_url=settings.base_url,
    model=settings.model,
    
)

class AISuggestRequest(BaseModel):
    match_id: int

def get_suggestion(sender: dict, receiver: dict, history: str) -> str:
    messages = [
        SystemMessage(content=f"""You are a friendly dating app assistant.
Your job is to help {sender['name']} keep the conversation going with {receiver['name']}.
Use {sender['name']}'s own interests and {receiver['name']}'s bio to suggest something 
{sender['name']} could say or ask. Keep it short, natural, and conversational.
Only give one suggestion.

{sender['name']}'s bio: {sender['bio']}
{receiver['name']}'s bio: {receiver['bio']}
"""),
        HumanMessage(content=f"""Here is the current conversation:
{history}

What should {sender['name']} say or ask {receiver['name']} next?""")
    ]
    response = llm.invoke(messages)
    return response.content


@api_router.post("/ai-suggest")  
async def ai_suggest(request: AISuggestRequest, user: AuthDep, db: SessionDep):
    mine = db.exec(select(Profile).where(Profile.user_id == user.id)).one_or_none()
    if not mine:
        raise HTTPException(status_code=404, detail="Profile not found")

    match = db.get(Match, request.match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    other_id = match.profile2_id if match.profile1_id == mine.id else match.profile1_id
    other = db.get(Profile, other_id)
    if not other:
        raise HTTPException(status_code=404, detail="Other profile not found")

    recent_messages = db.exec(
        select(Message)
        .where(Message.match_id == request.match_id)
        .order_by(Message.sent_at.desc())
        .limit(10)
    ).all()
    recent_messages.reverse()

    if not recent_messages:
        history = "The conversation just started, there are no messages yet."
    else:
        lines = []
        for msg in recent_messages:
            sender_name = mine.username if msg.sender_profile_id == mine.id else other.username
            lines.append(f"{sender_name}: {msg.content}")
        history = "\n".join(lines)

    sender   = {"name": mine.username,  "bio": mine.bio  or "No bio provided"}
    receiver = {"name": other.username, "bio": other.bio or "No bio provided"}

    # Run blocking LLM call in a thread so it doesn't block the event loop
    suggestion = await asyncio.get_event_loop().run_in_executor(
        None, partial(get_suggestion, sender, receiver, history)
    )

    return {"suggestions": [suggestion]}