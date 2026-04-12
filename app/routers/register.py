from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Request, status, Form, HTTPException
from app.dependencies import SessionDep
from app.schemas.auth import SignupRequest
from app.models.models import *
from app.services.auth_service import AuthService
from app.repositories.user import UserRepository
from app.utilities.flash import flash
from . import router, templates
from datetime import date
from sqlalchemy import func

# View route (loads the page)
@router.get("/register", response_class=HTMLResponse)
async def register_view(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={
            "today": date.today().isoformat()
        }
    )

# Action route (performs an action)
@router.post('/register', response_class=HTMLResponse, status_code=status.HTTP_201_CREATED)
def signup_user(request:Request, db:SessionDep, 
    username: str = Form(),
    email: str = Form(),
    password: str = Form(),
    age:str= Form(),
    birthday: date = Form(),
    gender: str = Form(),
    preference: str = Form(),

):
    
    calculated_age = (date.today() - birthday).days //365
    if calculated_age != int(age):
     return RedirectResponse(url="/register?error=Your age and birthday don't match", status_code=status.HTTP_303_SEE_OTHER)
     
    if calculated_age < 18 or calculated_age > 100:
      return RedirectResponse(url="/register?error=You need to be 18 years or older to access this application",status_code=status.HTTP_303_SEE_OTHER )
       
    existing_username = db.exec(select(Profile).where(func.lower(Profile.username) == username.strip().lower())).first()
    if existing_username:
      return RedirectResponse(url="/register?error=Username already taken", status_code=status.HTTP_303_SEE_OTHER)

    existing_email = db.exec(select(User).where(func.lower(User.email) == email.strip().lower())).first()
    if existing_email:
      return RedirectResponse(url="/register?error=Email already in use", status_code=status.HTTP_303_SEE_OTHER)


    user_repo = UserRepository(db)
    auth_service = AuthService(user_repo)
    try:
        user = auth_service.register_user(username, email, password)
        newProfile = Profile (
            user_id=user.id,
            username=username,
            age=age,
            birthday=birthday,
            gender=gender,
            preferred_gender=preference,
        )
        db.add(newProfile)
        db.commit()

        flash(request, "Registration completed! Sign in now!")
        return RedirectResponse(url=request.url_for("login_view"), status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        flash(request, "Username or email already exists", "danger")
        return RedirectResponse(url=request.url_for("register_view"), status_code=status.HTTP_303_SEE_OTHER)
