import os
from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import JSONResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from passlib.context import CryptContext

from app.database import users_collection

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-in-production")
SESSION_COOKIE = "palette_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days

serializer = URLSafeTimedSerializer(SECRET_KEY, salt="palette-auth")


def hash_password(password: str) -> str:
    password = password.encode("utf-8")[:72].decode("utf-8", "ignore")
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    plain = plain.encode("utf-8")[:72].decode("utf-8", "ignore")
    return pwd_context.verify(plain, hashed)


def create_session_token(user_id: str) -> str:
    return serializer.dumps({"user_id": user_id})


def decode_session_token(token: str) -> Optional[str]:
    try:
        data = serializer.loads(token, max_age=COOKIE_MAX_AGE)
        return data.get("user_id")
    except (BadSignature, SignatureExpired):
        return None


def get_current_user(request: Request):
    if users_collection is None:
        return None

    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None

    user_id = decode_session_token(token)
    if not user_id:
        return None

    try:
        return users_collection.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None


@router.get("/me")
def me(request: Request):
    user = get_current_user(request)
    if not user:
        return {"authenticated": False}

    return {
        "authenticated": True,
        "user_id": str(user["_id"]),
        "email": user["email"]
    }


@router.post("/register")
def register(
    response: Response,
    email: str = Form(...),
    password: str = Form(...)
):
    if users_collection is None:
        return JSONResponse({"error": "Database unavailable"}, status_code=503)

    email = email.strip().lower()

    if len(password) < 6:
        return JSONResponse({"error": "Password must be at least 6 characters"}, status_code=400)

    if users_collection.find_one({"email": email}):
        return JSONResponse({"error": "User already exists"}, status_code=400)

    result = users_collection.insert_one({
        "email": email,
        "password": hash_password(password),
        "created_at": datetime.utcnow()
    })

    token = create_session_token(str(result.inserted_id))
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=COOKIE_MAX_AGE
    )

    return {
        "message": "Registered successfully",
        "user_id": str(result.inserted_id),
        "email": email
    }


@router.post("/login")
def login(
    response: Response,
    email: str = Form(...),
    password: str = Form(...)
):
    if users_collection is None:
        return JSONResponse({"error": "Database unavailable"}, status_code=503)

    email = email.strip().lower()
    user = users_collection.find_one({"email": email})

    if not user or not verify_password(password, user["password"]):
        return JSONResponse({"error": "Invalid credentials"}, status_code=401)

    token = create_session_token(str(user["_id"]))
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=COOKIE_MAX_AGE
    )

    return {
        "message": "Login successful",
        "user_id": str(user["_id"]),
        "email": user["email"]
    }


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"message": "Logged out successfully"}
