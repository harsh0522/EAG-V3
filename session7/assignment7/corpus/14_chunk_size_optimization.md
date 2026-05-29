# Chunk Size Optimization

## Problem Statement

Chunking documents into segments for indexing involves a precision-recall trade-off that has no universally optimal answer. Chunks that are too small miss important context; chunks that are too large dilute the query signal with irrelevant content and exceed the token budget allocated for retrieved context.

## Solution / Pattern

Optimal chunk size depends on the query distribution and document structure. For factual question-answering over structured documents (technical manuals, legal filings), use smaller chunks of 150–300 tokens to maximize retrieval precision. For narrative documents (research papers, reports), use larger chunks of 400–600 tokens to preserve argumentative context. For code retrieval, chunk at logical boundaries (function definitions, class declarations) regardless of token count.

Use overlapping chunks: set overlap to 10–15% of chunk size. An overlap of 50 tokens on 400-token chunks means that a fact appearing near a chunk boundary will be fully captured in at least one chunk rather than split across two partial chunks.

## Key Details

- Evaluate chunk size by measuring answer accuracy on a held-out QA set at chunk sizes of 128, 256, 512, and 1024 tokens; plot the accuracy-size curve and select the inflection point where accuracy plateaus.
- Use recursive text splitters that respect natural boundaries (paragraph breaks, section headers, sentence endings) rather than hard token-count splits; hard splits mid-sentence degrade embedding quality because sentence-boundary cues carry structural information.
- "Parent-child" chunking stores large parent chunks for context and indexes small child chunks for retrieval; when a child chunk is retrieved, the full parent is injected into the prompt, balancing retrieval precision with generative context richness.
- For tables and structured data, do not split rows across chunks; tables should be kept intact even if they exceed the target chunk size, because partial tables are uninterpretable.
- Re-chunk and re-index when you change embedding models; different models have different optimal chunk sizes due to their attention window characteristics and tokenization.
