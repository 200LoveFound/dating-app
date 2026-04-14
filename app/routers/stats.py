from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlmodel import select, func

from app.dependencies.session import SessionDep
from app.dependencies.auth import AdminDep
from app.models.models import Profile, Like, Match, reportedProfile
from . import templates
from app.services.websocket_service import websocket_service

stats_router = APIRouter()

#to return a list of information about accounts that would be meaninful to admin such as
# hottest acc - profile acc with the most received likes
# acc that received the most reports 
# the number of accs that were blocked
# total like count for accounts
# total macth count for accounts

@stats_router.get("/admin/stats", response_class=HTMLResponse)
async def admin_stats_page(request: Request, db:SessionDep, user: AdminDep):
    # total likes
    totallikes = len(db.exec(select(Like)).all())
    #total mataches made
    matches = db.exec(select(Match)).all()
    totalmatches=len(matches)
    #total reports made
    totalreports = len (db.exec(select(reportedProfile)).all())
    blocked = db.exec(select(Profile).where(Profile.is_blocked==True)).all()
    totalblocked = len(blocked)

    #profile with the most likes ("hottest account")
    query = db.exec(select(Profile, func.count(Like.id).label("like_count")).join(Like, Like.liked_id == Profile.id).group_by(Profile.id).order_by(func.count(Like.id).desc())).first()
    hottestaccount = None
    hottestlikecount = 0
    if query:
        hottestaccount = query[0]
        hottestlikecount= query[1]
    
    #profile with the most reports (most reported account)
    rquery = db.exec(select(Profile, func.count(reportedProfile.id).label("report_count")).join(reportedProfile, reportedProfile.profile_id==Profile.id).group_by(Profile.id).order_by(func.count(reportedProfile.id).desc())).first()
    mostreported = None
    mostreportedcount = 0
    if rquery:
        mostreported = rquery[0]
        mostreportedcount = rquery[1]
    
    #to get active number of chats
    active_chats = websocket_service.get_active_chat_count()

    return templates.TemplateResponse(
        request=request,
        name="stats.html",
        context={
            "user":user,
            "totallikes":totallikes,
            "totalmatches":totalmatches,
            "totalreports":totalreports,
            "totalblocked":totalblocked,
            "hottestaccount":hottestaccount,
            "hottestlikecount":hottestlikecount,
            "mostreported":mostreported,
            "mostreportedcount":mostreportedcount,
            "active_chats": active_chats,
        }
    )


@stats_router.get("/admin/report-stats")
async def report_stats_data(user: AdminDep, db: SessionDep):
    reports = db.exec(select(reportedProfile)).all()
    profilereporters = {}

    for r in reports:
        if r.profile_id not in profilereporters:
            profilereporters[r.profile_id] = set()
        profilereporters[r.profile_id].add(r.reported_by)

    result = {}
    for profile_id, reporter_ids in profilereporters.items():
        profile = db.get(Profile, profile_id)
        if profile:
            result[profile.username] = len(reporter_ids)

    return result


@stats_router.get("/admin/like-stats")
async def like_stats_data(user: AdminDep, db: SessionDep):
    likes = db.exec(select(Like)).all()

    profilelikes = {}
    for l in likes:
        profilelikes[l.liked_id] = profilelikes.get(l.liked_id, 0) + 1

    result = {}
    for profile_id, like_count in profilelikes.items():
        profile = db.get(Profile, profile_id)
        if profile:
            result[profile.username] = like_count

    return result