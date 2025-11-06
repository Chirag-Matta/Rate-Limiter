from fastapi import FastAPI, Request, Response
import time , asyncio
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict
from typing import Dict
from redis import asyncio as aioredis



app = FastAPI()


class AdvancedMware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.redis_client = aioredis.from_url("redis://localhost")
        self.capacity = 3
        self.refill_rate = 1  # tokens per second
    
    async def log_msg(self, message: str):
        print(f"[LOG]: {message}")
        
    async def dispatch(self, request: Request, call_next):
            
        client_ip = request.client.host
        key = f"rate_limit:{client_ip}"
        current_time = time.time()
        data = await self.redis_client.hgetall(key)
        
        if not data:
            tokens = self.capacity
            last_refill = current_time
        else:
            tokens = float(data.get(b"tokens", b"0").decode())
            last_refill = float(data.get(b"last_refill", b"0").decode())
            
        elapsed_time = current_time - last_refill
        tokens = min(self.capacity, tokens + elapsed_time * self.refill_rate)
        last_refill = current_time
        
        if tokens < 1:
            await self.log_msg(f"Rate limit hit for {client_ip}")
            return Response("Too Many Requests", status_code=429)
        else:
            tokens -= 1
            await self.redis_client.hset(key, mapping={
                "tokens": tokens,
                "last_refill": last_refill
            })
        await self.redis_client.expire(key, 10)
    
        
        # # Rate limiting (1 request per second per IP)
        # if current_time - self.rate_limit_records[client_ip] < 1:
        #     await self.log_msg(f"Rate limit hit for {client_ip}")
        #     return Response("Too Many Requests", status_code=429)
        
        # self.rate_limit_records[client_ip] = current_time
        path = request.url.path
        await self.log_msg(f"Request from {client_ip} to {path}")
        
        # Process the request and measure time
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Add custom header
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"
        
        # Log asynchronously
        await self.log_msg(f"Processed request from {start_time} to {current_time:.4f}s")
        await self.log_msg(f"Processed request from {client_ip} in {process_time:.4f}s")
        return response

# Initialize Redis client and middleware on startup

# Create Redis before adding middleware
# redis_client = asyncio.run(init_redis())
app.add_middleware(AdvancedMware)

@app.on_event("startup")
async def startup_event():
    app.state.redis_client = await aioredis.from_url("redis://localhost")
    print("Redis client initialized")


@app.on_event("shutdown")
async def shutdown_event():
    redis_client = app.state.redis_client
    await redis_client.close()
    await redis_client.connection_pool.disconnect()



@app.get("/")
async def root():
    return {"message": "Hello from custom middleware!"}
