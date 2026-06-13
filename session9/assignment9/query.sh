#!/bin/bash
# Run all 4 comparison queries from the assignment spec, one at a time.
# A 90s pause is inserted between runs so the Gemini free-tier quota
# (observed ~5 req/min) has time to reset before the next run's
# Planner + parallel Researcher nodes start firing.
set -e

cd "$(dirname "$0")"

uv run python run.py "Compare 3 laptops under ₹80,000."

sleep 90

uv run python run.py "Compare 5 AI coding tools by free plan and paid plan."

sleep 90

uv run python run.py "Compare top 3 Hugging Face text-generation models sorted by likes."

sleep 90

uv run python run.py "Compare 5 CNC/VMC training institutes in Bangalore."
