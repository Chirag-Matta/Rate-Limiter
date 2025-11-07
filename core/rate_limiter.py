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
    
    def _get_limits(self, tier_cfg: Dict[str, Any], health: SystemHealth) -> Tuple[float, float, int]:
        """
        Get appropriate limits based on tier config and system health.
        
        NORMAL: Use burst capacity with HIGH refill rate for quick bursts
        DEGRADED: Use degraded limits for free tier, base for paid tiers
        """
        ttl = int(tier_cfg.get("ttl", 60))
        base_config = tier_cfg["base"]
        
        if health == SystemHealth.DEGRADED:
            # In degraded state: use degraded config if available, otherwise base
            limit_config = tier_cfg.get("degraded", base_config)
            capacity = float(limit_config["capacity"])
            refill = float(limit_config.get("refill_rate", base_config["refill_rate"]))
        else:
            # In normal state: use burst capacity
            burst_config = tier_cfg.get("burst", {})
            capacity = float(burst_config.get("capacity", base_config["capacity"]))
            
            # OPTION 1 (RECOMMENDED): High refill rate for true burst capability
            # Use a multiplier of the base refill rate or set to capacity for instant refill
            refill = float(base_config["refill_rate"]) * 10  # 10x faster refill during burst
            
            # OPTION 2: Instant refill (uncomment to use)
            # refill = capacity  # Refills to full capacity in 1 second
        
        print(f"[DEBUG] Tier limits - Health: {health.value}, Capacity: {capacity}, Refill: {refill}")
        
        return capacity, refill, ttl
    
    async def allow_request(self, api_key: str, tier: str) -> Tuple[bool, float, float, float, SystemHealth]:
        """
        Check if request is allowed based on current rate limit and system health.
        
        Returns: (allowed, tokens_remaining, last_used, capacity, health)
        """
        
        # Get current system health
        health = await self.health_manager.get_health()
        
        # Get tier configuration
        tiers = self.config_manager.get_tiers()
        tier_cfg = tiers.get(tier) or tiers.get(self.default_tier)
        
        # Get limits based on system health
        capacity, refill_rate, ttl = self._get_limits(tier_cfg, health)
        
        key = f"rate_limit:{api_key}"
        
        try: 
            data = await self.redis_client.hgetall(key)
        except Exception as e:
            print(f"Redis error: {e}")
            return True, capacity, time.time(), capacity, health
        
        current_time = time.time()
        
        if not data:
            # First request - start with full capacity minus one
            tokens = capacity - 1
            last_used = current_time
        else:
            tokens = float(data.get(b"tokens", b"0").decode())
            last_used = float(data.get(b"last_used", b"0").decode())
            
            # Refill tokens based on elapsed time
            elapsed_time = current_time - last_used
            refilled_tokens = tokens + (elapsed_time * refill_rate)
            
            # Cap at current capacity (handles capacity changes due to health state)
            tokens = min(capacity, refilled_tokens)
            
            print(f"[DEBUG] Token state - Before: {tokens:.2f}, Elapsed: {elapsed_time:.2f}s, Refill rate: {refill_rate}, Added: {elapsed_time * refill_rate:.2f}, After refill: {tokens:.2f}")
            
            if tokens < 1:
                return False, tokens, last_used, capacity, health
            
            tokens -= 1
            last_used = current_time
        
        # Store updated state
        await self.redis_client.hset(key, mapping={
            "tokens": str(tokens),
            "last_used": str(last_used)
        })
        await self.redis_client.expire(key, ttl)
        
        return True, tokens, last_used, capacity, health