#!/bin/bash

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

BASE_URL="http://localhost:8000"
ADMIN_TOKEN="admin_secret_token_change_in_production"

clear_rate_limit() {
    local key=$1
    if [ -z "$key" ]; then
        redis-cli DEL "rate_limit:127.0.0.1" > /dev/null
    else
        redis-cli DEL "rate_limit:$key" > /dev/null
    fi
}

test_until_limit() {
    local tier_name=$1
    local api_key=$2
    local expected_limit=$3
    local health_state=$4
    
    echo -e "\n${CYAN}┌─────────────────────────────────────────────┐${NC}"
    echo -e "${CYAN}│ ${YELLOW}$tier_name${CYAN} in ${MAGENTA}$health_state${CYAN} (expect: ${GREEN}~$expected_limit${CYAN}) │${NC}"
    echo -e "${CYAN}└─────────────────────────────────────────────┘${NC}"
    
    # Clear rate limit
    if [ -z "$api_key" ]; then
        clear_rate_limit ""
    else
        clear_rate_limit "$api_key"
    fi
    
    sleep 0.3
    
    success=0
    consecutive_fails=0
    request_num=1
    max_requests=$((expected_limit + 10))
    
    while [ $request_num -le $max_requests ]; do
        if [ -z "$api_key" ]; then
            code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/test")
        else
            code=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $api_key" "$BASE_URL/test")
        fi
        
        if [ "$code" == "200" ]; then
            echo -e "${GREEN}✓${NC}"
            ((success++))
            consecutive_fails=0
        else
            echo -e "${RED}✗${NC}"
            ((consecutive_fails++))
            
            if [ $consecutive_fails -ge 3 ]; then
                echo -e "${YELLOW}  (stopped after 3 consecutive failures)${NC}"
                break
            fi
        fi
        
        ((request_num++))
        sleep 0.02
    done
    
    echo -e "\n${CYAN}Result: ${GREEN}$success${CYAN} successful | Expected: ${YELLOW}~$expected_limit${NC}"
    
    lower=$((expected_limit - 1))
    upper=$((expected_limit + 1))
    
    if [ $success -ge $lower ] && [ $success -le $upper ]; then
        echo -e "${GREEN}✓ PASS${NC}"
    else
        echo -e "${RED}✗ FAIL (got $success, expected $lower-$upper)${NC}"
    fi
}

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════╗"
echo "║   QUICK RATE LIMITER TEST (Small Scale)  ║"
echo "╚═══════════════════════════════════════════╝"
echo -e "${NC}"

# ============================================================================
# NORMAL STATE
# ============================================================================
echo -e "\n${BLUE}═══════════════════════════════════════════${NC}"
echo -e "${BLUE}         NORMAL STATE (Burst Mode)         ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════${NC}"

curl -s -X POST "$BASE_URL/system/health" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  -d '{"status": "NORMAL"}' > /dev/null

sleep 0.5

test_until_limit "FREE      " "" 10 "NORMAL"
test_until_limit "PRO       " "pro" 25 "NORMAL"
test_until_limit "ENTERPRISE" "enterprise" 50 "NORMAL"

# ============================================================================
# DEGRADED STATE
# ============================================================================
echo -e "\n${BLUE}═══════════════════════════════════════════${NC}"
echo -e "${BLUE}        DEGRADED STATE (Load Shed)         ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════${NC}"

curl -s -X POST "$BASE_URL/system/health" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  -d '{"status": "DEGRADED"}' > /dev/null

sleep 0.5

test_until_limit "FREE      " "" 2 "DEGRADED"
test_until_limit "PRO       " "pro" 15 "DEGRADED"
test_until_limit "ENTERPRISE" "enterprise" 30 "DEGRADED"

# ============================================================================
# SUMMARY TABLE
# ============================================================================
echo -e "\n${BLUE}═══════════════════════════════════════════${NC}"
echo -e "${BLUE}              SUMMARY TABLE                ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════${NC}"
echo -e ""
echo -e "${CYAN}Tier        │ Normal  │ Degraded │ Impact${NC}"
echo -e "────────────┼─────────┼──────────┼────────"
echo -e "${YELLOW}Free        ${NC}│  ${GREEN}~10${NC}    │   ${RED}~2${NC}     │ ${RED}-80%${NC}"
echo -e "${YELLOW}Pro         ${NC}│  ${GREEN}~25${NC}    │   ${GREEN}~15${NC}    │ ${YELLOW}-40%${NC}"
echo -e "${YELLOW}Enterprise  ${NC}│  ${GREEN}~50${NC}    │   ${GREEN}~30${NC}    │ ${YELLOW}-40%${NC}"
echo -e ""
echo -e "${GREEN}Key Takeaway:${NC}"
echo -e "  • Free tier gets hit hardest in degraded state"
echo -e "  • Paid tiers maintain better service quality"
echo -e "  • Enterprise has highest absolute capacity"
echo -e ""
echo -e "${GREEN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║            TESTS COMPLETED!               ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}\n"