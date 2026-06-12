#!/bin/bash
# Run all assignment 8 task queries one by one.
# Run each line individually (don't just execute the whole file) so you can
# inspect logs / kill+resume between runs as needed.

# --- Task 1: five base queries ---
uv run python run.py "Say hello."

uv run python run.py "Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date, death date, and three key contributions to information theory."

uv run python run.py "Find the populations of London, Paris, Berlin and tell me which two are closest in size."

uv run python run.py "Read /nonexistent/path.txt and tell me what's in it."

uv run python run.py "For Lagos, Cairo, and Kinshasa, find current populations and growth rates and tell me which is growing fastest."
# Ctrl+C this one mid-flight, note the printed session id (s8-xxxxxxxx), then:
uv run python run.py "" --resume s8-xxxxxxxx

# --- Task 2: custom parallel fan-out ---
uv run python run.py "Find the GDP, population, and capital city of Japan, Brazil, and Nigeria, then compare which country has the highest GDP per capita."

# --- Task 3: Critic pass and fail ---
# Run A (pass)
uv run python run.py "Fetch the Wikipedia page for Marie Curie and extract her birth year, nationality, field of study, and major discovery."
# Run B (fail)
uv run python run.py "Fetch the Wikipedia page for a minor historical figure and extract their birth year, nationality, field of study, and major discovery — even if some are not stated on the page."

# --- Task 4: Coder (computation) ---
uv run python run.py "Find the populations of Tokyo, Delhi, and Shanghai, and tell me which two cities have populations that differ by less than 5% of each other."

# --- Task 5: unit_converter skill ---
uv run python run.py "Convert 330 metres to feet."
