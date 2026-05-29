# Embedding Space Analysis

## Problem Statement

Embedding spaces are high-dimensional and opaque. Without tools to analyze the structure of your embedding space, it is impossible to diagnose retrieval failures, identify corpus quality issues, or understand why certain queries consistently fail to retrieve relevant documents.

## Solution / Pattern

Embedding space analysis uses dimensionality reduction and clustering to make the structure of high-dimensional embeddings interpretable. Apply UMAP (Uniform Manifold Approximation and Projection) rather than t-SNE for embedding visualization; UMAP preserves global structure better than t-SNE, making it possible to identify broad topical clusters and outliers. Reduce to 2D for visualization and 10–20 dimensions for clustering; reducing directly to 2D for analysis loses too much structure.

Cluster the embedded corpus using HDBSCAN with min_cluster_size set to 1% of the total corpus size; this identifies natural topical groupings and reveals outliers that may be noise, duplicates, or problematic documents.

## Key Details

- Run embedding space analysis at index creation time and after every significant corpus update; changes in cluster structure between analyses indicate corpus composition shifts that may affect retrieval quality.
- A healthy embedding space for a topically diverse corpus should have 10–50 well-separated clusters; a space with fewer than 5 clusters indicates that the corpus is topically narrow or that the embedding model is not discriminating well between content types.
- Identify "hubness" problems: vectors that appear as nearest neighbors for an unusually large fraction of queries (top 0.1% most-retrieved vectors). Hubs inflate retrieval metrics and indicate embedding space distortions; remove hub documents from the index and investigate why they are so central.
- Compute the mean cosine similarity between random pairs of vectors in the index; a mean above 0.5 indicates the embedding space is too concentrated and retrieval will have poor discriminability. This is an early warning of the embedding collapse problem.
- Use embedding space analysis to validate chunking strategy: chunks that belong to the same parent document should cluster together; if they do not, the chunking is splitting semantic units across chunks in ways that degrade embedding quality.
- Visualize the positions of failed query embeddings (queries where users rejected the retrieved results) relative to successful query embeddings; failed queries that cluster in sparse regions of the embedding space identify gaps in corpus coverage that should be addressed by adding new content.
