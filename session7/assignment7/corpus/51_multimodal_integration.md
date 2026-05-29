# Multimodal Integration

## Problem Statement

Multimodal inputs — images, audio, PDFs, video frames — require preprocessing pipelines that differ fundamentally from text processing. Teams unfamiliar with multimodal engineering often underestimate the complexity of normalizing diverse input formats, managing the significantly higher token costs of visual inputs, and evaluating multimodal output quality.

## Solution / Pattern

Structure multimodal integration as a two-phase pipeline. In the preprocessing phase, normalize inputs to the model's required format: resize images to the optimal resolution for the target model, convert PDFs to images at 150–300 DPI (lower DPI degrades OCR accuracy, higher DPI increases token cost without proportional quality gain), segment audio into 30-second chunks for models with audio context limits. In the inference phase, structure prompts to explicitly direct the model's attention to the visual component before asking questions about it.

## Key Details

- Image tokens are significantly more expensive than text tokens; a 1024x1024 image costs approximately 1,590 tokens on GPT-4o using the high-detail setting. Resize images to the minimum resolution necessary for the task before sending — for most text extraction tasks, 768x1024 is sufficient.
- Use the "low detail" image mode for tasks that require only coarse visual understanding (classifying image type, identifying whether a chart is present); the cost difference is approximately 10x (85 tokens vs. 850+ tokens) for the same image.
- For document processing, extract text with an OCR engine first and send the text as input when the document has legible machine-encoded text; fallback to image input only for scanned documents or images with embedded text. OCR text is 5–10x cheaper per page than image input.
- Evaluate multimodal outputs with task-specific metrics: for document understanding, measure field extraction accuracy; for image captioning, use CLIPScore alongside text quality metrics; for chart question-answering, measure numerical accuracy separately from textual accuracy.
- Track the rate of visual hallucinations (claims about image content not present in the image) as a separate metric from text hallucinations; visual hallucination rates are typically 2–3x higher than text hallucination rates for the same model.
- Cache preprocessed visual inputs (as base64 or file handles) rather than re-preprocessing them on each call; image resizing and PDF rendering are CPU-intensive operations that add 100–500ms per call.
