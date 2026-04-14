from sqlmodel import *
from app.database import create_db_and_tables, get_cli_session, drop_all
from app.models.user import *
from app.models.models import *
from app.utilities.security import encrypt_password
import csv

def seed_database():
    with get_cli_session() as db:

        existing_admin = db.exec(
            select(User).where(User.username == "admin")
        ).first()

        if not existing_admin:
            admin = User(
                username="admin",
                email="admin@mail.com",
                password=encrypt_password("adminpass"),
                role="admin"
            )

            db.add(admin)
            db.commit()
            db.refresh(admin)

            admin_profile = adminProfile(
                user_id=admin.id,
                username=admin.username,
                age="35",
                gender="female",
                birthday=datetime.strptime("1986-01-13", "%Y-%m-%d").date(),
                bio="System administrator",
                preferred_gender="any",
                picture1=None,
                picture2=None,
                picture3=None,
                is_verified=True
            )

            db.add(admin_profile)
            db.commit()

            print("Admin seeded")

        import_csv_profiles(db)

def import_csv_profiles(db):
     
        try:
            with open ("sample_profiles.csv", newline="", encoding ="utf-8") as f:
                reader=csv.DictReader(f)
                counter = 0
                for row in reader:
                    try:
                        username = (row.get("username") or "").strip()
                        email = (row.get("email") or "").strip()
                        passwordstr = (row.get("password") or "").strip()
                        password = encrypt_password(passwordstr)
                        role = (row.get("role") or "regularuser").strip()
                        ageval = (row.get("age") or "").strip()
                        genderval = (row.get("gender") or "").strip()
                        birthdayval = (row.get("birthday") or "").strip()
                        bioval = (row.get("bio") or "").strip() or None
                        preferred = (row.get("preferred_gender") or "any").strip() 
                        picture1val = (row.get("picture1") or "").strip() or None
                        picture2val = (row.get("picture2") or "").strip() or None
                        picture3val = (row.get("picture3") or "").strip() or None
                        isverifiedstring = (row.get("is_verified") or "false").strip().lower()
                        isverifiedval = isverifiedstring in ["true", "1", "yes" ] 

                        #to prevent duplicate user
                        existing = db.exec(select(User).where((User.username == username) | (User.email==email))).first()
                        if existing:
                            print (f"Skipping duplicate user: {username}")
                            continue
                        #create new user
                        user = User(
                            username=username, 
                            email=email,
                            password=password,
                            role=role
                        )
                        db.add(user)
                        db.commit()
                        db.refresh(user)
                        #create profile for new user
                        profile = Profile (
                            user_id = user.id,
                            username = username,
                            age=ageval,
                            gender=genderval,
                            birthday=datetime.strptime(birthdayval, "%Y-%m-%d").date(),
                            bio=bioval,
                            preferred_gender=preferred,
                            picture1 = picture1val,
                            picture2 = picture2val,
                            picture3=picture3val,
                            is_verified=isverifiedval
                        )
                        db.add(profile)
                        db.commit()
                        counter += 1
                    except Exception as e:
                        db.rollback()
                        print(f"Skipping row for {row.get('username', 'unknown')} due to error {e}.")
                print (f"Profile import done: {counter} rows added.\n")

        except FileNotFoundError:
            print ("sample_profiles.csv File not found.\n")