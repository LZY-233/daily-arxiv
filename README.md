# Daily arXiv Research Radar

[Live demo](https://lzy-233.github.io/daily-arxiv/) | [Daily workflow](https://github.com/LZY-233/daily-arxiv/actions/workflows/daily.yml)

Daily arXiv is a self-hosted research-paper radar for finding relevant work in the daily arXiv stream. It fetches recent paper metadata, applies a transparent preference-based ranking policy, enriches the highest-ranked papers with Chinese summaries and one-sentence TL;DRs, and publishes the result as a static GitHub Pages site.

The default editorial profile focuses on foundation-model research: LLMs, multimodal language models, Mixture-of-Experts, agents, training methods, model architecture, reasoning, and efficiency. It currently boosts MoE, scaling-law, compute-matched, routing, and training-mechanism work while down-ranking papers whose main contribution is hallucination analysis, benchmark construction, or safety evaluation.

## Features

- Fetches recent papers from multiple arXiv categories and deduplicates cross-listed entries.
- Filters and ranks papers using readable JSON configuration rather than an opaque recommender.
- Groups results into **Must Read**, **Browse**, and **Watch** tiers.
- Uses `deepseek-v4-flash` to produce a faithful Chinese abstract and a concise Chinese TL;DR for the top 15 papers.
- Reuses previously generated summaries to avoid paying for the same paper version twice.
- Falls back to the original English abstract when the API key is absent or AI enrichment fails.
- Publishes a responsive, backend-free website with search, topic filters, saved/read/ignored states, and expandable abstracts.
- Stores auditable JSON/JSONL data and never downloads paper PDFs.
- Runs automatically with GitHub Actions and deploys through GitHub Pages.

## How it works

```text
arXiv API
   ↓
category fetch + time-window filtering + deduplication
   ↓
topic matching + exclusions + quality/preference signals
   ↓
Must Read / Browse / Watch ranking
   ↓
DeepSeek enrichment for uncached featured papers
   ↓
JSONL archive + latest.json + static GitHub Pages site
```

Ranking and AI enrichment use only titles and abstracts. A high rank or an AI summary is not a full-paper quality review.

## Run locally

Requirements:

- Python 3.11 or newer
- No third-party Python packages

Clone the repository and run the offline fixture first:

```bash
git clone https://github.com/LZY-233/daily-arxiv.git
cd daily-arxiv
python scripts/daily.py --fixture tests/fixtures/arxiv_feed.xml --now 2026-09-03T10:00:00+08:00
python -m http.server 8000 --directory site
```

Open <http://localhost:8000>.

Fetch real arXiv data:

```bash
python scripts/daily.py --lookback-hours 72 --max-results 1000
```

Without `DEEPSEEK_API_KEY`, this command still completes and publishes English abstracts.

To enable Chinese summaries locally, set the key only in an environment variable.

PowerShell:

```powershell
$env:DEEPSEEK_API_KEY = "your-key"
python scripts/daily.py --lookback-hours 72 --max-results 1000
```

Bash:

```bash
export DEEPSEEK_API_KEY="your-key"
python scripts/daily.py --lookback-hours 72 --max-results 1000
```

Never place an API key in a tracked file.

## Build your own daily paper radar

The following guide turns a fork into an independently scheduled paper radar.

### 1. Fork the repository

Click **Fork** on GitHub and create the fork under your own account. GitHub does not copy Actions secrets into forks, so you must configure your own API key later.

Clone your fork:

```bash
git clone https://github.com/YOUR_USERNAME/daily-arxiv.git
cd daily-arxiv
```

You may keep the existing generated history as an example. If you want an entirely new archive, remove the generated files under `data/papers/`, `data/runs/`, `data/latest.json`, and `site/data/latest.json` in your fork before the first production run.

### 2. Choose arXiv categories and search preferences

Edit [`config/topics.json`](config/topics.json). Its main fields are:

| Field | Purpose |
| --- | --- |
| `categories` | arXiv categories queried independently, such as `cs.CL`, `cs.AI`, or `cs.LG`. |
| `lookback_hours` | Default local lookback window when the CLI does not override it. |
| `must_read_count` | Number of papers placed in the highest-priority tier. |
| `browse_count` | Number of additional featured papers. |
| `topics` | Topic IDs, display labels, priorities, weights, and matching phrases. |
| `quality_signals` | Phrases that indicate methods, scale, evidence, or open resources. |
| `preference_signals.boost` | Extra points for work matching personal interests. |
| `preference_signals.title_penalty` | Down-ranking rules for unwanted primary contributions. |
| `vertical_exclusions` | Application areas or narrow tasks to remove. |
| `foundation_overrides` | General-method phrases that can override a vertical exclusion. |

A minimal custom topic looks like this:

```json
{
  "id": "retrieval",
  "label": "Retrieval / RAG",
  "priority": "core",
  "weight": 16,
  "phrases": ["retrieval-augmented generation", "retrieval augmented generation", "RAG"]
}
```

Matching is currently case-insensitive substring matching over the title and English abstract. Keep phrases specific enough to avoid accidental matches. After adding a new topic ID, also add its website label to `topicLabels` in [`site/assets/app.js`](site/assets/app.js). Unknown IDs still work but are displayed as the raw ID.

Useful customization patterns:

- Increase a topic's `weight` to rank it more highly.
- Add a boost when a technique matters to you but should not be a required topic.
- Add a title penalty when you want papers to remain searchable but rarely enter the featured tiers.
- Add a vertical exclusion when an entire application area is out of scope.
- Use `foundation_overrides` carefully: matching one of these phrases allows a paper through even when it matches an exclusion.

Test preference changes without fetching arXiv again:

```bash
python scripts/daily.py --source-json data/latest.json
```

### 3. Customize the output language or summary policy

The DeepSeek prompt is in [`src/daily_arxiv/enrichment.py`](src/daily_arxiv/enrichment.py). Edit the `instructions` text if you want another language, a different TL;DR style, or different terminology rules. Keep the `abstract_zh`, `tldr_zh`, and `arxiv_id` output keys unless you also update the data model and frontend.

The current website interface is Chinese. To localize the interface itself, update the visible strings in [`site/index.html`](site/index.html) and the labels in [`site/assets/app.js`](site/assets/app.js).

By default, only Must Read and Browse papers are enriched, up to 15 papers per run. Existing summaries are cached by arXiv ID and version.

### 4. Add the DeepSeek API key

Create a DeepSeek API key in your own DeepSeek account. In the forked GitHub repository:

1. Open **Settings → Secrets and variables → Actions**.
2. Select the **Secrets** tab.
3. Click **New repository secret**.
4. Name it exactly `DEEPSEEK_API_KEY`.
5. Paste the key and save it.

The workflow injects this secret into only the fetch-and-rank step. It is never written to the repository, generated JSON, or Git history.

Optional repository variables can be added under **Settings → Secrets and variables → Actions → Variables**:

| Variable | Default | Description |
| --- | --- | --- |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | DeepSeek model used for enrichment. |
| `DEEPSEEK_ENRICH_LIMIT` | `15` locally | Maximum number of featured papers enriched per run. |
| `DEEPSEEK_BATCH_SIZE` | `5` locally | Papers sent in each API request. |

The included workflow currently exposes `DEEPSEEK_MODEL`. To control the other two values in Actions, add them to the step's `env` block in [`.github/workflows/daily.yml`](.github/workflows/daily.yml).

### 5. Enable GitHub Actions write access

The workflow commits updated JSON data back to the repository, so it needs write access:

1. Open **Settings → Actions → General**.
2. Under **Workflow permissions**, select **Read and write permissions**.
3. Save the setting.
4. Open the repository's **Actions** tab and enable workflows if GitHub asks you to do so for the fork.

### 6. Enable GitHub Pages

1. Open **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.
3. No branch or folder selection is required; the workflow uploads the `site/` directory directly.

After the first successful deployment, the site will normally be available at:

```text
https://YOUR_USERNAME.github.io/daily-arxiv/
```

### 7. Run the workflow once

Open **Actions → Daily arXiv radar**, click **Run workflow**, select the default branch, and confirm the run.

A successful run should complete these stages:

1. Run tests.
2. Fetch and rank recent papers.
3. Generate or reuse Chinese summaries.
4. Commit updated data.
5. Deploy GitHub Pages.

Check `stats.enrichment` in `data/latest.json` or the latest line in `data/runs/YYYY-MM.jsonl`:

```json
{
  "provider": "deepseek",
  "model": "deepseek-v4-flash",
  "status": "completed",
  "generated": 15,
  "failed_batches": 0,
  "missing_outputs": 0
}
```

`skipped_no_key` means the secret was not available. `partial` or `failed` means the site was still published, but some or all featured papers fell back to English.

### 8. Adjust the schedule

The default schedule is defined in [`.github/workflows/daily.yml`](.github/workflows/daily.yml):

```yaml
schedule:
  - cron: "7 2 * * 1-5"
```

GitHub cron expressions use UTC. This expression requests 02:07 UTC, Monday through Friday, which is 10:07 in Asia/Shanghai. Scheduled workflows can start later than the requested minute.

To run every calendar day at the same UTC time, use:

```yaml
- cron: "7 2 * * *"
```

The included workflow explicitly passes `--lookback-hours 72`. If you change `lookback_hours` in `config/topics.json`, also change or remove that CLI argument in the workflow; otherwise the workflow value takes precedence.

## Configuration reference

The pipeline recognizes these environment variables:

| Name | Required | Default | Purpose |
| --- | --- | --- | --- |
| `DEEPSEEK_API_KEY` | No | Empty | Enables Chinese AI enrichment. |
| `DEEPSEEK_MODEL` | No | `deepseek-v4-flash` | Selects the DeepSeek model. |
| `DEEPSEEK_ENRICH_LIMIT` | No | `15` | Limits the number of featured papers sent for enrichment. |
| `DEEPSEEK_BATCH_SIZE` | No | `5` | Controls API request batch size. |

CLI options:

```text
--fixture PATH          Use an offline Atom fixture instead of arXiv
--source-json PATH      Re-rank an existing latest.json without fetching
--now ISO_DATETIME      Override the run timestamp
--lookback-hours N      Override the configured time window
--max-results N         Maximum results requested per arXiv category
--config PATH           Use a different topic configuration file
```

## Data layout

```text
config/topics.json          Categories, topics, weights, and preference rules
data/latest.json            Latest complete ranked result
data/papers/YYYY-MM.jsonl   Deduplicated monthly paper archive
data/runs/YYYY-MM.jsonl     Append-only run statistics
site/index.html             Static application shell
site/assets/                Frontend JavaScript and CSS
site/data/latest.json       Browser-facing copy of the latest result
src/daily_arxiv/            Fetching, parsing, ranking, enrichment, and storage
scripts/daily.py            Local and scheduled entry point
tests/                      Unit tests and offline arXiv fixture
```

Saved, read, and ignored states are stored only in the browser's `localStorage`. They are not committed or synchronized across devices.

## Testing and development

Run the test suite:

```bash
python -m unittest discover -s tests -v
```

Validate the frontend JavaScript when Node.js is available:

```bash
node --check site/assets/app.js
```

The project deliberately uses only the Python standard library, including for arXiv and DeepSeek HTTP requests.

## Current limitations

- Ranking is a heuristic baseline based on titles and abstracts, not citation impact or full-text review.
- Chinese summaries and TL;DRs are model-generated and should be checked against the original abstract.
- PDF content, experiment details, and reproducibility claims are not reviewed.
- Scheduled GitHub Actions runs are not guaranteed to start at the exact cron minute.
- Browser reading state is local to one browser profile.
- Delayed re-review, citation tracking, code-activity checks, weekly digests, and notifications are not implemented yet.

## Privacy and cost

- arXiv metadata and generated summaries are stored in the public repository.
- Paper PDFs are linked but never downloaded or committed.
- The DeepSeek API receives the title and English abstract of featured papers.
- API usage is limited and cached, but the repository owner is responsible for provider charges.
- Keep all credentials in environment variables or GitHub Actions Secrets.

## License

Released under the [MIT License](LICENSE).
