# Retrieval-Augmented Generation

## Problem Statement

LLMs have fixed knowledge cutoffs and cannot reliably recall specific facts, internal documents, or recent information without hallucinating plausible-sounding but incorrect details. Asking a model to answer questions about proprietary or up-to-date content without grounding produces confidently wrong answers.

## Solution / Pattern

Retrieval-Augmented Generation (RAG) grounds model responses in retrieved document chunks. At query time, the user's question is embedded and compared against an index of pre-embedded document chunks. The top-k most relevant chunks are injected into the prompt as context, and the model is instructed to answer using only the provided context and to explicitly cite which chunks support each claim.

The retrieval step and the generation step should be treated as separately optimizable components. Improving retrieval recall (getting the right chunks) typically delivers more quality improvement than improving generation quality in isolation.

## Key Details

- Set k (number of retrieved chunks) between 3 and 8 for most tasks; below 3, relevant information is often missing; above 8, irrelevant chunks dilute the signal and increase hallucination risk.
- Measure retrieval recall separately from end-to-end answer accuracy; if retrieval recall at k=5 is below 70% on your evaluation set, improving the retrieval pipeline will have more impact than prompt engineering.
- Include chunk metadata (document title, section heading, page number) in the retrieved context; this significantly improves citation accuracy and helps the model resolve contradictions between chunks from different sources.
- Use a separate reranking step after initial retrieval to reorder the top-20 candidates to top-5 using a cross-encoder model; cross-encoder reranking improves end-to-end accuracy by 10–18% compared to using vector search alone.
- Implement a "no relevant context found" path; instruct the model to explicitly state when retrieved chunks do not contain sufficient information to answer the question rather than generating an answer from parametric knowledge.
