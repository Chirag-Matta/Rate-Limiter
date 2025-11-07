#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

BASE_URL="http://localhost:8000"
ADMIN_TOKEN="admin_secret_token_change_in_production"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Rate Limiting Test Script${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Function to clear rate limit for specific key
clear_rate_limit() {
    local key=$1
    echo -e "${YELLOW}Clearing rate limit for: $key${NC}"
    redis-cli DEL "rate_limit:$key" > /dev/null
}

# Function to make requests and show headers
make_requests() {
    local tier=$1
    local api_key=$2
    local count=$3
    local description=$4
    
    echo -e "${YELLOW}Testing: $description${NC}"
    echo -e "Tier: $tier | Count: $count requests\n"
    
    # Clear the rate limit before testing
    if [ -z "$api_key" ]; then
        clear_rate_limit "127.0.0.1"
    else
        clear_rate_limit "$api_key"
    fi
    
    sleep 1
    
    success_count=0
    fail_count=0
    
    for i in $(seq 1 $count); do
        if [ -z "$api_key" ]; then
            response=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$BASE_URL/test")
        else
            response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -H "X-API-Key: $api_key" "$BASE_URL/test")
        fi
        
        http_code=$(echo "$response" | grep "HTTP_CODE" | cut -d: -f2)
        
        if [ "$http_code" == "200" ]; then
            echo -e "Request $i: ${GREEN}✓ SUCCESS${NC}"
            ((success_count++))
        else
            echo -e "Request $i: ${RED}✗ RATE LIMITED (429)${NC}"
            ((fail_count++))
        fi
        
        sleep 0.1
    done
    
    echo -e "\n${BLUE}Summary: ${GREEN}$success_count succeeded${NC}, ${RED}$fail_count failed${NC}\n"
    echo ""
}

# Test 1: Check initial system health
echo -e "${BLUE}1. Checking System Health${NC}"
curl -s "$BASE_URL/system/health" | jq '.'
echo -e "\n"

# Test 2: Free tier in NORMAL state (should burst to 20 RPM)
echo -e "${BLUE}2. Testing FREE tier in NORMAL state (burst limit: 20)${NC}"
make_requests "free" "" 25 "Free tier - should allow ~20 requests before limiting"

sleep 2

# Test 3: Pro tier in NORMAL state (should burst to 150 RPM)
echo -e "${BLUE}3. Testing PRO tier in NORMAL state (burst limit: 150)${NC}"
make_requests "pro" "pro" 30 "Pro tier - should allow 30+ requests easily"

sleep 2

# Test 4: Switch to DEGRADED state
echo -e "${BLUE}4. Switching System Health to DEGRADED${NC}"
curl -s -X POST "$BASE_URL/system/health" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  -d '{"status": "DEGRADED"}' | jq '.'
echo -e "\n"

sleep 1

# Test 5: Free tier in DEGRADED state (should drop to 2 RPM)
echo -e "${BLUE}5. Testing FREE tier in DEGRADED state (limit: 2)${NC}"
make_requests "free" "" 10 "Free tier degraded - should only allow ~2 requests"

# Test 6: Pro tier in DEGRADED state (enforced at 100 RPM)
echo -e "${BLUE}6. Testing PRO tier in DEGRADED state (enforced: 100)${NC}"
make_requests "pro" "pro" 50 "Pro tier degraded - strict enforcement at base limit"

# Test 7: Enterprise tier in DEGRADED state (enforced at 1000 RPM)
echo -e "${BLUE}7. Testing ENTERPRISE tier in DEGRADED state (enforced: 1000)${NC}"
make_requests "enterprise" "enterprise" 50 "Enterprise tier - should still get full capacity"

# Test 8: Switch back to NORMAL
echo -e "${BLUE}8. Switching System Health back to NORMAL${NC}"
curl -s -X POST "$BASE_URL/system/health" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  -d '{"status": "NORMAL"}' | jq '.'
echo -e "\n"

sleep 1

# Test 9: Verify free tier bursting is restored
echo -e "${BLUE}9. Testing FREE tier after returning to NORMAL${NC}"
make_requests "free" "" 25 "Free tier - bursting should be restored"

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Testing Complete!${NC}"
echo -e "${BLUE}========================================${NC}"