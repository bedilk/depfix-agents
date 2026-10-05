#!/usr/bin/env bash
# Test script for expanded E2E coverage across archived and legacy codebases
# Usage: bash scripts/test-e2e-repos.sh

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

echo "Testing expanded E2E coverage..."
echo ""

results_file="research/e2e-expanded-test-$(date +%Y%m%d-%H%M%S).md"
mkdir -p research

{
  echo "# E2E Test Results — Expanded Coverage"
  echo ""
  echo "Testing against archived and legacy codebases with multiple providers."
  echo ""
  echo "| Repo | Providers | Ecosystem | Files | Call Sites | Status | Time |"
  echo "|---|---|---|---|---|---|---|"
} > "$results_file"

PASS=0
FAIL=0

# Test 1: ragflow with multiple providers
echo "[1/6] Testing ragflow (openai, elasticsearch, mongodb, redis, mysql)..."
if timeout 15m bash scripts/test_pipeline.sh openai,elasticsearch,mongodb,redis,mysql:bedilk/ragflow > .local/test-ragflow.log 2>&1; then
  PASS=$((PASS + 1))
  status="✓"
  files=$(grep -oP 'files scanned: \K[0-9]+' .local/test-ragflow.log | tail -1 || echo "?")
  sites=$(grep -oP 'call sites: \K[0-9]+' .local/test-ragflow.log | tail -1 || echo "?")
  echo "| bedilk/ragflow | openai, elasticsearch, mongodb, redis, mysql | mixed | $files | $sites | $status | - |" >> "$results_file"
else
  FAIL=$((FAIL + 1))
  echo "| bedilk/ragflow | openai, elasticsearch, mongodb, redis, mysql | mixed | ? | ? | ✗ | - |" >> "$results_file"
fi

# Test 2: courses with anthropic
echo "[2/6] Testing courses (anthropic)..."
if timeout 10m bash scripts/test_pipeline.sh anthropic:bedilk/courses > .local/test-courses.log 2>&1; then
  PASS=$((PASS + 1))
  status="✓"
  files=$(grep -oP 'files scanned: \K[0-9]+' .local/test-courses.log | tail -1 || echo "?")
  sites=$(grep -oP 'call sites: \K[0-9]+' .local/test-courses.log | tail -1 || echo "?")
  echo "| bedilk/courses | anthropic | mixed | $files | $sites | $status | - |" >> "$results_file"
else
  FAIL=$((FAIL + 1))
  echo "| bedilk/courses | anthropic | mixed | ? | ? | ✗ | - |" >> "$results_file"
fi

# Test 3: openai-agents-python with openai
echo "[3/6] Testing openai-agents-python (openai)..."
if timeout 10m bash scripts/test_pipeline.sh openai:bedilk/openai-agents-python > .local/test-openai-agents.log 2>&1; then
  PASS=$((PASS + 1))
  status="✓"
  files=$(grep -oP 'files scanned: \K[0-9]+' .local/test-openai-agents.log | tail -1 || echo "?")
  sites=$(grep -oP 'call sites: \K[0-9]+' .local/test-openai-agents.log | tail -1 || echo "?")
  echo "| bedilk/openai-agents-python | openai | Python | $files | $sites | $status | - |" >> "$results_file"
else
  FAIL=$((FAIL + 1))
  echo "| bedilk/openai-agents-python | openai | Python | ? | ? | ✗ | - |" >> "$results_file"
fi

# Test 4: hyper with sentry
echo "[4/6] Testing hyper (sentry)..."
if timeout 10m bash scripts/test_pipeline.sh sentry:bedilk/hyper > .local/test-hyper.log 2>&1; then
  PASS=$((PASS + 1))
  status="✓"
  files=$(grep -oP 'files scanned: \K[0-9]+' .local/test-hyper.log | tail -1 || echo "?")
  sites=$(grep -oP 'call sites: \K[0-9]+' .local/test-hyper.log | tail -1 || echo "?")
  echo "| bedilk/hyper | sentry | Rust | $files | $sites | $status | - |" >> "$results_file"
else
  FAIL=$((FAIL + 1))
  echo "| bedilk/hyper | sentry | Rust | ? | ? | ✗ | - |" >> "$results_file"
fi

# Test 5: studiocms with multiple providers
echo "[5/6] Testing studiocms (astro, stripe, sentry)..."
if timeout 15m bash scripts/test_pipeline.sh astro,stripe,sentry:bedilk/studiocms > .local/test-studiocms.log 2>&1; then
  PASS=$((PASS + 1))
  status="✓"
  files=$(grep -oP 'files scanned: \K[0-9]+' .local/test-studiocms.log | tail -1 || echo "?")
  sites=$(grep -oP 'call sites: \K[0-9]+' .local/test-studiocms.log | tail -1 || echo "?")
  echo "| bedilk/studiocms | astro, stripe, sentry | TypeScript | $files | $sites | $status | - |" >> "$results_file"
else
  FAIL=$((FAIL + 1))
  echo "| bedilk/studiocms | astro, stripe, sentry | TypeScript | ? | ? | ✗ | - |" >> "$results_file"
fi

# Test 6: website with multiple providers
echo "[6/6] Testing website (mongodb, stripe, sendgrid)..."
if timeout 15m bash scripts/test_pipeline.sh mongodb,stripe,sendgrid:bedilk/website > .local/test-website.log 2>&1; then
  PASS=$((PASS + 1))
  status="✓"
  files=$(grep -oP 'files scanned: \K[0-9]+' .local/test-website.log | tail -1 || echo "?")
  sites=$(grep -oP 'call sites: \K[0-9]+' .local/test-website.log | tail -1 || echo "?")
  echo "| bedilk/website | mongodb, stripe, sendgrid | TypeScript | $files | $sites | $status | - |" >> "$results_file"
else
  FAIL=$((FAIL + 1))
  echo "| bedilk/website | mongodb, stripe, sendgrid | TypeScript | ? | ? | ✗ | - |" >> "$results_file"
fi

# Summary
{
  echo ""
  echo "## Summary"
  echo ""
  echo "- **Passed:** $PASS / 6"
  echo "- **Failed:** $FAIL / 6"
  echo ""
  echo "### Archived/Legacy Repos"
  echo ""
  echo "These are additional archived repos for testing against older codebases:"
  echo ""
  echo "| # | Repo | Ecosystem | Providers | Status |"
  echo "|---|---|---|---|---|"
  echo "| 1 | supabase-community/nextjs-openai-doc-search | Node.js (npm) | openai, @supabase/supabase-js | Archived early 2024 |"
  echo "| 2 | mckaywrigley/chatbot-ui | TypeScript (npm) | openai | v1 legacy codebase |"
  echo "| 3 | hwchase17/chat-your-data | Python (PyPI) | openai, langchain | Archived 2024 |"
  echo "| 4 | mayooear/gpt4-pdf-chatbot-langchain | TypeScript (npm) | openai, langchain, pinecone | Archived mid-2024 |"
  echo ""
  echo "To test archived repos, run:"
  echo ""
  echo "\`\`\`bash"
  echo "bash scripts/test_pipeline.sh openai:bedilk/nextjs-openai-doc-search"
  echo "bash scripts/test_pipeline.sh openai:bedilk/chatbot-ui"
  echo "bash scripts/test_pipeline.sh openai,langchain:bedilk/chat-your-data"
  echo "bash scripts/test_pipeline.sh openai,langchain:bedilk/ai-pdf-chatbot-langchain"
  echo "\`\`\`"
} >> "$results_file"

echo ""
echo "Results written to: $results_file"
echo "Passed: $PASS / 6, Failed: $FAIL / 6"
