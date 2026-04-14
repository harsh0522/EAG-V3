// ===================================================================
// DevOps Sentinel AI — popup.js
// ===================================================================

// ===== Constants =====
const DEFAULT_API_KEY = 'AIzaSyDPVcJXiwi2VQQlXaR4qV6G07uoU6PXEgA';
const MODEL = 'gemini-3-flash-preview';
const API_URL = `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent`;

const SYSTEM_PROMPT = `You are a Senior Staff DevOps Engineer with 15 years of experience in Infrastructure as Code and Kubernetes internals. You have deep expertise in Kubernetes API versions, Helm charts, ArgoCD, Terraform, Terragrunt, Ansible, Jenkins, GitHub Actions, Docker, containerd, Istio, and all major CNCF projects. You provide precise, expert-level analysis with actionable recommendations, catching subtle misconfigurations that junior engineers miss.`;

// ===== Application State =====
const appState = {
  apiKey: DEFAULT_API_KEY,
  currentTab: 'yaml',
  yamlRawOutput: '',
  terraformRawOutput: '',
  newsItems: [],
  currentFilter: 'all',
};

// ===================================================================
// UTILITY FUNCTIONS
// ===================================================================

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function showToast(message, type = '') {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = `toast show ${type}`;
  setTimeout(() => { toast.className = 'toast'; }, 2500);
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    showToast('Copied to clipboard!', 'success');
  }).catch(() => {
    // Fallback for clipboard API
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0;';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
      document.execCommand('copy');
      showToast('Copied to clipboard!', 'success');
    } catch {
      showToast('Copy failed — select text manually', 'error');
    }
    document.body.removeChild(ta);
  });
}

// ===================================================================
// SYNTAX HIGHLIGHTER
// ===================================================================

function highlightYAML(code) {
  let out = escapeHtml(code);

  // Process line by line to avoid cross-contamination
  const lines = out.split('\n');
  const result = lines.map(line => {
    // Comments
    const commentIdx = line.search(/(^|\s)#/);
    let commentSuffix = '';
    let workLine = line;
    if (commentIdx !== -1) {
      const hashPos = line.indexOf('#', commentIdx);
      commentSuffix = `<span class="h-comment">${line.slice(hashPos)}</span>`;
      workLine = line.slice(0, hashPos);
    }

    // Document markers
    if (/^\s*(---|\.\.\.)$/.test(workLine.trim())) {
      return `<span class="h-doc">${workLine}</span>${commentSuffix}`;
    }

    // Keys (word before colon)
    workLine = workLine.replace(/^(\s*)([\w\-\.\/]+)(\s*:)/, (m, indent, key, colon) => {
      return `${indent}<span class="h-key">${key}</span>${colon}`;
    });

    // List item dashes
    workLine = workLine.replace(/^(\s*)(- )/, (m, indent, dash) => {
      return `${indent}<span class="h-doc">${dash}</span>`;
    });

    // Double-quoted strings
    workLine = workLine.replace(/(&quot;)((?:\\.|[^&])*?)(&quot;)/g,
      '<span class="h-string">$1$2$3</span>');

    // Single-quoted strings
    workLine = workLine.replace(/'([^']*)'/g,
      "<span class=\"h-string\">'$1'</span>");

    // Anchors & aliases
    workLine = workLine.replace(/([&*]\w+)/g,
      '<span class="h-anchor">$1</span>');

    // Booleans and null
    workLine = workLine.replace(/\b(true|false|null|yes|no|on|off|True|False|Null)\b/g,
      '<span class="h-bool">$1</span>');

    // Numbers (only standalone)
    workLine = workLine.replace(/(?<=:\s*)(-?\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b/gi,
      '<span class="h-num">$1</span>');

    return workLine + commentSuffix;
  });

  return result.join('\n');
}

function highlightHCL(code) {
  let out = escapeHtml(code);
  const lines = out.split('\n');
  const result = lines.map(line => {
    // Single-line comments
    const commentMatch = line.match(/^(.*?)(\/\/[^\n]*)$/);
    let commentSuffix = '';
    let workLine = line;
    if (commentMatch) {
      workLine = commentMatch[1];
      commentSuffix = `<span class="h-comment">${commentMatch[2]}</span>`;
    }
    const hashMatch = workLine.match(/^([^#]*)(#[^\n]*)$/);
    if (hashMatch) {
      workLine = hashMatch[1];
      commentSuffix = `<span class="h-comment">${hashMatch[2]}</span>` + commentSuffix;
    }

    // HCL keywords
    workLine = workLine.replace(
      /\b(resource|module|variable|output|provider|data|locals|terraform|required_providers|required_version|backend|lifecycle|dynamic|for_each|count|depends_on|source|version|default|description|type|sensitive|nullable|ephemeral|moved|import|check)\b/g,
      '<span class="h-keyword">$1</span>'
    );

    // Type keywords
    workLine = workLine.replace(
      /\b(string|number|bool|list|map|set|object|tuple|any)\b/g,
      '<span class="h-type">$1</span>'
    );

    // Function calls
    workLine = workLine.replace(
      /\b([a-z][a-z_]+)(\()/g,
      '<span class="h-func">$1</span>$2'
    );

    // Double-quoted strings (including interpolations)
    workLine = workLine.replace(/(&quot;)((?:\\.|[^&])*?)(&quot;)/g,
      '<span class="h-string">$1$2$3</span>');

    // Attribute names (word before =)
    workLine = workLine.replace(/^(\s*)([\w_-]+)(\s*=(?!=))/,
      (m, indent, key, eq) => `${indent}<span class="h-attr">${key}</span>${eq}`
    );

    // Booleans / null
    workLine = workLine.replace(/\b(true|false|null)\b/g,
      '<span class="h-bool">$1</span>');

    // Numbers
    workLine = workLine.replace(/\b(-?\d+(?:\.\d+)?)\b/g,
      '<span class="h-num">$1</span>');

    return workLine + commentSuffix;
  });

  // Multi-line comments (block comments)
  return result.join('\n').replace(
    /\/\*([\s\S]*?)\*\//g,
    '<span class="h-comment">/*$1*/</span>'
  );
}

function syntaxHighlight(code, lang) {
  if (!code) return '';
  const language = (lang || '').toLowerCase();
  if (language === 'yaml' || language === 'yml') return highlightYAML(code);
  if (language === 'hcl' || language === 'terraform' || language === 'tf') return highlightHCL(code);
  return escapeHtml(code);
}

// ===================================================================
// MARKDOWN / RESPONSE RENDERER
// ===================================================================

/**
 * Detects if a response is primarily code (has a fenced code block).
 * Returns { isCode, lang, code, explanation } object.
 */
function parseResponse(text) {
  // Try to find a fenced code block
  const codeBlockRe = /```(\w*)\n([\s\S]*?)```/g;
  const codeBlocks = [];
  let match;
  while ((match = codeBlockRe.exec(text)) !== null) {
    codeBlocks.push({ lang: match[1] || 'text', code: match[2].trimEnd() });
  }

  // Remove code blocks from text to get the explanation
  const explanationText = text.replace(/```[\s\S]*?```/g, '').trim();

  return { codeBlocks, explanationText };
}

function renderMarkdown(text) {
  if (!text) return '';
  let html = escapeHtml(text);

  // Headers
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2 style="font-size:14px;font-weight:600;color:var(--accent-blue);margin:10px 0 4px;">$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h2 style="font-size:15px;font-weight:700;color:var(--accent-blue);margin:10px 0 4px;">$1</h2>');

  // Bold & italic
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Bullet lists
  html = html.replace(/^[\*\-] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/^(\d+)\. (.+)$/gm, '<li><strong>$1.</strong> $2</li>');

  // Wrap consecutive <li> items in <ul>
  html = html.replace(/(<li>[\s\S]*?<\/li>)(\n<li>[\s\S]*?<\/li>)*/g, '<ul style="padding-left:16px;margin:6px 0;">$&</ul>');

  // Paragraphs (double newline)
  html = html.replace(/\n\n/g, '</p><p style="margin:8px 0;">');
  html = `<p style="margin:0 0 8px;">${html}</p>`;

  // Single newlines
  html = html.replace(/\n/g, '<br>');

  return html;
}

function buildOutputHTML(parsed, outputType) {
  const { codeBlocks, explanationText } = parsed;
  let html = '';

  // Render explanation text
  if (explanationText) {
    html += `<div class="output-text">${renderMarkdown(explanationText)}</div>`;
  }

  // Render code blocks
  codeBlocks.forEach((block, i) => {
    const langLabel = block.lang || 'code';
    const highlighted = syntaxHighlight(block.code, block.lang);
    const blockId = `code-block-${outputType}-${i}`;
    html += `
      <div class="code-wrapper" style="margin-top:${explanationText || i > 0 ? '10px' : '0'};">
        <div class="code-header">
          <span class="code-lang">${langLabel}</span>
          <button class="copy-btn" onclick="copyCodeBlock('${blockId}')">&#128203; Copy</button>
        </div>
        <div class="code-block" id="${blockId}">${highlighted}</div>
      </div>`;
  });

  return html || '<div class="output-text">No output received.</div>';
}

function copyCodeBlock(blockId) {
  const el = document.getElementById(blockId);
  if (!el) return;
  const text = el.innerText || el.textContent;
  copyToClipboard(text);

  // Visual feedback on that specific button
  const btn = el.previousElementSibling?.querySelector('.copy-btn');
  if (btn) {
    btn.textContent = '✓ Copied!';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.innerHTML = '&#128203; Copy';
      btn.classList.remove('copied');
    }, 2000);
  }
}

function showLoading(bodyEl) {
  bodyEl.innerHTML = `
    <div class="loading-container">
      <div class="spinner"></div>
      <span class="loading-text">AI is analyzing your code&hellip;</span>
    </div>`;
}

function showError(bodyEl, message) {
  bodyEl.innerHTML = `
    <div class="error-output">
      <span class="error-icon">&#9888;</span>
      <div>${escapeHtml(message)}</div>
    </div>`;
}

// ===================================================================
// GEMINI API
// ===================================================================

async function callGemini(userMessage) {
  const key = appState.apiKey || DEFAULT_API_KEY;

  const requestBody = {
    system_instruction: {
      parts: [{ text: SYSTEM_PROMPT }]
    },
    contents: [
      {
        role: 'user',
        parts: [{ text: userMessage }]
      }
    ],
    generationConfig: {
      temperature: 0.3,
      maxOutputTokens: 2048,
    }
  };

  const response = await fetch(`${API_URL}?key=${encodeURIComponent(key)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    const errBody = await response.json().catch(() => ({}));
    const errMsg = errBody?.error?.message || `HTTP ${response.status}: ${response.statusText}`;
    throw new Error(errMsg);
  }

  const data = await response.json();
  const text = data?.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!text) throw new Error('Empty response from Gemini API.');
  return text;
}

// ===================================================================
// TAB: YAML DEBUGGER
// ===================================================================

async function handleYamlAction(action) {
  const input = document.getElementById('yamlInput').value.trim();
  if (!input) {
    showToast('Please paste some YAML code first.', 'error');
    return;
  }

  const outputSection = document.getElementById('yamlOutput');
  const outputBody = document.getElementById('yamlOutputBody');
  const badge = document.getElementById('yamlOutputBadge');
  const explainBtn = document.getElementById('explainYamlBtn');
  const correctBtn = document.getElementById('correctYamlBtn');

  // Set badge
  if (action === 'explain') {
    badge.textContent = 'Explain';
    badge.className = 'badge badge-explain';
  } else {
    badge.textContent = 'Correct';
    badge.className = 'badge badge-correct';
  }

  outputSection.classList.remove('hidden');
  showLoading(outputBody);
  explainBtn.disabled = true;
  correctBtn.disabled = true;

  try {
    let prompt;
    if (action === 'explain') {
      prompt = `Analyze the following YAML code and provide a detailed explanation. Identify:
1. Any syntax errors, indentation issues, or schema violations
2. The purpose and structure of the configuration
3. Kubernetes API version compatibility issues (if applicable)
4. Common structural mistakes or anti-patterns
5. Security concerns or missing best practices

Be specific about line numbers and field names when pointing out issues.

\`\`\`yaml
${input}
\`\`\``;
    } else {
      prompt = `Correct and optimize the following YAML code. Fix ALL issues including:
1. Syntax errors and indentation problems
2. Schema violations or invalid field values
3. Deprecated API versions (update to current stable versions)
4. Missing required fields
5. Apply Kubernetes/Docker best practices

Return the corrected YAML in a fenced code block, then briefly explain the key changes made.

\`\`\`yaml
${input}
\`\`\``;
    }

    const responseText = await callGemini(prompt);
    appState.yamlRawOutput = responseText;

    const parsed = parseResponse(responseText);
    outputBody.innerHTML = buildOutputHTML(parsed, 'yaml');

  } catch (err) {
    showError(outputBody, `API Error: ${err.message}`);
    appState.yamlRawOutput = '';
  } finally {
    explainBtn.disabled = false;
    correctBtn.disabled = false;
  }
}

// ===================================================================
// TAB: TERRAFORM ANALYZER
// ===================================================================

async function handleTerraformAction(action) {
  const input = document.getElementById('terraformInput').value.trim();
  if (!input) {
    showToast('Please paste some Terraform HCL code first.', 'error');
    return;
  }

  const outputSection = document.getElementById('terraformOutput');
  const outputBody = document.getElementById('terraformOutputBody');
  const badge = document.getElementById('terraformOutputBadge');
  const logicBtn = document.getElementById('logicCheckBtn');
  const fixBtn = document.getElementById('fixDeprecationsBtn');

  if (action === 'logic') {
    badge.textContent = 'Logic Check';
    badge.className = 'badge badge-logic';
  } else {
    badge.textContent = 'Fix Deprecations';
    badge.className = 'badge badge-fix';
  }

  outputSection.classList.remove('hidden');
  showLoading(outputBody);
  logicBtn.disabled = true;
  fixBtn.disabled = true;

  try {
    let prompt;
    if (action === 'logic') {
      prompt = `Perform a comprehensive logic check on the following Terraform HCL code. Analyze:
1. Infrastructure impact — what resources will be created, modified, or destroyed
2. Variable declarations and their usage (missing variables, unused variables)
3. Module references and output dependencies
4. Provider configuration correctness
5. Resource naming conventions and tagging strategy
6. Potential drift risks or idempotency issues
7. Cost implications of the infrastructure defined
8. IAM permissions or security group rules that may be too permissive

\`\`\`hcl
${input}
\`\`\``;
    } else {
      prompt = `Update the following Terraform HCL code to fix all deprecations and modernize syntax. Address:
1. Deprecated resource types or attributes — replace with current equivalents
2. Provider version constraints — update to latest stable versions
3. Deprecated lifecycle arguments
4. Old interpolation syntax (e.g., \${} inside strings that no longer need it)
5. Deprecated provider block patterns
6. Module source paths or version constraints that are outdated
7. Any arguments removed in recent provider versions

Return the fully updated HCL in a fenced code block, then list the key changes with the before → after for each deprecation fixed.

\`\`\`hcl
${input}
\`\`\``;
    }

    const responseText = await callGemini(prompt);
    appState.terraformRawOutput = responseText;

    const parsed = parseResponse(responseText);
    outputBody.innerHTML = buildOutputHTML(parsed, 'terraform');

  } catch (err) {
    showError(outputBody, `API Error: ${err.message}`);
    appState.terraformRawOutput = '';
  } finally {
    logicBtn.disabled = false;
    fixBtn.disabled = false;
  }
}

// ===================================================================
// TAB: NEWS HUB
// ===================================================================

const NEWS_PROMPT = `You are a DevOps and cloud-native expert. Generate a JSON array of exactly 9 recent industry news items — 3 for each of these categories: "Kubernetes", "AI/Cloud", "Security".

For each item provide:
- "title": Clear, descriptive headline (string)
- "date": Publication date in YYYY-MM-DD format (use realistic recent dates from 2024-2025)
- "category": Exactly one of: "Kubernetes", "AI/Cloud", "Security"
- "url": Real direct URL to official documentation, blog post, GitHub release, or CVE advisory
- "summary": One clear sentence describing the update and its significance

Focus areas:
- Kubernetes: New alpha/beta features, API deprecations, recent release notes
- AI/Cloud: LLM/AI integrations in AWS/GCP/Azure, AI-assisted DevOps tooling, Kubernetes AI operators
- Security: CVEs for CNCF tools (Istio, ArgoCD, Helm, Trivy, etc.), supply chain security, RBAC hardening

Return ONLY a raw JSON array. No markdown fences. No explanation. Start directly with [`;

async function loadNews() {
  const newsOutput = document.getElementById('newsOutput');
  const refreshBtn = document.getElementById('refreshNewsBtn');

  newsOutput.innerHTML = `
    <div class="loading-container">
      <div class="spinner"></div>
      <span class="loading-text">Fetching latest DevOps &amp; AI updates&hellip;</span>
    </div>`;
  refreshBtn.disabled = true;

  try {
    const responseText = await callGemini(NEWS_PROMPT);

    // Extract JSON array from response
    let jsonText = responseText.trim();
    // Remove potential markdown fences
    jsonText = jsonText.replace(/^```json\s*/i, '').replace(/^```\s*/i, '').replace(/\s*```$/, '');
    // Find the JSON array
    const startIdx = jsonText.indexOf('[');
    const endIdx = jsonText.lastIndexOf(']');
    if (startIdx === -1 || endIdx === -1) throw new Error('No JSON array found in response.');
    jsonText = jsonText.slice(startIdx, endIdx + 1);

    const items = JSON.parse(jsonText);
    if (!Array.isArray(items) || items.length === 0) throw new Error('Invalid news data received.');

    appState.newsItems = items;
    renderNews(appState.currentFilter);

  } catch (err) {
    newsOutput.innerHTML = `
      <div class="error-output" style="margin:8px 0;">
        <span class="error-icon">&#9888;</span>
        <div>Failed to load news: ${escapeHtml(err.message)}</div>
      </div>`;
  } finally {
    refreshBtn.disabled = false;
  }
}

function getCategoryClass(category) {
  const cat = (category || '').toLowerCase();
  if (cat === 'kubernetes') return 'cat-kubernetes';
  if (cat === 'ai/cloud' || cat === 'ai' || cat === 'cloud') return 'cat-ai';
  if (cat === 'security') return 'cat-security';
  return 'cat-default';
}

function renderNews(filter) {
  appState.currentFilter = filter;
  const newsOutput = document.getElementById('newsOutput');

  if (!appState.newsItems || appState.newsItems.length === 0) return;

  let items = appState.newsItems;
  if (filter !== 'all') {
    items = items.filter(item => {
      const cat = (item.category || '').toLowerCase();
      if (filter === 'kubernetes') return cat === 'kubernetes';
      if (filter === 'ai') return cat.includes('ai') || cat.includes('cloud');
      if (filter === 'security') return cat === 'security';
      return true;
    });
  }

  if (items.length === 0) {
    newsOutput.innerHTML = `<div class="news-placeholder"><div class="news-placeholder-icon">&#128269;</div><div style="color:var(--text-secondary);">No items in this category.</div></div>`;
    return;
  }

  const cardsHTML = items.map(item => {
    const catClass = getCategoryClass(item.category);
    const categoryLabel = item.category || 'Update';
    const safeTitle = escapeHtml(item.title || 'Untitled');
    const safeSummary = escapeHtml(item.summary || '');
    const safeDate = escapeHtml(item.date || '');
    const safeUrl = item.url ? escapeHtml(item.url) : '#';
    const isValidUrl = item.url && (item.url.startsWith('https://') || item.url.startsWith('http://'));

    return `
      <div class="news-card">
        <div class="news-card-header">
          <div class="news-title">${safeTitle}</div>
          <span class="news-category ${catClass}">${escapeHtml(categoryLabel)}</span>
        </div>
        ${safeSummary ? `<div class="news-summary">${safeSummary}</div>` : ''}
        <div class="news-footer">
          <span class="news-date">&#128197; ${safeDate || 'Recent'}</span>
          ${isValidUrl
            ? `<a class="news-link" href="${safeUrl}" target="_blank" rel="noopener noreferrer">Source &#8599;</a>`
            : `<span class="text-muted text-sm">No link available</span>`
          }
        </div>
      </div>`;
  }).join('');

  newsOutput.innerHTML = `<div class="news-list">${cardsHTML}</div>`;
}

// ===================================================================
// SETTINGS
// ===================================================================

function openSettings() {
  const modal = document.getElementById('settingsModal');
  const apiKeyInput = document.getElementById('apiKeyInput');
  apiKeyInput.value = appState.apiKey === DEFAULT_API_KEY ? '' : appState.apiKey;
  apiKeyInput.placeholder = appState.apiKey === DEFAULT_API_KEY
    ? 'Using default key (from .env)'
    : 'Enter your Gemini API key…';
  modal.classList.remove('hidden');
}

function closeSettings() {
  document.getElementById('settingsModal').classList.add('hidden');
}

function saveSettings() {
  const val = document.getElementById('apiKeyInput').value.trim();
  if (val) {
    appState.apiKey = val;
  } else {
    appState.apiKey = DEFAULT_API_KEY;
  }
  // Persist to chrome.storage
  if (typeof chrome !== 'undefined' && chrome.storage) {
    chrome.storage.sync.set({ geminiApiKey: appState.apiKey });
  }
  closeSettings();
  showToast('Settings saved!', 'success');
}

async function loadSavedSettings() {
  if (typeof chrome !== 'undefined' && chrome.storage) {
    return new Promise((resolve) => {
      chrome.storage.sync.get(['geminiApiKey'], (result) => {
        if (result.geminiApiKey) {
          appState.apiKey = result.geminiApiKey;
        }
        resolve();
      });
    });
  }
}

// ===================================================================
// TAB SWITCHING
// ===================================================================

function switchTab(tabName) {
  // Update state
  appState.currentTab = tabName;

  // Update tab buttons
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabName);
  });

  // Show/hide tab content (preserve DOM state — do NOT clear inputs)
  document.querySelectorAll('.tab-content').forEach(section => {
    const isActive = section.id === `${tabName}-tab`;
    if (isActive) {
      section.classList.add('active');
      section.style.display = 'block';
    } else {
      section.classList.remove('active');
      section.style.display = 'none';
    }
  });
}

// ===================================================================
// NEWS FILTER BUTTONS
// ===================================================================

function setupNewsFilters() {
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderNews(btn.dataset.filter);
    });
  });
}

// ===================================================================
// INITIALIZATION
// ===================================================================

document.addEventListener('DOMContentLoaded', async () => {

  // Load persisted settings
  await loadSavedSettings();

  // ===== Tab Navigation =====
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // Initialize tab display (first tab active)
  document.querySelectorAll('.tab-content').forEach((section, i) => {
    if (i === 0) {
      section.classList.add('active');
      section.style.display = 'block';
    } else {
      section.classList.remove('active');
      section.style.display = 'none';
    }
  });

  // ===== YAML Tab =====
  document.getElementById('explainYamlBtn').addEventListener('click', () => handleYamlAction('explain'));
  document.getElementById('correctYamlBtn').addEventListener('click', () => handleYamlAction('correct'));
  document.getElementById('clearYamlBtn').addEventListener('click', () => {
    document.getElementById('yamlInput').value = '';
    document.getElementById('yamlOutput').classList.add('hidden');
    appState.yamlRawOutput = '';
  });

  // Copy YAML output
  document.getElementById('copyYamlOutput').addEventListener('click', () => {
    const text = appState.yamlRawOutput;
    if (text) copyToClipboard(text);
    else showToast('No output to copy yet.', '');
  });

  // ===== Terraform Tab =====
  document.getElementById('logicCheckBtn').addEventListener('click', () => handleTerraformAction('logic'));
  document.getElementById('fixDeprecationsBtn').addEventListener('click', () => handleTerraformAction('fix'));
  document.getElementById('clearTerraformBtn').addEventListener('click', () => {
    document.getElementById('terraformInput').value = '';
    document.getElementById('terraformOutput').classList.add('hidden');
    appState.terraformRawOutput = '';
  });

  // Copy Terraform output
  document.getElementById('copyTerraformOutput').addEventListener('click', () => {
    const text = appState.terraformRawOutput;
    if (text) copyToClipboard(text);
    else showToast('No output to copy yet.', '');
  });

  // ===== News Tab =====
  setupNewsFilters();
  document.getElementById('refreshNewsBtn').addEventListener('click', loadNews);

  // ===== Settings =====
  document.getElementById('settingsBtn').addEventListener('click', openSettings);
  document.getElementById('closeSettingsBtn').addEventListener('click', closeSettings);
  document.getElementById('cancelSettingsBtn').addEventListener('click', closeSettings);
  document.getElementById('saveSettingsBtn').addEventListener('click', saveSettings);
  document.getElementById('modalOverlay').addEventListener('click', closeSettings);

  // Close modal on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeSettings();
  });

});

// Expose copyCodeBlock globally for inline onclick handlers
window.copyCodeBlock = copyCodeBlock;
