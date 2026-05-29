# Chain of Density

## Problem Statement

Standard summarization prompts produce verbose output that buries key information in filler text. For document processing pipelines where the summary will be re-ingested by another model or embedded for retrieval, low information density wastes tokens and degrades downstream task performance.

## Solution / Pattern

Chain of Density (CoD) is an iterative summarization technique where the model produces increasingly compressed versions of a summary in successive passes, each time maintaining the same target length while incorporating more entities and facts. Start with an initial summary at roughly 10% of source length, then instruct the model to produce 3–5 progressively denser versions, each one adding 1–3 missing entities while keeping the word count constant by removing filler phrases.

The final dense summary is significantly more information-rich than a single-pass summary of equivalent length because the compression process forces the model to prioritize facts over transitional prose.

## Key Details

- Target 5 density iterations for long-form documents (over 2,000 words); 3 iterations suffice for short documents (under 500 words).
- Set a hard word count for each iteration pass — the model will not self-regulate length without an explicit constraint; specify the target in the instruction, e.g., "in exactly 80 words."
- Evaluate density by counting named entities per 100 words in the final summary; good CoD output typically achieves 8–12 entities per 100 words versus 3–5 in naive summaries.
- CoD summaries show approximately 22% higher recall on downstream QA tasks compared to single-pass summaries of equivalent token length, based on standard benchmarks.
- Do not apply CoD to summaries that will be read by humans as the final product; dense summaries are optimized for machine consumption and feel terse and telegraphic to human readers.
- Use temperature 0.3 for CoD iterations to balance consistency with the flexibility to rephrase toward compression.
