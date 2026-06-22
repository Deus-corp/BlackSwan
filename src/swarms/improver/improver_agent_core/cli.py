from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
from typing import Final, Optional, Sequence

from ..improver_agent import DEFAULT_MEMORY_DB, ImproverAgent, logger

PROVIDER_CHOICES: Final = ("auto", "gemini", "deepseek")


def _csv_env(value: str | None) -> str:
    if value is None:
        return ""
    return ",".join(part.strip() for part in value.split(",") if part.strip())


def _clear_provider_env() -> None:
    keys = (
        "GEMINI_API_KEYS",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "GEMINI_CRITIC_MODEL",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_MODEL",
        "DEEPSEEK_API_URL",
    )
    for key in keys:
        os.environ.pop(key, None)


def _set_if_present(key: str, value: str | None) -> None:
    if value is not None and str(value).strip():
        os.environ[key] = str(value).strip()


def _apply_provider_overrides(args: argparse.Namespace) -> None:
    """
    Apply provider selection and CLI overrides via environment variables.

    ImproverAgent uses environment-based auto-detection:
    - Gemini is preferred when Gemini keys are present.
    - DeepSeek is used when Gemini is unavailable and DeepSeek key is present.
    """
    if args.provider == "auto":
        _set_if_present("GEMINI_API_KEYS", _csv_env(args.gemini_api_keys))
        _set_if_present("GEMINI_MODEL", args.gemini_model)
        _set_if_present("GEMINI_CRITIC_MODEL", args.gemini_critic_model)
        _set_if_present("GEMINI_MODELS", args.gemini_models)
        _set_if_present("GEMINI_CRITIC_MODELS", args.gemini_critic_models)
        _set_if_present("DEEPSEEK_API_KEY", args.deepseek_api_key)
        _set_if_present("DEEPSEEK_MODEL", args.deepseek_model)
        _set_if_present("DEEPSEEK_API_URL", args.deepseek_api_url)
        return

    _clear_provider_env()

    if args.provider == "gemini":
        gemini_keys = _csv_env(args.gemini_api_keys) or os.environ.get("GEMINI_API_KEY", "")
        if not gemini_keys.strip():
            raise SystemExit("Gemini selected but no API key was provided.")

        os.environ["GEMINI_API_KEYS"] = gemini_keys

        if args.gemini_model:
            os.environ["GEMINI_MODEL"] = args.gemini_model
        if args.gemini_critic_model:
            os.environ["GEMINI_CRITIC_MODEL"] = args.gemini_critic_model

        if args.gemini_models:
            os.environ["GEMINI_MODELS"] = args.gemini_models
        if args.gemini_critic_models:
            os.environ["GEMINI_CRITIC_MODELS"] = args.gemini_critic_models
            
        return

    if args.provider == "deepseek":
        deepseek_key = args.deepseek_api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        if not deepseek_key.strip():
            raise SystemExit("DeepSeek selected but no API key was provided.")

        os.environ["DEEPSEEK_API_KEY"] = deepseek_key.strip()

        if args.deepseek_model:
            os.environ["DEEPSEEK_MODEL"] = args.deepseek_model
        if args.deepseek_api_url:
            if not args.deepseek_api_url.startswith(("http://", "https://")):
                raise SystemExit("Invalid DeepSeek API URL.")
            os.environ["DEEPSEEK_API_URL"] = args.deepseek_api_url
        return

    raise SystemExit(f"Unsupported provider: {args.provider}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Autonomous code improver with memory, critique loop, "
            "validation, and proposal generation."
        )
    )

    parser.add_argument(
        "--single-pass",
        action="store_true",
        help="Run one improvement cycle and exit.",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
        help="Maximum number of improvement cycles to run before stopping.",
    )
    parser.add_argument(
        "--max-rate-limit-attempts",
        type=int,
        default=48,
        help="Maximum LLM rate-limit retry attempts before failing the current operation.",
    )
    parser.add_argument(
        "--max-llm-attempts",
        type=int,
        default=48,
        help="Maximum total LLM generation attempts before failing the current operation.",
    )
    parser.add_argument(
        "--llm-request-timeout",
        type=float,
        default=180.0,
        help="Timeout in seconds for a single LLM generation request.",
    )
    parser.add_argument(
        "--proposals",
        action="store_true",
        help="Generate project proposals after each cycle.",
    )
    parser.add_argument(
        "--memory-db",
        type=Path,
        default=DEFAULT_MEMORY_DB,
        help="Path to SQLite memory database.",
    )
    parser.add_argument(
        "--no-validation",
        action="store_true",
        help="Disable optional validation tools (ruff/mypy/pytest).",
    )
    parser.add_argument(
        "--no-critique",
        action="store_true",
        help="Disable critic/revision loop.",
    )
    parser.add_argument(
        "--max-files-per-batch",
        type=int,
        default=1,
        help="Maximum files processed per generation batch.",
    )
    parser.add_argument(
        "--max-files-total",
        type=int,
        default=None,
        help="Maximum total files processed per cycle.",
    )
    parser.add_argument(
        "--scan-dir",
        action="append",
        dest="scan_dirs",
        default=None,
        help="Directory to scan (can be passed multiple times).",
    )
    parser.add_argument(
        "--workspace-dir",
        type=Path,
        default=None,
        help=(
            "Optional isolated workspace directory where files are copied "
            "before improvements are applied."
        ),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override output directory.",
    )
    parser.add_argument(
        "--failed-dir",
        type=Path,
        default=None,
        help="Override failed/quarantine directory.",
    )
    parser.add_argument(
        "--proposals-dir",
        type=Path,
        default=None,
        help="Override proposals output directory.",
    )
    parser.add_argument(
        "--staging-dir",
        type=Path,
        default=None,
        help="Override validation staging directory.",
    )
    parser.add_argument(
        "--research-dir",
        type=Path,
        default=None,
        help="Override research artifact output directory.",
    )
    parser.add_argument(
        "--research-mode",
        action="store_true",
        help="Persist review artifacts for quarantined creative candidates.",
    )
    rewrite_group = parser.add_mutually_exclusive_group()
    rewrite_group.add_argument(
        "--prefer-patch",
        dest="prefer_patch",
        action="store_true",
        help="Prefer patch-oriented non-Python edits.",
    )
    rewrite_group.add_argument(
        "--full-rewrite",
        dest="prefer_patch",
        action="store_false",
        help="Prefer full-file rewrites.",
    )
    parser.set_defaults(prefer_patch=True)

    parser.add_argument(
        "--provider",
        choices=PROVIDER_CHOICES,
        default="auto",
        help="Force provider selection.",
    )

    parser.add_argument(
        "--gemini-api-keys",
        type=str,
        default=None,
        help="Comma-separated Gemini API keys.",
    )
    parser.add_argument(
        "--gemini-model",
        type=str,
        default=None,
        help="Override Gemini planner model.",
    )
    parser.add_argument(
        "--gemini-models",
        type=str,
        default=None,
        help=(
            "Comma-separated Gemini planner model fallback chain. "
            "Example: gemini-3.1-flash-lite,gemini-3.5-flash,gemini-2.5-flash-lite"
        ),
    )
    parser.add_argument(
        "--gemini-critic-models",
        type=str,
        default=None,
        help=(
            "Comma-separated Gemini critic model fallback chain. "
            "Defaults to --gemini-models or GEMINI_MODELS when unset."
        ),
    )
    parser.add_argument(
        "--gemini-critic-model",
        type=str,
        default=None,
        help="Override Gemini critic model.",
    )

    parser.add_argument(
        "--deepseek-api-key",
        type=str,
        default=None,
        help="Override DeepSeek API key.",
    )
    parser.add_argument(
        "--deepseek-model",
        type=str,
        default=None,
        help="Override DeepSeek planner model.",
    )
    parser.add_argument(
        "--deepseek-api-url",
        type=str,
        default=None,
        help="Override DeepSeek API URL.",
    )

    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    _apply_provider_overrides(args)

    scan_dirs: Optional[Sequence[str]]
    scan_dirs = args.scan_dirs if args.scan_dirs else None

    agent = ImproverAgent(
        single_pass=args.single_pass,
        max_cycles=args.max_cycles,
        max_rate_limit_attempts=args.max_rate_limit_attempts,
        max_llm_attempts=args.max_llm_attempts,
        llm_request_timeout=args.llm_request_timeout,
        proposals=args.proposals,
        memory_db=args.memory_db,
        enable_validation=not args.no_validation,
        enable_critique=not args.no_critique,
        max_files_per_batch=args.max_files_per_batch,
        max_files_total=args.max_files_total,
        scan_dirs=scan_dirs,
        output_dir=args.output_dir,
        failed_dir=args.failed_dir,
        proposals_dir=args.proposals_dir,
        staging_dir=args.staging_dir,
        research_dir=args.research_dir,
        research_mode=args.research_mode,
        prefer_patch=args.prefer_patch,
        workspace_dir=args.workspace_dir,
    )

    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        logger.info("ImproverAgent stopped by user.")


if __name__ == "__main__":
    main()