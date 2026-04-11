from fastapi import APIRouter, HTTPException, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import status
from app.dependencies.session import SessionDep
from app.dependencies.auth import AdminDep, IsUserLoggedIn, get_current_user, is_admin
from . import router, templates
from sqlmodel import *
from app.models.models import *
from app.utilities.flash import *


@router.get("/admin", response_class=HTMLResponse)
async def admin_home_view(
    request: Request,
    user: AdminDep,
    db:SessionDep
):
    #get all reports sent to admin
    reports = db.exec(select(reportedProfile)).all()
    reportedrows = []
    #get information for each report in all reports
    for r in reports:
        reportedprofile = db.get(Profile, r.profile_id)
        reporterprofile = db.get(Profile, r.reported_by)
        reportedrows.append({
            "id":r.id,
            "reason":r.reason,
            "date_reported":r.date_reported,
            "reported_profile":reportedprofile,
            "reporter_profile":reporterprofile
        })
    return templates.TemplateResponse(
        request=request, 
        name="admin.html",
        context={
            "user": user,
            "reports":reportedrows
        }
    )

#to ignore a reported account
@router.post("/admin/ignore/{report_id}")
async def ignore_report(
    request: Request,
    user: AdminDep,
    db:SessionDep,
    report_id: int
):
    report = db.get(reportedProfile, report_id)
    if not report:
        raise HTTPException(
            detail="Report to ignore is not found",
            status_code=404
        )
    db.delete(report)
    db.commit()
    flash(request, "Report has been ignored and deleted")
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

#to set a profile to blocked
@router.post("/admin/block/{report_id}")
async def block_reportedprofile(
    user: AdminDep,
    request: Request,
    db:SessionDep,
    report_id: int
):
    report = db.get(reportedProfile, report_id)
    if not report:
        raise HTTPException(detail="Report to block is not found", status_code=404)
    
    reportedprofile = db.get(Profile, report.profile_id)
    if not reportedprofile:
        raise HTTPException(detail="Reported Profile to block is not found", status_code=404)
    # reporteduser = db.get(Profile, reportedprofile.user_id)
    # if not reporteduser:
    #     raise HTTPException(detail="Report user to block is not found", status_code=404)
    reportedprofile.is_blocked = True
    db.add(reportedprofile)
    db.commit()
    flash(request, "User has been blocked")
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


