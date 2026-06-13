# Run report — 20260613_101722_compar

## 1. Original user goal

> Compare top 3 Hugging Face text-generation models sorted by likes

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
- turn 4: `[{'type': 'done', 'success': True, 'value': '1. deepseek-ai/DeepSeek-R1: 5.59M downloads, 685B parameters. 2. meta-llama/Meta-Llama-3-8B: 1.19M downloads, 8B parameters. 3. meta-llama/Llama-3.1-8B-Instruct: 9 downloads (data truncated), 8B parameters.'}]` → done(True)

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
373,192
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

The top 3 text-generation models on Hugging Face, ranked by their number of likes, are as follows:

1. deepseek-ai/DeepSeek-R1: 13.4k likes (5.59M downloads)
2. meta-llama/Meta-Llama-3-8B: 6.57k likes (1.19M downloads)
3. meta-llama/Llama-3.1-8B-Instruct: 6.07k likes (9.87M downloads)

DeepSeek-R1 currently leads the list as the most liked model.

## 8. Turn count and cost summary

- layer `a11y`: 4 turn(s)
- input tokens: 14489
- output tokens: 1132
- estimated cost: $0.000174
- wall-clock: 60.5s
