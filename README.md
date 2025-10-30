# RessyAI Backend

## Project Overview

RessyAI Backend is a FastAPI-based voice agent API server designed to handle real-time voice interactions, primarily integrating Twilio and Deepgram for telephony and speech-to-text services. It provides authentication, call management, and admin routes, and supports WebSocket connections for streaming audio and transcripts.

### Key Features
- **FastAPI** RESTful API with CORS support
- **WebSocket endpoint** for Twilio integration (`/twilio`)
- **Deepgram STS** for real-time speech-to-text
- **Call session management** and transcript storage
- **JWT-based authentication**
- **Modular structure** for routes, services, models, and utilities

## Project Structure
```
ressy-ai-backend/
├── Dockerfile
├── requirements.txt
├── start.sh
└── app/
    ├── main.py
    ├── main_fixed_final.py
    ├── config.json
    ├── config/
    ├── models/
    ├── routes/
    ├── services/
    └── utils/
```

## How to Run Locally

### Prerequisites
- Python 3.9+
- [pip](https://pip.pypa.io/en/stable/)
- (Optional) Docker

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables
Create a `.env` file in the root directory and add your Deepgram API key:
```
DEEPGRAM_API_KEY=your_deepgram_api_key
```

### 3. Start the Server
You can run the server using the provided script:
```bash
./start.sh
```
Or manually:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 5001 --reload
```

### 4. Docker Usage
To run in Docker:
```bash
docker build -t ressy-ai-backend .
docker run -p 5001:5001 --env DEEPGRAM_API_KEY=your_deepgram_api_key ressy-ai-backend
```

## API Endpoints
- `GET /` — Health check
- `GET /health` — Health status
- `POST /api/auth/*` — Authentication routes
- `POST /api/calls/*` — Call management
- `POST /api/admin/*` — Admin operations
- `WS /twilio` — WebSocket endpoint for Twilio audio streaming

## Configuration
- `app/config.json` — Deepgram agent configuration
- `.env` — Environment variables (API keys)

## Main Dependencies
- fastapi
- uvicorn
- websockets
- boto3
- python-dotenv
- bcrypt
- pyjwt
- python-multipart
- certifi

## Summary
This backend enables real-time voice agent capabilities, integrating Twilio for telephony and Deepgram for speech-to-text. It is modular, production-ready, and can be run locally or in Docker. See the code in `app/main.py` for the main application logic and WebSocket handling.
