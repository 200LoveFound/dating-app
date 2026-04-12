from sqlmodel import *
from typing import Optional
from pydantic import EmailStr
from app.dependencies import session
from app.models.user import UserBase, User
from datetime import datetime, date, timedelta

#two profiles, one for admin and one for a reg user on the dating app

class ProfileBase(SQLModel):
    username: str  
    age: str
    gender: str
    birthday: date
    bio: Optional[str] = None
    preferred_gender: str        #male or female alone, no crazy stuff
    picture1: Optional[str] = None   #to make registration easier for now
    picture2: Optional[str] = None
    picture3: Optional[str] = None
    is_verified: bool = False

class Profile(ProfileBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field( foreign_key="user.id")
    is_blocked: bool = False
    
class adminProfile(ProfileBase, table=True):  
   #inherited role from userBase
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    username: str  


class reportedProfile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id")
    reason: str
    date_reported: datetime = Field(default_factory=datetime.now)
    reported_by: int = Field(foreign_key="profile.id")  #the profile that reported the account

    #once an account is reported, the account will be placed in this table
    #this will be rendered in the admin dashboard for review, and the admin can decide to either ignore it or delete the account

class Like(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    liker_id: int = Field(foreign_key="profile.id")
    liked_id: int = Field(foreign_key="profile.id")
    date_liked: datetime = Field(default_factory=datetime.now)

    #this table will store the likes between profiles, and will be used to determine matches
    #junction table, kinda like a many to many relationship thing

    #function to find how long ago a like was made in hours

    def hours_since_liked(self):
        now = datetime.now()
        delta = now - self.date_liked
        return delta.total_seconds() / 3600
    
    # to use, in the router just call the function like this: like.hours_since_liked() and it will return the number of hours since the like was made

    #function to receive an id and see if there is a match, meaning if the liked_id has also liked the liker_id, then it's a match and we can return true, otherwise false

    def is_match(self, session: Session) -> bool:
        match = session.exec(
        select(Like).where(
            Like.liker_id == self.liked_id,
            Like.liked_id == self.liker_id
        )
    ).first()

        return match is not None
    
    #to use, in the router just call the function like this: like.is_match(session) and it will return true if there is a match, otherwise false

class Match(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    profile1_id: int = Field(foreign_key="profile.id")
    profile2_id: int = Field(foreign_key="profile.id")
    date_matched: datetime = Field(default_factory=datetime.now)



class DisLike(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    disliker_id: int = Field(foreign_key="profile.id")
    disliked_id: int = Field(foreign_key="profile.id")
    




# to generate daily picks for a user based on prefered gender, simialrities in age, and people who alr liked you
class DailyPick(SQLModel, table=True):
    id: Optional[int]=Field(default=None, primary_key=True)
    profile_id: int=Field(foreign_key="profile.id")    #for the user who is going to receieve the daily picks
    suggested_profile_id: int=Field(foreign_key="profile.id")   #who the daily picks could include
    date_generated: date=Field(default_factory=date.today)   