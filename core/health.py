from enum import Enum
from redis import asyncio as aioredis
from typing import Optional

class SystemHealth(str, Enum):
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"

class SystemHealthManager:
    """
    Manages global system health status stored in Redis.
    """
    
    HEALTH_KEY = "system:health:status"
    DEFAULT_HEALTH = SystemHealth.NORMAL
    
    def __init__(self, redis_client):
        self.redis_client = redis_client
    
    async def get_health(self) -> SystemHealth:
        """Get current system health status from Redis."""
        try:
            status = await self.redis_client.get(self.HEALTH_KEY)
            if status:
                status_str = status.decode('utf-8')
                return SystemHealth(status_str)
            return self.DEFAULT_HEALTH
        except Exception as e:
            print(f"Error reading system health: {e}")
            return self.DEFAULT_HEALTH
    
    async def set_health(self, status: SystemHealth) -> bool:
        """Set system health status in Redis."""
        try:
            await self.redis_client.set(self.HEALTH_KEY, status.value)
            return True
        except Exception as e:
            print(f"Error setting system health: {e}")
            return False
    
    async def is_degraded(self) -> bool:
        """Check if system is in degraded state."""
        health = await self.get_health()
        return health == SystemHealth.DEGRADED