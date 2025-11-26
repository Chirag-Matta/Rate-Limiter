import time
from typing import Dict, Any, Tuple
from redis import asyncio as aioredis
from core.health import SystemHealthManager, SystemHealth

class RateLimiter:
    """
    Redis-backed token bucket rate limiter with dynamic load-aware limiting.
    Handles rate limiting logic, token refills, and adapts based on system health.
    """
    
    def __init__(self, redis_client, config_manager, health_manager, default_tier: str = "free"):
        self.redis_client = redis_client
        self.config_manager = config_manager
        self.health_manager = health_manager
        self.default_tier = default_tier
    
    def _get_limits(self, tier: str, tier_cfg: Dict[str, Any], health: SystemHealth) -> Tuple[float, float, int]:
        """
        Get appropriate limits based on tier config and system health.
        
        NORMAL: Use burst capacity to maximize utilization
        DEGRADED: Use degraded limits for free tier, base for paid tiers
        """
        ttl = int(tier_cfg.get("ttl", 60))
        base_config = tier_cfg["base"]
        
        if health == SystemHealth.DEGRADED:
            limit_config = tier_cfg.get("degraded", base_config)
            capacity = float(limit_config["capacity"])
            refill = float(limit_config.get("refill_rate", base_config["refill_rate"]))
            print(f"[DEBUG] DEGRADED mode - Tier: {tier}, Capacity: {capacity}, Refill: {refill}")
        else:
            burst_config = tier_cfg.get("burst", {})
            capacity = float(burst_config.get("capacity", base_config["capacity"]))
            refill = float(base_config["refill_rate"])
            print(f"[DEBUG] NORMAL mode - Tier: {tier}, Burst Capacity: {capacity}, Refill: {refill}")
        
        return capacity, refill, ttl
    
    async def allow_request(self, api_key: str, tier: str) -> Tuple[bool, float, float, float, SystemHealth]:
        """
        Check if request is allowed based on current rate limit and system health.
        
        Returns: (allowed, tokens_remaining, last_used, capacity, health)
        """
        
        health = await self.health_manager.get_health()
        print(f"[DEBUG] Current system health: {health.value}")
        
        tiers = self.config_manager.get_tiers()
        tier_cfg = tiers.get(tier)
        
        if not tier_cfg:
            print(f"[WARNING] Tier '{tier}' not found, using default tier '{self.default_tier}'")
            tier = self.default_tier
            tier_cfg = tiers.get(self.default_tier)
        
        print(f"[DEBUG] Processing request for tier: {tier}")
        
        capacity, refill_rate, ttl = self._get_limits(tier, tier_cfg, health)
        
        key = f"rate_limit:{api_key}"
        
        try: 
            data = await self.redis_client.hgetall(key)
        except Exception as e:
            print(f"[ERROR] Redis error: {e}")
            return True, capacity, time.time(), capacity, health
        
        current_time = time.time()
        
        if not data:
            tokens = capacity - 1
            last_used = current_time
            print(f"[DEBUG] First request - Starting with {tokens}/{capacity} tokens")
        else:
            tokens = float(data.get(b"tokens", b"0").decode())
            last_used = float(data.get(b"last_used", b"0").decode())
            
            elapsed_time = current_time - last_used
            refilled_tokens = tokens + (elapsed_time * refill_rate)
            
            tokens = min(refill_rate, refilled_tokens)
            
            print(f"[DEBUG] Token state - Before: {tokens:.2f}, Elapsed: {elapsed_time:.2f}s, Refilled: {refilled_tokens:.2f}, Capacity: {capacity}, After refill: {tokens:.2f}")
            
            if tokens < 1:
                print(f"[DEBUG] RATE LIMITED - Not enough tokens ({tokens:.2f} < 1)")
                return False, tokens, last_used, capacity, health
            
            tokens -= 1
            last_used = current_time
        
        await self.redis_client.hset(key, mapping={
            "tokens": str(tokens),
            "last_used": str(current_time)
        })
        await self.redis_client.expire(key, ttl)
        
        print(f"[DEBUG] Request ALLOWED - Remaining tokens: {tokens:.2f}/{capacity}")
        
        return True, tokens, last_used, capacity, health