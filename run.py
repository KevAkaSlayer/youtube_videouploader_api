from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import requests
from io import BytesIO

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaIoBaseUpload

# Define the scope for YouTube upload
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

app = FastAPI()

# Pydantic model for request body: now video_path is actually the video URL.
class VideoUploadRequest(BaseModel):
    video_url: str= r"https://drive.usercontent.google.com/u/0/uc?id=1t2U7YORidXA48i6ihKNSiH2iH3skxZq3&export=download"  # Changed from video_path to video_url
    title: str = "Uploaded from Python"
    description: str = "This is the most awesome description ever"
    tags: list[str] = ["test", "api", "python"]
    category_id: str = "22"
    privacy_status: str = "private"
    publish_at: str = "2025-04-10T10:30:00Z"

def authenticate_youtube():
    """
    Authenticate with YouTube API using OAuth 2.0 and return the YouTube service object.
    """
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    client_secret = r"C:\Users\AC\OneDrive\Desktop\json\client.json"

    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(client_secret, SCOPES)
    credentials = flow.run_local_server(port=0)

    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)
    return youtube

def download_video(url: str) -> BytesIO:
    """
    Downloads the video content from the provided URL into a BytesIO object.
    """
    # Stream the content to handle large files efficiently
    response = requests.get(url, stream=True)
    response.raise_for_status()  # Raise an HTTPError on a bad status
    video_bytes = BytesIO()
    for chunk in response.iter_content(chunk_size=8192):
        video_bytes.write(chunk)
    video_bytes.seek(0)  # Reset the pointer to the start of the BytesIO object
    return video_bytes

def upload_video(youtube, request: VideoUploadRequest):
    """
    Upload a video to YouTube using the provided YouTube service object and request data.
    Downloads the video from a URL, then uploads it.
    """
    request_body = {
        "snippet": {
            "categoryId": request.category_id,
            "title": request.title,
            "description": request.description,
            "tags": request.tags,
        },
        "status": {
            "privacyStatus": request.privacy_status,
            "publishAt": request.publish_at,
        },
    }

    # Download the video from the provided URL
    video_content = download_video(request.video_url)
    
    # Use MediaIoBaseUpload to upload the video from a file-like object
    media_body = MediaIoBaseUpload(video_content, mimetype="video/mp4", chunksize=-1, resumable=True)

    upload_request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media_body,
    )

    response = None
    while response is None:
        status, response = upload_request.next_chunk()
        if status:
            print(f"Upload {int(status.progress() * 100)}% complete.")

    return response

@app.post("/upload/")
async def upload_endpoint(video_request: VideoUploadRequest):
    """
    FastAPI endpoint to handle video upload requests.
    Expects a JSON payload with a video URL and metadata.
    """
    try:
        youtube = authenticate_youtube()
        response = upload_video(youtube, video_request)
        return {"video_id": response.get("id"), "message": "Video uploaded successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
