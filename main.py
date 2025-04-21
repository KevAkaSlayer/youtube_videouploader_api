import os
import tempfile
import time
import uuid
import traceback
import logging
from urllib.parse import urlparse

import aiofiles
import requests
import boto3
from fastapi import (
    FastAPI, HTTPException, UploadFile, File, Form, Request, Query
)
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from pymongo import MongoClient
from dotenv import load_dotenv

import google_auth_oauthlib.flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import google.auth.transport.requests

# ─────────── Logging & Debug Setup ───────────────────────────────────────────────
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("uvicorn.error")

app = FastAPI(debug=True)

@app.exception_handler(Exception)
async def debug_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    logger.error(f"Unhandled exception:\n{tb}")
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "traceback": tb.splitlines()},
    )

# ─────────── CORS & Config ────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Lock down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()

# MongoDB & Token Store
mongo = MongoClient(os.getenv("MONGO_URI"))
tokens = mongo["youtube_uploader"]["tokens"]

# Cloudflare R2 (S3-compatible)
s3 = boto3.client(
    "s3",
    endpoint_url=os.getenv("R2_ENDPOINT_URL"),
    aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
)
R2_BUCKET = os.getenv("R2_BUCKET_NAME")

# OAuth2 (Google)
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
OAUTH_CLIENT_CONFIG = {
    "web": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "redirect_uris": [REDIRECT_URI],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

# File validation
ALLOWED_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
ALLOWED_MIMES = {
    "video/mp4", "video/quicktime", "video/x-msvideo",
    "video/x-matroska", "video/webm"
}

# Privacy options
PRIVACY_OPTIONS = ["public", "private", "unlisted"]

# ─────────── Models ─────────────────────────────────────────────────────────────
class VideoUploadRequest(BaseModel):
    upload_type: str = Field(..., pattern="^(url|local)$")
    video_url: Optional[str] = None
    local_video_path: Optional[str] = None
    title: str
    description: str
    tags: List[str]
    category_id: str
    privacy_status: str
    publish_at: Optional[str] = None
    embeddable: Optional[bool] = False
    made_for_kids: Optional[bool] = False
    paid_product_placement: Optional[bool] = False
    auto_levels: Optional[bool] = False
    notify_subscribers: Optional[bool] = True
    stabilize: Optional[bool] = False
    thumbnail_url: Optional[str] = None

# ─────────── Helpers ────────────────────────────────────────────────────────────
def get_youtube_client(user_id: str):
    user = tokens.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(401, "User not authenticated")
    creds = Credentials(
        token=user["access_token"],
        refresh_token=user["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds)

async def save_upload_file(upload_file: UploadFile) -> str:
    ext = os.path.splitext(upload_file.filename)[1].lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(400, f"Unsupported extension: {ext}")
    if upload_file.content_type not in ALLOWED_MIMES:
        raise HTTPException(400, f"Unsupported MIME type: {upload_file.content_type}")
    tmp_dir = tempfile.gettempdir()
    unique = f"{uuid.uuid4()}{ext}"
    path = os.path.join(tmp_dir, unique)
    async with aiofiles.open(path, 'wb') as f:
        await f.write(await upload_file.read())
    return path

async def download_url_to_temp_and_r2(url: str):
    resp = requests.get(url, stream=True)
    resp.raise_for_status()
    key = os.path.basename(urlparse(url).path) or f"video_{int(time.time())}.mp4"
    s3.upload_fileobj(resp.raw, R2_BUCKET, key)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(key)[1])
    s3.download_fileobj(R2_BUCKET, key, tmp)
    tmp.close()
    return tmp.name, key

def build_request_body(meta: VideoUploadRequest):
    return {
        "snippet": {
            "title": meta.title,
            "description": meta.description,
            "tags": meta.tags,
            "categoryId": meta.category_id,
            "thumbnails": {"default": {"url": meta.thumbnail_url or ""}},
        },
        "status": {
            "privacyStatus": meta.privacy_status,
            "embeddable": meta.embeddable,
            "selfDeclaredMadeForKids": meta.made_for_kids,
            **({"publishAt": meta.publish_at} if meta.publish_at else {}),
        },
        "paidProductPlacementDetails": {
            "hasPaidProductPlacement": meta.paid_product_placement
        },
    }

# ─────────── Routes ─────────────────────────────────────────────────────────────
@app.get("/")
def index():
    return {"message": "ContentOS FastAPI Backend is running!"}

@app.get("/auth/login")
def login():
    state = str(uuid.uuid4())
    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        OAUTH_CLIENT_CONFIG, scopes=SCOPES
    )
    flow.redirect_uri = REDIRECT_URI
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state
    )
    return RedirectResponse(auth_url)

@app.get("/auth/callback")
def auth_callback(request: Request, code: str, state: str):
    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        OAUTH_CLIENT_CONFIG, scopes=SCOPES
    )
    flow.redirect_uri = REDIRECT_URI
    flow.fetch_token(code=code)
    creds = flow.credentials
    oauth_req = google.auth.transport.requests.Request()
    oauth2_svc = build("oauth2", "v2", credentials=creds)
    info = oauth2_svc.userinfo().get().execute()
    google_sub = info.get("id") or info.get("sub")
    google_email = info.get("email")
    if not google_sub or not google_email:
        raise HTTPException(400, "Failed to get identity from Google")
    tokens.update_one(
        {"user_id": google_sub},
        {"$set": {
            "email": google_email,
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_expiry": creds.expiry.isoformat(),
        }},
        upsert=True
    )
    return {"message": f"Authenticated as {google_email}", "user_id": google_sub}

@app.get("/categories/")
def list_categories(
    email: str = Query(..., description="Authenticated user's email"),
    region_code: str = Query("US", alias="regionCode", description="ISO country code")
):
    user = tokens.find_one({"email": email})
    if not user:
        raise HTTPException(401, "User not authenticated")
    youtube = get_youtube_client(user["user_id"])
    resp = youtube.videoCategories().list(
        part="snippet",
        regionCode=region_code
    ).execute()
    return [
        {"id": item["id"], "title": item["snippet"]["title"]}
        for item in resp.get("items", [])
    ]

@app.get("/privacy-options/")
def get_privacy_options():
    return PRIVACY_OPTIONS

@app.post("/upload/")
async def upload_video(
    upload_type: str = Form(...),
    file: Optional[UploadFile] = File(None),
    video_url: Optional[str] = Form(None),
    title: str = Form(...),
    description: str = Form(...),
    tags: List[str] = Form(...),
    category_id: str = Form(...),
    privacy_status: str = Form(...),
    publish_at: Optional[str] = Form(None),
    embeddable: bool = Form(False),
    made_for_kids: bool = Form(False),
    paid_product_placement: bool = Form(False),
    auto_levels: bool = Form(False),
    notify_subscribers: bool = Form(True),
    stabilize: bool = Form(False),
    thumbnail_url: Optional[str] = Form(None),
    email: str = Form(...),
):
    user = tokens.find_one({"email": email})
    if not user:
        raise HTTPException(401, "User not found")
    youtube = get_youtube_client(user["user_id"])

    if upload_type == "url":
        if not video_url:
            raise HTTPException(400, "video_url is required for URL upload")
        video_path, r2_key = await download_url_to_temp_and_r2(video_url)
    elif upload_type == "local":
        if not file:
            raise HTTPException(400, "file is required for local upload")
        video_path = await save_upload_file(file)
        r2_key = None
    else:
        raise HTTPException(400, "upload_type must be 'url' or 'local'")

    meta = VideoUploadRequest(
        upload_type=upload_type,
        video_url=video_url,
        local_video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        category_id=category_id,
        privacy_status=privacy_status,
        publish_at=publish_at,
        embeddable=embeddable,
        made_for_kids=made_for_kids,
        paid_product_badged_product_placement=paid_product_placement,
        auto_levels=auto_levels,
        notify_subscribers=notify_subscribers,
        stabilize=stabilize,
        thumbnail_url=thumbnail_url
    )
    body = build_request_body(meta)
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    insert = youtube.videos().insert(
        part="snippet,status,paidProductPlacementDetails",
        body=body,
        media_body=media,
        autoLevels=auto_levels,
        notifySubscribers=notify_subscribers,
        stabilize=stabilize
    )
    resp = None
    while resp is None:
        status, resp = insert.next_chunk()
        if status:
            print(f"Upload {int(status.progress()*100)}%")

    if r2_key:
        s3.delete_object(Bucket=R2_BUCKET, Key=r2_key)
        os.remove(video_path)

    # Completed upload: return JSON response
    return JSONResponse(
        status_code=200,
        content={"video_id": resp.get("id"), "message": "Upload complete!"}
    )
