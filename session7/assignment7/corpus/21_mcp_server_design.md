# MCP Server Design

## Problem Statement

The Model Context Protocol (MCP) enables LLM applications to connect to external data sources and tools through a standardized interface. Poorly designed MCP servers expose overly broad capabilities, return unstructured data, and provide inadequate error messages, causing the model to make incorrect tool selections and fail to recover from errors.

## Solution / Pattern

Design MCP servers with the principle of minimal capability exposure: expose only the tools necessary for the expected task domain, and make each tool's scope as narrow as practical. Each tool's description should specify exactly what it returns, what inputs it requires, and what it does not do. Models use tool descriptions to decide which tool to call; ambiguous descriptions lead to incorrect selections.

Return structured data from every MCP tool — JSON objects with consistent schemas, not raw text or HTML. Include a `status` field (success/error) in every response so the model can parse the outcome without inferring from content alone.

## Key Details

- Tool descriptions must be under 200 tokens; longer descriptions are truncated in some model implementations and reduce the effectiveness of tool selection.
- Include at least one concrete input-output example in each tool's description, formatted as a short inline note rather than a full JSON block; examples improve tool selection accuracy by approximately 25% compared to description-only tools.
- Implement per-tool rate limits at the MCP server layer, not only at the backend API layer; this provides a defense-in-depth against agent loops that call the same tool repeatedly.
- Return error messages that describe what went wrong and what the model should try instead; "Resource not found: the document ID 'X' does not exist, try searching by title using the search_documents tool" is far more recoverable than "404 Not Found."
- Use semantic versioning for MCP server APIs; breaking changes to tool schemas must increment the major version and the client must negotiate the version on connection to prevent silent schema mismatches.
- Log all incoming tool calls server-side with timestamps and caller identity; this log is essential for auditing agent behavior and diagnosing failures when the client-side logs are incomplete.
