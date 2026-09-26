# FAP 1.0.01 Web-Assisted Self-Improvement

## Purpose

This side branch adds a bounded self-improvement loop to public FAP:

```text
goal / failure
  -> current web research (OpenAI Responses API + web_search)
  -> repository plan
  -> external reasoning proposes a bounded patch
  -> detached Git worktree
  -> focused + regression verification
  -> bounded repair when verification fails
  -> verified candidate or reject
```

The loop does not merge or push `main`. Promotion remains a separate explicit gate.

## ChatGPT browser behavior

`--open-chatgpt-ui` opens `https://chatgpt.com/` in the normal system browser for a human-visible session.

The automated reasoning path does **not** scrape the ChatGPT web UI, cookies, or browser session. It uses the OpenAI Responses API so UI changes and login state do not become a runtime dependency.

## Credentials

Set the API key in the process environment:

### PowerShell

```powershell
$env:OPENAI_API_KEY = "..."
$env:FAP_OPENAI_MODEL = "gpt-5.6-sol"
```

### bash

```bash
export OPENAI_API_KEY="..."
export FAP_OPENAI_MODEL="gpt-5.6-sol"
```

Do not commit API keys, cookies, browser profiles, or session tokens.

## Example

Run from a non-main branch:

```bash
python fap_self_improvement_controller.py \
  --goal "Improve fap_repository_test_selector.py without weakening existing verification" \
  --branch side/1.0.01-my-candidate \
  --preferred-path fap_repository_test_selector.py
```

Open ChatGPT visibly as well:

```bash
python fap_self_improvement_controller.py \
  --goal "Investigate and improve repository test selection" \
  --branch side/1.0.01-my-candidate \
  --preferred-path fap_repository_test_selector.py \
  --open-chatgpt-ui
```

Disable network research while retaining the same bounded patch path:

```bash
python fap_self_improvement_controller.py \
  --goal "Improve fap_repository_test_selector.py" \
  --branch side/1.0.01-my-candidate \
  --preferred-path fap_repository_test_selector.py \
  --no-web-search
```

## Safety and integrity gates

The controller:

- refuses `main` and `master` as self-improvement targets;
- treats repository excerpts, webpages, comments, and test output as untrusted data;
- allows model-proposed edits only for exact paths and operations already selected by the repository planner;
- uses planner-owned SHA-256 preconditions instead of trusting a model-provided hash;
- reuses the existing detached-worktree executor, security policy, verifier, and bounded repair loop;
- does not allow a failed candidate to promote itself;
- does not automatically merge or push the verified candidate.

A `verified_candidate` result means the proposed patch passed the selected verification inside an isolated worktree. It is not equivalent to a mainline release.

## Verification

The dedicated CI runs without a real OpenAI credential. The HTTP transport is mocked and verifies:

- Responses API request construction and web-search tool selection;
- extraction of response text and source URLs;
- ChatGPT UI opening only when explicitly enabled;
- rejection of out-of-plan file edits;
- planner SHA preservation;
- refusal to self-modify `main`.
