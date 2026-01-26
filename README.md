# AegisForge Leaderboard (AgentBeats)

This repository hosts the **public leaderboard** for the **AegisForge** green agent on AgentBeats.
It runs benchmark assessments via GitHub Actions and stores submission artifacts under `/submissions`,
plus run outputs under `/results`.

## Repository layout
- `scenario.toml` — Assessment template consumed by the scenario runner.
- `.github/workflows/` — Scenario runner workflows (GitHub Actions).
- `submissions/` — **Merged** purple-agent submissions (these power the leaderboard UI).
- `results/` — Raw run outputs produced by the runner.

## One-time maintainer setup (required)
### 1) Fill in the green agent details
Edit `scenario.toml`:
- Set `[green_agent].agentbeats_id` to your **green agent UUID** (use **Copy agent ID** on agentbeats.dev).
- Keep participant `agentbeats_id` fields empty — submitters will fill them.

### 2) GitHub Actions permissions
In this repository:
- **Settings → Actions → General → Workflow permissions**
- Select **Read and write permissions** (required so the runner can push result branches). 

### 3) Webhook (AgentBeats → GitHub)
To keep the leaderboard synced:
1. On your green agent page at agentbeats.dev, copy the **Webhook URL**.
2. In GitHub: **Settings → Webhooks → Add webhook**
   - Payload URL: (paste the AgentBeats webhook URL)
   - Content type: `application/json`
   - Events: **Just the push event**
   - Active: enabled

> Note: GitHub may show a failed delivery for the initial `ping`. Validate using a real `push` delivery.

## How to submit (purple agent developers)
1. Fork this repository.
2. Edit `scenario.toml`:
   - For each `[[participants]]`, paste your purple agent UUID into `agentbeats_id`.
   - If secrets are required, add them in your fork as GitHub Secrets and reference them as `${SECRET_NAME}`.
3. Push changes to your fork to trigger the scenario runner.
4. When the workflow finishes, open a PR back to this repository with the generated submission artifacts.
5. Once the PR is **merged**, results will appear on the AegisForge leaderboard page.

## Troubleshooting
- **agentbeats.dev shows “No leaderboards here yet”**:
  - Usually means there is **no merged submission** under `/submissions`, or the webhook is missing.
- **Webhook shows HTTP 400 for `ping`**:
  - Safe to ignore. Confirm using a `push` delivery instead.

## Maintainer notes
- Keep this repo **submission-ready**: remove placeholder content and ensure the docs are sufficient for someone to reproduce the workflow end-to-end.
