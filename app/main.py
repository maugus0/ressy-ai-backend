import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, calls, admin, users, menus, restaurants, specials, orders, order_history, transcripts, faqs
from app.api.websocket import twilio_websocket_handler

app = FastAPI(title="Voice Agent API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(calls.router, prefix="/api/v1/calls", tags=["calls"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(menus.router, prefix="/api/v1/menu", tags=["menu"])
app.include_router(restaurants.router, prefix="/api/v1/restaurants", tags=["restaurants"])
app.include_router(specials.router, prefix="/api/v1/specials", tags=["specials"])
app.include_router(orders.router, prefix="/api/v1/orders", tags=["orders"])
app.include_router(order_history.router, prefix="/api/v1/order-history", tags=["order-history"])
app.include_router(transcripts.router, prefix="/api/v1/transcripts", tags=["transcripts"])
app.include_router(faqs.router, prefix="/api/v1/faqs", tags=["faqs"])


# WebSocket Endpoint
@app.websocket("/twilio")
async def twilio_websocket(websocket: WebSocket):
    await twilio_websocket_handler(websocket)


# Health Route
@app.get("/")
async def root():
    return {"message": "Voice Agent API running", "status": "healthy"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": asyncio.get_event_loop().time()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001, reload=True)
