#!/usr/bin/env python3
"""
Inter-annotator agreement for ei-bench.

Compares two annotation files, computes Cohen's kappa,
and prints disagreements for adjudication.

Usage:
  python agree.py annotations_a.jsonl annotations_b.jsonl
  python agree.py annotations_a.jsonl annotations_b.jsonl --export disagreements.csv
"""

import json
import sys
from pathlib import Path


def load_annotations(path):
    annotations = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                a = json.loads(line)
                annotations[a['article_id']] = a
    return annotations


def cohen_kappa(labels_a, labels_b):
    """Cohen's kappa for two lists of binary labels (0/1)."""
    assert len(labels_a) == len(labels_b)
    n = len(labels_a)
    if n == 0:
        return 0.0

    # observed agreement
    agree = sum(a == b for a, b in zip(labels_a, labels_b))
    p_o = agree / n

    # expected agreement by chance
    a_pos = sum(labels_a) / n
    b_pos = sum(labels_b) / n
    p_e = (a_pos * b_pos) + ((1 - a_pos) * (1 - b_pos))

    if p_e == 1.0:
        return 1.0

    return (p_o - p_e) / (1 - p_e)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='ei-bench inter-annotator agreement')
    parser.add_argument('file_a', help='First annotation file (JSONL)')
    parser.add_argument('file_b', help='Second annotation file (JSONL)')
    parser.add_argument('--articles', help='Articles JSONL (to show titles in disagreements)')
    parser.add_argument('--export', help='Export disagreements to CSV')

    args = parser.parse_args()

    ann_a = load_annotations(Path(args.file_a))
    ann_b = load_annotations(Path(args.file_b))

    # find overlap
    overlap_ids = sorted(set(ann_a.keys()) & set(ann_b.keys()))

    if not overlap_ids:
        print("No overlapping articles found.")
        sys.exit(1)

    # load article titles if available
    titles = {}
    if args.articles:
        with open(args.articles) as f:
            for line in f:
                line = line.strip()
                if line:
                    art = json.loads(line)
                    titles[art['id']] = art.get('title', '')

    # extract labels
    labels_a = [1 if ann_a[aid]['answer'] == 'yes' else 0 for aid in overlap_ids]
    labels_b = [1 if ann_b[aid]['answer'] == 'yes' else 0 for aid in overlap_ids]

    annotator_a = ann_a[overlap_ids[0]].get('annotator', Path(args.file_a).stem)
    annotator_b = ann_b[overlap_ids[0]].get('annotator', Path(args.file_b).stem)

    # compute stats
    n = len(overlap_ids)
    agree = sum(a == b for a, b in zip(labels_a, labels_b))
    kappa = cohen_kappa(labels_a, labels_b)

    yes_a = sum(labels_a)
    yes_b = sum(labels_b)

    # disagreements
    disagreements = []
    for aid, la, lb in zip(overlap_ids, labels_a, labels_b):
        if la != lb:
            disagreements.append({
                'article_id': aid,
                'title': titles.get(aid, ''),
                annotator_a: 'yes' if la else 'no',
                annotator_b: 'yes' if lb else 'no',
                'read_a': ann_a[aid].get('read_article', ''),
                'read_b': ann_b[aid].get('read_article', ''),
            })

    # print results
    print()
    print("=" * 60)
    print(" INTER-ANNOTATOR AGREEMENT")
    print("=" * 60)
    print()
    print(f"  Annotators:     {annotator_a}  vs  {annotator_b}")
    print(f"  Overlap:        {n} articles")
    print(f"  Agreement:      {agree}/{n} ({agree/n*100:.1f}%)")
    print(f"  Cohen's kappa:  {kappa:.3f}")
    print()

    # interpret kappa
    if kappa >= 0.8:
        interp = "strong agreement"
    elif kappa >= 0.6:
        interp = "moderate agreement"
    elif kappa >= 0.4:
        interp = "fair agreement — consider tightening criteria"
    else:
        interp = "poor agreement — criteria need rework"
    print(f"  Interpretation: {interp}")
    print()

    # class distribution
    print(f"  {annotator_a}: {yes_a} yes, {n - yes_a} no ({yes_a/n*100:.1f}% positive)")
    print(f"  {annotator_b}: {yes_b} yes, {n - yes_b} no ({yes_b/n*100:.1f}% positive)")
    print()

    # confusion matrix
    both_yes = sum(a == 1 and b == 1 for a, b in zip(labels_a, labels_b))
    both_no = sum(a == 0 and b == 0 for a, b in zip(labels_a, labels_b))
    a_yes_b_no = sum(a == 1 and b == 0 for a, b in zip(labels_a, labels_b))
    a_no_b_yes = sum(a == 0 and b == 1 for a, b in zip(labels_a, labels_b))

    print(f"  Confusion matrix:")
    print(f"  {'':>20} {annotator_b}")
    print(f"  {'':>20} {'yes':>6} {'no':>6}")
    print(f"  {annotator_a:>12} yes  {both_yes:>6} {a_yes_b_no:>6}")
    print(f"  {'':>12} no   {a_no_b_yes:>6} {both_no:>6}")
    print()

    # disagreements
    if disagreements:
        print(f"  DISAGREEMENTS ({len(disagreements)})")
        print("  " + "-" * 56)
        for d in disagreements:
            title = d['title'][:48] or f"(id: {d['article_id']})"
            print(f"  {title}")
            print(f"    {annotator_a}: {d[annotator_a]:>3}  {annotator_b}: {d[annotator_b]:>3}")
        print()
    else:
        print("  No disagreements — perfect agreement.")
        print()

    # export
    if args.export:
        import csv
        fieldnames = ['article_id', 'title', annotator_a, annotator_b, 'read_a', 'read_b', 'adjudicated']
        with open(args.export, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for d in disagreements:
                d['adjudicated'] = ''  # blank column for manual adjudication
                writer.writerow(d)
        print(f"  Disagreements exported to: {args.export}")
        print(f"  Fill in the 'adjudicated' column (yes/no) and use it as ground truth.")
        print()


if __name__ == '__main__':
    main()
