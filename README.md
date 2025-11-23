# RessyAI Backend

FastAPI backend for a multitenant, function-calling voice agent. It streams Twilio audio to Deepgram STS, builds restaurant-specific prompts (menu, specials, FAQs), executes app functions (orders, reservations, FAQs, etc.), and persists calls, transcripts, and orders to MySQL.

## What’s Inside

- **WebSocket call flow**: `/voice` Twilio webhook hands off to `/twilio` WebSocket; `app/services/websocket_service.py` coordinates Twilio ⇄ Deepgram audio, function calls, barge-in, farewells, and transcript capture.
- **Deepgram Agent FC**: `app/agent_fc/*` wires Deepgram function calls to app services (orders, reservations, conversation helpers).
- **REST APIs**: Auth, users, restaurants, menus, specials, orders, transcripts, FAQs under `/api/v1/*` (see routers in `app/api`).
- **Multitenant routing**: Resolves restaurant by Twilio number, loads menu + FAQs, injects into prompts, stores transcripts per call.
- **MySQL persistence**: Repositories in `app/repositories/mysql_*.py` back menus, restaurants, orders, users, transcripts.

## Quickstart

### Prereqs

- Python 3.9+
- MySQL reachable with schema matching `migrations/queries.sql`
- (Optional) Docker

### Setup

```bash
pip install -r requirements.txt
```

Create `.env` in the repo root:

```env
# Deepgram
DEEPGRAM_API_KEY=your_deepgram_key

# MySQL
DB_HOST=localhost
DB_NAME=ressy
DB_USERNAME=root
DB_PASSWORD=secret
DB_PORT=3306

# Local dev
USE_MOCK_DATA=false
```

### Run

```bash
./start.sh
# or
uvicorn app.main:app --host 0.0.0.0 --port 5001 --reload
```

Docker:

```bash
docker build -t ressy-ai-backend .
docker run -p 5001:5001 --env-file .env ressy-ai-backend
```

## Call Flow (Twilio → Deepgram)

1. Twilio hits `POST /voice`, which responds with a `<Stream>` that points to `wss://<host>/twilio` and passes `fromNumber`/`toNumber`.
2. `app/api/websocket.py` hands the socket to `WebSocketService`.
3. The service:
   - Looks up the restaurant by Twilio number, pulls Deepgram API key/keyterms.
   - Builds dynamic prompt with menu + FAQs (`prompt_loader.load_think_prompt`).
   - Streams audio to Deepgram STS, forwards agent audio back to Twilio, handles barge-in/clear.
   - Routes function calls (orders/reservations/etc.) via `app/agent_fc`.
   - Writes transcripts and order data to MySQL.

## Key Endpoints

- Health: `GET /`, `GET /health`
- Twilio webhook: `POST /voice` (returns TwiML `<Stream>`)
- Twilio WebSocket: `WS /twilio`
- REST APIs (prefix `/api/v1`): `auth`, `users`, `restaurants`, `menu`, `specials`, `orders`, `order-history`, `transcripts`, `faqs`, `calls`, `admin`

## Testing

```bash
pytest
```

Note: Tests that touch MySQL expect the database reachable per your `.env`.

## Useful Paths

- Entrypoint: `app/main.py`
- WebSocket plumbing: `app/services/websocket_service.py`
- Deepgram config: `app/services/deepgram_service.py`
- Function call handlers: `app/agent_fc/functions/*`
- Migrations/SQL: `migrations/`
