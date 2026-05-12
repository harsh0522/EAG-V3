import os
from pathlib import Path

# Load .env from project root before importing gateway_client
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

from evaluator import run_evaluator


def main():
    idea = input("Enter your project idea: ").strip()
    if not idea:
        print("No idea provided. Exiting.")
        return

    print("\nProcessing your idea through 4 LLM steps...\n")
    result = run_evaluator(idea)
    print(result)


if __name__ == "__main__":
    main()
