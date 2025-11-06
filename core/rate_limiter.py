import time
from redis import asyncio as aioredis

class RateLimiter:
    """
    Redis-backed token bucket rate limiter.
    Handles rate limiting logic, token refills, and Redis I/O with timeouts.
    """
    
    def __init__(self,redis_client , capacity=3, refill_rate=1,ttl = 5):
        self.redis_client = redis_client
        self.capacity = capacity
        self.refill_rate = refill_rate  
        self.ttl = ttl
        
    def allow_request(self, key: str) -> tuple(bool, float, float):
        try: 
            data = self.redis.hgetall(key)
        except Exception as e:
            print(f"Redis error: {e}")
            return True, self.capacity, time.time()
        
        if not data:
            tokens = self.capacity
            last_refill = time.time()
        else:
            tokens = float(data.get(b"tokens", b"0").decode())
            last_refill = float(data.get(b"last_refill", b"0").decode())
            
            elapsed_time = time.time() - last_refill
            tokens = min(self.capacity, tokens + elapsed_time * self.refill_rate)
            last_refill = time.time()
            
        if tokens < 1:
            return False, tokens, last_refill
        else:
            tokens -= 1
            self.redis_client.hset(key, mapping={
                "tokens": tokens,
                "last_refill": last_refill
            })
            self.redis_client.expire(key, self.ttl)
            return True, tokens, last_refill