from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import googleapiclient.http

# Define the scope for YouTube upload
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Initialize FastAPI app
app = FastAPI()

# Pydantic model for request body
class VideoUploadRequest(BaseModel):
    video_path: str = r"C:\Users\AC\Videos\Screen Recordings\demo.mp4"
    title: str = "Uploaded from Python"
    description: str = "This is the most awesome description ever"
    tags: list = ["test", "api", "python"]
    category_id: str = "22"
    privacy_status: str = "private"
    publish_at: str = "2025-04-10T10:30:00Z"



def authenticate_youtube():
    """
    Authenticate with YouTube API using OAuth 2.0 and return the YouTube service object.
    """
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    client_secret = r"C:\Users\AC\OneDrive\Desktop\json\client.json"

    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
        client_secret, SCOPES
    )
    credentials = flow.run_local_server(port=0)

    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)
    return youtube

def upload_video(youtube, request: VideoUploadRequest):
    """
    Upload a video to YouTube using the provided YouTube service object and request data.
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

    media_file = request.video_path

    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=googleapiclient.http.MediaFileUpload(media_file, chunksize=-1, resumable=True),
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload {int(status.progress() * 100)}% complete.")

    return response

@app.post("/upload/")
async def upload_endpoint(video_request: VideoUploadRequest):
    """
    FastAPI endpoint to handle video upload requests.
    """
    try:
        youtube = authenticate_youtube()
        response = upload_video(youtube, video_request)
        return {"video_id": response.get("id"), "message": "Video uploaded successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
