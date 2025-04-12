from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import requests
import tempfile
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import googleapiclient.http

# Define the scope for YouTube upload.
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

app = FastAPI()

# Pydantic model for the incoming JSON payload.
class VideoUploadRequest(BaseModel):
    video_url: str = r"https://drive.usercontent.google.com/u/0/uc?id=1t2U7YORidXA48i6ihKNSiH2iH3skxZq3&export=download"
    title: str = "Uploaded from FastAPI"
    description: str = "This is an automated upload via FastAPI"
    tags: List[str] = ["test", "api", "python"]
    category_id: str = "22"
    privacy_status: str = "private"
    publish_at: Optional[str] = "2025-04-12T10:30:00Z"

def authenticate_youtube():
    """
    Authenticate with the YouTube API using OAuth 2.0 and return the YouTube service object.
    """
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    client_secret = r"C:\Users\AC\OneDrive\Desktop\json\client.json"
    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
        client_secret, SCOPES
    )
    credentials = flow.run_local_server(port=0)
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)
    return youtube

def download_video_to_temp(url: str) -> str:
    """
    Downloads the video from the provided URL to a temporary file.
    Returns the file path of the temporary file.
    """
    response = requests.get(url, stream=True)
    response.raise_for_status()  # Raise an error if the HTTP status is not successful
    
    # Create a temporary file. delete=False allows us to use it after closing.
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    try:
        with open(temp_file.name, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    except Exception as e:
        os.unlink(temp_file.name)  # Delete the file if an error occurs
        raise e
    return temp_file.name

def upload_video(youtube, request: VideoUploadRequest):
    """
    Uploads a video to YouTube using the provided YouTube service object.
    Downloads the video from the given URL to a temporary file, then uploads it.
    Deletes the temporary file only after a successful upload.
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
    
    # Step 1: Download the video to a temporary file.
    temp_file_path = download_video_to_temp(request.video_url)
    response = None
    
    try:
        # Step 2: Create the media upload object.
        media_body = googleapiclient.http.MediaFileUpload(
            temp_file_path, chunksize=-1, resumable=True, mimetype="video/mp4"
        )
        upload_request = youtube.videos().insert(
            part="snippet,status",
            body=request_body,
            media_body=media_body,
        )
    
        # Step 3: Monitor the upload progress.
        while response is None:
            status, response = upload_request.next_chunk()
            if status:
                print(f"Upload {int(status.progress() * 100)}% complete.")
    except Exception as e:
        print("An error occurred during upload:", e)
        raise e
    else:
        # Only delete the temporary file if the upload was successful.
        try:
            os.remove(temp_file_path)
            print("Temporary file deleted successfully.")
        except Exception as del_e:
            print("Warning: Could not delete temporary file:", del_e)
    
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
