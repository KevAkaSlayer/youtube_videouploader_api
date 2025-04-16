import os
import requests
import tempfile
import time
import uuid
from urllib.parse import urlparse

import boto3
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import List, Optional
from pymongo import MongoClient
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

import google_auth_oauthlib.flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import google.auth.transport.requests

# Load environment variables
load_dotenv()

# FastAPI app setup
app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB setup
client = MongoClient(os.getenv("MONGO_URI"))
db = client["youtube_uploader"]
tokens_collection = db["tokens"]

# Cloudflare R2 setup
s3_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("R2_ENDPOINT_URL"),
    aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
)
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")

# OAuth scopes and redirect URI
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

# OAuth Config
OAUTH_CLIENT_CONFIG = {
    "web": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "redirect_uris": [REDIRECT_URI],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

class VideoUploadRequest(BaseModel):
    video_url: str
    title: str
    description: str
    tags: List[str]
    category_id: str
    privacy_status: str
    publish_at: Optional[str]

@app.get("/auth/login")
def login():
    # Generate a unique user ID and flow for Google OAuth
    user_id = str(uuid.uuid4())  # Generate a temporary user ID
    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        OAUTH_CLIENT_CONFIG, scopes=SCOPES
    )
    flow.redirect_uri = REDIRECT_URI

    auth_url, _ = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent", state=user_id
    )
    return RedirectResponse(auth_url)

@app.get("/auth/callback")
def auth_callback(request: Request, code: str, state: str):
    user_id = state  # This user_id is now a temporary unique identifier for the current login session

    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        OAUTH_CLIENT_CONFIG, scopes=SCOPES
    )
    flow.redirect_uri = REDIRECT_URI
    flow.fetch_token(code=code)

    credentials = flow.credentials

    # Fetch the user's email directly from Google API
    try:
        # Create a request object for token info
        request = google.auth.transport.requests.Request()
        
        # Use userinfo endpoint from Google's OAuth2 API
        oauth2_service = build('oauth2', 'v2', credentials=credentials)
        user_info = oauth2_service.userinfo().get().execute()
        
        # Get email from the response
        google_email = user_info.get('email')
        
        if not google_email:
            raise HTTPException(status_code=400, detail="Could not retrieve email from Google")
            
        print(f"Retrieved email: {google_email}")  # Add debug logging
    except Exception as e:
        print(f"Error getting user info: {str(e)}")  # Add debug logging
        raise HTTPException(status_code=500, detail=f"Error fetching user info: {str(e)}")

    # Make sure we have an email before continuing
    if not google_email:
        raise HTTPException(status_code=400, detail="No email was returned from Google")

    # Check if the user exists in the database
    user_record = tokens_collection.find_one({"email": google_email})

    if user_record:
        # If the user exists, update their token data
        tokens_collection.update_one(
            {"email": google_email},
            {
                "$set": {
                    "access_token": credentials.token,
                    "refresh_token": credentials.refresh_token if credentials.refresh_token else user_record.get("refresh_token"),
                    "token_expiry": credentials.expiry.isoformat(),
                }
            }
        )
        return {"message": f"Welcome back, {google_email}! Your tokens have been updated."}
    else:
        # If the user does not exist, create a new record with a new user_id
        tokens_collection.insert_one({
            "user_id": user_id,
            "email": google_email,
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_expiry": credentials.expiry.isoformat(),
        })
        return {"message": f"Authentication successful for {google_email}! New user created."}

def get_authenticated_youtube(user_id: str):
    user_tokens = tokens_collection.find_one({"user_id": user_id})
    if not user_tokens:
        raise HTTPException(status_code=401, detail="User not authenticated")

    creds = Credentials(
        token=user_tokens["access_token"],
        refresh_token=user_tokens["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        scopes=SCOPES,
    )

    return build("youtube", "v3", credentials=creds)

def download_to_r2(url: str, object_name: str):
    response = requests.get(url, stream=True)
    response.raise_for_status()

    bucket_name = os.getenv("R2_BUCKET_NAME")
    if not bucket_name:
        raise ValueError("R2_BUCKET_NAME environment variable is not set")

    s3_client.upload_fileobj(response.raw, bucket_name, object_name)

def download_from_r2_to_temp(object_name: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        s3_client.download_fileobj(R2_BUCKET_NAME, object_name, tmp)
        return tmp.name

@app.post("/upload/")
def upload_video(request: VideoUploadRequest, email: str):
    try:
        # Find the user by email
        user_data = tokens_collection.find_one({"email": email})
        if not user_data:
            raise HTTPException(status_code=401, detail="User not authenticated or not found")
        
        # Get the user_id from the database
        user_id = user_data["user_id"]
        
        # Use the existing function with the retrieved user_id
        youtube = get_authenticated_youtube(user_id)
        
        url_parts = urlparse(request.video_url)
        object_name = os.path.basename(url_parts.path)
        if not object_name or object_name == "download":
            object_name = f"video_{int(time.time())}.mp4"

        download_to_r2(request.video_url, object_name)
        video_path = download_from_r2_to_temp(object_name)

        request_body = {
            "snippet": {
                "title": request.title,
                "description": request.description,
                "tags": request.tags,
                "categoryId": request.category_id,
            },
            "status": {
                "privacyStatus": request.privacy_status,
                **({"publishAt": request.publish_at} if request.publish_at else {}),
            },
        }

        media_body = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        upload_request = youtube.videos().insert(
            part="snippet,status", body=request_body, media_body=media_body
        )

        response = None
        while response is None:
            status, response = upload_request.next_chunk()
            if status:
                print(f"Upload progress: {int(status.progress() * 100)}%")

        time.sleep(1)
        s3_client.delete_object(Bucket=R2_BUCKET_NAME, Key=object_name)

        for _ in range(3):
            try:
                os.remove(video_path)
                break
            except OSError:
                time.sleep(1)

        return {"video_id": response.get("id"), "message": "Video uploaded successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))