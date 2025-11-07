from starlette.middleware.base import BaseHTTPMiddleware
import time
from typing import Optional
from fastapi import Request, Response
from core.rate_limiter import RateLimiter
from core.config import ConfigManager
from core.health import SystemHealth

class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rate_limiter: Optional[RateLimiter] = None, config_manager: Optional[ConfigManager] = None):
        super().__init__(app)
        self.rate_limiter = rate_limiter
        self.config_manager = config_manager
    
    async def log_msg(self, message: str):
        print(f"[LOG]: {message}")
        
    def _extract_api_key(self, request: Request) -> Optional[str]:
        return request.headers.get("X-API-Key")
        
    async def dispatch(self, request: Request, call_next):
        
        # Initialize from app state if not set
        if not self.rate_limiter:
            self.rate_limiter = request.app.state.rate_limiter
        if not self.config_manager:
            self.config_manager = request.app.state.config_manager
        
        api_key = self._extract_api_key(request)
        tier = self.config_manager.get_api_key_tier(api_key) or self.rate_limiter.default_tier
        
        client_ip = request.client.host
        # Use API key as the rate limit key if provided, otherwise use IP
        rate_limit_key = api_key if api_key else client_ip
        
        await self.log_msg(f"Request from {client_ip}, tier: {tier}, key: {rate_limit_key}")
        
        # Check rate limit with system health awareness
        allowed, tokens, last_used, capacity, health = await self.rate_limiter.allow_request(rate_limit_key, tier)
        
        if not allowed:
            await self.log_msg(f"Rate limit hit for {client_ip} (tier: {tier}, health: {health.value})")
            
            # Calculate retry time based on refill rate
            tier_config = self.config_manager.get_tiers()[tier]
            if health == SystemHealth.DEGRADED:
                refill_rate = tier_config.get("degraded", tier_config["base"])["refill_rate"]
            else:
                refill_rate = tier_config["base"]["refill_rate"]
            
            wait_time = max(1, int((1.0 / refill_rate)))
            
            headers = {
                "Retry-After": str(wait_time),
                "X-RateLimit-Limit": str(int(capacity)),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(last_used + wait_time)),
                "X-RateLimit-Tier": tier,
                "X-System-Health": health.value,
            }
            return Response("Too Many Requests", status_code=429, headers=headers)
        
        start = time.time()
        response = await call_next(request)
        processing_time = time.time() - start
        
        # Add rate limit and system info headers
        response.headers["X-Processing-Time"] = f"{processing_time:.4f}s"
        response.headers["X-RateLimit-Limit"] = str(int(capacity))
        response.headers["X-RateLimit-Remaining"] = str(max(0, int(tokens)))
        response.headers["X-RateLimit-Tier"] = tier
        response.headers["X-System-Health"] = health.value
        
        await self.log_msg(f"Processed request from {client_ip} (tier: {tier}, health: {health.value}) in {processing_time:.4f}s")
        
        return response