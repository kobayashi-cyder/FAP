from __future__ import annotations

import argparse
import json

from fap_browser_operator import BrowserSessionConfig, ChatGPTWebUI, PlaywrightBrowser


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check FAP Chrome/CDP and wait for ChatGPT Web readiness."
    )
    parser.add_argument("--cdp-url", required=True)
    parser.add_argument("--wait-sec", type=float, default=600.0)
    parser.add_argument("--search-engine", choices=("google", "duckduckgo"), default="google")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    browser = PlaywrightBrowser(
        BrowserSessionConfig(
            cdp_url=args.cdp_url,
            search_engine=args.search_engine,
        )
    )
    try:
        browser.start()
        readiness = ChatGPTWebUI(browser).wait_until_ready(args.wait_sec)
        payload = {
            "state": "ready" if readiness.ready else "login_timeout",
            "browser_healthy": browser.is_healthy(),
            "chatgpt": readiness.to_dict(),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if readiness.ready else 3
    except Exception as exc:
        print(
            json.dumps(
                {
                    "state": "browser_error",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 5
    finally:
        browser.close()


if __name__ == "__main__":
    raise SystemExit(main())
