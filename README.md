# 🎬 YouTube Video Uploader API

A **FastAPI-based service** that enables uploading videos to YouTube using **Cloudflare R2** for temporary storage, with support for **scheduled publishing**.

---

## 🚀 Features

- **Upload Videos:** Upload videos to YouTube from any public URL.
- **Temporary Storage:** Utilize Cloudflare R2 for temporary video storage.
- **Scheduled Publishing:** Schedule videos to be published at a specific time.
- **Secure Authentication:** Implements OAuth 2.0 for secure access.
- **FastAPI Backend:** Built with FastAPI for high performance and ease of use.

---

## 🛠️ Prerequisites

- **Python 3.9 or higher**
- **Google Cloud Project** with YouTube Data API enabled
- **Cloudflare R2 account**
- **Google OAuth 2.0 client credentials**
- **MongoDB Atlas account**

---

## 📦 Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/KevAkaSlayer/youtube_videouploader_api.git
   cd youtube_videouploader_api
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**

   Export the following environment variables in your terminal or add them to your shell configuration file (e.g., `.bashrc`, `.zshrc`):

   ```bash
   export R2_ACCESS_KEY_ID=your_r2_access_key_here
   export R2_SECRET_ACCESS_KEY=your_r2_secret_key_here
   export R2_ENDPOINT_URL=https://your_r2_endpoint_url_here
   export R2_BUCKET_NAME=your_bucket_name_here

   # Google OAuth Configuration
   export GOOGLE_CLIENT_ID=your_google_client_id_here
   export GOOGLE_CLIENT_SECRET=your_google_client_secret_here
   export GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback

   # MongoDB Configuration
   export MONGO_URI=your_mongodb_connection_string_here
   ```

---

## 🚀 Usage

1. **Start the server:**

   ```bash
   uvicorn main:app --reload
   ```

2. **Authenticate with Google OAuth:**

   - Visit the `/auth/login` endpoint to generate an authentication URL.
   - Log in with your Google account and grant the required permissions.
   - After successful authentication, the server will store your tokens in the MongoDB database.

3. **Make a request to upload a video:**

   ```bash
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
     }' \
     -H "email: your_email@example.com"
   ```

4. **Expected response:**

   ```json
   {
     "video_id": "dQw4w9WgXcQ",
     "message": "Video uploaded successfully."
   }
   ```

---

## 📚 API Documentation

### **GET /auth/login**

Generates a Google OAuth login URL for user authentication.

### **GET /auth/callback**

Handles the OAuth callback and stores the user's tokens in the MongoDB database.

### **POST /upload/**

Uploads and schedules a YouTube video.

#### **Request Headers:**

- `email`: The email address of the authenticated user.

#### **Request Body:**

```json
{
  "video_url": "string",
  "title": "string",
  "description": "string",
  "tags": ["string"],
  "category_id": "string",
  "privacy_status": "string",
  "publish_at": "string (ISO 8601 format)"
}
```

#### **Responses:**

- **200 OK:** Returns the YouTube video ID and a success message.
- **401 Unauthorized:** User is not authenticated or not found.
- **500 Internal Server Error:** Returns an error message detailing what went wrong.

---

## ⚙️ Environment Variables

| Variable               | Description                | Example                               |
| ---------------------- | -------------------------- | ------------------------------------- |
| `R2_ACCESS_KEY_ID`     | Cloudflare R2 access key   | `your_r2_access_key_here`             |
| `R2_SECRET_ACCESS_KEY` | Cloudflare R2 secret key   | `your_r2_secret_key_here`             |
| `R2_ENDPOINT_URL`      | R2 endpoint URL            | `https://your_r2_endpoint_url_here`   |
| `R2_BUCKET_NAME`       | R2 bucket name             | `your_bucket_name_here`               |
| `GOOGLE_CLIENT_ID`     | Google OAuth client ID     | `your_google_client_id_here`          |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | `your_google_client_secret_here`      |
| `GOOGLE_REDIRECT_URI`  | Google OAuth redirect URI  | `http://localhost:8000/auth/callback` |
| `MONGO_URI`            | MongoDB connection string  | `your_mongodb_connection_string_here` |

---

## 📺 YouTube Category IDs

| ID  | Category         |
| --- | ---------------- |
| 1   | Film & Animation |
| 10  | Music            |
| 22  | People & Blogs   |
| 23  | Comedy           |
| 27  | Education        |

---

## 🐞 Troubleshooting

- **500 Error: Invalid credentials**  
  Ensure that your Google OAuth setup is correct and the `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI` are properly configured.

- **500 Error: `R2_BUCKET_NAME` not set**  
  Check that all required environment variables are set and exported correctly.

- **Upload timeout**  
  Verify that the video URL is publicly accessible and the server has a stable internet connection.

- **Database connection issues**  
  Ensure that the `MONGO_URI` is valid and the MongoDB cluster is accessible.

---

## 📄 License

This project is licensed under the **MIT License**.
