from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional
import uuid
import time
import base64

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

TOTAL_ORDERS = 54
RATE_LIMIT = 16
WINDOW = 10

orders_created = {}
client_requests = {}


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/orders", status_code=201)
def create_order(idempotency_key: str = Header(..., alias="Idempotency-Key")):
    if idempotency_key in orders_created:
        return orders_created[idempotency_key]

    order = {
        "id": str(uuid.uuid4()),
        "status": "created"
    }

    orders_created[idempotency_key] = order
    return order


@app.get("/orders")
def list_orders(limit: int = 10, cursor: Optional[str] = None):
    start = 1

    if cursor:
        start = int(base64.b64decode(cursor).decode())

    end = min(start + limit - 1, TOTAL_ORDERS)

    items = [{"id": i} for i in range(start, end + 1)]

    next_cursor = None
    if end < TOTAL_ORDERS:
        next_cursor = base64.b64encode(str(end + 1).encode()).decode()

    return {
        "items": items,
        "next_cursor": next_cursor
    }


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.url.path != "/orders":
        return await call_next(request)

    client = request.headers.get("X-Client-Id")

    if client:
        now = time.time()

        history = client_requests.get(client, [])
        history = [t for t in history if now - t < WINDOW]

        if len(history) >= RATE_LIMIT:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": "10"},
            )

        history.append(now)
        client_requests[client] = history

    return await call_next(request)