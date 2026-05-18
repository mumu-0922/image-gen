---
name: image-gen
description: Use when generating, editing, or planning images; adapting GPT Image 2 gallery prompt templates; creating prompt variants; preparing JSONL batches; or running explicit local imagegen CLI/API workflows.
---

# Image Gen

Single entry point for image work. Keep the system image skill as the engine and this skill as the router: prompt gallery, prompt rewriting, normal generation, edits, transparent images, and explicit CLI batch jobs all start here.

## Decision Tree

1. If the user asks for prompt ideas, templates, gallery patterns, variants, or batch JSONL, use the gallery workflow below.
2. If the user asks for normal image generation or editing, use the installed system `imagegen` workflow and prefer built-in generation.
3. If the user explicitly asks for CLI, API, model flags, fixed output paths, or batch execution, use the local CLI path below.
4. If the user asks for a relay, proxy, mirror, gateway, or "中转站 API", use the relay API rules below and do not run against the official endpoint.
5. If the user asks for transparent output, use the system `imagegen` transparent workflow: built-in generation on a flat chroma-key background plus local removal first. Use true CLI transparency only after explicit confirmation.

Do not call the third-party `gpt-image` CLI. Do not edit `.system/imagegen` files.

## Gallery Workflow

Read `references/gallery-index.md` to choose 1-3 categories, then read `references/craft-summary.md` for prompt craft. If a concrete category file is needed and is not mirrored locally, fetch the raw URL listed in the index or ask for network setup.

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

CLI path:

```text
C:\Users\123\.codex\skills\.system\imagegen\scripts\image_gen.py
```

JSONL job shape:

```jsonl
{"prompt":"Landscape 16:9 game start screen. Top title \"[exact title]\". Center: main visual. Bottom: primary button \"[exact button]\". Constraints: crisp text, no watermark.","size":"1536x1024","quality":"high","out":"start-screen.png"}
```

Dry-run before live API calls:

```powershell
python 'C:\Users\123\.codex\skills\.system\imagegen\scripts\image_gen.py' generate-batch `
  --input .\prompts.jsonl `
  --out-dir .\output\imagegen `
  --dry-run
```

Live run requires `OPENAI_API_KEY` and network:

```powershell
python 'C:\Users\123\.codex\skills\.system\imagegen\scripts\image_gen.py' generate-batch `
  --input .\prompts.jsonl `
  --out-dir .\output\imagegen `
  --concurrency 2 `
  --max-attempts 3
```

Never ask the user to paste secrets. Ask them to set `OPENAI_API_KEY` locally when live CLI execution is required.

## Relay API Rules

When the user asks to use a relay/proxy/mirror/gateway/中转站 API:

- Require `OPENAI_BASE_URL` to be set to the relay's OpenAI-compatible base URL, usually ending in `/v1`.
- Require `OPENAI_API_KEY` to be set to the relay key, not the official OpenAI key.
- Prefer `scripts/run-with-codex-auth.ps1` when the user wants to reuse the same URL/API key as Codex.
- Do not run a live CLI command if no relay base URL is available.
- Do not print secret values; only report whether the key is set.
- The relay must support the OpenAI-compatible Images API and return `b64_json` image data.

PowerShell setup pattern:

```powershell
$env:OPENAI_BASE_URL = 'https://your-relay.example/v1'
$env:OPENAI_API_KEY = '<set relay key locally; do not paste it in chat>'
```

Relay smoke test:

```powershell
.\scripts\run-with-codex-auth.ps1 generate-batch `
  --input .\references\relay-test.jsonl `
  --out-dir .\output\imagegen-relay-test `
  --concurrency 1 `
  --max-attempts 1
```

If the active Python environment lacks the `openai` package, install it into that environment or run the CLI through an environment that has it. Do not create a custom SDK runner.

If the relay returns a path/404 error, retry once with `-AppendV1` before the command:

```powershell
.\scripts\run-with-codex-auth.ps1 -AppendV1 generate-batch `
  --input .\references\relay-test.jsonl `
  --out-dir .\output\imagegen-relay-test `
  --concurrency 1 `
  --max-attempts 1
```

## Output Contract

For prompt-only work, return the final prompt or JSONL and state which gallery pattern informed it.

For generation work, report:

- final saved path or intended output path
- whether built-in generation or local CLI was used
- final prompt or prompt set
- any verification result, including dry-run payloads for batch work

## Resources

- `references/gallery-index.md`: upstream GPT Image 2 gallery category map and raw URLs.
- `references/craft-summary.md`: compact prompt-craft rules.
- `references/batch-sample.jsonl`: batch format smoke-test sample.
- `references/relay-test.jsonl`: one-image live smoke test for relay API execution.
- `scripts/run-with-codex-auth.ps1`: runs the local image CLI using Codex `config.toml` base URL and `auth.json` API key without printing secrets.
