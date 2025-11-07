#!/bin/bash

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

BASE_URL="http://localhost:8000"
ADMIN_TOKEN="admin_secret_token_change_in_production"

test_with_fresh_state() {
    tier_name=$1
    api_key=$2
    num_requests=$3
    expected_success=$4
    
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Testing: $tier_name${NC}"
    echo -e "${BLUE}========================================${NC}"
    
    # Clear Redis for this specific key
    if [ -z "$api_key" ]; then
        redis-cli DEL "rate_limit:127.0.0.1" > /dev/null
        echo -e "${YELLOW}Cleared rate limit for IP: 127.0.0.1${NC}"
    else
        redis-cli DEL "rate_limit:$api_key" > /dev/null
        echo -e "${YELLOW}Cleared rate limit for key: $api_key${NC}"
    fi
    
    sleep 1
    
    # Get first request to check headers
    echo -e "\n${YELLOW}Checking rate limit headers:${NC}"
    if [ -z "$api_key" ]; then
        curl -s -v "$BASE_URL/test" 2>&1 | grep -E "X-RateLimit|X-System" | head -5
    else
        curl -s -v -H "X-API-Key: $api_key" "$BASE_URL/test" 2>&1 | grep -E "X-RateLimit|X-System" | head -5
    fi
    
    echo -e "\n${YELLOW}Making $num_requests requests...${NC}\n"
    
    success=0
    fail=0
    
    for i in $(seq 1 $num_requests); do
        if [ -z "$api_key" ]; then
            code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/test")
        else
            code=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $api_key" "$BASE_URL/test")
        fi
        
        if [ "$code" == "200" ]; then
            echo -e "Request $i: ${GREEN}✓${NC}"
            ((success++))
        else
            echo -e "Request $i: ${RED}✗${NC}"
            ((fail++))
        fi
        sleep 0.05
    done
    
    echo -e "\n${BLUE}Results:${NC}"
    echo -e "  Success: ${GREEN}$success${NC}/$num_requests"
    echo -e "  Failed:  ${RED}$fail${NC}/$num_requests"
    echo -e "  Expected: ~${YELLOW}$expected_success${NC} successes"
    
    if [ $success -ge $expected_success ]; then
        echo -e "  ${GREEN}✓ PASS${NC}\n"
    else
        echo -e "  ${RED}✗ FAIL (got $success, expected at least $expected_success)${NC}\n"
    fi
}

# Set system to NORMAL
echo -e "${BLUE}Setting system health to NORMAL...${NC}"
curl -s -X POST "$BASE_URL/system/health" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  -d '{"status": "NORMAL"}' | jq -r '.new_status'
echo ""

# Test 1: Free tier - should burst to 20
test_with_fresh_state "Free Tier (NORMAL - Burst: 20)" "" 25 18

sleep 2

# Test 2: Pro tier - should burst to 150
test_with_fresh_state "Pro Tier (NORMAL - Burst: 150)" "pro" 50 48

sleep 2

# Test 3: Enterprise tier - should handle 1000
test_with_fresh_state "Enterprise Tier (NORMAL - 1000)" "enterprise" 50 48

sleep 2

# Switch to DEGRADED
echo -e "${BLUE}Setting system health to DEGRADED...${NC}"
curl -s -X POST "$BASE_URL/system/health" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  -d '{"status": "DEGRADED"}' | jq -r '.new_status'
echo ""

sleep 2

# Test 4: Free tier - should drop to 2
test_with_fresh_state "Free Tier (DEGRADED - Limit: 2)" "" 10 2

sleep 2

# Test 5: Pro tier - should enforce 100
test_with_fresh_state "Pro Tier (DEGRADED - Limit: 100)" "pro" 50 48

sleep 2

# Test 6: Enterprise tier - still 1000
test_with_fresh_state "Enterprise Tier (DEGRADED - Limit: 1000)" "enterprise" 50 48

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}All tests complete!${NC}"
echo -e "${GREEN}========================================${NC}"