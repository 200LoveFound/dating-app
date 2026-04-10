from fastapi import APIRouter, HTTPException, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import status
from app.dependencies.session import SessionDep
from app.dependencies.auth import AuthDep, IsUserLoggedIn, get_current_user, is_admin
from . import router, templates
from app.models.models import *
from sqlmodel import *
from typing import *
from app.utilities.flash import *


@router.get("/app", response_class=HTMLResponse)
async def user_home_view(
    request: Request,
    user: AuthDep,
    db:SessionDep
):
    #get user profile
    current_profile = db.exec(select(Profile).where(Profile.user_id == user.id)).first()
    if not current_profile:
        raise HTTPException (
            detail="Your profile was not found",
            status_code = 404
        )

    # get ids of profiles already liked
    liked_ids = db.exec(
        select(Like.liked_id).where(Like.liker_id == current_profile.id)
    ).all()
    
    # get ids of profiles already disliked
    disliked_ids = db.exec(
        select(DisLike.disliked_id).where(DisLike.disliker_id == current_profile.id)
    ).all()

   

    #get the list of ids for the profiles that this user has reported
    reportedids = db.exec(select(reportedProfile.profile_id).where(reportedProfile.reported_by==current_profile.id)).all()
    
    newquery = select(Profile).where(Profile.id!=current_profile.id, Profile.is_blocked==False)
    if reportedids:
        newquery=newquery.where(Profile.id.not_in(reportedids))
    if current_profile.preferred_gender.lower() != "any":
        newquery = newquery.where(Profile.gender==current_profile.preferred_gender)
    profiles = db.exec(newquery).all() 

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



    ##check if the profile you're liking alr liked you 
    mutual=db.exec(select(Like).where(Like.liker_id==profileId, Like.liked_id==mine.id)).first()
    if mutual:

        ##order it to prevent duplicates
        p1=min(mine.id, profileId)
        p2=max(mine.id, profileId)
        ##check if the mutual connection was alr made
        exist=db.exec(select(Match).where(Match.profile1_id==p1, Match.profile2_id==p2)).first()

        if not exist:
            match=Match(profile1_id=p1, profile2_id=p2)
            db.add(match)
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
            "mine" :mine,
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
            "mine" :mine,
            "profiles": liked_by
        }

    )
    

@router.get("/matches", response_class=HTMLResponse)
def see_matches(request: Request, user:AuthDep, db:SessionDep):
    mine=db.exec(select(Profile).where(Profile.user_id==user.id)).one_or_none()
    if not mine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found, cannot find see who liked your profile")
    matches=db.exec(select(Match).where((Match.profile1_id==mine.id)|(Match.profile2_id==mine.id))).all()

    matched_profiles=[]
    for m in matches:
        if m.profile1_id==mine.id:
            other_id=m.profile2_id
        else:
            other_id=m.profile1_id
        otherprof=db.exec(select(Profile).where(Profile.id==other_id)).one_or_none()
        if otherprof:
            matched_profiles.append(otherprof)

    return templates.TemplateResponse(
        request=request,
        name="matches.html",
        context={
            "user": user,
            "profiles": matched_profiles
        }
    )




@router.post("/unlike/{profileId}")
def unlike_profile(request: Request, user: AuthDep, db: SessionDep, profileId: int):
    mine=db.exec(select(Profile).where(Profile.user_id==user.id)).one_or_none()
    if not mine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    

    like=db.exec(select(Like).where(Like.liker_id==mine.id, Like.liked_id==profileId)).one_or_none()

    if not like:
        return RedirectResponse(
        url="/app",
        status_code=status.HTTP_303_SEE_OTHER
    )

    db.delete(like)
    db.commit()

    ## delete a match if a match was created prev with the person you want to unlike
    p1=min(mine.id, profileId)
    p2=max(mine.id, profileId)
    exist=db.exec(select(Match).where(Match.profile1_id==p1, Match.profile2_id==p2)).first()
    if exist:
        db.delete(exist)
        db.commit()

    return RedirectResponse(url="/liked", status_code=status.HTTP_303_SEE_OTHER)



#Route for user to make a report against another profile
@router.get("/report/{profile_id}", response_class=HTMLResponse)
async def report_from_view (request: Request, user: AuthDep, db:SessionDep, profile_id: int):
    profiletoreport = db.exec(select(Profile).where(Profile.id==profile_id)).one_or_none()
    if not profiletoreport:
        raise HTTPException(
            detail="Profile not found",
            status_code=404
        )
    #get the profile making the report
    currentprofile = db.exec(select(Profile).where(Profile.user_id==user.id)).first()
    if not currentprofile:
        raise HTTPException(
            detail = "Your profile was not found",
            status_code=404
        )
    #prevent a currentprofile from reporting themselves
    if currentprofile.id == profiletoreport.id:
        flash(request, "You cannot report your own profile")
        return RedirectResponse(url="/app", status_code=status.HTTP_303_SEE_OTHER)
        # raise HTTPException(
        #     detail="You cannot report your own profile",
        #     status_code = 400
        # )
    return templates.TemplateResponse(
        request=request,
        name="report.html",
        context={
            "user":user,
            "profiletoreport":profiletoreport
        }
    )

@router.post("/report/{profile_id}")
async def submit_report(request: Request, user: AuthDep, db: SessionDep, profile_id: int, reason: Annotated[str, Form()]):
    
    profiletoreport = db.get(Profile, profile_id)
    if not profiletoreport:
        raise HTTPException(
            detail="Profile not found",
            status_code=404
        )
    currentprofile = db.exec(select(Profile).where(Profile.user_id==user.id)).first()
    if not currentprofile:
        raise HTTPException(
            detail = "Your profile was not found",
            status_code=404
        )
    #prevent a currentprofile from reporting themselves
    if currentprofile.id == profiletoreport.id:
        flash(request, "You cannot report your own profile")
        return RedirectResponse(url="/app", status_code = status.HTTP_303_SEE_OTHER)
    
    existingreport = db.exec(select(reportedProfile).where(reportedProfile.profile_id==profiletoreport.id, reportedProfile.reported_by==currentprofile.id)).first()
    if existingreport:
        flash(request, "You have already reported this profile")
        return RedirectResponse(url="/app", status_code=status.HTTP_303_SEE_OTHER)
    
                    
    newreport = reportedProfile(
        profile_id = profiletoreport.id,
        reason=reason,
        reported_by = currentprofile.id
    )
    db.add(newreport)
    db.commit()
    return RedirectResponse(url="/app", status_code=status.HTTP_303_SEE_OTHER)
