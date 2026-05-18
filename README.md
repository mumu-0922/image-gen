# image-gen

Unified Codex skill for image generation workflows.

`image-gen` combines three paths into one entry point:

- normal image generation and editing through the installed system `imagegen` engine
- offline GPT Image 2 prompt-gallery lookup through bundled `references/gallery-*.md`
- explicit local CLI batch generation through `image_gen.py generate-batch`

The skill is designed for Codex on Windows, but the prompt gallery and JSONL batch format are portable.

## What Is Included

```text
SKILL.md
agents/openai.yaml
references/
  gallery-index.md
  gallery-*.md
  craft-summary.md
  batch-sample.jsonl
  relay-test.jsonl
scripts/
  run-with-codex-auth.ps1
LICENSE.upstream-gpt-image-2-skill
```

The `gallery-*.md` files are mirrored locally so Codex can search prompt templates without opening GitHub or raw URLs during normal use.

## Install

Copy this folder into your Codex skills directory as `image-gen`:

```powershell
Copy-Item -Recurse -Force . "$env:USERPROFILE\.codex\skills\image-gen"
```

Restart Codex after installing or updating the skill.

## Basic Use

Invoke it explicitly:

```text
$image-gen Find gaming HUD prompt patterns and adapt them into a children quiz runner style.
```

```text
$image-gen Create 8 batch JSONL prompts for a 16:9 educational game UI asset set.
```

```text
$image-gen Generate a 16:9 start-screen background using the local default image workflow, not CLI.
```

## Offline Prompt Gallery

Use these local references first:

- `references/gallery-index.md` chooses the category.
- `references/gallery-gaming.md`, `gallery-ui-ux-mockups.md`, and other category files provide concrete prompt patterns.
- `references/craft-summary.md` gives reusable prompt-writing rules.

The skill should borrow prompt structure, not blindly copy subjects:

- canvas and layout first
- exact visible text in quotes
- UI/product/diagram grammar
- style boundary
- constraints and avoid list

## Batch Generation

Batch jobs use JSONL:

```jsonl
{"prompt":"Landscape 16:9 game start screen. Top title \"[exact title]\". Center: main visual. Bottom: primary button \"[exact button]\". Constraints: crisp text, no watermark.","size":"1536x1024","quality":"high","out":"start-screen.png"}
```

Dry-run first:

```powershell
python "$env:USERPROFILE\.codex\skills\.system\imagegen\scripts\image_gen.py" generate-batch `
  --input .\references\batch-sample.jsonl `
  --out-dir .\output\imagegen `
  --dry-run
```

## Reuse Codex Relay API

If your Codex config already has a custom model provider and API key, use:

```powershell
$env:IMAGE_GEN_PYTHON='D:\yxk\test\.venv-image-gen-test\Scripts\python.exe'
powershell -ExecutionPolicy Bypass -File .\scripts\run-with-codex-auth.ps1 generate-batch `
  --input .\references\relay-test.jsonl `
  --out-dir .\output\imagegen-relay-test `
  --concurrency 1 `
  --max-attempts 1
```

The wrapper reads:

```text
%USERPROFILE%\.codex\config.toml
%USERPROFILE%\.codex\auth.json
```

It prints the base URL and only reports the API key as `<set>`.

## Notes

- Live CLI generation requires an OpenAI-compatible Images API that returns `b64_json`.
- Do not commit generated images, local virtual environments, or API keys.
- The offline gallery files are mirrored from `wuyoscar/gpt_image_2_skill`; keep `LICENSE.upstream-gpt-image-2-skill` when redistributing.
