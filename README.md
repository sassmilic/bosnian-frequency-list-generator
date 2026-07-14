# Bosnian lemma frequency list

A top-20,000 lemma frequency list for Bosnian, derived from the
[CLASSLA-web.bs 2.0](http://hdl.handle.net/11356/2079) web corpus
(~1.2 billion tokens, crawled 2024, license **CC0**) — the largest publicly
available Bosnian corpus, linguistically annotated with the CLASSLA-Stanza
pipeline.

## Deliverable

`data/bs_lemma_freq_top20k.tsv` — tab-separated, one row per **(lemma, UPOS)**
pair, sorted by frequency:

| column | meaning |
|---|---|
| `rank` | 1–20000 |
| `lemma` | lemma as assigned by CLASSLA-Stanza (proper nouns keep capitalization) |
| `upos` | [Universal Dependencies POS tag](https://universaldependencies.org/u/pos/) |
| `count` | absolute corpus frequency |
| `per_million` | frequency per million *kept* tokens (see filtering below) |

Homographs with different parts of speech are separate entries (e.g. *i* as
conjunction vs. *i* as particle). Merge on `lemma` if you want bare-lemma counts.

## Filtering

Included: all tokens **except**

- punctuation and symbols (UPOS `PUNCT`, `SYM`)
- proper nouns (UPOS `PROPN` — names of people, places, organizations)
- tokens whose lemma contains a digit (`2024`, `G6040`, …) — spelled-out
  numerals (*dva*, *prvi*) are kept

Foreign/residual tokens (`X`) are **kept**.
`per_million` is normalized over the total of tokens that survive this filter.

## Run statistics (2026-07-14)

- tokens kept: **924,876,479** (basis for `per_million`)
- punctuation/symbols/proper nouns excluded: 223,116,640
- digit-containing lemmas excluded: 20,919,801
- total token lines processed: 1.169 B, consistent with the published corpus
  size of 1.01 B words (words = total minus punctuation)
- unique (lemma, UPOS) pairs seen: 3,806,942
- count at rank 20,000: 1,788 (≈ 1.9 per million)

## Reproduce

```sh
make download   # ~9 GB tarball from CLARIN.SI (slow server, resumable)
make            # streams the 65 GB vert file, ~5 min on 12 cores
```

Requires Python 3, and optionally `pip install rapidgzip` for parallel
decompression (falls back to stdlib gzip). The corpus is streamed straight out
of the tarball — the uncompressed vert file is never written to disk. Peak RAM
is a few GB (worker processes flush partial counts to the merger).

## Vocabulary review

`make review` (or `python3 scripts/review_vocab.py`) walks through the list in
rank order, one word at a time: **Enter** = know it, **x** = don't,
**u** = undo, **q**/Ctrl-C = quit. Every keypress is saved immediately to
`data/review/decisions.tsv` (gitignored), so you can quit anytime and the next
run resumes at the first unreviewed word. Words you don't know are exported on
exit to `data/bs_unknown_words.tsv` (same columns as the main list).

## Source corpus format

The `.vert.tar.gz` contains one vertical-format (Sketch Engine/CWB) file.
Token lines have 6 tab-separated columns:

```
word    lempos    msd    upos    feats    id
stanju  stanje-n  Ncnsl  NOUN   Case=Loc|Gender=Neut|Number=Sing  5
```

The lemma is `lempos` minus its trailing `-x` POS-letter suffix. Structural
lines (`<text …>`, `<p …>`, `<s …>`, `<g/>`) contain no tabs.

## Citation

Kuzman, Taja et al. (2024): *South Slavic web corpus collection CLASSLA-web 2.0*.
Slovenian language resource repository CLARIN.SI,
<http://hdl.handle.net/11356/2079>.

See also: Kuzman et al. (2024),
[CLASSLA-web: Comparable Web Corpora of South Slavic Languages Enriched with
Linguistic and Genre Annotation](https://arxiv.org/abs/2403.12721).
