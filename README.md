🎬 YouTube Video Uploader API
A FastAPI-based service that enables uploading videos to YouTube using Cloudflare R2 for temporary storage, with support for scheduled publishing.​

🚀 Features
Upload Videos: Upload videos to YouTube from any public URL.​

Temporary Storage: Utilize Cloudflare R2 for temporary video storage.​

Scheduled Publishing: Schedule videos to be published at a specific time.​

Secure Authentication: Implements OAuth 2.0 for secure access.​

FastAPI Backend: Built with FastAPI for high performance and ease of use.​

🛠️ Prerequisites
Python 3.9 or higher​

Google Cloud Project with YouTube Data API enabled​

Cloudflare R2 account​

Google OAuth 2.0 client credentials​

📦 Installation
Clone the repository:

bash
Copy
Edit
git clone https://github.com/KevAkaSlayer/youtube_videouploader_api.git
cd youtube_videouploader_api
Install dependencies:

bash
Copy
Edit
pip install -r requirements.txt
Set up environment variables:

Create a .env file in the root directory with the following content:

env
Copy
Edit
# Cloudflare R2 Configuration
R2_ACCESS_KEY_ID=your_r2_access_key_here
R2_SECRET_ACCESS_KEY=your_r2_secret_key_here
R2_ENDPOINT_URL=https://your_account_id.r2.cloudflarestorage.com
R2_BUCKET_NAME=your_bucket_name_here

# YouTube API Configuration
CLIENT_SECRET=path/to/your/client_secret.json
🚀 Usage
Start the server:

bash
Copy
Edit
uvicorn main:app --reload
Make a request to upload a video:

bash
Copy
Edit
curl -X POST "http://localhost:8000/upload/" \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://example.com/video.mp4",
    "title": "API Upload Demo",
    "description": "Uploaded via FastAPI",
    "tags": ["demo", "backend"],
    "category_id": "22",
    "privacy_status": "private",
    "publish_at": "2025-04-12T10:30:00Z"
  }'
Expected response:

json
Copy
Edit
{
  "video_id": "dQw4w9WgXcQ",
  "message": "Video uploaded successfully."
}
📚 API Documentation
POST /upload/
Uploads and schedules a YouTube video.​

Request Body:

json
Copy
Edit
{
  "video_url": "string",
  "title": "string",
  "description": "string",
  "tags": ["string"],
  "category_id": "string",
  "privacy_status": "string",
  "publish_at": "string (ISO 8601 format)"
}
Responses:

200 OK: Returns the YouTube video ID and a success message.​

500 Internal Server Error: Returns an error message detailing what went wrong.​

⚙️ Environment Variables
Variable	Description	Example
R2_ACCESS_KEY_ID	Cloudflare R2 access key	f1974c3a4fc...
R2_SECRET_ACCESS_KEY	Cloudflare R2 secret key	52478750f72...
R2_ENDPOINT_URL	R2 endpoint URL	https://...r2.cloudflarestorage.com
R2_BUCKET_NAME	R2 bucket name	template
CLIENT_SECRET	Path to Google client secret JSON	path/to/client_secret.json
📺 YouTube Category IDs
ID	Category
1	Film & Animation
10	Music
22	People & Blogs
23	Comedy
27	Education
🐞 Troubleshooting
500 Error: Invalid credentials

Ensure that your Google OAuth setup is correct and the CLIENT_SECRET path is valid.​

500 Error: R2_BUCKET_NAME not set

Check that all required environment variables are set in your .env file.​

Upload timeout

Verify that the video URL is publicly accessible and the server has a stable internet connection.​

📄 License
This project is licensed under the MIT License.