import time
from redis import asyncio as aioredis

class RateLimiter:
    """
    Redis-backed token bucket rate limiter.
    Handles rate limiting logic, token refills, and Redis I/O with timeouts.
    """
    
    def __init__(self,redis_client , config_manager , tier="free"):
        self.redis_client = redis_client
        self.config_manager = config_manager
        self.tier = tier
        
    
    def _get_limits(self, tier_cfg: Dict[str, Any]) -> Tuple[float, float, int, float]:
        base = tier_cfg["base"]
        ttl = int(tier_cfg.get("ttl", 60))
        tokens = float(base["capacity"])
        refill = float(base["refill_rate"])
        return tokens, refill, ttl
    
        
    async def allow_request(self, api_key: str, tier: str) -> Tuple[bool, float, float, float]:
        
        tiers = self.config.get_tiers()
        tier_cfg = tiers.get(tier) or tiers.get(self.default_tier)
        tokens, refill_rate, ttl = self._select_limits(tier_cfg)
        
        key = f"rate_limit:{api_key}"
        
        try: 
            data = await self.redis_client.hgetall(key)
        except Exception as e:
            print(f"Redis error: {e}")
            return True, self.capacity, time.time()
        
        if not data:
            tokens = capacity
            last_used = time.time()
        else:
            tokens = float(data.get(b"tokens", b"0").decode())
            last_used = float(data.get(b"last_used", b"0").decode())
            
            elapsed_time = time.time() - last_used
            tokens = min(self.capacity, tokens + elapsed_time * self.refill_rate)
            last_used = time.time()
            
        if tokens < 1:
            return False, tokens, last_used
        else:
            tokens -= 1
            await self.redis_client.hset(key, mapping={
                "tokens": tokens,
                "last_used": last_used
            })
            self.redis_client.expire(key, self.ttl)
            return True, tokens, last_used