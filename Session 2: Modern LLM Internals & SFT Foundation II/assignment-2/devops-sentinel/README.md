# Project Specification: DevOps Sentinel AI

## Overview
DevOps Sentinel is a browser extension. It helps DevOps engineers debug, optimize, and stay updated with cloud-native technologies. It provides AI-driven analysis for YAML, Terraform, and Groovy. It also has a live feed for industry updates.

## Technical Stack Requirements
- Frontend: HTML5, CSS3 (Tailwind CSS preferred), JavaScript (ES6+)
- Code Display: Prism.js or Highlight.js for syntax highlighting
- Backend: Integration with LLM API (Gemini or OpenAI)
- Permissions: storage, scripting, activeTab
- should run on chrome (MAC + WIN)

## Architecture: 3-Tab Interface

### Tab 1: YAML Debugger
- Input: Text area for YAML code. This includes Kubernetes manifests, Docker Compose, and CI/CD pipelines.
- Action 1: Explain. The AI identifies syntax errors, indentation issues, and schema violations.
- Action 2: Correct. The AI returns a valid, optimized YAML block.
- Logic: Focus on K8s API versions and common structural mistakes.

### Tab 2: Terraform Analyzer
- Input: Text area for HCL (HashiCorp Configuration Language) snippets.
- Action 1: Logic Check. The AI explains the infrastructure impact of the code.
- Action 2: Fix Deprecations. The AI updates resource syntax to match the latest provider versions.
- Logic: Focus on provider blocks, variable declarations, and module outputs.

### Tab 3: DevOps + AI News Hub
- Content: A curated list of the latest updates in the DevOps ecosystem.
- Mandatory Categories:
  - Kubernetes (New alpha/beta features)
  - AI/LLM integrations for Cloud
  - Security patches for CNCF tools
- Format: List view with Title, Date, Category, and a direct URL to the source documentation.

## Functional Requirements
- Code blocks must include a 'Copy to Clipboard' button.
- The UI must maintain state when switching between tabs. Do not clear input.
- Implementation of a 'Loading' state during API calls.
- A Settings menu for users to input their own API Key.

## Prompt Engineering Guidelines
The system prompt must define the assistant as a "Senior Staff DevOps Engineer with 15 years of experience in Infrastructure as Code and Kubernetes internals." When sending code to the LLM, use this prompt.