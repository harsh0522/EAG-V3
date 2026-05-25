"""Validate agent against the four reference queries in validation.json."""
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

import asyncio
import json
import shutil
import sys

_STATE = Path(__file__).parent / "state"
_ARTIFACTS = _STATE / "artifacts"


def check(final: str, spec: dict, run_iters: int | None = None) -> list[str]:
    failures = []

    # Iteration cap
    if run_iters is not None:
        cap = spec.get("max_iterations", 14)
        if run_iters > cap:
            failures.append(f"exceeded max_iterations: {run_iters} > {cap}")

    # String checks on final answer
    for must in spec.get("must_contain", []):
        if must.lower() not in final.lower():
            failures.append(f"final answer missing: {must!r}")

    must_any = spec.get("must_contain_any_of", [])
    if must_any and not any(m.lower() in final.lower() for m in must_any):
        failures.append(f"final answer must contain one of: {must_any}")

    for must_not in spec.get("must_not_contain_any", []):
        if must_not.lower() in final.lower():
            failures.append(f"final answer must not contain: {must_not!r}")

    # Memory assertions
    mem_file = _STATE / "memory.json"
    memory_items = []
    if mem_file.exists():
        try:
            memory_items = json.loads(mem_file.read_text())
        except Exception:
            pass

    for assertion in spec.get("memory_assertions", []):
        kind = assertion.get("kind")
        min_count = assertion.get("min_count", 1)
        must_have_art = assertion.get("must_have_artifact_id", False)
        descriptor_contains = assertion.get("descriptor_contains", [])

        matching = [
            item for item in memory_items
            if (not kind or item.get("kind") == kind)
            and (not must_have_art or item.get("artifact_id"))
            and all(
                kw.lower() in (item.get("descriptor", "") + " ".join(item.get("keywords", []))).lower()
                for kw in descriptor_contains
            )
        ]
        if len(matching) < min_count:
            failures.append(
                f"memory assertion failed: expected >={min_count} items with kind={kind!r}"
                f" descriptor_contains={descriptor_contains}, found {len(matching)}"
            )

    # Artifact assertions
    artifacts = []
    if _ARTIFACTS.exists():
        for p in _ARTIFACTS.glob("*.json"):
            try:
                artifacts.append(json.loads(p.read_text()))
            except Exception:
                pass

    for assertion in spec.get("artifact_assertions", []):
        min_count = assertion.get("min_count", 1)
        min_size = assertion.get("min_size_bytes", 0)
        matching = [a for a in artifacts if a.get("size_bytes", 0) >= min_size]
        if len(matching) < min_count:
            failures.append(
                f"artifact assertion failed: expected >={min_count} artifacts with "
                f"size>={min_size} bytes, found {len(matching)}"
            )

    return failures


async def main():
    from agent6 import run

    spec_file = Path(__file__).parent / "validation.json"
    spec = json.loads(spec_file.read_text())

    results = []
    total_iters_tracker = {"count": 0}

    # Patch run() to track iterations
    import logger as log
    orig_iter_start = log.iter_start
    def tracking_iter_start(it: int):
        total_iters_tracker["count"] = it
        orig_iter_start(it)
    log.iter_start = tracking_iter_start

    for q in spec["queries"]:
        print(f"\n{'='*60}", flush=True)
        print(f"[validate] Query {q['id']}: {q['name']}", flush=True)
        print(f"[validate] {q['query'][:80]}...", flush=True)

        if q.get("clean_state_before"):
            if _STATE.exists():
                shutil.rmtree(_STATE)
            print("[validate] cleaned state/", flush=True)

        total_iters_tracker["count"] = 0
        try:
            final = await run(q["query"])
        except Exception as e:
            results.append((q["id"], [f"run() raised: {e}"]))
            print(f"[validate] ERROR: {e}", flush=True)
            continue

        iters = total_iters_tracker["count"]
        failures = check(final, q, run_iters=iters)

        # Follow-up query (Query C run 2)
        if q.get("follow_up"):
            fup = q["follow_up"]
            print(f"\n[validate] Follow-up: {fup['query']}", flush=True)
            total_iters_tracker["count"] = 0
            try:
                final2 = await run(fup["query"])
            except Exception as e:
                failures.append(f"follow_up run() raised: {e}")
                final2 = ""
            iters2 = total_iters_tracker["count"]
            failures += check(final2, fup, run_iters=iters2)

        results.append((q["id"], failures))

    print(f"\n{'='*60}", flush=True)
    print("[validate] Results:", flush=True)
    for qid, fs in results:
        status = "PASS" if not fs else "FAIL"
        print(f"  [{qid}] {status}", flush=True)
        for f in fs:
            print(f"       - {f}", flush=True)

    all_pass = all(not fs for _, fs in results)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    asyncio.run(main())
