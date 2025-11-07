import time
from typing import Dict, Any, Tuple
from redis import asyncio as aioredis

class RateLimiter:
    """
    Redis-backed token bucket rate limiter.
    Handles rate limiting logic, token refills, and Redis I/O with timeouts.
    """
    
    def __init__(self, redis_client, config_manager, default_tier: str = "free"):
        self.redis_client = redis_client
        self.config_manager = config_manager
        self.default_tier = default_tier
    
    def _get_limits(self, tier_cfg: Dict[str, Any]) -> Tuple[float, float, int]:
        base = tier_cfg["base"]
        ttl = int(tier_cfg.get("ttl", 60))
        capacity = float(base["capacity"])
        refill = float(base["refill_rate"])
        return capacity, refill, ttl
    
    async def allow_request(self, api_key: str, tier: str) -> Tuple[bool, float, float, float]:
        
        tiers = self.config_manager.get_tiers()
        tier_cfg = tiers.get(tier) or tiers.get(self.default_tier)
        capacity, refill_rate, ttl = self._get_limits(tier_cfg)
        
        key = f"rate_limit:{api_key}"
        
        try: 
            data = await self.redis_client.hgetall(key)
        except Exception as e:
            print(f"Redis error: {e}")
            return True, capacity, time.time(), capacity
        
        current_time = time.time()
        
        if not data:
            tokens = capacity - 1
            last_used = current_time
        else:
            tokens = float(data.get(b"tokens", b"0").decode())
            last_used = float(data.get(b"last_used", b"0").decode())
            
            elapsed_time = current_time - last_used
            tokens = min(capacity, tokens + elapsed_time * refill_rate)
            
            if tokens < 1:
                return False, tokens, last_used, capacity
            
            tokens -= 1
            last_used = current_time
        
        await self.redis_client.hset(key, mapping={
            "tokens": str(tokens),
            "last_used": str(last_used)
        })
        await self.redis_client.expire(key, ttl)
        
        return True, tokens, last_used, capacity