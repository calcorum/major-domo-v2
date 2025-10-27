#!/bin/bash
# Process Week 19 Transactions
# Moves all players to their new teams for week 19 transactions

set -e

API_BASE_URL="https://api.sba.manticorum.com"
API_TOKEN="${API_TOKEN:-}"

if [ -z "$API_TOKEN" ]; then
    echo "ERROR: API_TOKEN environment variable not set!"
    exit 1
fi

echo "======================================================================"
echo "PROCESSING WEEK 19 TRANSACTIONS"
echo "======================================================================"

# Transaction data: player_id:new_team_id:player_name
TRANSACTIONS=(
    "11782:502:Fernando Cruz"
    "11566:504:Brandon Pfaadt"
    "12127:529:Masataka Yoshida"
    "12317:531:Sam Hilliard"
    "11984:529:Jose Herrera"
    "11723:531:Dillon Tate"
    "11812:526:Giancarlo Stanton"
    "12199:526:Nicholas Castellanos"
    "11832:528:Hayden Birdsong"
    "11890:528:Andrew McCutchen"
)

SUCCESS_COUNT=0
FAILURE_COUNT=0
TOTAL=${#TRANSACTIONS[@]}

for i in "${!TRANSACTIONS[@]}"; do
    IFS=':' read -r player_id new_team_id player_name <<< "${TRANSACTIONS[$i]}"

    echo ""
    echo "[$((i+1))/$TOTAL] Processing transaction:"
    echo "  Player: $player_name"
    echo "  Player ID: $player_id"
    echo "  New Team ID: $new_team_id"

    response=$(curl -s -w "\n%{http_code}" -X PATCH \
        "${API_BASE_URL}/players/${player_id}?team_id=${new_team_id}" \
        -H "Authorization: Bearer ${API_TOKEN}" \
        -H "Content-Type: application/json")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" -eq 200 ] || [ "$http_code" -eq 204 ]; then
        echo "  ✓ Successfully updated $player_name"
        ((SUCCESS_COUNT++))
    else
        echo "  ✗ Failed to update $player_name (HTTP $http_code)"
        echo "  Response: $body"
        ((FAILURE_COUNT++))
    fi
done

echo ""
echo "======================================================================"
echo "TRANSACTION PROCESSING COMPLETE"
echo "======================================================================"
echo "✓ Successful: $SUCCESS_COUNT/$TOTAL"
echo "✗ Failed: $FAILURE_COUNT/$TOTAL"
echo "======================================================================"

if [ $FAILURE_COUNT -eq 0 ]; then
    exit 0
else
    exit 1
fi
