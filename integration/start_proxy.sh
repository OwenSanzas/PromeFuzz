#!/usr/bin/env bash
# Start the LiteLLM proxy that routes OpenAI-compatible requests from
# Gold/AGF/OFG/PromeFuzz to Claude Sonnet 4.6 on the Anthropic API.
#
# Prerequisites:
#   pip install 'litellm[proxy]'
#   export ANTHROPIC_API_KEY=sk-ant-...      # required
#   export OPENAI_API_KEY=sk-...             # required for embeddings
#
# The proxy listens on http://localhost:4000 and requires clients to send
# the master key (set in litellm_config.yaml, matches experiment_config.LLM_PROXY_MASTER_KEY).
#
# Check that it is up:
#   curl -sS http://localhost:4000/health -H "Authorization: Bearer sk-local-promefuzz-run"
#
# Stop with Ctrl-C or `pkill -f "litellm.*--config"`.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${HERE}/litellm_config.yaml"

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "ERROR: ANTHROPIC_API_KEY is not set." >&2
  echo "Export it and re-run: export ANTHROPIC_API_KEY=sk-ant-..." >&2
  exit 2
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "WARNING: OPENAI_API_KEY not set — PromeFuzz comprehender (RAG) will fail." >&2
  echo "         Set it if you plan to run the comprehend phase." >&2
fi

if ! command -v litellm >/dev/null 2>&1; then
  echo "ERROR: litellm not installed. Run: pip install 'litellm[proxy]'" >&2
  exit 2
fi

echo "Starting LiteLLM proxy with ${CONFIG} on port 4000..."
exec litellm --config "${CONFIG}" --port 4000 --num_workers 4
