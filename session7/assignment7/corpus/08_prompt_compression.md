# Prompt Compression

## Problem Statement

As applications scale, prompt token costs compound rapidly. A pipeline processing 100,000 requests per day with a 2,000-token prompt incurs 200 million input tokens daily. At $3 per million tokens, that is $600 per day in prompt costs alone — before output tokens. Reducing prompt size without sacrificing quality is a first-order engineering priority.

## Solution / Pattern

Prompt compression replaces verbose natural language instructions and context with information-dense equivalents. Three approaches apply at different layers. Lexical compression removes stop words, redundant phrases, and verbose connectives from fixed instruction sections — tools like LLMLingua achieve 2–4x compression with less than 5% performance degradation on standard benchmarks. Semantic compression replaces lengthy context passages with embedding-retrieved summaries of only the relevant portions. Structural compression replaces multi-sentence instructions with compact schema definitions or shorthand notations.

Apply compression to the fixed portions of your prompt first (system prompts, instructions, examples) before touching dynamic content. Fixed portions are repeated on every call and offer the highest compression leverage.

## Key Details

- Measure prompt compression impact by comparing task accuracy on a 500-example evaluation set before and after compression; accept compression only if accuracy drops less than 2 percentage points.
- LLMLingua-style token pruning works best on retrieval-augmented generation contexts where the retrieved passages are long and only partially relevant; it is less effective on few-shot examples where each token carries high information density.
- Compressing few-shot examples typically degrades performance more than compressing retrieved context; prioritize context compression and preserve examples at full fidelity.
- Cache compressed versions of static context documents in a key-value store indexed by document hash; recomputing compression on every request wastes CPU and adds 20–50ms of latency.
- Aim for a target of 60–70% of original prompt size as the compression goal; beyond this, accuracy degradation typically accelerates sharply.
