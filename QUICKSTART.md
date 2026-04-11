# Quick Start — Annotators

You'll be classifying news articles as existentially important or not. 
Read `annotate/GUIDE.md` for the full criteria and controls.

Ideally, do all three phases in order. If time is tight, 
Phase 3 alone is still valuable — skip straight to it.

## Phase 1: Calibration (both annotators, on a call, ~20 min)
```bash
cd annotate
python annotate.py --data ../bench/data/calibration.jsonl --output calibration_YOURNAME.jsonl --annotator YOURNAME
```

Go through all 20 articles together. Discuss disagreements openly. 
This is training — it's not scored.

## Phase 2: Overlap (both annotators, independently, ~30 min)
```bash
python annotate.py --data ../bench/data/overlap.jsonl --output overlap_YOURNAME.jsonl --annotator YOURNAME
```

100 articles. Do NOT discuss with the other annotator until both are done. 
This measures consistency between annotators.
Send your output file to Jorge when finished.

## Phase 3: Main annotation (solo, ~3-5 hours)
```bash
cd annotate
python annotate.py --data ../bench/data/articles_solo.jsonl --output annotations_YOURNAME.jsonl --annotator YOURNAME
```

Target: 500+ articles. Quit and resume anytime with `q`.
Each set has a different distribution — don't let previous sets 
calibrate your expectations.

**If you can only do one thing, do Phase 3.**

## Tips

- Read `annotate/GUIDE.md` before starting — it has the full criteria and controls
- Press `c` anytime during annotation to review the criteria
- Most articles are obvious no's from the title alone — speed is fine
- When in doubt, lean no
