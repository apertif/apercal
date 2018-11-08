FILE=small.tgz
URL=http://astron.nl/citt/apercal-testdata/small.tgz
VENV=$(CURDIR)/.venv2

.PHONY: run docker

all: run

$(VENV):
	virtualenv -p python2 ../.venv2

$(VENV)/bin/cwltool: $(VENV)
	$(VENV)/bin/pip install ..
	$(VENV)/bin/pip install -r requirements.txt

docker:
	docker build . -t apertif/apercal

data/${FILE}:
	mkdir -p data
	cd data && wget -q ${URL}

data/small: data/${FILE}
	cd data && tar zmxvf ${FILE}

run: $(VENV)/bin/cwltool data/small
	$(VENV)/bin/cwltool --enable-ext --outdir=cwl/outdir cwl/apercal.cwl cwl/job.yaml

