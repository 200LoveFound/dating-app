import uvicorn
from fastapi import FastAPI, Request, status
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from app.routers import templates, static_files, router, api_router
from app.config import get_settings
from contextlib import asynccontextmanager
import os


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.database import create_db_and_tables
    from app.models.models import Like, Match, DisLike, Profile, reportedProfile, adminProfile, Message, DailyPick
    from app.models.user import User
    from app.seed import seed_database
    create_db_and_tables()
    seed_database()
    yield



app = FastAPI(middleware=[
    Middleware(SessionMiddleware, secret_key=get_settings().secret_key)
],
    lifespan=lifespan
)   

app.include_router(router)
app.include_router(api_router)

os.makedirs("app/static/uploads", exist_ok=True)
app.mount("/static", static_files, name="static")


@app.exception_handler(status.HTTP_401_UNAUTHORIZED)
async def unauthorized_redirect_handler(request: Request, exc: Exception):
    return templates.TemplateResponse(
        request=request, 
        name="401.html",
    )

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=get_settings().app_host, port=get_settings().app_port, reload=get_settings().env.lower()!="production")