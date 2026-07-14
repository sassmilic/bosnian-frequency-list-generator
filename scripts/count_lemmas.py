#!/usr/bin/env python3
"""Count (lemma, UPOS) frequencies in a CLASSLA-web vertical-format corpus.

Reads the .vert.tar.gz distribution (e.g. CLASSLA-web.bs.2.0.vert.tar.gz),
streams the vert file inside it (never extracted to disk), and writes a
top-N frequency list as TSV: rank, lemma, upos, count, per_million.

Token lines have 6 tab-separated columns:
    word  lempos  msd  upos  feats  id
Lemma is recovered from lempos by stripping its trailing "-x" POS suffix.
Structural lines (<text>, <p>, <s>, <g/>, ...) contain no tabs and are skipped.

Filtering: tokens tagged PUNCT/SYM/PROPN and lemmas containing a digit are
excluded.
per_million is normalized over the total of *kept* tokens.

Architecture: rapidgzip parallel decompression -> tarfile (stream mode) ->
main process cuts newline-aligned chunks -> pool of worker processes count
into local dicts, flushing partial dicts to the main process to bound RAM.
"""

import argparse
import multiprocessing as mp
import re
import sys
import tarfile
import threading
import time

CHUNK_BYTES = 32 * 1024 * 1024
FLUSH_ENTRIES = 2_000_000  # worker ships its partial dict after this many keys
EXCLUDED_UPOS = (b"PUNCT", b"SYM", b"PROPN")
DIGIT_RE = re.compile(rb"\d")


def worker(in_q, out_q):
    counts = {}
    kept = 0
    punct = 0
    digits = 0
    malformed = 0
    digit_search = DIGIT_RE.search
    get = counts.get
    while True:
        chunk = in_q.get()
        if chunk is None:
            break
        for line in chunk.split(b"\n"):
            parts = line.split(b"\t")
            if len(parts) != 6:
                if b"\t" in line:
                    malformed += 1
                continue
            upos = parts[3]
            if upos in EXCLUDED_UPOS:
                punct += 1
                continue
            lempos = parts[1]
            if digit_search(lempos):
                digits += 1
                continue
            # strip "-x" suffix (hyphen + single lowercase POS letter)
            if len(lempos) > 2 and lempos[-2] == 0x2D and 0x61 <= lempos[-1] <= 0x7A:
                lemma = lempos[:-2]
            else:
                lemma = lempos
            key = lemma + b"\t" + upos
            counts[key] = get(key, 0) + 1
            get = counts.get
            kept += 1
        if len(counts) >= FLUSH_ENTRIES:
            out_q.put(("part", counts))
            counts = {}
            get = counts.get
    out_q.put(("part", counts))
    out_q.put(("done", (kept, punct, digits, malformed)))


def open_vert_stream(tar_gz_path, decompression_threads):
    """Yield the file object of the .vert member inside the tar.gz."""
    try:
        import rapidgzip

        raw = rapidgzip.open(tar_gz_path, parallelization=decompression_threads)
    except ImportError:
        sys.stderr.write("rapidgzip not available, falling back to gzip\n")
        import gzip

        raw = gzip.open(tar_gz_path, "rb")
    tar = tarfile.open(fileobj=raw, mode="r|")
    for member in tar:
        basename = member.name.rsplit("/", 1)[-1]
        if member.isfile() and basename.endswith(".vert") and not basename.startswith("._"):
            return tar.extractfile(member), member.size
    raise RuntimeError("no .vert member found in archive")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("archive", help="path to *.vert.tar.gz")
    ap.add_argument("-o", "--output", required=True, help="output TSV path")
    ap.add_argument("-n", "--top", type=int, default=20_000)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--dec-threads", type=int, default=4)
    args = ap.parse_args()

    t0 = time.time()
    in_q = mp.Queue(maxsize=16)
    out_q = mp.Queue()
    procs = [
        mp.Process(target=worker, args=(in_q, out_q), daemon=True)
        for _ in range(args.workers)
    ]
    for p in procs:
        p.start()

    master = {}
    stats = {"kept": 0, "punct": 0, "digits": 0, "malformed": 0}

    def merger():
        done = 0
        while done < args.workers:
            tag, payload = out_q.get()
            if tag == "part":
                mget = master.get
                for k, v in payload.items():
                    master[k] = mget(k, 0) + v
            else:
                kept, punct, digits, malformed = payload
                stats["kept"] += kept
                stats["punct"] += punct
                stats["digits"] += digits
                stats["malformed"] += malformed
                done += 1

    merge_thread = threading.Thread(target=merger)
    merge_thread.start()

    vert, vert_size = open_vert_stream(args.archive, args.dec_threads)
    fed = 0
    leftover = b""
    while True:
        block = vert.read(CHUNK_BYTES)
        if not block:
            if leftover:
                in_q.put(leftover)
                fed += len(leftover)
            break
        block = leftover + block
        cut = block.rfind(b"\n")
        if cut == -1:
            leftover = block
            continue
        in_q.put(block[: cut + 1])
        fed += cut + 1
        leftover = block[cut + 1 :]
        if fed % (CHUNK_BYTES * 32) < CHUNK_BYTES:
            elapsed = time.time() - t0
            sys.stderr.write(
                f"  {fed / 1e9:6.1f} GB of {vert_size / 1e9:.1f} GB "
                f"({fed / vert_size * 100:4.1f}%)  "
                f"{fed / 1e6 / elapsed:6.0f} MB/s\n"
            )
    for _ in procs:
        in_q.put(None)
    merge_thread.join()
    for p in procs:
        p.join()

    total_kept = stats["kept"]
    top = sorted(master.items(), key=lambda kv: (-kv[1], kv[0]))[: args.top]
    with open(args.output, "w", encoding="utf-8") as f:
        f.write("rank\tlemma\tupos\tcount\tper_million\n")
        for rank, (key, count) in enumerate(top, 1):
            lemma, upos = key.decode("utf-8").split("\t")
            f.write(f"{rank}\t{lemma}\t{upos}\t{count}\t{count / total_kept * 1e6:.2f}\n")

    elapsed = time.time() - t0
    sys.stderr.write(
        f"done in {elapsed / 60:.1f} min | {fed / 1e9:.2f} GB at "
        f"{fed / 1e6 / elapsed:.0f} MB/s\n"
        f"tokens kept: {stats['kept']:,} | punct/sym/propn excluded: {stats['punct']:,} | "
        f"digit lemmas excluded: {stats['digits']:,} | malformed: {stats['malformed']:,}\n"
        f"unique (lemma, upos) pairs: {len(master):,} | wrote top {len(top):,} "
        f"to {args.output}\n"
    )


if __name__ == "__main__":
    main()
