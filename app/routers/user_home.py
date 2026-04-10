from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import status
from app.dependencies.session import SessionDep
from app.dependencies.auth import AuthDep, IsUserLoggedIn, get_current_user, is_admin
from . import router, templates
from app.models.models import *
from sqlmodel import *


@router.get("/app", response_class=HTMLResponse)
async def user_home_view(
    request: Request,
    user: AuthDep,
    db:SessionDep
):
    
    current_profile = db.exec(select(Profile).where(Profile.user_id == user.id)).first()
    profiles = db.exec(select(Profile).where(Profile.gender == current_profile.preferred_gender)).all()


    return templates.TemplateResponse(
        request=request, 
        name="app.html",
        context={
            "user": user,
            "current_profile" : current_profile,
            "profiles":profiles
        }
    )




@router.post("/like/{profileId}")
def like_profile(request: Request, user: AuthDep, db:SessionDep, profileId: int):
    ##find the profile of the user that wants to like someone else's profile
    mine=db.exec(select(Profile).where(Profile.user_id==user.id)).one_or_none()
    if not mine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found, cannot like someone else's profile")
    
    ##stop yourself from liking you own profile
    if mine.id==profileId:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot like your own profile")
    

    ##make sure a profile exists for the profileId you wanna like
    prof=db.exec(select(Profile).where(Profile.id==profileId)).one_or_none()
    if not prof:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Profile you are trying to like does not exist"
        )
    

    

    ##check if this user alr liked that profile
    existing=db.exec(select(Like).where(Like.liker_id==mine.id, Like.liked_id==profileId)).first()

    if existing:
        return RedirectResponse(
            url="/app",
            status_code=status.HTTP_303_SEE_OTHER
        )
    
    newLike=Like(liker_id=mine.id, liked_id=profileId)
    db.add(newLike)
    db.commit()
    return RedirectResponse(
        url="/app",
        status_code=status.HTTP_303_SEE_OTHER
    )



@router.get("/liked", response_class=HTMLResponse)
def liked_profiles(request: Request, user: AuthDep, db:SessionDep):
    mine=db.exec(select(Profile).where(Profile.user_id==user.id)).one_or_none()
    if not mine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found, cannot find liked profiles")
    
    liked=db.exec(select(Profile).join(Like, Like.liked_id==Profile.id).where(Like.liker_id==mine.id)).all()

    return templates.TemplateResponse(
        request= request,
        name="liked.html",
        context={
            "user": user,
            "profiles": liked
        }

    )
    


@router.get("/liked_by", response_class=HTMLResponse)
def liked_by_profiles(request: Request, user: AuthDep, db:SessionDep):
    mine=db.exec(select(Profile).where(Profile.user_id==user.id)).one_or_none()
    if not mine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found, cannot find see who liked your profile")
    
    liked_by=db.exec(select(Profile).join(Like, Like.liker_id==Profile.id).where(Like.liked_id==mine.id)).all()

    return templates.TemplateResponse(
        request= request,
        name="liked_by.html",
        context={
            "user": user,
            "profiles": liked_by
        }

    )
    

