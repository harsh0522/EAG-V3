# Run report — 20260613_102624_compar

## 1. Original user goal

> Compare top 3 Hugging Face text-generation models sorted by likes.

## 2. Planner DAG

- `n:1` **planner** — success
- `n:2` **browser** — success
- `n:3` **distiller** — success
- `n:5` **critic** — success
- `n:4` **formatter** — success
  - n:1 → n:2
  - n:2 → n:3
  - n:3 → n:5
  - n:5 → n:4

## 3. Browser path chosen

- `n:2`: **a11y** (url: https://huggingface.co/models)

## 4. Browser actions taken

- turn 1: `[{'type': 'click', 'mark': 36}]` → ok
- turn 2: `[{'type': 'click', 'mark': 80}]` → ok
- turn 3: `[{'type': 'click', 'mark': 82}]` → ok
- turn 4: `[{'type': 'done', 'success': True, 'value': '1. deepseek-ai/DeepSeek-R1, 5.59M likes, Text Generation; 2. openai/gpt-oss-20b, 6.54M likes, Text Generation; 3. meta-llama/Meta-Llama-3-8B-Instruct, 6.42M likes, Text Generation'}]` → done(True)

## 5. Page state / screenshots

- `n:2`: 4 a11y turn(s) logged (see `logs/browser_actions_*.log` for per-turn snapshots)

## 6. Extracted data

`n:2`:
```
deepseek-ai/DeepSeek-R1
Text Generation • 685B • Updated • 5.59M • • 13.4k
Tasks
Parameters
Libraries
Inference Providers
373,195
Active filters: text-generation
Text Generation • 685B • Updated • 5.59M • • 13.4k
Text Generation • 8B • Updated • 1.19M • • 6.57k
Text Generation • 8B • Updated • 9.87M • • 6.07k
Text Generation • 176B • Updated • 5.65k • 5.01k
Text Generation • 120B • Updated • 3.81M • • 4.88k
Text Generation • 862B • Updated • 3.38M • • 4.8k
Text Generation • 7B • Updated • 258k • 4.78k
Text Generation • 22B • Updated • 6.54M • • 4.71k
Text Generation • 8B • Updated • 1.33M • • 4.59k
Text Generation • Updated • 176 • 4.5k
Text Generation • 7B • Updated • 404k • • 4.11k
Text Generation • 685B • Updated • 999k • • 4.09k
Text Generation • 3B • Updated • 438k • • 3.47k
Text Generation • 9B • Updated • 26.2k • • 3.35k
Text Generation • 0.1B • Updated • 13.2M • 3.3k
Text Generation • 7B • Updated • 1.38M • • 3.16k
Text Generation • 685B • Updated • 896k • • 3.13k
Text Generati …[truncated]
```

## 7. Final comparison table

Based on current Hugging Face data, here are the top 3 text-generation models sorted by their number of likes:

1. openai/gpt-oss-20b: 6.54M likes
2. meta-llama/Meta-Llama-3-8B-Instruct: 6.42M likes
3. deepseek-ai/DeepSeek-R1: 5.59M likes

The leading model is openai/gpt-oss-20b, which holds the highest popularity with 6.54 million likes.

## 8. Turn count and cost summary

- layer `a11y`: 4 turn(s)
- input tokens: 14456
- output tokens: 1070
- estimated cost: $0.000174
- wall-clock: 83.9s
