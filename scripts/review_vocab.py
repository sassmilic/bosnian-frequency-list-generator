#!/usr/bin/env python3
"""Interactive vocabulary self-review over the frequency list.

Walks through data/bs_lemma_freq_top20k.tsv in rank order, one word at a time:

    Enter  I know this word
    x      I don't know it
    u      undo the last decision
    q      quit (Ctrl-C also works)

Every decision is appended and flushed to data/review/decisions.tsv
immediately, so progress survives any exit and the next run resumes at the
first unreviewed word. On exit, words marked unknown are exported to
data/bs_unknown_words.tsv (same columns as the source list).
"""

import os
import sys
import termios
import tty

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FREQ_LIST = os.path.join(BASE, "data", "bs_lemma_freq_top20k.tsv")
LOG = os.path.join(BASE, "data", "review", "decisions.tsv")
UNKNOWN_OUT = os.path.join(BASE, "data", "bs_unknown_words.tsv")

KNOWN_MARK = "✓"  # ✓
UNKNOWN_MARK = "✗"  # ✗


def load_words():
    with open(FREQ_LIST, encoding="utf-8") as f:
        header = f.readline().rstrip("\n")
        rows = [line.rstrip("\n").split("\t") for line in f]
    return header, rows


def load_log(rows):
    """Return past decisions as a list of known-flags, validated against rows."""
    if not os.path.exists(LOG):
        return []
    decisions = []
    with open(LOG, encoding="utf-8") as f:
        for i, line in enumerate(f):
            rank, lemma, upos, known = line.rstrip("\n").split("\t")
            if i >= len(rows) or [rank, lemma, upos] != rows[i][:3]:
                sys.exit(
                    f"error: {LOG} line {i + 1} ({rank}\t{lemma}\t{upos}) does not "
                    f"match the frequency list — was the list regenerated?\n"
                    f"Move the log away to start over."
                )
            decisions.append(known == "1")
    return decisions


def append_decision(log_file, row, known):
    log_file.write(f"{row[0]}\t{row[1]}\t{row[2]}\t{1 if known else 0}\n")
    log_file.flush()
    os.fsync(log_file.fileno())


def truncate_last_decision():
    with open(LOG, encoding="utf-8") as f:
        lines = f.readlines()
    with open(LOG, "w", encoding="utf-8") as f:
        f.writelines(lines[:-1])


def export_unknown(header, rows, decisions):
    unknown = [rows[i] for i, known in enumerate(decisions) if not known]
    with open(UNKNOWN_OUT, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        for row in unknown:
            f.write("\t".join(row) + "\n")
    return len(unknown)


def main():
    header, rows = load_words()
    decisions = load_log(rows)
    total = len(rows)

    if len(decisions) >= total:
        n_unknown = export_unknown(header, rows, decisions)
        print(
            f"All {total:,} words already reviewed — {n_unknown:,} unknown words "
            f"in {os.path.relpath(UNKNOWN_OUT, os.getcwd())}"
        )
        return
    if decisions:
        print(
            f"Resuming at word {len(decisions) + 1:,} of {total:,} — "
            f"{sum(1 for k in decisions if not k):,} unknown so far"
        )
    else:
        print(f"Starting fresh: {total:,} words to review")
    print("[Enter] know it   [x] don't   [u] undo   [q] quit\n")

    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    log_file = open(LOG, "a", encoding="utf-8")

    # cbreak for the whole session (with TCSADRAIN so type-ahead keys are
    # never flushed away); restored in the finally block
    fd = sys.stdin.fileno()
    saved_termios = termios.tcgetattr(fd)
    tty.setcbreak(fd, termios.TCSADRAIN)

    i = len(decisions)
    try:
        while i < total:
            lemma = rows[i][1]
            sys.stdout.write(f"  {lemma}")
            sys.stdout.flush()
            key = sys.stdin.read(1)
            if not key:  # EOF (stdin closed)
                print()
                break
            if key in ("\r", "\n"):
                print(f"  {KNOWN_MARK}")
                append_decision(log_file, rows[i], True)
                decisions.append(True)
                i += 1
            elif key in ("x", "X"):
                print(f"  {UNKNOWN_MARK}")
                append_decision(log_file, rows[i], False)
                decisions.append(False)
                i += 1
            elif key in ("u", "U"):
                if decisions:
                    print("  (undone)")
                    decisions.pop()
                    i -= 1
                    log_file.close()
                    truncate_last_decision()
                    log_file = open(LOG, "a", encoding="utf-8")
                else:
                    print("  (nothing to undo)")
            elif key in ("q", "Q"):
                print()
                break
            else:
                print()  # ignored key: reprint the same word
    except KeyboardInterrupt:
        print()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved_termios)
        log_file.close()
        n_unknown = export_unknown(header, rows, decisions)
        done = len(decisions)
        if done == total:
            print(f"\nAll {total:,} words reviewed!", end=" ")
        else:
            print(f"\nProgress saved at word {done:,} of {total:,}.", end=" ")
        print(f"{n_unknown:,} unknown words in {os.path.relpath(UNKNOWN_OUT, os.getcwd())}")


if __name__ == "__main__":
    main()
