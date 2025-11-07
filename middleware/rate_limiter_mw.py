from starlette.middleware.base import BaseHTTPMiddleware
import time
from redis import asyncio as aioredis
from fastapi import Request, Response

class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rate_limiter: RateLimiter, config_manager: ConfigManager):
        super().__init__(app)
        self.rate_limiter = rate_limiter
        self.config = config_manager
    
    async def log_msg(self, message: str):
        print(f"[LOG]: {message}")
        
    def _extract_api_key(self, request: Request) -> Optional[str]:
        return request.headers.get("X-API-Key")
        
    async def dispatch(self, request: Request, call_next):
        
        api_key = self._extract_api_key(request)
        tier = self.config.get_api_key_tier(api_key) or self.rate_limiter.default_tier

        
        if not self.rate_limiter:
            self.rate_limiter = request.app.state.rate_limiter    
        
        client_ip = request.client.host
        key = f"rate_limit:{client_ip}"
        tokens, refill, last_used = await self.rate_limiter.allow_request(key, tier)
        
        if not allowed:
            await self.log_msg(f"Rate limit hit for {client_ip}")
            headers = {
                "Retry-After": f"{int(last_used + self.rate_limiter.ttl - time.time())}",
                "X-RateLimit-Limit": str(int(tokens)),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(last_used + self.rate_limiter.ttl)),
                "X-RateLimit-Tier": tier,
            }
            return Response("Too Many Requests", status_code=429,headers=headers)
        
        start = time.time()
        response = await call_next(request)
        preocessing_time = time.time() - start
        response.headers["X-Processing-Time"] = f"{preocessing_time:.4f}s"
        response.headers["X-RateLimit-Limit"] = str(int(tokens))
        response.headers["X-RateLimit-Remaining"] = str(max(0, int(tokens)))
        response.headers["X-RateLimit-Reset"] = str(int(last_used + self.rate_limiter.ttl))
        response.headers["X-RateLimit-Tier"] = tier
        
        
        await self.log_msg(f"Processed request from {client_ip} in {preocessing_time:.4f}s")
        await self.log_msg(f"Processed request from {start:.4f} to {time.time():.4f} in {preocessing_time:.4f}s")
        
        return response