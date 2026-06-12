#!/usr/bin/env python3
"""
Batch helper for the local image-gen skill.

This script does not call the image API unless verify/postprocess is invoked with
--run-missing. It prepares model-legal sizes, detects missing batch outputs,
post-processes images to exact final dimensions, and builds a thumbnail index.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


GPT_IMAGE_2_MIN_PIXELS = 655_360
GPT_IMAGE_2_MAX_PIXELS = 8_294_400
GPT_IMAGE_2_MAX_EDGE = 3840
GPT_IMAGE_2_MAX_RATIO = 3.0
DEFAULT_OUTPUT_FORMAT = "png"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass(frozen=True)
class BatchJob:
    index: int
    raw: Dict[str, Any]
    prompt: str


@dataclass(frozen=True)
class ExpectedOutput:
    job: BatchJob
    path: Path


def die(message: str, code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def parse_size(value: str) -> Tuple[int, int]:
    match = re.fullmatch(r"\s*([1-9][0-9]*)x([1-9][0-9]*)\s*", value)
    if not match:
        die(f"size must be WIDTHxHEIGHT, got {value!r}")
    return int(match.group(1)), int(match.group(2))


def normalize_output_format(value: Optional[str]) -> str:
    if not value:
        return DEFAULT_OUTPUT_FORMAT
    value = str(value).lower()
    if value == "jpg":
        return "jpeg"
    if value not in {"png", "jpeg", "webp"}:
        die(f"unsupported output_format {value!r}; use png, jpeg, or webp")
    return value


def ceil16(value: float) -> int:
    return max(16, int(math.ceil(value / 16.0)) * 16)


def floor16(value: float) -> int:
    return max(16, int(math.floor(value / 16.0)) * 16)


def fix_ratio_by_growing_short_edge(width: int, height: int) -> Tuple[int, int]:
    if width >= height and width / height > GPT_IMAGE_2_MAX_RATIO:
        height = ceil16(width / GPT_IMAGE_2_MAX_RATIO)
    elif height > width and height / width > GPT_IMAGE_2_MAX_RATIO:
        width = ceil16(height / GPT_IMAGE_2_MAX_RATIO)
    return width, height


def fix_ratio_by_shrinking_long_edge(width: int, height: int) -> Tuple[int, int]:
    if width >= height and width / height > GPT_IMAGE_2_MAX_RATIO:
        width = floor16(height * GPT_IMAGE_2_MAX_RATIO)
    elif height > width and height / width > GPT_IMAGE_2_MAX_RATIO:
        height = floor16(width * GPT_IMAGE_2_MAX_RATIO)
    return width, height


def is_legal_gpt_image_2_size(width: int, height: int) -> bool:
    max_edge = max(width, height)
    min_edge = min(width, height)
    pixels = width * height
    return (
        width % 16 == 0
        and height % 16 == 0
        and max_edge <= GPT_IMAGE_2_MAX_EDGE
        and max_edge / min_edge <= GPT_IMAGE_2_MAX_RATIO
        and GPT_IMAGE_2_MIN_PIXELS <= pixels <= GPT_IMAGE_2_MAX_PIXELS
    )


def legal_generation_size(final_width: int, final_height: int) -> Tuple[int, int]:
    """Return a gpt-image-2 legal source canvas for an arbitrary final size."""
    aspect = final_width / final_height
    if aspect > GPT_IMAGE_2_MAX_RATIO:
        base_height = final_height
        base_width = final_height * GPT_IMAGE_2_MAX_RATIO
    elif aspect < 1 / GPT_IMAGE_2_MAX_RATIO:
        base_width = final_width
        base_height = final_width * GPT_IMAGE_2_MAX_RATIO
    else:
        base_width = final_width
        base_height = final_height

    width = ceil16(base_width)
    height = ceil16(base_height)
    width, height = fix_ratio_by_growing_short_edge(width, height)

    while width * height < GPT_IMAGE_2_MIN_PIXELS:
        scale = math.sqrt(GPT_IMAGE_2_MIN_PIXELS / (width * height))
        width = ceil16(width * scale)
        height = ceil16(height * scale)
        width, height = fix_ratio_by_growing_short_edge(width, height)

    if max(width, height) > GPT_IMAGE_2_MAX_EDGE or width * height > GPT_IMAGE_2_MAX_PIXELS:
        scale = min(
            GPT_IMAGE_2_MAX_EDGE / max(width, height),
            math.sqrt(GPT_IMAGE_2_MAX_PIXELS / (width * height)),
        )
        width = floor16(width * scale)
        height = floor16(height * scale)
        width, height = fix_ratio_by_shrinking_long_edge(width, height)

    if not is_legal_gpt_image_2_size(width, height):
        die(
            "could not derive a legal gpt-image-2 canvas for "
            f"{final_width}x{final_height}; got {width}x{height}"
        )
    return width, height


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value[:60] if value else "job"


def read_jsonl(path: Path) -> List[BatchJob]:
    if not path.exists():
        die(f"input file not found: {path}")

    jobs: List[BatchJob] = []
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("{"):
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                die(f"invalid JSON on line {line_no}: {exc}")
            if "prompt" not in item or not str(item["prompt"]).strip():
                die(f"missing prompt on line {line_no}")
            raw = dict(item)
            prompt = str(raw["prompt"]).strip()
        else:
            prompt = line
            raw = {"prompt": prompt}
        jobs.append(BatchJob(index=len(jobs) + 1, raw=raw, prompt=prompt))

    if not jobs:
        die(f"no jobs found in {path}")
    return jobs


def write_jsonl(path: Path, jobs: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for job in jobs:
            handle.write(json.dumps(job, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")


def job_output_paths(
    job: BatchJob,
    out_dir: Path,
    default_output_format: str = DEFAULT_OUTPUT_FORMAT,
    default_n: int = 1,
) -> List[Path]:
    output_format = normalize_output_format(job.raw.get("output_format", default_output_format))
    ext = f".{output_format}"
    n = int(job.raw.get("n", default_n))
    if n < 1:
        die(f"job {job.index}: n must be >= 1")

    explicit_out = job.raw.get("out")
    if explicit_out:
        base = Path(str(explicit_out))
        if not base.suffix:
            base = base.with_suffix(ext)
        base = out_dir / base.name
    else:
        base = out_dir / f"{job.index:03d}-{slugify(job.prompt[:80])}{ext}"

    if n == 1:
        return [base]
    return [base.with_name(f"{base.stem}-{idx}{base.suffix}") for idx in range(1, n + 1)]


def expected_outputs(
    jobs: Sequence[BatchJob],
    out_dir: Path,
    output_format: str = DEFAULT_OUTPUT_FORMAT,
    n: int = 1,
) -> List[ExpectedOutput]:
    outputs: List[ExpectedOutput] = []
    for job in jobs:
        for path in job_output_paths(job, out_dir, output_format, n):
            outputs.append(ExpectedOutput(job=job, path=path))
    return outputs


def missing_outputs(outputs: Sequence[ExpectedOutput], min_bytes: int) -> List[ExpectedOutput]:
    missing: List[ExpectedOutput] = []
    for item in outputs:
        if not item.path.exists() or item.path.stat().st_size < min_bytes:
            missing.append(item)
    return missing


def unique_missing_jobs(missing: Sequence[ExpectedOutput]) -> List[Dict[str, Any]]:
    seen = set()
    jobs: List[Dict[str, Any]] = []
    for item in missing:
        if item.job.index in seen:
            continue
        seen.add(item.job.index)
        jobs.append(dict(item.job.raw))
    return jobs


def run_missing_jobs(
    missing_jsonl: Path,
    out_dir: Path,
    wrapper: Path,
    concurrency: int,
    max_attempts: int,
    force: bool,
    dry_run: bool,
) -> int:
    wrapper = wrapper.expanduser()
    base_args = [
        "generate-batch",
        "--input",
        str(missing_jsonl),
        "--out-dir",
        str(out_dir),
        "--concurrency",
        str(concurrency),
        "--max-attempts",
        str(max_attempts),
    ]
    if force:
        base_args.append("--force")
    if dry_run:
        base_args.append("--dry-run")

    if wrapper.suffix.lower() == ".ps1":
        command = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(wrapper),
            *base_args,
        ]
    else:
        command = [str(wrapper), *base_args]

    print("running missing jobs:")
    print(" ".join(quote_arg(part) for part in command))
    return subprocess.call(command)


def default_wrapper_path() -> str:
    codex_home = Path(os.getenv("CODEX_HOME") or Path.home() / ".codex")
    script_dir = codex_home / "skills" / "image-gen" / "scripts"
    if platform.system().lower().startswith("win"):
        return str(script_dir / "run-with-codex-auth.ps1")
    return str(script_dir / "run-with-codex-auth.sh")


def quote_arg(value: str) -> str:
    if re.search(r"\s", value):
        return "'" + value.replace("'", "''") + "'"
    return value


def import_pillow():
    try:
        from PIL import Image
    except Exception as exc:
        die(
            "Pillow is required for crop/index commands. Run with "
            "`uv run --with pillow python imagegen_batch_helper.py ...` "
            f"or install pillow in the active Python environment. ({exc})"
        )
    return Image


def save_cover_crop(source: Path, dest: Path, final_width: int, final_height: int) -> Tuple[int, int]:
    Image = import_pillow()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image.load()
        src_width, src_height = image.size
        scale = max(final_width / src_width, final_height / src_height)
        resized_width = max(final_width, int(math.ceil(src_width * scale)))
        resized_height = max(final_height, int(math.ceil(src_height * scale)))
        resampling = getattr(Image, "Resampling", Image).LANCZOS
        if (resized_width, resized_height) != image.size:
            image = image.resize((resized_width, resized_height), resampling)
        left = max(0, (resized_width - final_width) // 2)
        top = max(0, (resized_height - final_height) // 2)
        image = image.crop((left, top, left + final_width, top + final_height))
        if dest.suffix.lower() in {".jpg", ".jpeg"} and image.mode in {"RGBA", "LA", "P"}:
            image = image.convert("RGB")
        image.save(dest)
        return src_width, src_height


def collect_images(image_dir: Path) -> List[Path]:
    if not image_dir.exists():
        die(f"image directory not found: {image_dir}")
    return sorted(
        path
        for path in image_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def make_thumbnail(source: Path, thumb_dir: Path, max_edge: int) -> Tuple[Path, Tuple[int, int]]:
    Image = import_pillow()
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb = thumb_dir / source.name
    with Image.open(source) as image:
        image.load()
        original_size = image.size
        resampling = getattr(Image, "Resampling", Image).LANCZOS
        preview = image.copy()
        preview.thumbnail((max_edge, max_edge), resampling)
        if thumb.suffix.lower() in {".jpg", ".jpeg"} and preview.mode in {"RGBA", "LA", "P"}:
            preview = preview.convert("RGB")
        preview.save(thumb)
    return thumb, original_size


def file_size_label(path: Path) -> str:
    size = path.stat().st_size
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def group_name(path: Path) -> str:
    stem = path.stem
    if "-" in stem:
        return stem.split("-", 1)[0]
    return "images"


def relative_uri(path: Path, base: Path) -> str:
    try:
        rel = path.relative_to(base.parent)
    except ValueError:
        rel = path
    return rel.as_posix().replace("#", "%23")


def build_index(image_dir: Path, output: Path, thumb_max: int, title: str) -> None:
    images = collect_images(image_dir)
    if not images:
        die(f"no images found in {image_dir}")
    thumb_dir = output.parent / f"{output.stem}_thumbs"

    rows: List[Tuple[str, Path, Path, Tuple[int, int], str]] = []
    for image in images:
        thumb, dimensions = make_thumbnail(image, thumb_dir, thumb_max)
        rows.append((group_name(image), image, thumb, dimensions, file_size_label(image)))

    groups: Dict[str, List[Tuple[Path, Path, Tuple[int, int], str]]] = {}
    for group, image, thumb, dimensions, size_label in rows:
        groups.setdefault(group, []).append((image, thumb, dimensions, size_label))

    parts = [
        "<!doctype html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{html.escape(title)}</title>",
        "<style>",
        ":root{color-scheme:light;background:#f5f7fb;color:#17202a;font-family:Arial,'Microsoft YaHei',sans-serif}",
        "body{margin:0;padding:28px}",
        "h1{font-size:28px;margin:0 0 6px}",
        "h2{font-size:18px;margin:28px 0 12px;text-transform:capitalize}",
        ".meta{color:#5d6d7e;margin-bottom:18px}",
        ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}",
        ".card{background:#fff;border:1px solid #d7dde8;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(18,27,43,.08)}",
        ".card img{display:block;width:100%;aspect-ratio:16/9;object-fit:cover;background:#e9edf5}",
        ".info{padding:10px 12px}",
        ".name{font-weight:700;word-break:break-all}",
        ".dim{color:#5d6d7e;font-size:13px;margin-top:4px}",
        "a{color:inherit;text-decoration:none}",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>{html.escape(title)}</h1>",
        f'<div class="meta">{len(images)} images · source: {html.escape(str(image_dir))}</div>',
    ]
    for group in sorted(groups):
        parts.append(f"<h2>{html.escape(group)}</h2>")
        parts.append('<div class="grid">')
        for image, thumb, dimensions, size_label in groups[group]:
            image_href = relative_uri(image, output)
            thumb_src = relative_uri(thumb, output)
            label = image.name
            parts.extend(
                [
                    '<div class="card">',
                    f'<a href="{html.escape(image_href)}" target="_blank">',
                    f'<img src="{html.escape(thumb_src)}" alt="{html.escape(label)}">',
                    "</a>",
                    '<div class="info">',
                    f'<div class="name">{html.escape(label)}</div>',
                    f'<div class="dim">{dimensions[0]}x{dimensions[1]} · {html.escape(size_label)}</div>',
                    "</div>",
                    "</div>",
                ]
            )
        parts.append("</div>")
    parts.extend(["</body>", "</html>", ""])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {output}")


def cmd_plan(args: argparse.Namespace) -> int:
    final_width, final_height = parse_size(args.final_size)
    gen_width, gen_height = legal_generation_size(final_width, final_height)
    payload = {
        "final_size": f"{final_width}x{final_height}",
        "generation_size": f"{gen_width}x{gen_height}",
        "needs_postprocess": (gen_width, gen_height) != (final_width, final_height),
        "postprocess": "cover-resize plus center-crop to final size",
    }
    if args.input:
        jobs = read_jsonl(Path(args.input))
        payload["jobs"] = len(jobs)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_prepare(args: argparse.Namespace) -> int:
    final_width, final_height = parse_size(args.final_size)
    gen_width, gen_height = legal_generation_size(final_width, final_height)
    jobs = read_jsonl(Path(args.input))
    prepared: List[Dict[str, Any]] = []
    for job in jobs:
        item = dict(job.raw)
        item["size"] = f"{gen_width}x{gen_height}"
        if args.quality and "quality" not in item:
            item["quality"] = args.quality
        if args.output_format and "output_format" not in item:
            item["output_format"] = args.output_format
        prepared.append(item)
    write_jsonl(Path(args.output), prepared)
    print(
        f"wrote {args.output} with generation size {gen_width}x{gen_height} "
        f"for final {final_width}x{final_height}"
    )
    return 0


def verify_and_maybe_rerun(args: argparse.Namespace) -> Tuple[List[ExpectedOutput], List[ExpectedOutput]]:
    jobs = read_jsonl(Path(args.input))
    outputs = expected_outputs(jobs, Path(args.out_dir), args.output_format, args.n)
    missing = missing_outputs(outputs, args.min_bytes)
    if missing:
        missing_jsonl = Path(args.missing_jsonl)
        write_jsonl(missing_jsonl, unique_missing_jobs(missing))
        print(f"missing outputs: {len(missing)}")
        print(f"wrote retry batch: {missing_jsonl}")
        for item in missing[:20]:
            print(f"- {item.path}")
        if len(missing) > 20:
            print(f"... {len(missing) - 20} more")
        if args.run_missing:
            code = run_missing_jobs(
                missing_jsonl=missing_jsonl,
                out_dir=Path(args.out_dir),
                wrapper=Path(args.wrapper),
                concurrency=args.concurrency,
                max_attempts=args.max_attempts,
                force=args.force,
                dry_run=args.dry_run,
            )
            if code != 0:
                die(f"missing rerun failed with exit code {code}", code)
            if args.dry_run:
                print("dry-run: missing files were not rechecked because no images were generated")
                return outputs, missing
            missing = missing_outputs(outputs, args.min_bytes)
            if missing:
                die(f"{len(missing)} outputs still missing after rerun", 2)
    else:
        print(f"all expected outputs exist: {len(outputs)}")
    return outputs, missing


def cmd_verify(args: argparse.Namespace) -> int:
    _, missing = verify_and_maybe_rerun(args)
    if missing and args.run_missing and args.dry_run:
        return 0
    return 2 if missing else 0


def cmd_postprocess(args: argparse.Namespace) -> int:
    final_width, final_height = parse_size(args.final_size)
    outputs, missing = verify_and_maybe_rerun(args)
    if missing:
        return 2
    final_dir = Path(args.final_dir)
    for item in outputs:
        dest = final_dir / item.path.name
        src_w, src_h = save_cover_crop(item.path, dest, final_width, final_height)
        if (src_w, src_h) != (final_width, final_height):
            print(f"{item.path.name}: {src_w}x{src_h} -> {final_width}x{final_height}")
    if not args.no_index:
        output = Path(args.index)
        if not output.is_absolute():
            output = final_dir / output
        build_index(final_dir, output, args.thumb_max, args.title)
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    build_index(Path(args.image_dir), Path(args.output), args.thumb_max, args.title)
    return 0


def add_common_verify_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, help="JSONL batch file")
    parser.add_argument("--out-dir", required=True, help="directory used by image_gen.py --out-dir")
    parser.add_argument("--output-format", default=DEFAULT_OUTPUT_FORMAT)
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("--min-bytes", type=int, default=1)
    parser.add_argument("--missing-jsonl", default="missing.jsonl")
    parser.add_argument("--run-missing", action="store_true", help="call the relay wrapper for missing jobs")
    parser.add_argument("--dry-run", action="store_true", help="dry-run the missing rerun command")
    parser.add_argument("--force", action="store_true", help="pass --force to image_gen.py when rerunning")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument(
        "--wrapper",
        default=default_wrapper_path(),
        help="path to run-with-codex-auth.sh on WSL/Linux or run-with-codex-auth.ps1 on Windows",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare, verify, rerun, crop, and index image-gen batches.")
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="show legal generation size for an arbitrary final size")
    plan.add_argument("--final-size", required=True)
    plan.add_argument("--input")
    plan.set_defaults(func=cmd_plan)

    prepare = sub.add_parser("prepare", help="write a JSONL copy with legal generation size")
    prepare.add_argument("--input", required=True)
    prepare.add_argument("--output", required=True)
    prepare.add_argument("--final-size", required=True)
    prepare.add_argument("--quality")
    prepare.add_argument("--output-format")
    prepare.set_defaults(func=cmd_prepare)

    verify = sub.add_parser("verify", help="detect missing/empty outputs and optionally rerun them")
    add_common_verify_args(verify)
    verify.set_defaults(func=cmd_verify)

    postprocess = sub.add_parser("postprocess", help="crop/resize outputs to exact final size and build an index")
    add_common_verify_args(postprocess)
    postprocess.add_argument("--final-size", required=True)
    postprocess.add_argument("--final-dir", required=True)
    postprocess.add_argument("--index", default="index.html")
    postprocess.add_argument("--no-index", action="store_true")
    postprocess.add_argument("--thumb-max", type=int, default=420)
    postprocess.add_argument("--title", default="Image Reference Overview")
    postprocess.set_defaults(func=cmd_postprocess)

    index = sub.add_parser("index", help="build a thumbnail HTML overview for an image directory")
    index.add_argument("--image-dir", required=True)
    index.add_argument("--output", required=True)
    index.add_argument("--thumb-max", type=int, default=420)
    index.add_argument("--title", default="Image Reference Overview")
    index.set_defaults(func=cmd_index)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
