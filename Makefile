CORPUS_URL = https://www.clarin.si/repository/xmlui/bitstream/handle/11356/2079/CLASSLA-web.bs.2.0.vert.tar.gz
ARCHIVE    = data/raw/CLASSLA-web.bs.2.0.vert.tar.gz
OUTPUT     = data/bs_lemma_freq_top20k.tsv

all: $(OUTPUT)

download: $(ARCHIVE)

$(ARCHIVE):
	mkdir -p data/raw
	curl -L -C - --retry 10 --retry-delay 10 -o $(ARCHIVE) "$(CORPUS_URL)"

$(OUTPUT): $(ARCHIVE) scripts/count_lemmas.py
	python3 scripts/count_lemmas.py $(ARCHIVE) -o $(OUTPUT) --workers 9 --dec-threads 4

.PHONY: all download
