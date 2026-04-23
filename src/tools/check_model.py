from __future__ import annotations

import argparse

from ..llm.client import call_llm
from ..llm.env import ENV

CHECK_SYSTEM_PROMPT = (
    "If the user writes 'Ping', reply with 'Pong' and nothing else."
)
CHECK_USER_PROMPT = "Ping"


def build_parser(registered_model_names: list[str]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check whether one or more configured models return a minimal response."
    )
    parser.add_argument(
        "--model-name",
        choices=registered_model_names,
        help="Model profile name from model_configs.yaml.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Test all model profiles from model_configs.yaml.",
    )
    return parser


def parse_args(registered_model_names: list[str]) -> argparse.Namespace:
    parser = build_parser(registered_model_names)
    args = parser.parse_args()
    if args.all == bool(args.model_name):
        parser.error("Set exactly one of --model-name or --all.")
    return args


def iter_selected_models(
    args: argparse.Namespace, registered_model_names: list[str]
) -> list[str]:
    if args.all:
        return registered_model_names
    return [args.model_name]


def clip_preview(text: str, max_length: int = 80) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 1] + "…"


def main() -> None:
    registered_model_names = sorted(ENV.get_registered_model_names())
    args = parse_args(registered_model_names)

    for model_name in iter_selected_models(args, registered_model_names):
        config = ENV.get_model_config(model_name)
        print(f"[{model_name}] calling {config.model}")
        try:
            response = call_llm(
                CHECK_SYSTEM_PROMPT,
                CHECK_USER_PROMPT,
                model_name=model_name,
            )
        except Exception as exc:
            print(f"[{model_name}] error: {exc}")
            continue

        print(f"[{model_name}] ok: {clip_preview(response)}")


if __name__ == "__main__":
    main()
