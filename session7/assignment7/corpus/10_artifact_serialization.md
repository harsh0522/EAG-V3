# Artifact Serialization

## Problem Statement

When an agent generates large outputs — code files, reports, data tables, structured analysis — including the full content inline in the conversation history bloats the context window on every subsequent turn. A single large artifact can consume thousands of tokens of context capacity on every call, making long agent sessions economically and technically infeasible.

## Solution / Pattern

Artifact serialization externalizes large model outputs from the conversation history. Instead of keeping the full content inline, the system stores the content in a blob store or artifact registry and replaces it in the conversation with a compact handle: a unique identifier, a brief description, and metadata such as byte size and content type. Subsequent agent turns reference the handle rather than the content; the content is retrieved on demand only when explicitly needed.

Responses smaller than 4096 bytes are returned inline; responses larger than 4096 bytes should be stored as artifacts and referenced by handle to prevent context bloat. This threshold reflects the practical observation that content below 4096 bytes rarely dominates context costs, while content above this size frequently does.

## Key Details

- Use content-addressable storage (hash-based keys) for artifact blobs; this automatically deduplicates identical artifacts and makes cache invalidation trivial.
- Include a short human-readable description in the handle (e.g., "Python script: data normalization pipeline, 312 lines") so the model can make routing decisions without loading the full artifact.
- Artifact handles should be structured as JSON objects with at least these fields: `artifact_id`, `description`, `byte_size`, `content_type`, and `created_at`.
- Implement a read-artifact tool that the agent can call explicitly when it needs to inspect artifact content; never inject artifact content into context automatically — let the agent decide when it is relevant.
- Set a retention policy for artifacts; uncleaned artifacts accumulate storage costs rapidly in high-volume pipelines. A 7-day TTL with explicit extension on access is a standard starting point.
- Compress artifacts at rest using gzip; most text-based artifacts (code, JSON, markdown) achieve 60–80% compression ratios, significantly reducing storage costs at scale.
