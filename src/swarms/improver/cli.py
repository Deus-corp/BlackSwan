from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
from typing import Final, Optional, Sequence

from src.swarms.improver.improver_agent import (
    DEFAULT_MEMORY_DB,
    ImproverAgent,
    logger,
)

PROVIDER_CHOICES: Final = ("auto", "mistral", "groq", "gemini")


def _csv_env(value: str | None) -> str:
    if value is None:
        return ""
    return ",".join(part.strip() for part in value.split(",") if part.strip())


def _clear_provider_env() -> None:
    keys = (
        "MISTRAL_API_KEY",
        "MISTRAL_API_URL",
        "MISTRAL_MODEL",
        "MISTRAL_CRITIC_MODEL",
        "GROQ_API_KEY",
        "GROQ_API_KEY2",
        "GROQ_API_URL",
        "GROQ_MODEL",
        "GROQ_CRITIC_MODEL",
        "GEMINI_API_KEYS",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "GEMINI_CRITIC_MODEL",
    )

    for key in keys:
        os.environ.pop(key, None)


def _apply_provider_overrides(args: argparse.Namespace) -> None:
    """
    Apply explicit provider selection into environment variables so
    ImproverAgent can continue using its provider auto-detection logic.
    """
    if args.provider == "auto":
        return

    mistral_key = (
        args.mistral_api_key
        or os.environ.get("MISTRAL_API_KEY", "")
    )

    groq_key = (
        args.groq_api_key
        or os.environ.get("GROQ_API_KEY2")
        or os.environ.get("GROQ_API_KEY", "")
    )

    gemini_keys = (
        args.gemini_api_keys
        or os.environ.get("GEMINI_API_KEYS")
        or os.environ.get("GEMINI_API_KEY", "")
    )

    _clear_provider_env()

    if args.provider == "mistral":
        if not mistral_key:
            raise SystemExit("Mistral selected but no API key was provided.")

        os.environ["MISTRAL_API_KEY"] = mistral_key

        if args.mistral_api_url:
            if not args.mistral_api_url.startswith(("http://", "https://")):
                raise SystemExit("Invalid Mistral API URL.")
            os.environ["MISTRAL_API_URL"] = args.mistral_api_url

        if args.mistral_model:
            os.environ["MISTRAL_MODEL"] = args.mistral_model

        if args.mistral_critic_model:
            os.environ["MISTRAL_CRITIC_MODEL"] = args.mistral_critic_model

        return

    if args.provider == "groq":
        if not groq_key:
            raise SystemExit("Groq selected but no API key was provided.")

        os.environ["GROQ_API_KEY"] = groq_key

        if args.groq_api_url:
            if not args.groq_api_url.startswith(("http://", "https://")):
                raise SystemExit("Invalid Groq API URL.")
            os.environ["GROQ_API_URL"] = args.groq_api_url

        if args.groq_model:
            os.environ["GROQ_MODEL"] = args.groq_model

        if args.groq_critic_model:
            os.environ["GROQ_CRITIC_MODEL"] = args.groq_critic_model

        return

    if args.provider == "gemini":
        if not gemini_keys:
            raise SystemExit("Gemini selected but no API key was provided.")

        os.environ["GEMINI_API_KEYS"] = _csv_env(gemini_keys)

        if args.gemini_model:
            os.environ["GEMINI_MODEL"] = args.gemini_model

        if args.gemini_critic_model:
            os.environ["GEMINI_CRITIC_MODEL"] = args.gemini_critic_model

        return

    raise SystemExit(f"Unsupported provider: {args.provider}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Autonomous code improver with memory, critique loop, "
            "validation, and proposal generation."
        )
    )

    #
    # Core behavior
    #
    parser.add_argument(
        "--single-pass",
        action="store_true",
        help="Run one improvement cycle and exit.",
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

    #
    # Scan configuration
    #
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

    #
    # Output configuration
    #
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

    #
    # Rewrite mode
    #
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

    #
    # Provider
    #
    parser.add_argument(
        "--provider",
        choices=PROVIDER_CHOICES,
        default="auto",
        help="Force provider selection.",
    )

    #
    # Mistral
    #
    parser.add_argument(
        "--mistral-api-key",
        type=str,
        default=None,
        help="Override Mistral API key.",
    )

    parser.add_argument(
        "--mistral-api-url",
        type=str,
        default=None,
        help="Override Mistral API URL.",
    )

    parser.add_argument(
        "--mistral-model",
        type=str,
        default=None,
        help="Override Mistral planner model.",
    )

    parser.add_argument(
        "--mistral-critic-model",
        type=str,
        default=None,
        help="Override Mistral critic model.",
    )

    #
    # Groq
    #
    parser.add_argument(
        "--groq-api-key",
        type=str,
        default=None,
        help="Override Groq API key.",
    )

    parser.add_argument(
        "--groq-api-url",
        type=str,
        default=None,
        help="Override Groq API URL.",
    )

    parser.add_argument(
        "--groq-model",
        type=str,
        default=None,
        help="Override Groq planner model.",
    )

    parser.add_argument(
        "--groq-critic-model",
        type=str,
        default=None,
        help="Override Groq critic model.",
    )

    #
    # Gemini
    #
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
        "--gemini-critic-model",
        type=str,
        default=None,
        help="Override Gemini critic model.",
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
        proposals=args.proposals,
        memory_db=args.memory_db,
        enable_validation=not args.no_validation,
        enable_critique=not args.no_critique,
        max_files_per_batch=args.max_files_per_batch,
        scan_dirs=scan_dirs,
        output_dir=args.output_dir,
        failed_dir=args.failed_dir,
        proposals_dir=args.proposals_dir,
        staging_dir=args.staging_dir,
        prefer_patch=args.prefer_patch,
        workspace_dir=args.workspace_dir,
    )

    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        logger.info("ImproverAgent stopped by user.")


if __name__ == "__main__":
    main()