# Dynamic Load-Aware Rate Limiter

A production-ready, Redis-backed rate limiting system with dynamic load adaptation. This system automatically adjusts rate limits based on system health, providing burst capacity during normal operations and protecting resources during degraded states.

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [How It Works](#-how-it-works)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [API Reference](#-api-reference)
- [Testing](#-testing)
- [Docker Deployment](#-docker-deployment)
- [Monitoring](#-monitoring)
- [Performance](#-performance)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

## ✨ Features

### Core Capabilities

- **🚀 Token Bucket Algorithm**: Efficient, smooth rate limiting with configurable capacity and refill rates
- **🔄 Dynamic Load Adaptation**: Automatically adjusts limits based on system health (NORMAL/DEGRADED)
- **💎 Multi-Tier Support**: Three built-in tiers (Free, Pro, Enterprise) with different limits
- **⚡ Burst Capacity**: Allows traffic bursts during normal operations for better user experience
- **🛡️ Load Shedding**: Protects system resources by reducing free tier limits during degraded states
- **📊 Real-time Metrics**: Rate limit headers in every response for client-side monitoring
- **🔐 API Key Authentication**: Tier-based access control with configurable mappings
- **🏥 Health Management**: Admin endpoint for system health state transitions
- **🐳 Docker Ready**: Complete containerization with docker-compose setup
- **⚙️ Configuration Hot-Reload**: Cached configuration with TTL-based refresh

### Technical Highlights

- **Asynchronous**: Built on FastAPI and async Redis for high performance
- **Distributed**: Redis-backed storage for multi-instance deployments
- **Scalable**: Designed to handle high request volumes
- **Fault Tolerant**: Graceful degradation on Redis failures
- **Observable**: Comprehensive logging and debugging capabilities
- **Production Ready**: Health checks, retry logic, and proper error handling

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Request                        │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │            RateLimiterMiddleware                      │  │
│  │  • Extract API Key                                    │  │
│  │  • Determine Tier                                     │  │
│  │  • Check Rate Limit                                   │  │
│  │  • Add Response Headers                               │  │
│  └────────────┬─────────────────────────────────────────┘  │
│               │                                              │
│               ▼                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              RateLimiter Core                         │  │
│  │  • Token Bucket Logic                                 │  │
│  │  • Dynamic Limit Selection                            │  │
│  │  • Token Refill Calculation                           │  │
│  └────────────┬──────────────┬──────────────────────────┘  │
│               │              │                              │
│               ▼              ▼                              │
│  ┌────────────────┐  ┌─────────────────┐                  │
│  │ ConfigManager  │  │ HealthManager   │                  │
│  │ • Load Tiers   │  │ • Get Health    │                  │
│  │ • Load API Keys│  │ • Set Health    │                  │
│  │ • Cache w/ TTL │  │ • Health Checks │                  │
│  └────────────────┘  └─────────────────┘                  │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
              ┌───────────────────────────┐
              │     Redis Storage         │
              │  • Rate Limit State       │
              │  • System Health Status   │
              │  • Distributed Locking    │
              └───────────────────────────┘
```

### Component Overview

#### 1. **RateLimiterMiddleware** (`middleware/rate_limiter_mw.py`)
- Intercepts all incoming requests
- Extracts API key from `X-API-Key` header
- Determines user tier (free/pro/enterprise)
- Enforces rate limits before reaching endpoints
- Adds rate limit headers to responses

#### 2. **RateLimiter** (`core/rate_limiter.py`)
- Implements token bucket algorithm
- Calculates token refills based on elapsed time
- Selects appropriate limits based on system health
- Manages Redis state for each API key/IP

#### 3. **SystemHealthManager** (`core/health.py`)
- Tracks global system health (NORMAL/DEGRADED)
- Stores health state in Redis
- Provides health check interface

#### 4. **ConfigManager** (`core/config.py`)
- Loads tier configurations from JSON
- Manages API key to tier mappings
- Implements caching with TTL for performance

## 🔧 How It Works

### Token Bucket Algorithm

Each user gets a "bucket" of tokens that refills over time:

1. **Initial State**: Bucket starts with `capacity - 1` tokens
2. **Token Consumption**: Each request consumes 1 token
3. **Token Refill**: Tokens refill at `refill_rate` per second
4. **Capacity Cap**: Tokens never exceed the current capacity
5. **Rate Limit**: Request denied when tokens < 1

```python
tokens_available = min(capacity, current_tokens + (elapsed_time * refill_rate))
if tokens_available >= 1:
    allow_request()
    tokens_available -= 1
else:
    deny_request()  # 429 Too Many Requests
```

### Dynamic Load Adaptation

The system operates in two modes:

#### 🟢 NORMAL Mode (Burst Capacity)
- **Goal**: Maximize user experience
- **Strategy**: Allow burst traffic to improve responsiveness
- **Implementation**: Uses `burst.capacity` with base `refill_rate`

```
Free Tier:       10 requests burst (5 base + 5 burst)
Pro Tier:        25 requests burst (15 base + 10 burst)
Enterprise Tier: 50 requests burst (30 base + 20 burst)
```

#### 🔴 DEGRADED Mode (Load Shedding)
- **Goal**: Protect system resources
- **Strategy**: Reduce free tier aggressively, maintain paid tiers
- **Implementation**: Uses `degraded` config for free, base for paid

```
Free Tier:       2 requests (-80% impact)
Pro Tier:        15 requests (-40% impact)
Enterprise Tier: 30 requests (-40% impact)
```

### Multi-Tier System

| Tier       | Normal Capacity | Degraded Capacity | Refill Rate | TTL  |
|------------|----------------|-------------------|-------------|------|
| Free       | 10 (burst)     | 2                 | 1 req/sec   | 30s  |
| Pro        | 25 (burst)     | 15                | 2 req/sec   | 60s  |
| Enterprise | 50 (burst)     | 30                | 5 req/sec   | 120s |

## 📦 Installation

### Prerequisites

- Python 3.11 or higher
- Redis 7.0 or higher
- Docker & Docker Compose (for containerized deployment)

### Option 1: Local Installation

```bash
# 1. Clone the repository
git clone https://github.com/Chirag-Matta/dynamic-rate-limiter.git
cd dynamic-rate-limiter

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start Redis
redis-server

# 5. Run the application
uvicorn main:app --reload

# 6. Verify installation
curl http://localhost:8000/health
```

### Option 2: Docker Installation

```bash
# 1. Clone the repository
git clone https://github.com/Chirag-Matta/dynamic-rate-limiter.git
cd dynamic-rate-limiter

# 2. Build and start services
docker-compose up --build -d

# 3. Verify installation
curl http://localhost:8000/health

# 4. View logs
docker-compose logs -f
```

## ⚙️ Configuration

### Tier Configuration (`config/tiers.json`)

```json
{
  "free": {
    "base": { 
      "capacity": 5,      // Base bucket capacity
      "refill_rate": 1    // Tokens per second
    },
    "burst": { 
      "capacity": 10      // Burst capacity in NORMAL mode
    },
    "degraded": { 
      "capacity": 2,      // Capacity in DEGRADED mode
      "refill_rate": 0.5  // Slower refill in DEGRADED
    },
    "ttl": 30             // Redis key expiration (seconds)
  },
  "pro": {
    "base": { "capacity": 15, "refill_rate": 2 },
    "burst": { "capacity": 25 },
    "degraded": { "capacity": 15, "refill_rate": 2 },
    "ttl": 60
  },
  "enterprise": {
    "base": { "capacity": 30, "refill_rate": 5 },
    "burst": { "capacity": 50 },
    "degraded": { "capacity": 30, "refill_rate": 5 },
    "ttl": 120
  }
}
```

### API Key Mapping (`config/api_keys.json`)

**Production Note**: Use secure, randomly generated API keys:

### Environment Variables

Create a `.env` file:

```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379

# Security
ADMIN_TOKEN=your_secure_admin_token_here

# Application
CONFIG_TTL=20
DEFAULT_TIER=free
```

## 🚀 Usage

### Basic Request (Free Tier)

```bash
curl http://localhost:8000/test
```

Response:
```json
{
  "message": "Request successful!",
  "timestamp": 1699564800.123
}
```

Headers:
```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 9
X-RateLimit-Tier: free
X-System-Health: NORMAL
```

### Request with API Key (Pro Tier)

```bash
curl -H "X-API-Key: pro" http://localhost:8000/test
```

Headers:
```
X-RateLimit-Limit: 25
X-RateLimit-Remaining: 24
X-RateLimit-Tier: pro
X-System-Health: NORMAL
```

### Rate Limited Response

When rate limit is exceeded:

```bash
HTTP/1.1 429 Too Many Requests
Retry-After: 1
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1699564801
X-RateLimit-Tier: free
X-System-Health: NORMAL

Too Many Requests
```

### Admin Operations

#### Check System Health

```bash
curl http://localhost:8000/system/health
```

Response:
```json
{
  "health": "NORMAL",
  "timestamp": 1699564800.123
}
```

#### Set System to DEGRADED

```bash
curl -X POST http://localhost:8000/system/health \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: admin_secret_token_change_in_production" \
  -d '{"status": "DEGRADED"}'
```

Response:
```json
{
  "message": "System health updated successfully",
  "previous_status": "NORMAL",
  "new_status": "DEGRADED",
  "timestamp": 1699564800.456
}
```

#### Restore to NORMAL

```bash
curl -X POST http://localhost:8000/system/health \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: admin_secret_token_change_in_production" \
  -d '{"status": "NORMAL"}'
```

## 📚 API Reference

### Endpoints

#### `GET /`
Root endpoint showing API status.

**Response:**
```json
{
  "message": "API is running!",
  "timestamp": 1699564800.123
}
```

---

#### `GET /health`
Application health check.

**Response:**
```json
{
  "status": "healthy",
  "redis": "connected",
  "health": "NORMAL"
}
```

---

#### `GET /test`
Test endpoint for rate limiting verification.

**Headers:**
- `X-API-Key` (optional): API key for tier identification

**Response:**
```json
{
  "message": "Request successful!",
  "timestamp": 1699564800.123
}
```

**Response Headers:**
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Tier`: User tier (free/pro/enterprise)
- `X-System-Health`: Current system health (NORMAL/DEGRADED)
- `X-Processing-Time`: Request processing time

---

#### `GET /system/health`
Get current system health status.

**Response:**
```json
{
  "health": "NORMAL",
  "timestamp": 1699564800.123
}
```

---

#### `POST /system/health`
Update system health status (Admin only).

**Headers:**
- `X-Admin-Token`: Admin authentication token (required)
- `Content-Type`: application/json

**Request Body:**
```json
{
  "status": "DEGRADED"  // or "NORMAL"
}
```

**Response:**
```json
{
  "message": "System health updated successfully",
  "previous_status": "NORMAL",
  "new_status": "DEGRADED",
  "timestamp": 1699564800.456
}
```

**Status Codes:**
- `200`: Success
- `403`: Invalid admin token
- `500`: Failed to update health

### Rate Limit Response Headers

All API responses include these headers:

| Header                   | Description                           | Example    |
|--------------------------|---------------------------------------|------------|
| `X-RateLimit-Limit`      | Maximum requests in current capacity  | `10`       |
| `X-RateLimit-Remaining`  | Requests remaining in bucket          | `7`        |
| `X-RateLimit-Reset`      | Unix timestamp when limit resets      | `1699564860` |
| `X-RateLimit-Tier`       | Current user tier                     | `free`     |
| `X-System-Health`        | Current system health state           | `NORMAL`   |
| `X-Processing-Time`      | Request processing duration           | `0.0234s`  |
| `Retry-After`            | Seconds to wait (429 only)            | `1`        |

## 🧪 Testing

### Automated Test Scripts

#### Quick Test (`debug_rate_limiter.sh`)

Tests all tiers in both NORMAL and DEGRADED states:

```bash
chmod +x debug_rate_limiter.sh
./debug_rate_limiter.sh
```

Output:
```
╔═══════════════════════════════════════════╗
║   QUICK RATE LIMITER TEST (Small Scale)  ║
╚═══════════════════════════════════════════╝

═══════════════════════════════════════════
         NORMAL STATE (Burst Mode)         
═══════════════════════════════════════════

┌─────────────────────────────────────────────┐
│ FREE       in NORMAL (expect: ~10)          │
└─────────────────────────────────────────────┘
✓✓✓✓✓✓✓✓✓✓✗✗✗

Result: 10 successful | Expected: ~10
✓ PASS
```

#### Comprehensive Test (`test_rate_limiting.sh`)

Detailed testing with header inspection:

```bash
chmod +x test_rate_limiting.sh
./test_rate_limiting.sh
```

#### Simple Test (`simple_test.sh`)

Basic functionality verification:

```bash
chmod +x simple_test.sh
./simple_test.sh
```

### Manual Testing

#### Test Free Tier Burst

```bash
# Clear existing limits
redis-cli DEL "rate_limit:127.0.0.1"

# Make 15 requests rapidly
for i in {1..15}; do
  echo "Request $i:"
  curl -s -i http://localhost:8000/test | grep -E "HTTP|X-RateLimit"
  sleep 0.1
done
```

Expected: ~10 succeed, then 429 responses

#### Test Pro Tier

```bash
# Clear limits
redis-cli DEL "rate_limit:pro"

# Test with API key
for i in {1..30}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "X-API-Key: pro" \
    http://localhost:8000/test
done
```

Expected: ~25 succeed (200), then 5 fail (429)

#### Test Health State Transition

```bash
# Start in NORMAL
curl -X POST http://localhost:8000/system/health \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: admin_secret_token_change_in_production" \
  -d '{"status": "NORMAL"}'

# Clear limits
redis-cli DEL "rate_limit:127.0.0.1"

# Test free tier (should get ~10)
for i in {1..15}; do
  curl -s -o /dev/null -w "%{http_code} " http://localhost:8000/test
done
echo ""

# Switch to DEGRADED
curl -X POST http://localhost:8000/system/health \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: admin_secret_token_change_in_production" \
  -d '{"status": "DEGRADED"}'

# Clear limits
redis-cli DEL "rate_limit:127.0.0.1"

# Test again (should get ~2)
for i in {1..15}; do
  curl -s -o /dev/null -w "%{http_code} " http://localhost:8000/test
done
echo ""
```

### Unit Testing

Create `tests/test_rate_limiter.py`:

```python
import pytest
from core.rate_limiter import RateLimiter
from core.health import SystemHealth

@pytest.mark.asyncio
async def test_token_refill(rate_limiter):
    # Test token refill calculation
    pass

@pytest.mark.asyncio
async def test_burst_capacity(rate_limiter):
    # Test burst mode in NORMAL state
    pass

@pytest.mark.asyncio
async def test_degraded_limits(rate_limiter):
    # Test load shedding in DEGRADED state
    pass
```

Run tests:
```bash
pytest tests/ -v
```

## 🐳 Docker Deployment

### Development

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f app

# Restart after code changes
docker-compose restart app

# Stop services
docker-compose down
```

### Production

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    networks:
      - internal
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M

  app:
    build: .
    environment:
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
      - ADMIN_TOKEN=${ADMIN_TOKEN}
    networks:
      - internal
      - external
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1'
          memory: 1G

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    networks:
      - external
    depends_on:
      - app

networks:
  internal:
    driver: overlay
  external:
    driver: bridge

volumes:
  redis_data:
```

Deploy:
```bash
docker stack deploy -c docker-compose.prod.yml rate_limiter
```

### Kubernetes Deployment

Create `k8s/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rate-limiter
spec:
  replicas: 3
  selector:
    matchLabels:
      app: rate-limiter
  template:
    metadata:
      labels:
        app: rate-limiter
    spec:
      containers:
      - name: app
        image: rate-limiter:latest
        ports:
        - containerPort: 8000
        env:
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: redis-secret
              key: url
        resources:
          limits:
            memory: "1Gi"
            cpu: "1000m"
          requests:
            memory: "512Mi"
            cpu: "500m"
```

## 📊 Monitoring

### Logging

Application logs include:

```
[INIT] Redis connected successfully ✅
[INIT] System health set to NORMAL ✅
[MIDDLEWARE]: Request from 127.0.0.1, tier: free
[DEBUG] NORMAL mode - Tier: free, Burst Capacity: 10, Refill: 1
[DEBUG] Request ALLOWED - Remaining tokens: 9.00/10
[MIDDLEWARE]: ✓ Request processed (tier: free, remaining: 9.00/10)
```

### Metrics Endpoint

Add Prometheus metrics:

```python
from prometheus_client import Counter, Histogram, Gauge

requests_total = Counter('rate_limiter_requests_total', 
                        'Total requests', ['tier', 'status'])
requests_duration = Histogram('rate_limiter_request_duration_seconds',
                             'Request duration')
rate_limit_remaining = Gauge('rate_limiter_tokens_remaining',
                            'Tokens remaining', ['tier'])
```

### Redis Monitoring

```bash
# Monitor Redis operations
redis-cli MONITOR

# Check memory usage
redis-cli INFO memory

# View all rate limit keys
redis-cli KEYS "rate_limit:*"

# Get specific bucket state
redis-cli HGETALL "rate_limit:pro"
```

### Application Metrics

Key metrics to track:

- **Request Rate**: Requests per second by tier
- **Rate Limit Hit Rate**: Percentage of 429 responses
- **Token Utilization**: Average tokens remaining
- **Health State Duration**: Time in NORMAL vs DEGRADED
- **Response Time**: P50, P95, P99 latencies

## ⚡ Performance

### Benchmarks

System tested on:
- **Hardware**: 4 CPU cores, 8GB RAM
- **Redis**: Local instance
- **Tool**: Apache Bench

```bash
# Free tier (10 req burst)
ab -n 1000 -c 10 http://localhost:8000/test
Requests per second:    245.67 [#/sec]
Time per request:       40.705 [ms]

# Pro tier (25 req burst)
ab -n 1000 -c 10 -H "X-API-Key: pro" http://localhost:8000/test
Requests per second:    267.43 [#/sec]
Time per request:       37.389 [ms]
```

### Optimization Tips

1. **Redis Connection Pooling**
   ```python
   redis_pool = aioredis.ConnectionPool.from_url(
       REDIS_URL, 
       max_connections=50
   )
   ```

2. **Config Caching**
   - Already implemented with TTL
   - Adjust TTL based on update frequency

3. **Batch Operations**
   - Use Redis pipelines for multiple operations
   - Reduce network round trips

4. **Rate Limit Key TTL**
   - Automatically expires unused keys
   - Prevents memory bloat

## 🔍 Troubleshooting

### Issue: Rate limits not working

**Symptoms**: All requests succeed, no 429 responses

**Solutions**:
```bash
# Check Redis connection
redis-cli PING

# Verify rate limit keys are being created
redis-cli KEYS "rate_limit:*"

# Check application logs
docker-compose logs app | grep "rate_limit"

# Ensure middleware is loaded
curl -v http://localhost:8000/test | grep X-RateLimit
```

### Issue: System always in DEGRADED state

**Symptoms**: Free tier limited to 2 requests

**Solutions**:
```bash
# Check current health
curl http://localhost:8000/system/health

# Reset to NORMAL
curl -X POST http://localhost:8000/system/health \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: admin_secret_token_change_in_production" \
  -d '{"status": "NORMAL"}'

# Check Redis value
redis-cli GET "system:health:status"
```

### Issue: Redis connection errors

**Symptoms**: `Connection refused` errors

**Solutions**:
```bash
# Check if Redis is running
docker-compose ps redis
redis-cli PING

# Check Redis logs
docker-compose logs redis

# Verify REDIS_URL
echo $REDIS_URL

# Test connection
redis-cli -u redis://localhost:6379 PING
```

### Issue: API key not recognized

**Symptoms**: Always using free tier despite API key

**Solutions**:
```bash
# Verify API key in config
cat config/api_keys.json

# Check header format
curl -H "X-API-Key: pro" -v http://localhost:8000/test 2>&1 | grep "X-API-Key"

# Check logs for tier detection
docker-compose logs app | grep "tier:"

# Clear config cache (wait for TTL or restart)
docker-compose restart app
```

### Issue: Burst capacity not working

**Symptoms**: Hitting limit at base capacity

**Solutions**:
```bash
# Check system health (must be NORMAL for burst)
curl http://localhost:8000/system/health

# Verify tier config
cat config/tiers.json | jq '.free.burst'

# Check debug logs
docker-compose logs app | grep "Burst Capacity"
```

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

### Development Setup

```bash
# Fork and clone
git clone https://github.com/Chirag-Matta/dynamic-rate-limiter.git
cd dynamic-rate-limiter

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dev dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v

# Format code
black .
isort .

# Lint
flake8 .
mypy .
```

### Submitting Changes

1. Create a feature branch: `git checkout -b feature/amazing-feature`
2. Make your changes and add tests
3. Ensure all tests pass: `pytest tests/ -v`
4. Format code: `black . && isort .`
5. Commit: `git commit -m 'Add amazing feature'`
6. Push: `git push origin feature/amazing-feature`
7. Open a Pull Request

### Code Style

- Follow PEP 8 guidelines
- Use type hints
- Add docstrings to functions/classes
- Write tests for new features
- Update documentation

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- FastAPI for the excellent web framework
- Redis for reliable in-memory storage
- The Python asyncio community

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Chirag-Matta/dynamic-rate-limiter/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Chirag-Matta/dynamic-rate-limiter/discussions)
- **Email**: mattachirag980@gmail.com