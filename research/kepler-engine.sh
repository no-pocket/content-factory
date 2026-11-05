#!/bin/sh
set -eu

model=${KEPLER_MODEL:-qwen2.5:3b}
case "$model" in
  *[!A-Za-z0-9_.:-]*|*:*:*|:*|*:) echo "Invalid model name" >&2; exit 2 ;;
esac
name=${model%:*}
tag=${model#*:}
if [ "$name" = "$model" ] || [ -z "$name" ] || [ -z "$tag" ]; then
  echo "Invalid model name" >&2
  exit 2
fi
manifest="/models/models/manifests/registry.ollama.ai/library/$name/$tag"
if [ ! -f "$manifest" ]; then
  echo "Ollama model manifest missing: $model" >&2
  exit 2
fi
digest=$(sed -n 's/.*"mediaType":"application\/vnd\.ollama\.image\.model","digest":"sha256:\([0-9a-f]*\)".*/\1/p' "$manifest")
if [ -z "$digest" ] || [ ! -f "/models/models/blobs/sha256-$digest" ]; then
  echo "Ollama model blob missing: $model" >&2
  exit 2
fi
exec /build/bin/llama-server \
  -m "/models/models/blobs/sha256-$digest" \
  --host 0.0.0.0 --port 8080 \
  --ctx-size "${KEPLER_CTX_SIZE:-4096}" \
  --batch-size "${KEPLER_BATCH_SIZE:-512}" \
  --ubatch-size "${KEPLER_UBATCH_SIZE:-256}" \
  --gpu-layers "${KEPLER_GPU_LAYERS:-99}" \
  --threads "${KEPLER_THREADS:-4}"
