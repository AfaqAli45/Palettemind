from datetime import datetime
import hashlib

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.inference import generate_best_palettes
from app.database import palettes_collection, likes_collection, dislikes_collection
from app.auth import router as auth_router, get_current_user
from app.schemas import FeedbackRequest

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(auth_router)


def make_palette_hash(palette):
    normalized = "|".join(color.lower() for color in palette)
    return hashlib.sha256(normalized.encode()).hexdigest()


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/generate")
def generate_palette_api(
    request: Request,
    n: int = 5,
    style: str = "vibrant",
    temp: str = "any",
    bright: str = "any"
):
    try:
        user = get_current_user(request)
        user_id = str(user["_id"]) if user else None

        n = max(1, min(n, 15))

        personalized = user is not None

        # guests cannot use personalization
        if not personalized:
            style = "vibrant"
            temp = "any"
            bright = "any"

        palettes, scores = generate_best_palettes(
            n_return=n,
            n_samples=min(max(n * 8, 40), 100),
            style=style,
            temperature=temp,
            brightness=bright,
            user_id=user_id
        )

        if palettes_collection is not None:
            try:
                palettes_collection.insert_one({
                    "user_id": user_id,
                    "palettes": palettes,
                    "scores": scores,
                    "style": style,
                    "temperature": temp,
                    "brightness": bright,
                    "personalized": personalized,
                    "created_at": datetime.utcnow()
                })
            except Exception as e:
                print("DB Error:", e)

        return {
            "palettes": palettes,
            "scores": scores,
            "personalized": personalized
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        print("❌ ERROR:", e)
        return JSONResponse(
            {
                "error": str(e),
                "palettes": [],
                "scores": [],
                "personalized": False
            },
            status_code=500
        )



@app.post("/feedback/like")
def like_palette(request: Request, payload: FeedbackRequest):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Login required"}, status_code=401)

    if likes_collection is None:
        return JSONResponse({"error": "Database unavailable"}, status_code=503)

    user_id = str(user["_id"])
    palette_hash = make_palette_hash(payload.palette)

    if dislikes_collection is not None:
        dislikes_collection.delete_one({
            "user_id": user_id,
            "palette_hash": palette_hash
        })

    likes_collection.update_one(
        {
            "user_id": user_id,
            "palette_hash": palette_hash
        },
        {
            "$set": {
                "user_id": user_id,
                "palette": payload.palette,
                "palette_hash": palette_hash,
                "updated_at": datetime.utcnow()
            },
            "$setOnInsert": {
                "created_at": datetime.utcnow()
            }
        },
        upsert=True
    )

    return {"message": "Palette liked successfully"}


@app.post("/feedback/dislike")
def dislike_palette(request: Request, payload: FeedbackRequest):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Login required"}, status_code=401)

    if dislikes_collection is None:
        return JSONResponse({"error": "Database unavailable"}, status_code=503)

    user_id = str(user["_id"])
    palette_hash = make_palette_hash(payload.palette)

    if likes_collection is not None:
        likes_collection.delete_one({
            "user_id": user_id,
            "palette_hash": palette_hash
        })

    dislikes_collection.update_one(
        {
            "user_id": user_id,
            "palette_hash": palette_hash
        },
        {
            "$set": {
                "user_id": user_id,
                "palette": payload.palette,
                "palette_hash": palette_hash,
                "updated_at": datetime.utcnow()
            },
            "$setOnInsert": {
                "created_at": datetime.utcnow()
            }
        },
        upsert=True
    )

    return {"message": "Palette disliked successfully"}


@app.get("/my-likes")
def my_likes(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Login required"}, status_code=401)

    if likes_collection is None:
        return {"liked_palettes": []}

    user_id = str(user["_id"])
    docs = list(
        likes_collection.find({"user_id": user_id}).sort("updated_at", -1)
    )

    return {
        "liked_palettes": [doc["palette"] for doc in docs]
    }
