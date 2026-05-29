# Attention Is All You Need
**Authors:** Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Łukasz Kaiser, Illia Polosukhin  
**Year:** 2017  
**Venue:** NeurIPS

## Abstract

The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely. Experiments on two machine translation tasks show these models to be superior in quality while being more parallelizable and requiring significantly less time to train.

## Key Contributions

### 1. The Transformer Architecture

The paper introduces the Transformer, a model architecture relying entirely on an attention mechanism to draw global dependencies between input and output. Unlike recurrent models, the Transformer allows for significantly more parallelization and can reach a new state of the art in translation quality after being trained for as little as twelve hours on eight P100 GPUs.

The architecture consists of an encoder that maps an input sequence of symbol representations to a sequence of continuous representations. Given this, the decoder then generates an output sequence of symbols one element at a time. At each step the model is auto-regressive, consuming the previously generated symbols as additional input when generating the next.

### 2. Multi-Head Self-Attention

Instead of performing a single attention function with d_model-dimensional keys, values and queries, the authors found it beneficial to linearly project the queries, keys and values h times with different, learned linear projections to dk, dk and dv dimensions respectively. On each of these projected versions of queries, keys and values they then perform the attention function in parallel, yielding dv-dimensional output values.

The scaled dot-product attention formula is: Attention(Q, K, V) = softmax(QK^T / sqrt(d_k)) V. The scaling by 1/sqrt(d_k) counteracts the effect of having large dot products push the softmax function into regions with extremely small gradients.

Multi-head attention with h=8 parallel attention heads enables the model to jointly attend to information from different representation subspaces at different positions.

### 3. Positional Encoding

Since the model contains no recurrence and no convolution, positional encodings are injected to give the model information about the relative or absolute position of the tokens in the sequence. Positional encodings have the same dimension d_model as the embeddings so that the two can be summed. The authors use sine and cosine functions of different frequencies to encode position information, which allows the model to attend to relative positions.

## Architecture Details

- **Encoder:** Stack of N=6 identical layers, each with two sub-layers: multi-head self-attention and position-wise fully connected feed-forward network
- **Decoder:** Stack of N=6 identical layers with an additional third sub-layer performing multi-head attention over encoder output
- **Model dimensions:** d_model=512, d_ff=2048, h=8 attention heads, d_k=d_v=64
- **Training:** Used Adam optimizer with a custom learning rate schedule including a warmup period of 4000 steps

## Results

- WMT 2014 English-to-German: 28.4 BLEU (outperforming all previous ensembles)
- WMT 2014 English-to-French: 41.8 BLEU (new state of the art, single model)
- Training cost: fraction of prior best models — 8 P100 GPUs for 12 hours (base) or 3.5 days (big)

## Impact

The Transformer architecture has become the foundation for virtually all modern large language models. Its ability to process sequences in parallel (unlike RNNs) and to model long-range dependencies directly through attention has made it the de facto standard for natural language processing, computer vision, and multimodal AI systems. The architecture enables efficient scaling: by increasing model depth and width, performance improves predictably.
