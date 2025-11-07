from fastapi import FastAPI, Request, Response, HTTPException, Header
from pydantic import BaseModel
import time
from typing import Optional
from redis import asyncio as aioredis
from core.rate_limiter import RateLimiter
from core.config import ConfigManager
from core.health import SystemHealthManager, SystemHealth
from middleware.rate_limiter_mw import RateLimiterMiddleware

app = FastAPI()

# Admin authentication token (in production, use proper auth)
ADMIN_TOKEN = "admin_secret_token_change_in_production"

class HealthStatusUpdate(BaseModel):
    status: SystemHealth

@app.on_event("startup")
async def startup_event():
    # Initialize shared Redis client
    app.state.redis = await aioredis.from_url("redis://localhost")
    
    # Initialize config manager
    app.state.config_manager = ConfigManager()
    
    # Initialize system health manager
    app.state.health_manager = SystemHealthManager(app.state.redis)
    
    # Initialize rate limiter with system health awareness
    app.state.rate_limiter = RateLimiter(
        redis_client=app.state.redis,
        config_manager=app.state.config_manager,
        health_manager=app.state.health_manager,
        default_tier="free"
    )
    
    # Set initial system health to NORMAL
    await app.state.health_manager.set_health(SystemHealth.NORMAL)
    
    print("[INIT] Redis connected & components initialized ✅")
    print("[INIT] System health set to NORMAL ✅")

# Add middleware after defining app
app.add_middleware(RateLimiterMiddleware)

@app.on_event("shutdown")
async def shutdown_event():
    redis = app.state.redis
    await redis.close()
    await redis.connection_pool.disconnect()
    print("[SHUTDOWN] Redis connection closed ✅")

@app.get("/")
async def root():
    return {"message": "API is running!", "timestamp": time.time()}

@app.get("/health")
async def health():
    health = await app.state.health_manager.get_health()
    return {
        "status": "healthy",
        "redis": "connected",
        "health": health.value
    }

@app.post("/system/health")
async def update_health(
    health_update: HealthStatusUpdate,
    x_admin_token: Optional[str] = Header(None)
):
    """
    Protected admin endpoint to update system health status.
    
    Usage:
        curl -X POST http://localhost:8000/system/health \
             -H "Content-Type: application/json" \
             -H "X-Admin-Token: admin_secret_token_change_in_production" \
             -d '{"status": "DEGRADED"}'
    """
    
    # Verify admin token
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    
    # Update system health
    success = await app.state.health_manager.set_health(health_update.status)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update system health")
    
    print(f"[ADMIN] System health updated to {health_update.status.value} ✅")
    
    return {
        "message": "System health updated successfully",
        "previous_status": (await app.state.health_manager.get_health()).value,
        "new_status": health_update.status.value,
        "timestamp": time.time()
    }

@app.get("/system/health")
async def get_health():
    """
    Public endpoint to check current system health status.
    """
    health = await app.state.health_manager.get_health()
    return {
        "health": health.value,
        "timestamp": time.time()
    }

@app.get("/test")
async def test_endpoint():
    """Test endpoint to verify rate limiting is working."""
    return {
        "message": "Request successful!",
        "timestamp": time.time()
    }