#!/usr/bin/env bash
# Countdown helper — run this between queries to let the Gemini free-tier
# quota window roll over before retrying. Usage: ./wait_quota.sh [seconds]
secs="${1:-90}"
for ((i=secs; i>0; i--)); do
    printf "\rWaiting for Gemini quota to reset... %3ds remaining " "$i"
    sleep 1
done
echo -e "\rDone waiting — go ahead and run your next query.            "
