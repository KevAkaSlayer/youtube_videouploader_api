import os
import boto3
import requests
import tempfile
import time
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import googleapiclient.http
import logging
from dotenv import load_dotenv
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Define the scope for YouTube upload.
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

app = FastAPI()

# Pydantic model for the incoming JSON payload.
class VideoUploadRequest(BaseModel):
    video_url: str = r"https://drive.usercontent.google.com/u/0/uc?id=1t2U7YORidXA48i6ihKNSiH2iH3skxZq3&export=download"
    title: str = "Uploaded from FastAPI using cloudflare r2 final video"
    description: str = "This is an automated upload via FastAPI"
    tags: List[str] = ["test", "api", "python"]
    category_id: str = "22"
    privacy_status: str = "private"
    publish_at: Optional[str] = "2025-04-12T8:30:00Z"

# Initialize boto3 client for Cloudflare R2
s3_client = boto3.client(
    's3',
    endpoint_url=os.getenv('R2_ENDPOINT_URL'),
    aws_access_key_id=os.getenv('R2_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('R2_SECRET_ACCESS_KEY')
)

def authenticate_youtube():
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    client_secret = r"C:\Users\AC\OneDrive\Desktop\json\client.json"
    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
        client_secret, SCOPES
    )
    credentials = flow.run_local_server(port=0)
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)
    return youtube

def download_video_to_r2(url: str, object_name: str):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Ensure bucket name is a string and not None
        bucket_name = os.getenv('R2_BUCKET_NAME')
        if not bucket_name:
            raise ValueError("R2_BUCKET_NAME environment variable is not set")
            
        # Upload to R2
        s3_client.upload_fileobj(response.raw, bucket_name, object_name)
        return True
    except Exception as e:
        logger.error(f"Error downloading video to R2: {e}")
        raise

def upload_video(youtube, request: VideoUploadRequest):
    # Generate a unique object name based on the URL
    url_parts = urlparse(request.video_url)
    object_name = os.path.basename(url_parts.path)
    if not object_name or object_name == "download":
        object_name = f"video_{int(time.time())}.mp4"
        
    # Use system temp directory
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, object_name)
    
    try:
        # Download to R2
        download_video_to_r2(request.video_url, object_name)
        
        # Download from R2 to temp file
        bucket_name = os.getenv('R2_BUCKET_NAME')
        s3_client.download_file(bucket_name, object_name, temp_file_path)
        
        # Prepare upload to YouTube
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
        
        # Use a context manager for MediaFileUpload to ensure it's closed properly
        with open(temp_file_path, 'rb') as file_obj:
            media_body = googleapiclient.http.MediaFileUpload(
                temp_file_path, 
                chunksize=-1, 
                resumable=True, 
                mimetype="video/mp4"
            )
            
            # Upload to YouTube
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
        
        # Sleep briefly to ensure the file handle is released
        time.sleep(1)
        
        # Clean up
        s3_client.delete_object(Bucket=bucket_name, Key=object_name)
        
        # Try deleting with a retry mechanism
        for _ in range(3):
            try:
                os.remove(temp_file_path)
                break
            except OSError:
                time.sleep(1)
        
        return response
    except Exception as e:
        # Log the error but don't try to delete the file here
        logger.error(f"Error in upload process: {e}")
        raise
        
@app.post("/upload/")
async def upload_endpoint(video_request: VideoUploadRequest):
    try:
        youtube = authenticate_youtube()
        response = upload_video(youtube, video_request)
        return {"video_id": response.get("id"), "message": "Video uploaded successfully."}
    except Exception as e:
        logger.error(f"Upload endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))