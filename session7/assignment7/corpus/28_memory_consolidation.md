# Memory Consolidation

## Problem Statement

Without consolidation, agent memory stores grow indefinitely, accumulating redundant, outdated, and contradictory records. Large unmanaged memory stores degrade retrieval precision because irrelevant old memories compete with current, relevant ones for injection slots.

## Solution / Pattern

Memory consolidation is a scheduled process that periodically merges, summarizes, and prunes memory records. It operates in three phases. In the merge phase, near-duplicate records (cosine similarity above 0.92) are merged into a single canonical record with updated metadata. In the summarization phase, clusters of related episodic memories are summarized into a single higher-level semantic memory (e.g., 10 memories about a user's preferences for concise output are consolidated into one semantic fact). In the pruning phase, low-confidence records, stale records that have not been retrieved in 60 days, and records that have been superseded by newer contradictory records are deleted.

Run consolidation weekly for low-volume systems and nightly for high-volume systems.

## Key Details

- Use a clustering algorithm (k-means or HDBSCAN) on memory embeddings to identify groups for summarization; HDBSCAN is preferred because it does not require a pre-specified number of clusters and handles noise points well.
- Summarize clusters of 5 or more episodic memories into a single semantic memory; clusters smaller than 5 are not worth the consolidation overhead and the summary would be poorly grounded.
- Always preserve the original records in an archive before deletion; irreversible consolidation is a data quality risk — the archive allows rollback if consolidation produces incorrect summaries.
- Consolidation quality is measured by retrieval precision before and after: run a fixed query set and measure the fraction of top-5 retrieved memories that are relevant; consolidation should improve this metric, not degrade it.
- Log consolidation statistics (records merged, summarized, pruned, archive size) as operational metrics; a sudden drop in records pruned is an early sign that the similarity threshold is too high and memory bloat is accumulating.
- Schedule consolidation during off-peak hours; the clustering step is computationally expensive and can degrade serving performance if run during high-traffic periods.
