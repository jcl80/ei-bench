#!/usr/bin/env python3
"""
ei-bench annotation tool

Curses-based TUI for controlled article annotation.
All timestamps, keypresses, and interactions are logged automatically.

List view:
  up/down or j/k  — navigate articles
  left/right       — change page
  Enter            — view article detail
  n                — jump to next unannotated
  q                — save and quit

Detail view:
  o  — open article URL in browser
  s  — toggle AI-generated summary
  t  — toggle cached article text
  c  — show criteria reference
  y  — mark as existentially important
  n  — mark as NOT existentially important
  d  — mark as defective/skip (junk, paywall, foreign language, etc.)
  Esc — back to list
"""

import json
import sys
import os
import time
import webbrowser
import curses
import textwrap
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault('ESCDELAY', '25')


CRITERIA_LINES = [
    "An article is existentially important if it describes:",
    "",
    "  * More than 100 deaths",
    "  * A novel pathogen or spreading sickness",
    "  * Conflict between nuclear powers",
    "  * Conflict that could escalate into global conflict",
    "  * Terrorist groups displaying new capabilities",
    "  * Events that could threaten humanity as a whole",
    "",
    "NOT existentially important:",
    "",
    "  * Opinion pieces and editorials",
    "  * Reviews of past events (9/11, historical conflicts)",
    "  * Minor developments in ongoing conflicts",
    "    (unless involving escalation or 1000+ deaths)",
    "  * Events that are important but don't threaten",
    "    humanity at scale (e.g., Moon landing)",
    "",
    "Many articles are important but NOT existentially so.",
    "Only mark 'yes' for events meeting the threshold above.",
]


def load_articles(path):
    articles = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                articles.append(json.loads(line))
    return articles


def load_existing_annotations(path):
    """Load existing annotations to support resume. Latest entry per article wins."""
    annotations = {}
    if path.exists():
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    a = json.loads(line)
                    annotations[a['article_id']] = a
    return annotations


def save_annotation(path, annotation):
    with open(path, 'a') as f:
        f.write(json.dumps(annotation) + '\n')


class AnnotationApp:
    def __init__(self, articles, annotations, output_path, annotator):
        self.articles = articles
        self.annotations = annotations
        self.output_path = output_path
        self.annotator = annotator

        self.selected_idx = 0
        self.current_page = 0
        self.items_per_page = 1
        self.mode = "list"  # list | detail | criteria | article_text | confirm

        # detail view state (reset on each enter)
        self.summary_revealed = False
        self.article_text_revealed = False
        self.opened_url = False
        self.open_count = 0
        self.detail_scroll = 0
        self.article_text_scroll = 0
        self.article_shown_at = 0
        self.keypresses = []

        # confirm state (after y/n, before saving)
        self.pending_answer = None

        self.status_message = ""
        self.status_time = 0

    # ── main loop ────────────────────────────────────────────────

    def run(self, stdscr):
        self.scr = stdscr
        curses.curs_set(0)
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)
        curses.init_pair(2, curses.COLOR_RED, -1)
        curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(4, curses.COLOR_CYAN, -1)
        curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(6, 8, -1)  # dim gray

        self._jump_to_next_unannotated(from_idx=0)

        while True:
            self.scr.erase()
            h, w = self.scr.getmaxyx()
            self.items_per_page = max(1, h - 4)
            self.current_page = self.selected_idx // self.items_per_page

            if self.mode == "list":
                self._draw_list(h, w)
            elif self.mode == "detail":
                self._draw_detail(h, w)
            elif self.mode == "criteria":
                self._draw_criteria(h, w)
            elif self.mode == "article_text":
                self._draw_article_text(h, w)
            elif self.mode == "confirm":
                self._draw_confirm(h, w)

            self.scr.refresh()
            key = self.scr.getch()

            if self.mode == "list":
                if self._handle_list(key) == "quit":
                    return
            elif self.mode == "detail":
                self._handle_detail(key)
            elif self.mode == "criteria":
                self._handle_criteria(key)
            elif self.mode == "article_text":
                self._handle_article_text(key)
            elif self.mode == "confirm":
                self._handle_confirm(key)

    # ── navigation helpers ───────────────────────────────────────

    def _jump_to_next_unannotated(self, from_idx=0):
        for i in range(from_idx, len(self.articles)):
            if self.articles[i]['id'] not in self.annotations:
                self.selected_idx = i
                return True
        return False

    def _enter_detail(self):
        self.mode = "detail"
        self.summary_revealed = False
        self.article_text_revealed = False
        self.opened_url = False
        self.open_count = 0
        self.detail_scroll = 0
        self.article_text_scroll = 0
        self.article_shown_at = time.time()
        self.keypresses = []
        self.pending_answer = None

    # ── drawing helpers ──────────────────────────────────────────

    def _safe_addstr(self, y, x, text, attr=curses.A_NORMAL):
        h, w = self.scr.getmaxyx()
        if y < 0 or y >= h:
            return
        text = text[:max(0, w - x - 1)]
        try:
            self.scr.addnstr(y, x, text, max(0, w - x - 1), attr)
        except curses.error:
            pass

    def _draw_hline(self, y, w, attr=curses.A_NORMAL):
        self._safe_addstr(y, 0, "\u2500" * (w - 1), attr)

    def _draw_wrapped(self, y, x, text, attr, w, max_lines=None):
        """Draw word-wrapped text. Returns next y."""
        h, _ = self.scr.getmaxyx()
        wrap_width = max(10, w - x - 1)
        lines = textwrap.wrap(text, width=wrap_width) or [""]
        if max_lines:
            lines = lines[:max_lines]
        for line in lines:
            if y >= h - 1:
                break
            self._safe_addstr(y, x, line, attr)
            y += 1
        return y

    # ── list view ────────────────────────────────────────────────

    def _draw_list(self, h, w):
        done = len(self.annotations)
        total = len(self.articles)

        header = f" ei-bench  {done}/{total} annotated"
        if self.annotator:
            header += f"  [{self.annotator}]"
        self._safe_addstr(0, 0, header, curses.color_pair(4) | curses.A_BOLD)
        self._draw_hline(1, w, curses.color_pair(6))

        start = self.current_page * self.items_per_page
        end = min(start + self.items_per_page, total)

        for row, idx in enumerate(range(start, end)):
            y = row + 2
            article = self.articles[idx]
            aid = article['id']
            title = article.get('title', '(no title)')

            # marker + style
            if aid in self.annotations:
                ans = self.annotations[aid]['answer']
                if ans == 'yes':
                    marker, style = "\u25a0", curses.color_pair(1)
                elif ans == 'defective':
                    marker, style = "x", curses.color_pair(2)
                else:
                    marker, style = "\u00b7", curses.color_pair(6)
            else:
                marker, style = " ", curses.A_NORMAL

            if idx == self.selected_idx:
                style = curses.color_pair(3)

            num = f"{idx + 1:>4}"
            line = f" {marker} {num}  {title}"
            # fill rest of line for selected highlight
            if idx == self.selected_idx:
                line = line.ljust(w - 1)
            self._safe_addstr(y, 0, line, style)

        # status bar
        num_pages = max(1, (total + self.items_per_page - 1) // self.items_per_page)
        bar = f" \u2191\u2193 navigate | \u2190\u2192 page {self.current_page + 1}/{num_pages} | Enter: detail | n: next unannotated | q: quit"
        if self.status_message and time.time() - self.status_time < 3:
            bar = f" {self.status_message}"
        self._safe_addstr(h - 1, 0, bar.ljust(w - 1), curses.color_pair(5))

    def _handle_list(self, key):
        total = len(self.articles)

        if key == ord('q') or key == ord('Q'):
            return "quit"
        elif key == curses.KEY_UP or key == ord('k'):
            if self.selected_idx > 0:
                self.selected_idx -= 1
        elif key == curses.KEY_DOWN or key == ord('j'):
            if self.selected_idx < total - 1:
                self.selected_idx += 1
        elif key == curses.KEY_RIGHT or key == ord('l'):
            max_page = (total - 1) // self.items_per_page
            if self.current_page < max_page:
                self.current_page += 1
                self.selected_idx = self.current_page * self.items_per_page
        elif key == curses.KEY_LEFT or key == ord('h'):
            if self.current_page > 0:
                self.current_page -= 1
                self.selected_idx = self.current_page * self.items_per_page
        elif key in (curses.KEY_ENTER, ord('\n'), 10, 13):
            self._enter_detail()
        elif key == ord('n') or key == ord('N'):
            self._jump_to_next_unannotated(from_idx=self.selected_idx + 1)
        return None

    # ── detail view ──────────────────────────────────────────────

    def _draw_detail(self, h, w):
        article = self.articles[self.selected_idx]
        aid = article['id']
        already = aid in self.annotations
        y = 1

        # progress
        done = len(self.annotations)
        total = len(self.articles)
        prog = f" [{self.selected_idx + 1}/{total}]  {done} annotated"
        self._safe_addstr(0, 0, prog, curses.color_pair(4))

        # title
        title = article.get('title', '(no title)')
        y = self._draw_wrapped(y, 2, title, curses.A_BOLD, w, max_lines=3)
        y += 1

        # link
        link = article.get('link', '')
        if link:
            self._safe_addstr(y, 2, link, curses.A_UNDERLINE | curses.color_pair(4))
            y += 1
        y += 1

        # existing annotation badge
        if already:
            ans = self.annotations[aid]['answer']
            if ans == 'yes':
                badge_style = curses.color_pair(1) | curses.A_BOLD
            elif ans == 'defective':
                badge_style = curses.color_pair(2) | curses.A_BOLD
            else:
                badge_style = curses.color_pair(2) | curses.A_BOLD
            self._safe_addstr(y, 2, f"ANNOTATED: {ans.upper()}", badge_style)
            y += 2

        # summary
        if self.summary_revealed:
            summary = article.get('summary', '')
            self._safe_addstr(y, 2, "SUMMARY", curses.color_pair(4) | curses.A_BOLD)
            y += 1
            if summary:
                y = self._draw_wrapped(y, 2, summary, curses.A_NORMAL, w, max_lines=max(1, h - y - 4))
            else:
                self._safe_addstr(y, 2, "(no summary available)", curses.color_pair(6))
                y += 1
            y += 1

        # article text indicator
        has_text = bool(article.get('article_text', '').strip())
        if has_text and not self.article_text_revealed:
            self._safe_addstr(y, 2, "[t] Article text available", curses.color_pair(6))
            y += 1
        elif has_text and self.article_text_revealed:
            self._safe_addstr(y, 2, "[t] Article text (press t for full screen)", curses.color_pair(1))
            y += 1
        elif not has_text:
            self._safe_addstr(y, 2, "(no cached article text)", curses.color_pair(6))
            y += 1

        # controls
        if already:
            bar = " Esc: back | o: open URL | s: summary | t: article text | c: criteria"
        else:
            bar = " y: YES  n: NO  d: DEFECTIVE | o: open | s: summary | t: text | c: criteria | Esc"
        self._safe_addstr(h - 1, 0, bar.ljust(w - 1), curses.color_pair(5))

    def _handle_detail(self, key):
        ts = datetime.now(timezone.utc).isoformat()

        # log keypress
        if 32 <= key < 127:
            key_name = chr(key)
        else:
            key_name = f"<{key}>"
        self.keypresses.append({'key': key_name, 'time': ts})

        article = self.articles[self.selected_idx]
        aid = article['id']
        already = aid in self.annotations

        if key == 27:  # Esc
            self.mode = "list"
        elif key in (ord('o'), ord('O')):
            link = article.get('link', '')
            if link:
                webbrowser.open(link)
                self.opened_url = True
                self.open_count += 1
        elif key in (ord('s'), ord('S')):
            self.summary_revealed = not self.summary_revealed
        elif key in (ord('t'), ord('T')):
            text = article.get('article_text', '').strip()
            if text:
                self.article_text_revealed = True
                self.article_text_scroll = 0
                self.mode = "article_text"
        elif key in (ord('c'), ord('C')):
            self.mode = "criteria"
        elif key in (ord('d'), ord('D')) and not already:
            # defective — save immediately, no confirm needed
            time_spent = round(time.time() - self.article_shown_at, 1)
            annotation = {
                'article_id': aid,
                'annotator': self.annotator,
                'answer': 'defective',
                'read_article': False,
                'opened_url': self.opened_url,
                'open_count': self.open_count,
                'revealed_summary': self.summary_revealed,
                'viewed_article_text': self.article_text_revealed,
                'time_spent_seconds': time_spent,
                'timestamp': ts,
                'keypresses': self.keypresses,
            }
            save_annotation(self.output_path, annotation)
            self.annotations[aid] = annotation

            short = article.get('title', '')[:50]
            self.status_message = f"Defective: {short}..."
            self.status_time = time.time()

            if self._jump_to_next_unannotated(from_idx=self.selected_idx + 1):
                self._enter_detail()
            else:
                self.mode = "list"
                self.status_message = f"Done! All {len(self.articles)} articles annotated."
                self.status_time = time.time()
        elif key in (ord('y'), ord('n')) and not already:
            self.pending_answer = 'yes' if key == ord('y') else 'no'
            self.mode = "confirm"

    # ── article text view ────────────────────────────────────────

    def _draw_article_text(self, h, w):
        article = self.articles[self.selected_idx]
        text = article.get('article_text', '')

        self._safe_addstr(0, 0, " ARTICLE TEXT", curses.color_pair(4) | curses.A_BOLD)
        self._draw_hline(1, w, curses.color_pair(6))

        # wrap the full text into lines
        wrap_width = max(10, w - 3)
        all_lines = []
        for paragraph in text.split('\n'):
            paragraph = paragraph.strip()
            if paragraph:
                all_lines.extend(textwrap.wrap(paragraph, width=wrap_width))
                all_lines.append("")  # blank between paragraphs
            else:
                all_lines.append("")

        # display with scroll offset
        visible = h - 4  # header + hline + status bar + padding
        for i in range(visible):
            line_idx = self.article_text_scroll + i
            if line_idx >= len(all_lines):
                break
            self._safe_addstr(i + 2, 1, all_lines[line_idx], curses.A_NORMAL)

        # scroll indicator
        total_lines = len(all_lines)
        if total_lines > visible:
            pct = min(100, int((self.article_text_scroll + visible) / total_lines * 100))
            pos = f"{pct}%"
        else:
            pos = "all"
        bar = f" up/down or j/k: scroll | Esc: back to detail | {pos}"
        self._safe_addstr(h - 1, 0, bar.ljust(w - 1), curses.color_pair(5))

    def _handle_article_text(self, key):
        article = self.articles[self.selected_idx]
        text = article.get('article_text', '')
        h, w = self.scr.getmaxyx()

        wrap_width = max(10, w - 3)
        total_lines = 0
        for paragraph in text.split('\n'):
            paragraph = paragraph.strip()
            if paragraph:
                total_lines += len(textwrap.wrap(paragraph, width=wrap_width)) + 1
            else:
                total_lines += 1

        visible = h - 4
        max_scroll = max(0, total_lines - visible)

        if key == 27:  # Esc
            self.mode = "detail"
        elif key in (curses.KEY_DOWN, ord('j')):
            self.article_text_scroll = min(self.article_text_scroll + 1, max_scroll)
        elif key in (curses.KEY_UP, ord('k')):
            self.article_text_scroll = max(self.article_text_scroll - 1, 0)
        elif key in (curses.KEY_NPAGE, ord(' ')):  # page down
            self.article_text_scroll = min(self.article_text_scroll + visible, max_scroll)
        elif key == curses.KEY_PPAGE:  # page up
            self.article_text_scroll = max(self.article_text_scroll - visible, 0)

    # ── confirm view ─────────────────────────────────────────────

    def _draw_confirm(self, h, w):
        article = self.articles[self.selected_idx]
        title = article.get('title', '(no title)')

        mid_y = h // 2 - 3

        self._safe_addstr(mid_y, 2, "CONFIRM ANNOTATION", curses.A_BOLD)
        mid_y += 2

        ans_text = self.pending_answer.upper()
        ans_style = curses.color_pair(1) if self.pending_answer == 'yes' else curses.color_pair(2)
        self._safe_addstr(mid_y, 2, f"Article: {title[:w - 14]}", curses.A_NORMAL)
        mid_y += 1
        self._safe_addstr(mid_y, 2, f"Answer:  {ans_text}", ans_style | curses.A_BOLD)
        mid_y += 2

        self._safe_addstr(mid_y, 2, "Did you read the full article text?", curses.A_BOLD)
        mid_y += 2
        self._safe_addstr(mid_y, 2, "[y] Yes, I read the article", curses.A_NORMAL)
        mid_y += 1
        self._safe_addstr(mid_y, 2, "[n] No, I decided from title/summary", curses.A_NORMAL)
        mid_y += 1
        self._safe_addstr(mid_y, 2, "[Esc] Cancel, go back", curses.color_pair(6))

        self._safe_addstr(h - 1, 0, " y: read article | n: title/summary only | Esc: cancel".ljust(w - 1), curses.color_pair(5))

    def _handle_confirm(self, key):
        if key == 27:  # Esc — cancel, go back to detail
            self.pending_answer = None
            self.mode = "detail"
            return

        if key not in (ord('y'), ord('n')):
            return

        ts = datetime.now(timezone.utc).isoformat()
        read_article = (key == ord('y'))

        article = self.articles[self.selected_idx]
        aid = article['id']
        time_spent = round(time.time() - self.article_shown_at, 1)

        annotation = {
            'article_id': aid,
            'annotator': self.annotator,
            'answer': self.pending_answer,
            'read_article': read_article,
            'opened_url': self.opened_url,
            'open_count': self.open_count,
            'revealed_summary': self.summary_revealed,
            'viewed_article_text': self.article_text_revealed,
            'time_spent_seconds': time_spent,
            'timestamp': ts,
            'keypresses': self.keypresses,
        }

        save_annotation(self.output_path, annotation)
        self.annotations[aid] = annotation

        short = article.get('title', '')[:50]
        self.status_message = f"Saved: {short}... -> {annotation['answer']}"
        self.status_time = time.time()

        self.pending_answer = None

        # auto-advance to next unannotated, stay in detail mode
        if self._jump_to_next_unannotated(from_idx=self.selected_idx + 1):
            self._enter_detail()
        else:
            self.mode = "list"
            self.status_message = f"Done! All {len(self.articles)} articles annotated."
            self.status_time = time.time()

    # ── criteria view ────────────────────────────────────────────

    def _draw_criteria(self, h, w):
        self._safe_addstr(0, 0, " EXISTENTIAL IMPORTANCE CRITERIA", curses.color_pair(4) | curses.A_BOLD)
        self._draw_hline(1, w, curses.color_pair(6))

        for i, line in enumerate(CRITERIA_LINES):
            y = i + 3
            if y >= h - 2:
                break
            self._safe_addstr(y, 1, line, curses.A_NORMAL)

        self._safe_addstr(h - 1, 0, " Press any key to go back".ljust(w - 1), curses.color_pair(5))

    def _handle_criteria(self, key):
        self.mode = "detail"


# ── entry point ──────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description='ei-bench annotation tool')
    parser.add_argument('--data', required=True, help='Path to articles JSONL')
    parser.add_argument('--output', default='annotations.jsonl', help='Path to save annotations')
    parser.add_argument('--annotator', required=True, help='Annotator identifier (e.g. initials)')
    parser.add_argument('--no-criteria', action='store_true', help='Skip showing criteria at start')

    args = parser.parse_args()
    articles_path = Path(args.data)
    output_path = Path(args.output)

    if not articles_path.exists():
        print(f"Error: {articles_path} not found")
        sys.exit(1)

    articles = load_articles(articles_path)
    annotations = load_existing_annotations(output_path)

    if not articles:
        print("No articles found.")
        sys.exit(1)

    # show criteria before entering curses (plain terminal)
    if not args.no_criteria and not annotations:
        print()
        print("=" * 60)
        print(" EXISTENTIAL IMPORTANCE CRITERIA")
        print("=" * 60)
        for line in CRITERIA_LINES:
            print(f"  {line}")
        print("=" * 60)
        print()
        input(" Press Enter to begin annotating...")

    if annotations:
        remaining = sum(1 for a in articles if a['id'] not in annotations)
        print(f"\n Resuming: {len(annotations)}/{len(articles)} done, {remaining} remaining.\n")
        time.sleep(1)

    app = AnnotationApp(articles, annotations, output_path, args.annotator)
    curses.wrapper(app.run)

    done = len(app.annotations)
    total = len(articles)
    print(f"\n {done}/{total} annotated. Results: {output_path}\n")


if __name__ == '__main__':
    main()
