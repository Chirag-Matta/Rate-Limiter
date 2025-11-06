from starlette.middleware.base import BaseHTTPMiddleware
import time
from redis import asyncio as aioredis
from fastapi import Request, Response

class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app , rate_limiter: RateLimiter):
        super().__init__(app)
        self.rate_limiter = rate_limiter
        
    
    async def log_msg(self, message: str):
        print(f"[LOG]: {message}")
        
    async def dispatch(self, request: Request, call_next):
        
        if not self.rate_limiter:
            self.rate_limiter = request.app.state.rate_limiter    
        
        client_ip = request.client.host
        key = f"rate_limit:{client_ip}"
        allowed,tokens,last_refill = self.rate_limiter.allow_request(key)
        if not allowed:
            await self.log_msg(f"Rate limit hit for {client_ip}")
            return Response("Too Many Requests", status_code=429)
        
        start = time.time()
        response = await call_next(request)
        preocessing_time = time.time() - start
        response.headers["X-Process-Time"] = f"{preocessing_time:.4f}s"
        await self.log_msg(f"Processed request from {client_ip} in {preocessing_time:.4f}s")
        await self.log_msg(f"Processed request from {start:.4f} to {time.time():.4f} in {preocessing_time:.4f}s")
        
        return response