# FAP 1.0.01 Browser-Driven Self-Improvement

## Purpose

This side branch makes **real browser operation** the default self-improvement path.

```text
goal / failure
  -> FAP attaches to or launches Chrome
  -> FAP operates ChatGPT Web UI
  -> ChatGPT proposes search queries
  -> FAP opens a real search engine in Chrome
  -> FAP visits result pages and reads rendered text
  -> FAP sends browser-gathered evidence back through ChatGPT Web UI
  -> repository plan
  -> bounded patch proposal through ChatGPT Web UI
  -> detached Git worktree
  -> focused + regression verification
  -> bounded repair through ChatGPT Web UI
  -> verified candidate or reject
```

The browser path does **not** require an OpenAI API key.

The previous Responses API implementation remains available only as an explicit
fallback with `--backend api`.

## What "browser mode" means

Browser mode is not a URL-fetch substitute. FAP actually drives a Chromium
browser using Playwright:

- opens ChatGPT in a visible Chrome window;
- types prompts into the rendered ChatGPT composer;
- waits for and reads the rendered assistant response;
- opens Google or DuckDuckGo in the same browser;
- executes searches;
- follows result links;
- reads rendered page text;
- feeds the gathered evidence back into the reasoning loop.

The browser operator also exposes bounded `goto`, `click`, `fill`, and
`press` primitives for future browser tasks.

## Authentication model

Authentication stays under human control.

FAP does not read or export:

- passwords;
- browser cookie databases;
- session tokens;
- local-storage databases;
- browser credential stores.

Use a dedicated persistent Chrome profile for FAP. Log into ChatGPT manually
once in that profile. Later runs reuse the browser session by controlling the
visible browser.

## Windows setup

Install the Python Playwright package once:

```powershell
python -m pip install playwright
```

When FAP connects to an installed Chrome over CDP, a Playwright browser download
is not required.

Then launch a browser-driven self-improvement run:

```powershell
.\RUN_FAP_BROWSER_SELF_IMPROVE.ps1 `
  -Goal "Improve repository test selection without weakening verification" `
  -Branch "side/1.0.01-my-candidate" `
  -PreferredPath "fap_repository_test_selector.py"
```

The launcher:

1. finds installed Google Chrome;
2. creates/reuses `%LOCALAPPDATA%\FAP\browser-profile`;
3. starts Chrome with a local remote-debugging port;
4. opens ChatGPT;
5. connects FAP to that browser;
6. executes the browser-first self-improvement loop.

If ChatGPT is not signed in, sign in manually in the opened FAP Chrome window
and run the command again.

## Direct Python use

Attach to a Chrome instance already exposing CDP:

```powershell
python fap_self_improvement_controller.py `
  --backend browser `
  --cdp-url http://127.0.0.1:9222 `
  --goal "Improve fap_repository_test_selector.py" `
  --branch side/1.0.01-my-candidate `
  --preferred-path fap_repository_test_selector.py
```

Or let Playwright launch Chrome with a dedicated persistent profile:

```powershell
python fap_self_improvement_controller.py `
  --backend browser `
  --browser-profile "$env:LOCALAPPDATA\FAP\browser-profile" `
  --goal "Improve fap_repository_test_selector.py" `
  --branch side/1.0.01-my-candidate `
  --preferred-path fap_repository_test_selector.py
```

Browser mode is the CLI default, so `--backend browser` may be omitted.

## Search behavior

Default search engine:

```text
google
```

Alternative:

```powershell
--search-engine duckduckgo
```

With browser research enabled, FAP asks ChatGPT Web for a small set of search
queries, executes them in Chrome, visits a bounded number of result pages, and
provides the rendered evidence to ChatGPT Web.

Use `--no-web-search` to keep ChatGPT Web reasoning but skip search-engine
navigation.

## Optional API fallback

The old path is still available explicitly:

```powershell
$env:OPENAI_API_KEY = "..."
python fap_self_improvement_controller.py `
  --backend api `
  --goal "Improve fap_repository_test_selector.py" `
  --branch side/1.0.01-my-candidate
```

API mode is not the default.

## Safety and integrity gates

The controller:

- refuses `main` and `master` as self-improvement targets;
- treats repository excerpts, webpages, comments, and test output as untrusted
  data;
- accepts model-proposed edits only for exact paths and operations already
  selected by the repository planner;
- preserves planner-owned SHA-256 preconditions;
- reuses the detached-worktree executor, security policy, verifier, and bounded
  repair loop;
- restricts browser navigation helpers to HTTP(S);
- never automatically merges or pushes a failed candidate;
- keeps mainline promotion as a separate explicit gate.

A `verified_candidate` result means the patch passed the selected verification
inside an isolated worktree. It is not equivalent to a mainline release.

## Verification

The dedicated CI does not log into ChatGPT or contact external websites. It
tests the browser-control layer through fakes and verifies:

- browser mode is the default CLI backend;
- API mode remains explicit fallback;
- unsafe URL schemes are rejected;
- browser search query parsing is bounded;
- browser evidence is passed into the ChatGPT reasoning phase;
- no-search mode skips search-engine navigation;
- proposal edits cannot escape planner-selected paths;
- planner SHA preconditions are preserved;
- main/master self-modification is refused;
- the PowerShell launcher parses successfully;
- credential-like material is not committed.
