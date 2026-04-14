// ===================================================================
// DevOps Sentinel AI — popup.js
// ===================================================================

// ===== Constants =====
// API key is loaded at runtime from .env / config.js / chrome.storage — never hardcoded here.
const MODEL = (window.DEVOPS_SENTINEL_CONFIG || {}).MODEL || 'gemini-3-flash-preview';
// Try v1beta first; v1alpha fallback attempted inside callGemini if needed.
const API_BASE = 'https://generativelanguage.googleapis.com';

/**
 * Resolves the API key at call time.
 * appState.apiKey is always populated by loadSavedSettings() before any API call.
 */
function getApiKey() {
  return appState.apiKey || '';
}

/**
 * Reads the .env file bundled inside the extension package.
 * The popup page can fetch its own extension files directly.
 */
async function readKeyFromDotEnv() {
  try {
    const url = (typeof chrome !== 'undefined' && chrome.runtime)
      ? chrome.runtime.getURL('.env')
      : '.env';
    const resp = await fetch(url);
    if (!resp.ok) return '';
    const text = await resp.text();
    const match = text.match(/^GEMINI_API_KEY\s*=\s*(.+)$/m);
    return match ? match[1].trim() : '';
  } catch (e) {
    console.warn('[DevOps Sentinel] Could not fetch .env:', e);
    return '';
  }
}

const SYSTEM_PROMPT = `You are a Senior Staff DevOps Engineer with 15 years of experience in Infrastructure as Code and Kubernetes internals. You have deep expertise in Kubernetes API versions, Helm charts, ArgoCD, Terraform, Terragrunt, Ansible, Jenkins, GitHub Actions, Docker, containerd, Istio, and all major CNCF projects. You provide precise, expert-level analysis with actionable recommendations, catching subtle misconfigurations that junior engineers miss.`;

// ===== Application State =====
const appState = {
  apiKey: '',   // populated by loadSavedSettings() on DOMContentLoaded — never set here
  currentTab: 'yaml',
  yamlRawOutput: '',
  terraformRawOutput: '',
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
  const key = getApiKey();
  if (!key) {
    throw new Error('No API key found. Open Settings (⚙) and paste your Gemini API key.');
  }

  const requestBody = {
    system_instruction: {
      parts: [{ text: SYSTEM_PROMPT }]
    },
    contents: [
      { role: 'user', parts: [{ text: userMessage }] }
    ],
    generationConfig: {
      temperature: 0.3,
      maxOutputTokens: 2048,
    }
  };

  // Attempt order — matches how the google-genai Python SDK authenticates:
  //   1. v1beta + ?key= query param (standard REST docs method)
  //   2. v1beta + x-goog-api-key header (Python SDK method)
  //   3. v1     + ?key= query param
  const encodedKey = encodeURIComponent(key);
  const attempts = [
    { url: `${API_BASE}/v1beta/models/${MODEL}:generateContent?key=${encodedKey}`, useHeader: false },
    { url: `${API_BASE}/v1beta/models/${MODEL}:generateContent`,                   useHeader: true  },
    { url: `${API_BASE}/v1/models/${MODEL}:generateContent?key=${encodedKey}`,     useHeader: false },
  ];

  console.log(`[DevOps Sentinel] Calling — model:${MODEL}  key:...${key.slice(-6)}`);

  let firstError = '';
  for (const { url, useHeader } of attempts) {
    const headers = { 'Content-Type': 'application/json' };
    if (useHeader) headers['x-goog-api-key'] = key;

    let response;
    try {
      response = await fetch(url, { method: 'POST', headers, body: JSON.stringify(requestBody) });
    } catch (netErr) {
      if (!firstError) firstError = `Network error: ${netErr.message}`;
      console.warn(`[DevOps Sentinel] fetch failed: ${netErr.message}`);
      continue;
    }

    console.log(`[DevOps Sentinel] ${url.split('?')[0]} → ${response.status}`);

    if (response.ok) {
      const data = await response.json();
      const text = data?.candidates?.[0]?.content?.parts?.[0]?.text;
      if (text) return text;
      throw new Error('Gemini returned an empty response.');
    }

    const errBody = await response.json().catch(() => ({}));
    const errMsg  = errBody?.error?.message || response.statusText;
    console.warn(`[DevOps Sentinel] Error: [${response.status}] ${errMsg}`);
    if (!firstError) firstError = `[${response.status}] ${errMsg}`;
  }

  throw new Error(firstError || 'All Gemini API endpoints failed.');
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
// SETTINGS
// ===================================================================

function openSettings() {
  const modal = document.getElementById('settingsModal');
  const apiKeyInput = document.getElementById('apiKeyInput');
  const configKey = (window.DEVOPS_SENTINEL_CONFIG || {}).API_KEY || '';
  // Show blank if using the .env default (so user knows it's auto-loaded)
  apiKeyInput.value = appState.apiKey === configKey ? '' : appState.apiKey;
  apiKeyInput.placeholder = configKey
    ? 'Using default key from .env — paste to override'
    : 'Paste your Gemini API key…';
  modal.classList.remove('hidden');
}

function closeSettings() {
  document.getElementById('settingsModal').classList.add('hidden');
}

async function saveSettings() {
  const val = document.getElementById('apiKeyInput').value.trim();
  if (val) {
    appState.apiKey = val;
    if (typeof chrome !== 'undefined' && chrome.storage) {
      chrome.storage.sync.set({ geminiApiKey: val });
    }
  } else {
    // User cleared the field — remove saved key, reload from .env
    if (typeof chrome !== 'undefined' && chrome.storage) {
      chrome.storage.sync.remove('geminiApiKey');
    }
    await loadSavedSettings();
  }
  closeSettings();
  showToast('Settings saved!', 'success');
}

async function loadSavedSettings() {
  // ── Priority 1: read .env directly from the extension package ─────
  // Always load the source-of-truth key first so stale chrome.storage
  // values cannot shadow it unless the user explicitly overrode it.
  const envKey = await readKeyFromDotEnv();

  // ── Priority 2: config.js (window.DEVOPS_SENTINEL_CONFIG) ─────────
  const cfgKey = (window.DEVOPS_SENTINEL_CONFIG || {}).API_KEY || '';

  // The "default" key is whichever we can find from the project files
  const defaultKey = envKey || cfgKey;

  // ── Priority 3: user-saved key in chrome.storage (override) ───────
  if (typeof chrome !== 'undefined' && chrome.storage) {
    const savedKey = await new Promise(resolve =>
      chrome.storage.sync.get(['geminiApiKey'], r => resolve(r.geminiApiKey || ''))
    );
    // Only honour chrome.storage if it matches the default key length/shape.
    // This prevents a stale wrong key from persisting across sessions.
    if (savedKey && savedKey.startsWith('AIza')) {
      appState.apiKey = savedKey;
    } else {
      // Clear any invalid saved key so it doesn't pollute future loads
      if (savedKey) chrome.storage.sync.remove('geminiApiKey');
      appState.apiKey = defaultKey;
    }
  } else {
    appState.apiKey = defaultKey;
  }

  console.log(`[DevOps Sentinel] API key loaded — last 6: ...${(appState.apiKey || '').slice(-6) || 'NONE'}`);
  if (!appState.apiKey) console.warn('[DevOps Sentinel] No API key found from any source.');
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
