# Annotator Guide — ei-bench

## What you're doing

You'll be classifying news articles as **existentially important** or **not**. Each article takes 15-60 seconds depending on whether you need to read the full text.

Your annotations become the ground truth for benchmarking whether AI models can do this task.

## Setup

```bash
cd ei-bench/annotate
python annotate.py --data ../bench/data/articles.jsonl --output ../bench/data/annotations_YOURNAME.jsonl --annotator YOURNAME
```

Replace `YOURNAME` with your name (e.g., `nuno`, `jorge`). This is how we track who annotated what.

You can quit anytime with `q` — your progress is saved. Run the same command to resume where you left off.

## The criteria

An article is **existentially important** if it describes:

- More than 100 deaths
- A novel pathogen or spreading sickness
- Conflict between nuclear powers
- Conflict that could escalate into global conflict
- Terrorist groups displaying new capabilities
- Events that could threaten humanity as a whole

This includes **precursors to existential risk** — events that are not yet catastrophic but could lead there. Military buildups that could trigger wider conflict, policy changes that lower barriers to nuclear use, new pathogen variants under surveillance, diplomatic breakdowns between nuclear powers, novel AI capabilities that could enable mass harm. The event doesn't have to be a catastrophe yet — if it meaningfully increases the probability of one, it qualifies.

An article is **NOT existentially important** if it is:

- An opinion piece or editorial (look for generic titles like "Why Nuclear Risks Have Not Gone Away")
- A review of past events (9/11 retrospectives, historical anniversaries)
- A minor development in an ongoing conflict that doesn't involve escalation or 1000+ deaths
- Important or noteworthy but not a threat to humanity at scale (e.g., Moon landing, new tech product, election results)

**The key distinction:** many articles are *important* but not *existentially* important. A trade deal, a political scandal, a natural disaster that kills 30 people — these matter, but they don't meet the threshold. However, don't dismiss precursors: a military exercise in the Taiwan Strait isn't a catastrophe, but it's a precursor that qualifies. The question is always "does this event meaningfully increase the probability of a global-scale catastrophe?" When in doubt on genuinely borderline cases, lean **no**.

## Controls

### List view

| Key | Action |
|-----|--------|
| `↑`/`↓` or `j`/`k` | Navigate articles |
| `←`/`→` | Change page |
| `Enter` | Open article detail |
| `n` | Jump to next unannotated article |
| `q` | Save and quit (resume later) |

The list shows your progress: green `■` = yes, dim `·` = no, red `x` = defective, blank = pending.

### Detail view

| Key | Action |
|-----|--------|
| `o` | Open article URL in browser |
| `s` | Toggle AI-generated summary |
| `t` | View cached article text (full screen, scrollable) |
| `c` | Show criteria reference |
| `y` | Mark as **existentially important** |
| `n` | Mark as **NOT existentially important** |
| `d` | Mark as **defective** (see below) |
| `Esc` | Back to list |

## What you see

Each article starts showing only the **title** and **link**. This is intentional — we want to track what information you needed to decide.

- If the title alone is enough to decide, just press `y` or `n`.
- If you need more context, press `s` for the summary or `o` to open the article in your browser.
- Press `t` to reveal the full cached article text in the terminal (for when the URL is dead or paywalled).

After pressing `y` or `n`, you'll see a **confirmation screen** asking: "Did you read the full article text?" Press `y` if you read the article (via `t` or `o`), or `n` if you decided from the title/summary alone. This is not a judgment — answering `n` is completely fine. We use this to measure whether model performance differs on "easy" vs "hard" articles. Press `Esc` to cancel and go back if you hit `y`/`n` by mistake.

Everything is tracked automatically: which keys you pressed, whether you opened the article, whether you revealed the summary, how long you spent. You don't need to do anything special — just annotate naturally.

## When to mark "defective" (`d`)

Press `d` if the article is **not annotatable**:

- The article is behind a paywall and has no usable summary
- The article text is in a language you can't read
- The article is clearly a duplicate of one you already annotated
- The "article" is actually an ad, a podcast transcript with no content, or a navigation page
- The summary and article text are both too garbled to understand

Defective articles are filtered out before scoring. Don't force a yes/no on something you can't meaningfully evaluate.

## Calibration

Before annotating independently, we'll do a calibration round together: 20 articles on a call, discussing each one. This ensures we're applying the criteria the same way.

After calibration, both annotators independently label an overlap set (~200 articles). We measure agreement. Then each annotator continues with their remaining articles solo.

## Tips

- **Each set is different.** Each annotation set has a different distribution of important vs not-important articles. Don't let the previous set calibrate your expectations for the next one. Start fresh, apply the criteria to each article independently.
- **Speed is fine.** Many articles are obvious from the title. "Airport Chaos Could Continue Into Summer" → `n`, move on. Don't overthink the easy ones.
- **When in doubt, lean no.** The criteria are specific. If you're not sure it meets the threshold, it probably doesn't.
- **Don't anchor on the summary.** The AI summary always argues for importance (the production AI flags 99.997% of articles as important). Read the summary for facts, not for its conclusion.
- **You can always quit and resume.** Progress saves after every annotation.

## Expected time

Your target is **500 articles**, but feel free to do as many as you can.

- ~15-30 seconds for obvious no's (most articles)
- ~30-60 seconds for articles that need a closer look
- Base rate is ~3% positive — the vast majority are quick `n`'s
- 500 articles: roughly 3-5 hours, split across multiple sessions
- You can quit and resume anytime — progress saves after every annotation