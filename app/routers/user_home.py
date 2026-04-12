from fastapi import APIRouter, HTTPException, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import status
from app.dependencies.session import SessionDep
from app.dependencies.auth import AuthDep, IsUserLoggedIn, get_current_user, is_admin
from . import router, templates
from app.models.models import *
from sqlmodel import *
from typing import Annotated
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

    if liked_ids:
        newquery = newquery.where(Profile.id.not_in(liked_ids))

    if disliked_ids:
        newquery = newquery.where(Profile.id.not_in(disliked_ids))

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
    existing=db.exec(select(Like).where((Like.liker_id==mine.id) & (Like.liked_id==profileId))).first()

    if existing:
        return RedirectResponse(
            url="/app",
            status_code=status.HTTP_303_SEE_OTHER
        )
    
    newLike=Like(liker_id=mine.id, liked_id=profileId)
    db.add(newLike)
    db.commit()



    ##check if the profile you're liking alr liked you 
    mutual=db.exec(select(Like).where((Like.liker_id==profileId)&( Like.liked_id==mine.id))).first()
    if mutual:

        ##order it to prevent duplicates
        p1=min(mine.id, profileId)
        p2=max(mine.id, profileId)
        ##check if the mutual connection was alr made
        exist=db.exec(select(Match).where((Match.profile1_id==p1)& (Match.profile2_id==p2))).first()

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
            matched_profiles.append({
                "match_id" : m.id,
                "profile" : otherprof
            })

    return templates.TemplateResponse(
        request=request,
        name="matches.html",
        context={
            "user": user,
            "mine" : mine,
            "profiles": matched_profiles
        }
    )




@router.post("/unlike/{profileId}")
def unlike_profile(request: Request, user: AuthDep, db: SessionDep, profileId: int):
    mine=db.exec(select(Profile).where(Profile.user_id==user.id)).one_or_none()
    if not mine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    

    like=db.exec(select(Like).where((Like.liker_id==mine.id) & (Like.liked_id==profileId))).one_or_none()

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
    exist=db.exec(select(Match).where((Match.profile1_id==p1) & (Match.profile2_id==p2))).first()
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



##for daily picks
@router.get("/daily_picks", response_class=HTMLResponse)
def daily_picks(request: Request, user: AuthDep, db:SessionDep):
    mine=db.exec(select(Profile).where(Profile.user_id==user.id)).one_or_none()
    if not mine: 
        raise HTTPException(status_code=404, detail="Profile not found")
    
    today=date.today()

    ##check if daily picks was alr generated for that user today
    existing=db.exec(select(DailyPick).where((DailyPick.profile_id==mine.id)& (DailyPick.date_generated==today))).all()
    if not existing:
        ##get everyone who liked 
        liked_ids=db.exec(select(Like.liked_id).where(Like.liker_id==mine.id)).all()

        ##everyone who disliked
        disliked_ids=db.exec(select(DisLike.disliked_id).where(DisLike.disliker_id==mine.id)).all()

        ##get reported 
        reported_ids=db.exec(select(reportedProfile.profile_id).where(reportedProfile.reported_by==mine.id)).all()

        q=select(Profile).where(Profile.id!=mine.id, Profile.is_blocked==False)

        if liked_ids:
            q=q.where(Profile.id.not_in(liked_ids))

        if disliked_ids:
            q=q.where(Profile.id.not_in(disliked_ids))


        if reported_ids:
            q=q.where(Profile.id.not_in(reported_ids))

        
        if mine.preferred_gender.lower() !="any":
            q=q.where(Profile.gender==mine.preferred_gender)

        candidates=db.exec(q).all()

        ##use a score system to keep track of the top picks
        scored=[]
        for c in candidates: 
            score=0

            ##give boost if the profile is verified
            if c.is_verified:
                score+=5
            
            ##find age diff between the profiles, and if similar in age (2 yrs, 5yrs, 10) then give boost to that profile
            try:
                diff=abs(int(c.age)-int(mine.age))
                if diff<=2:
                    score+=5
                elif diff<=5:
                    score+=3
                elif diff<=10:
                    score+=1
            except:
                pass

            ##see if other profile alr liked you 
            liked_alr=db.exec(select(Like).where((Like.liker_id==c.id)&(Like.liked_id==mine.id))).first()
            if liked_alr:
                score+=10

            scored.append((c, score))
        
        ##sort all scores in desc order (so top picks are first)
        scored.sort(key=lambda x: x[1], reverse=True)

        ##get top 5 picks
        top=scored[:5]

        for prof, score in top:
            dailyPick= DailyPick(profile_id=mine.id, suggested_profile_id=prof.id)
            db.add(dailyPick)
        db.commit()


        #get new daily picked candiddates
        existing=db.exec(select(DailyPick).where((DailyPick.profile_id==mine.id)&(DailyPick.date_generated==today))).all()
    ##to account for if the user alr liked/disliked a profile in the daily top picks
    liked_ids=db.exec(select(Like.liked_id).where(Like.liker_id==mine.id)).all()

    disliked_ids=db.exec(select(DisLike.disliked_id).where(DisLike.disliker_id==mine.id)).all()

    ##get the daily picked candidates' profiles
    suggestedprofiles=[]
    for pick in existing:
        #skip if the user alr liked/disliked the profile
        if pick.suggested_profile_id in liked_ids:
            continue
        if pick.suggested_profile_id in disliked_ids:
            continue


        profile=db.exec(select(Profile).where(Profile.id==pick.suggested_profile_id)).one_or_none()
        if profile:
            suggestedprofiles.append(profile)
    completed=False
    if len(existing)>0 and len(suggestedprofiles)==0:
        completed=True
    return templates.TemplateResponse(
        request=request,
        name="daily_picks.html",
        context={
            "user": user,
            "mine": mine,
            "profiles": suggestedprofiles,
            "completed": completed
        }
    )
        



@router.post("/dislike/{profileId}")
def dislike_profile(request: Request, user: AuthDep, db: SessionDep, profileId: int):
    mine=db.exec(select(Profile).where(Profile.user_id==user.id)).one_or_none()
    if not mine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    
    if mine.id==profileId:
        flash(request, "You cannot dislike your own profile")
        return RedirectResponse(url="/app", status_code=status.HTTP_303_SEE_OTHER)
    
    like=db.exec(select(Profile).where((Profile.id==profileId) )).one_or_none()

    if not like:
        
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    
    ##see if user alr dislikde this profile
    existing=db.exec(select(DisLike).where((DisLike.disliker_id==mine.id)& (DisLike.disliked_id==profileId))).first()
    if existing:
        return RedirectResponse(url="/app", status_code=status.HTTP_303_SEE_OTHER)


    newDislike=DisLike(disliker_id=mine.id, disliked_id=profileId)
    db.add(newDislike)
    db.commit()
    return RedirectResponse(url="/app", status_code=status.HTTP_303_SEE_OTHER)



# @router.get("/profile/{profileId}", response_class=HTMLResponse)
# def profile_info(request: Request, user: AuthDep, db:SessionDep, profileId: int):
#     mine=db.exec(select(Profile).where(Profile.user_id==user.id)).one_or_none()
#     if not mine:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    
#     prof=db.exec(select(Profile).where(Profile.id==profileId)).one_or_none()
#     if not mine:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    
#     ##prevents viewing your own profile
#     if mine.id==profileId:
#         flash(request, "You cannot view your own profile")
#         return RedirectResponse(url="/app", status_code=status.HTTP_303_SEE_OTHER)
    
#     #check if alr liked/disliked/matched
#     alr_liked=db.exec(select(Like).where((Like.liker_id==mine.id)& (Like.liked_id==prof.id))).first()

#     alr_disliked = db.exec(
#         select(DisLike).where((DisLike.disliker_id == mine.id) &(DisLike.disliked_id == prof.id))).first()

   
#     p1 = min(mine.id, prof.id)
#     p2 = max(mine.id, prof.id)

#     matched = db.exec(select(Match).where((Match.profile1_id == p1) & (Match.profile2_id == p2))).first()

#     return templates.TemplateResponse(
#         request=request,
#         name="profile_info.html",
#         context={
#             "user": user,
#             "mine": mine,
#             "profile": prof,
#             "already_liked": alr_liked is not None,
#             "already_disliked": alr_disliked is not None,
#             "matched": matched is not None
#         }
#     )



@router.get("/my_profile", response_class=HTMLResponse)
def my_profile_info(request: Request, user: AuthDep, db:SessionDep):
    mine=db.exec(select(Profile).where(Profile.user_id==user.id)).one_or_none()
    if not mine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return templates.TemplateResponse(
        request=request,
        name="my_profile.html",
        context={
            "user":user,
            "mine": mine
        }
    )


@router.get("/my_profile/edit", response_class=HTMLResponse)
def edit_my_profile_view(request: Request, user: AuthDep, db:SessionDep):
    mine=db.exec(select(Profile).where(Profile.user_id==user.id)).one_or_none()
    if not mine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return templates.TemplateResponse(
        request=request,
        name="edit_profile.html",
        context={
            "user":user,
            "mine": mine
        }
    )


@router.post("/my_profile/edit")
def edit_my_profile_action(request: Request, user: AuthDep, db:SessionDep, username: Annotated[str, Form()], bio: Annotated[str, Form()], age:Annotated[str, Form()], preferred_gender:Annotated[str, Form()]):
    mine=db.exec(select(Profile).where(Profile.user_id==user.id)).one_or_none()
    if not mine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    mine.username=username
    mine.bio=bio
    mine.age=age
    mine.preferred_gender=preferred_gender
    db.add(mine)
    db.commit()
    flash(request, "Profile updated successfully! ")

    return RedirectResponse(
        url="/my_profile", status_code=status.HTTP_303_SEE_OTHER
    )