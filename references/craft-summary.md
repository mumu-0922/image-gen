# Prompt Craft Summary

Distilled from the upstream `craft.md` in `wuyoscar/gpt_image_2_skill`.

## Core Move

Use gallery examples as structural references. Preserve the user's subject and constraints; borrow only the prompt architecture.

## Checklist

1. Start with artifact type and canvas.
   - `Landscape 16:9 game HUD mockup`
   - `3:4 vertical Chinese poster`
   - `Conference-paper figure on a white background`
2. Specify layout zones before visual decoration.
   - `top title`, `left diagram`, `right summary`, `bottom legend`
   - `3x2 grid`, `4x3 small-multiples grid`, `front/side/back character sheet`
3. Quote exact text.
   - Use straight quotes for every required visible string.
   - Keep Chinese copy verbatim.
   - Add `crisp`, `legible`, `large enough`, and `no garbled characters` when text matters.
4. Use domain grammar.
   - UI: product name, screen size, header, tabs, cards, rows, data, nav.
   - Diagrams: nodes, arrows, panels, labels, legend, line styles, color meanings.
   - Research figures: columns, zones, blocks, heatmaps, dashed paths, publication style.
   - Posters: headline hierarchy, subcopy, offer, brand area, negative space.
5. Control consistency for multi-panel outputs.
   - Exact panel count.
   - Role per panel.
   - Shared palette, costume, lighting, character identity, axes, or labels.
6. Use camera context for realism.
   - `RAW iPhone photo`, `shot from the crowd`, `eye-level 28mm lens feel`, `low three-quarter product angle`.
7. Separate style, material, lighting, and palette.
8. End with avoid/constraints.
   - `no watermark`
   - `no extra text`
   - `no QR code`
   - `no real logos/trademarks unless supplied`
   - `no tiny unreadable labels`

## JSON-Style Product Pattern

Use this for complex product/food scenes:

```text
/* PRODUCT_RENDER_CONFIG: Short Name
VERSION: 1.0.0
AESTHETIC: Premium Commercial Photography */
{
  "GLOBAL_SETTINGS": {
    "aspect_ratio": "2:3 vertical",
    "style": "hyper-realistic commercial photography",
    "clarity": "sharp foreground, micro-texture visibility"
  },
  "ENVIRONMENT": {
    "background": "warm gradient studio backdrop",
    "lighting": "directional softbox with glossy highlights"
  },
  "CORE_ASSETS": {
    "primary_subject": "hero product",
    "materials": ["brushed metal", "condensation", "paper label"],
    "composition": "diagonal zero-gravity arrangement"
  },
  "OUTPUT": {
    "mood": "premium, editorial",
    "avoid": ["cheap e-commerce banner", "plastic CGI", "fake brand logos"]
  }
}
```

## Batch Job Shape

Use per-line JSON objects:

```jsonl
{"prompt":"<final prompt>","size":"1536x1024","quality":"high","out":"asset-name.png"}
```

Run with:

```powershell
python 'C:\Users\123\.codex\skills\.system\imagegen\scripts\image_gen.py' generate-batch --input .\prompts.jsonl --out-dir .\output\imagegen --dry-run
```
