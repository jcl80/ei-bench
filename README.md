# ei-bench

Benchmark for evaluating how well LLMs can classify news articles as existentially important, using controlled human annotations as ground truth.

## Background

This benchmark was born from a failed first attempt. We tried using production labels from Sentinel's [Eye of Sauron](https://github.com/NunoSempere/eye-of-sauron) pipeline as ground truth — 8,042 articles labeled yes/no by a human reviewer. When GPT-5 scored 10% precision against those labels, we investigated and found the annotation process was noisy: batch review (10+ articles at a time), no controlled criteria application, and the annotator had access to more information than we were giving the models.

So we built this. Fresh articles, defined criteria, controlled annotation, matched inputs between human and model.

## What is "existential importance"?

An article is existentially important if it describes events that could threaten humanity at scale:

- More than 100 deaths
- A novel pathogen or spreading sickness
- Conflict between nuclear powers
- Conflict that could escalate into global conflict
- Terrorist groups displaying new capabilities
- Events that could threaten humanity as a whole

This includes precursors to existential risk — events that are not yet catastrophic but could lead there (military buildups, diplomatic breakdowns between nuclear powers, novel pathogen variants, etc.).

Opinion pieces, reviews of past events, and minor developments in ongoing conflicts (unless involving escalation or 1000+ deaths) are NOT existentially important. Many articles describe events that are important or noteworthy but not existentially so.

These criteria come from the production [CheckExistentialImportance](https://github.com/NunoSempere/eye-of-sauron) function.

## Dataset

2,472 articles from March–April 2026 production data, cleaned and deduplicated. These articles:

- Were never seen by the human reviewer before (no prior labels, no hindsight bias)
- Are post-training-cutoff for all tested models
- Have cached full article text for reproducibility
- Were filtered to require both summary and article text
- Were deduplicated by content (AP/Reuters wire stories appearing across multiple outlets)

Each article was annotated by two independent human reviewers who received:
- Article title
- AI-generated summary (from the production pipeline)
- Cached full article text
- The existential importance criteria (listed above)

For each article the annotator recorded:
- **important**: yes, no, or defective (junk/unreadable — filtered before scoring)
- **read_article**: whether they read the full article text, or decided from the title/summary alone

Models receive the same information the annotator received (title, summary, cached article text).

## Repo structure

```
ei-bench/
├── QUICKSTART.md                # annotator quickstart (phases 1-3)
├── annotate/                    # annotation interface
│   ├── annotate.py              # curses TUI for human annotation
│   └── GUIDE.md                 # full annotator guide
│
├── bench/                       # benchmarking harness
│   ├── data/
│   │   ├── calibration.jsonl    # 20 articles for calibration round
│   │   ├── overlap.jsonl        # 100 articles for inter-annotator agreement
│   │   └── articles_solo.jsonl  # 2,422 articles for solo annotation
│   ├── agree.py                 # inter-annotator agreement (Cohen's kappa)
│   ├── prompts/
│   │   ├── prompt_a.txt         # with criteria
│   │   └── prompt_b.txt         # bare (no criteria)
│   ├── results/                 # model outputs
│   ├── runner.py                # run models
│   └── eval.py                  # scoring
│
└── README.md
```

## Annotation methodology

The annotator receives the existential importance criteria before starting. For each article they see the title, link, and can reveal the summary and cached article text. They record:

1. Is this article existentially important? (yes / no / defective)
2. Did you read the full article text? (yes / no — asked as a confirmation after each yes/no annotation)

Defective articles (junk scrapes, paywalled teasers, foreign language, duplicates) are flagged and filtered out before scoring. Articles where the annotator read the full text vs decided from summary only are tracked separately. This lets us measure whether model performance differs on "easy" articles (decidable from summary) vs "hard" articles (required full reading).

Two annotators independently label an overlap set (~100 articles). Agreement is measured with Cohen's kappa (`bench/agree.py`). Disagreements are adjudicated through discussion.

## Models

Candidate models that fit at original or near-lossless precision on a single purchasable GPU:

| Model | Architecture | VRAM |
|-------|-------------|------|
| gpt-oss-120b | MoE 117B (5.1B active) | ~65GB MXFP4 |
| gpt-oss-20b | MoE 21B (3.6B active) | ~16GB MXFP4 |
| Qwen3.5-27B | Dense 27B | ~54GB BF16 |
| Qwen3-32B | Dense 32B | ~64GB BF16 |
| Qwen3.5-9B | Dense 9B | ~18GB BF16 |
| Gemma 3 27B | Dense 27B | ~54GB BF16 |
| GLM-4-32B | Dense 32B | ~64GB BF16 |

GPT-5 and GPT-5-mini included as API baselines.

All open models served via vLLM on RTX Pro 6000 Blackwell (96GB).

## Metrics

- **Precision** — of articles the model flags, what fraction did the human also flag?
- **Recall** — of articles the human flagged, how many does the model catch?
- **F1** — harmonic mean
- **Speed** — articles classified per minute

Split by:
- Annotator read full article vs summary-only decision

## Setup

```bash
uv sync
echo "OPENAI_API_KEY=sk-..." > .env
```

## Running annotation

See [QUICKSTART.md](QUICKSTART.md) for the three-phase annotation process (calibration, overlap, solo).

## Inter-annotator agreement

```bash
cd bench
python3 agree.py data/overlap_annotator1.jsonl data/overlap_annotator2.jsonl --articles data/overlap.jsonl --export data/disagreements.csv
```

## Running benchmarks

```bash
cd bench
python runner.py --model gpt-5-mini --prompt prompt_a --data data/articles.jsonl --workers 10
python eval.py --results results/<run>/ --annotations data/annotations.jsonl
```

## Related

- [threat-bench](https://github.com/jcl80/threat-bench) — the original benchmark (Reddit track + initial news track)
- [Eye of Sauron](https://github.com/NunoSempere/eye-of-sauron) — the production pipeline
- [Blog series](https://jorgecambra.com/blog/offloading-sentinel-local-inference-part-0) — Part 0 (Reddit), Part 1 (news + this benchmark)