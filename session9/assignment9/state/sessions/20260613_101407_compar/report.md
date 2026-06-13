# Run report — 20260613_101407_compar

## 1. Original user goal

> Compare top 3 Hugging Face text-generation models sorted by likes

## 2. Planner DAG

- `n:1` **planner** — success
- `n:2` **browser** — success
- `n:3` **distiller** — success
- `n:5` **critic** — success
- `n:6` **planner** — success
- `n:7` **browser** — success
- `n:8` **distiller** — success
- `n:10` **critic** — success
- `n:9` **formatter** — success
  - n:1 → n:2
  - n:2 → n:3
  - n:3 → n:5
  - n:5 → n:4
  - n:6 → n:7
  - n:7 → n:8
  - n:8 → n:10
  - n:10 → n:9

## 3. Browser path chosen

- `n:2`: **a11y** (url: https://huggingface.co/models)
- `n:7`: **a11y** (url: https://huggingface.co/models)

## 4. Browser actions taken

- turn 1: `[{'type': 'click', 'mark': 36}]` → ok
- turn 2: `[{'type': 'click', 'mark': 80}]` → ok
- turn 3: `[{'type': 'click', 'mark': 82}]` → ok
- turn 4: `[{'type': 'done', 'success': True, 'value': '1. deepseek-ai/DeepSeek-R1: 5.59M likes, Text Generation, 685B parameters. 2. openai/gpt-oss-20b: 6.54M likes, Text Generation, 22B parameters. 3. bigscience/bloom: 5.65k likes, Text Generation, 176B parameters.'}]` → done(True)
- turn 1: `[{'type': 'click', 'mark': 36}]` → ok
- turn 2: `[{'type': 'click', 'mark': 80}]` → ok
- turn 3: `[{'type': 'click', 'mark': 82}]` → ok
- turn 4: `[{'type': 'done', 'success': True, 'value': '1. deepseek-ai/DeepSeek-R1: 5.59M likes, Description: Text Generation • 685B • Updated Mar 27, 2025. 2. openai/gpt-oss-20b: 6.54M likes, Description: Text Generation • 22B • Updated Aug 26, 2025. 3. openai/gpt-oss-120b: 3.81M likes, Description: Text Generation • 120B • Updated Aug 26, 2025.'}]` → done(True)

## 5. Page state / screenshots

- `n:2`: 4 a11y turn(s) logged (see `logs/browser_actions_*.log` for per-turn snapshots)
- `n:7`: 4 a11y turn(s) logged (see `logs/browser_actions_*.log` for per-turn snapshots)

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
`n:7`:
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

1. openai/gpt-oss-20b: 6.54M likes (22B parameters, updated Aug 26, 2025)
2. deepseek-ai/DeepSeek-R1: 5.59M likes (685B parameters, updated Mar 27, 2025)
3. openai/gpt-oss-120b: 3.81M likes (120B parameters, updated Aug 26, 2025)

The openai/gpt-oss-20b model currently leads the group with the highest number of likes.

## 8. Turn count and cost summary

- layer `a11y`: 8 turn(s)
- input tokens: 0
- output tokens: 0
- estimated cost: $0.000320
- wall-clock: 141.2s
