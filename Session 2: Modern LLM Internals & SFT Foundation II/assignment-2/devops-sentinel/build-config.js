/**
 * build-config.js
 * Reads the .env file and generates config.js for the Chrome extension.
 * Run once before loading the extension:  node build-config.js
 */

const fs   = require('fs');
const path = require('path');

const envPath    = path.join(__dirname, '.env');
const outputPath = path.join(__dirname, 'config.js');

if (!fs.existsSync(envPath)) {
  console.error('❌  .env file not found. Create one with GEMINI_API_KEY=<your-key>');
  process.exit(1);
}

// Parse .env (simple KEY=VALUE, ignores comments and blank lines)
const envVars = {};
fs.readFileSync(envPath, 'utf8')
  .split('\n')
  .forEach(line => {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) return;
    const [key, ...rest] = trimmed.split('=');
    envVars[key.trim()] = rest.join('=').trim();
  });

const apiKey = envVars['GEMINI_API_KEY'];
if (!apiKey) {
  console.error('❌  GEMINI_API_KEY not found in .env');
  process.exit(1);
}

const output = `// AUTO-GENERATED — do not edit manually.
// Regenerate with:  node build-config.js
// Source of truth:  .env  (never commit .env or this file to version control)
window.DEVOPS_SENTINEL_CONFIG = {
  API_KEY: "${apiKey}",
  MODEL:   "gemini-3-flash-preview"
};
`;

fs.writeFileSync(outputPath, output, 'utf8');
console.log('✅  config.js generated successfully from .env');
