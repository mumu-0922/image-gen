---
name: image-gen
description: Use when generating, editing, or planning images; adapting GPT Image 2 gallery prompt templates; creating prompt variants; preparing JSONL batches; or running explicit local imagegen CLI/API workflows on Windows or WSL/Linux.
---

# Image Gen

Single entry point for image work. Keep the system `imagegen` skill as the engine and this skill as the router: prompt gallery, prompt rewriting, normal generation, edits, transparent images, custom final sizes, relay API runs, and explicit CLI batch jobs all start here.

## Decision Tree

1. If the user asks for prompt ideas, templates, gallery patterns, variants, or batch JSONL, use the gallery workflow below.
2. If the user asks for normal image generation or editing, use the installed system `imagegen` workflow and prefer built-in generation.
3. If the user explicitly asks for CLI, API, model flags, fixed output paths, relay/proxy, or batch execution, use the local CLI path below.
4. If the user asks for a relay, proxy, mirror, gateway, or "中转站 API", use the relay API rules below and do not run against the official endpoint unless explicitly requested.
5. If the user asks for transparent output, use chroma-key generation plus local removal first. This is mandatory for `gpt-image-2`, relay/中转站, batch CLI, and fixed-path workflows; do not request direct transparent PNG from those paths. Use true CLI transparency only after explicit confirmation and only with a model/path that supports it.

Do not call the third-party `gpt-image` CLI. Do not edit `.system/imagegen` files.

## User Preference: No Manual Confirmation for Live Image Generation

When the user explicitly asks to generate/edit/replace game or project images with联网 image-gen, proceed directly with live generation instead of asking for another confirmation. This applies to CLI batch, Codex-auth wrapper, relay/中转站, and fixed-output workflows.

Do not pause for confirmation just because network access, image credits, relay usage, or output paths are involved. Make a reasonable prompt/path choice from the project context, run generation, post-process, validate, and report the saved paths.

Still ask only when one of these hard blockers applies:

- Required inputs are missing and cannot be reasonably inferred.
- The operation is destructive beyond replacing the requested asset.
- The user asks to switch to a different model/path that needs new credentials or true native transparency fallback.
- The execution environment itself requires an approval prompt for filesystem/network escalation; in that case request the smallest scoped approval/prefix once, then continue.

## Hard Rule: Transparent Output with gpt-image-2 / Relays

`gpt-image-2` and many OpenAI-compatible relays/中转站 do **not** support model-native transparent PNG output. Never request direct transparency from `gpt-image-2`, and never include transparency-only API parameters such as `background: "transparent"` when the selected model is `gpt-image-2` or when using a relay unless that relay/model support has already been explicitly verified in this session.

For any transparent PNG/cutout/sprite/logo/button/title asset on `gpt-image-2` or relay paths, always use this workflow by default:

1. Prompt the model to generate the subject on a perfectly flat chroma-key background (`#00ff00` by default; use magenta/blue only if green conflicts with the subject).
2. Make the prompt explicitly forbid shadows, gradients, texture, reflections, floor planes, and the key color inside the subject.
3. Save the chroma-key source under the project or run folder.
4. Remove the key locally with `$CODEX_HOME/skills/.system/imagegen/scripts/remove_chroma_key.py` or an equivalent deterministic local post-process when Pillow/helper availability blocks the standard helper.
5. Validate the result has an alpha channel, transparent corners, plausible subject coverage, and no obvious key-color fringe before copying it into runtime assets.

If a user asks for “transparent” while also asking for `gpt-image-2`, relay, 中转站, batch CLI, or fixed output paths, silently translate that into “chroma-key generation + local alpha removal” instead of attempting direct transparent generation. Only discuss true/native transparency if the chroma-key path fails or the asset is too complex for keying.

## Platform Paths

Resolve paths from `CODEX_HOME` when set; otherwise use `$HOME/.codex` on WSL/Linux and `%USERPROFILE%\.codex` on Windows.

WSL/Linux defaults:

```text
Skill:   ~/.codex/skills/image-gen
Engine:  ~/.codex/skills/.system/imagegen/scripts/image_gen.py
Wrapper: ~/.codex/skills/image-gen/scripts/run-with-codex-auth.sh
Helper:  ~/.codex/skills/image-gen/scripts/imagegen_batch_helper.py
```

Windows defaults:

```text
Skill:   C:\Users\123\.codex\skills\image-gen
Engine:  C:\Users\123\.codex\skills\.system\imagegen\scripts\image_gen.py
Wrapper: C:\Users\123\.codex\skills\image-gen\scripts\run-with-codex-auth.ps1
Helper:  C:\Users\123\.codex\skills\image-gen\scripts\imagegen_batch_helper.py
```

On WSL, prefer the Linux files under `~/.codex`. Do not route through `/mnt/c/...` unless the user explicitly wants to operate on Windows-side assets.

## Gallery Workflow

Read `references/gallery-index.md` to choose 1-3 categories, then read the matching local `references/gallery-*.md` files and `references/craft-summary.md`. The `gallery-*.md` files are mirrored locally for offline use; use the raw URLs in the index only to refresh or repair missing files.

Borrow structure, not subject:

- canvas and layout first
- exact visible text in quotes
- product/UI/diagram grammar
- style boundary
- constraints and avoid list

Keep user-provided Chinese copy verbatim.

## Normal Generation

Use the system `imagegen` behavior:

- Prefer built-in image generation for ordinary generation, edits, and simple transparent requests.
- Save project-bound assets into the workspace, not only under default generated-image storage.
- Do not use CLI just because the user asks for size, quality, or a destination path.
- For edits, inspect local target images first when using the built-in path.

## Local CLI Batch

Use this only when the user explicitly asks for CLI/API/model/batch/fixed-path execution.

For transparent assets in CLI batch mode, do **not** add `background: "transparent"` to `gpt-image-2` jobs. Write each JSONL prompt with a flat chroma-key background requirement, generate a normal PNG, then run local key removal into the final transparent PNG. Keep both the chroma source and alpha final in the batch record.

WSL/Linux dry-run:

```bash
python3 ~/.codex/skills/.system/imagegen/scripts/image_gen.py generate-batch \
  --input ./prompts.jsonl \
  --out-dir ./output/imagegen \
  --dry-run
```

WSL/Linux live relay run using Codex auth:

```bash
~/.codex/skills/image-gen/scripts/run-with-codex-auth.sh generate-batch \
  --input ./prompts.jsonl \
  --out-dir ./output/imagegen \
  --concurrency 2 \
  --max-attempts 3
```

Windows live relay run using Codex auth:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\Users\123\.codex\skills\image-gen\scripts\run-with-codex-auth.ps1' generate-batch `
  --input .\prompts.jsonl `
  --out-dir .\output\imagegen `
  --concurrency 2 `
  --max-attempts 3
```

The wrappers read Codex auth without printing secrets, append `/v1` to `base_url` by default, and delegate through `scripts/imagegen_with_timeout.py`, which keeps the system engine unchanged while setting a longer OpenAI SDK request timeout.

- WSL override timeout: `--request-timeout 900` or `IMAGE_GEN_REQUEST_TIMEOUT=900`.
- Windows override timeout: `-RequestTimeout 900` or `IMAGE_GEN_REQUEST_TIMEOUT=900`.
- WSL no `/v1` append: `--no-append-v1`.
- Windows no `/v1` append: `-NoAppendV1`.
- For live WSL runs, the shell wrapper prefers `uv run --with openai --with pillow` when `uv` exists; otherwise it uses `python3` and the active environment must have `openai` installed.

## Custom Sizes

Users may request custom final sizes. Honor the requested final dimensions, but choose a model-legal generation size first and post-process if needed.

For `gpt-image-2`, generation size must satisfy:

- `auto` or `WIDTHxHEIGHT`
- width and height are multiples of 16
- max edge <= `3840`
- long/short ratio <= `3:1`
- total pixels between `655360` and `8294400`

If the requested final size is illegal for generation, generate the nearest larger legal canvas, then crop or resize to the exact requested final size. Common case:

```text
requested final: 1920x1080
generate:        1920x1088
post-process:    center-crop to 1920x1080
```

State both the generation size and final saved size in the result.

For batch work, prefer the helper instead of hand-editing sizes.

WSL/Linux:

```bash
python3 ~/.codex/skills/image-gen/scripts/imagegen_batch_helper.py plan \
  --input ./prompts.jsonl \
  --final-size 1920x1080

python3 ~/.codex/skills/image-gen/scripts/imagegen_batch_helper.py prepare \
  --input ./prompts.jsonl \
  --output ./prompts.gen.jsonl \
  --final-size 1920x1080
```

Windows:

```powershell
python 'C:\Users\123\.codex\skills\image-gen\scripts\imagegen_batch_helper.py' plan `
  --input .\prompts.jsonl `
  --final-size 1920x1080

python 'C:\Users\123\.codex\skills\image-gen\scripts\imagegen_batch_helper.py' prepare `
  --input .\prompts.jsonl `
  --output .\prompts.gen.jsonl `
  --final-size 1920x1080
```

Use `prompts.gen.jsonl` for generation. The helper writes UTF-8 without BOM and changes each job's `size` to the nearest legal generation canvas.

## Batch Recovery and Review

After a live batch, always verify expected outputs before claiming completion.

WSL/Linux:

```bash
python3 ~/.codex/skills/image-gen/scripts/imagegen_batch_helper.py verify \
  --input ./prompts.gen.jsonl \
  --out-dir ./raw \
  --missing-jsonl ./missing.jsonl
```

If files are missing or zero-byte, rerun only those jobs. On WSL the helper defaults to `run-with-codex-auth.sh`:

```bash
python3 ~/.codex/skills/image-gen/scripts/imagegen_batch_helper.py verify \
  --input ./prompts.gen.jsonl \
  --out-dir ./raw \
  --missing-jsonl ./missing.jsonl \
  --run-missing
```

For exact final dimensions plus a thumbnail review page:

```bash
uv run --with pillow python3 ~/.codex/skills/image-gen/scripts/imagegen_batch_helper.py postprocess \
  --input ./prompts.gen.jsonl \
  --out-dir ./raw \
  --final-dir ./final-1920x1080 \
  --final-size 1920x1080 \
  --index index.html
```

Windows equivalents use the same helper with PowerShell line continuations. If `--run-missing` is used on Windows, the helper defaults to `run-with-codex-auth.ps1`.

Use `index` when images are already post-processed:

```bash
uv run --with pillow python3 ~/.codex/skills/image-gen/scripts/imagegen_batch_helper.py index \
  --image-dir ./final-1920x1080 \
  --output ./final-1920x1080/index.html
```

Reliable recovery depends on predictable outputs. Prefer an explicit `out` field in every JSONL job; otherwise the helper mirrors the system CLI slug naming.

JSONL job shape:

```jsonl
{"prompt":"Landscape 16:9 game start screen. Top title \"[exact title]\". Center: main visual. Bottom: primary button \"[exact button]\". Constraints: crisp text, no watermark.","size":"1536x1024","quality":"high","out":"start-screen.png"}
```

Transparent/cutout JSONL jobs for `gpt-image-2` must be normal PNG jobs with chroma-key instructions, for example:

```jsonl
{"model":"gpt-image-2","prompt":"Create the requested subject on a perfectly flat solid #00ff00 chroma-key background for later background removal. No shadows, gradients, texture, floor plane, watermark, or key color inside the subject.","size":"1536x512","quality":"high","output_format":"png","out":"asset_chroma.png"}
```

Then remove the chroma key locally and save the final alpha asset separately (for example `asset.png`).

Write JSONL as UTF-8 without BOM. In PowerShell, prefer `Set-Content -Encoding utf8NoBOM` or .NET `UTF8Encoding($false)`. In WSL/Linux, normal Python `Path.write_text(..., encoding="utf-8")`, shell heredocs, or `printf` are fine.

Live run requires `OPENAI_API_KEY` and network. Never ask the user to paste secrets. Ask them to set `OPENAI_API_KEY` locally or use the Codex-auth wrapper when live CLI execution is required.

## Relay API Rules

When the user asks to use a relay/proxy/mirror/gateway/中转站 API:

- Require `OPENAI_BASE_URL` to be set to the relay's OpenAI-compatible base URL, usually ending in `/v1`.
- Require `OPENAI_API_KEY` to be set to the relay key, not the official OpenAI key.
- Prefer the Codex-auth wrapper when the user wants to reuse the same URL/API key as Codex:
  - WSL/Linux: `scripts/run-with-codex-auth.sh`
  - Windows: `scripts/run-with-codex-auth.ps1`
- Do not run a live CLI command if no relay base URL is available.
- Do not print secret values; only report whether the key is set.
- The relay must support the OpenAI-compatible Images API and return `b64_json` image data.
- Treat relay transparency support as unsupported by default. For transparent/cutout assets through a relay, generate on chroma-key and remove the background locally; do not send direct transparent-background parameters unless support was verified in this session.

WSL/Linux setup pattern:

```bash
export OPENAI_BASE_URL='https://your-relay.example/v1'
export OPENAI_API_KEY='<set relay key locally; do not paste it in chat>'
```

WSL/Linux relay smoke test:

```bash
~/.codex/skills/image-gen/scripts/run-with-codex-auth.sh generate-batch \
  --input ~/.codex/skills/image-gen/references/relay-test.jsonl \
  --out-dir ./output/imagegen-relay-test \
  --concurrency 1 \
  --max-attempts 1
```

Windows setup pattern:

```powershell
$env:OPENAI_BASE_URL = 'https://your-relay.example/v1'
$env:OPENAI_API_KEY = '<set relay key locally; do not paste it in chat>'
```

Windows relay smoke test:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\Users\123\.codex\skills\image-gen\scripts\run-with-codex-auth.ps1' generate-batch `
  --input .\references\relay-test.jsonl `
  --out-dir .\output\imagegen-relay-test `
  --concurrency 1 `
  --max-attempts 1
```

If the active Python environment lacks the `openai` package, install it into that environment or run the CLI through an environment that has it. Do not create a custom SDK runner.

## Output Contract

For prompt-only work, return the final prompt or JSONL and state which gallery pattern informed it.

For generation work, report:

- final saved path or intended output path
- whether built-in generation or local CLI was used
- final prompt or prompt set
- any verification result, including dry-run payloads for batch work

## Resources

- `references/gallery-index.md`: upstream GPT Image 2 gallery category map and raw URLs.
- `references/gallery-*.md`: offline prompt gallery category files.
- `references/craft-summary.md`: compact prompt-craft rules.
- `references/batch-sample.jsonl`: batch format smoke-test sample.
- `references/relay-test.jsonl`: one-image live smoke test for relay API execution.
- `scripts/run-with-codex-auth.sh`: WSL/Linux wrapper using Codex `config.toml` base URL and `auth.json` API key without printing secrets.
- `scripts/run-with-codex-auth.ps1`: Windows wrapper using Codex `config.toml` base URL and `auth.json` API key without printing secrets.
- `scripts/imagegen_with_timeout.py`: wraps the system image CLI with a longer SDK timeout for slow relay image generation.
- `scripts/imagegen_batch_helper.py`: prepares legal batch sizes, detects missing outputs, reruns missing jobs, crops to exact final dimensions, and builds thumbnail HTML indexes.

## Attribution

The offline `references/gallery-*.md` prompt gallery files are mirrored from `wuyoscar/gpt_image_2_skill`. Preserve the bundled upstream license file when publishing or redistributing this skill.
