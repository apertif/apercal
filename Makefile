FILE=small.tgz
URL=http://astron.nl/citt/apercal-testdata/small.tgz
VENV=$(CURDIR)/.venv2
CWLTOOL=$(VENV)/bin/cwltool --enable-ext  --no-compute-checksum --outdir=cwl/outdir --leave-tmp --cachedir=cache --leave-tmpdir --tmpdir-prefix=apercal

.PHONY: run docker test

all: run

$(VENV):
	virtualenv -p python2 $(VENV)

$(VENV)/bin/cwltool: $(VENV)
	$(VENV)/bin/pip install .
	$(VENV)/bin/pip install -r cwl/requirements.txt
	$(VENV)/bin/pip install -r test/requirements.txt

docker:
	docker build . -t apertif/apercal

data/${FILE}:
	mkdir -p data
	cd data && wget -q ${URL}

data/small: data/${FILE}
	cd data && tar zmxvf ${FILE}

run: $(VENV)/bin/cwltool data/small
	 $(CWLTOOL) cwl/apercal.cwl cwl/job.yaml

convert: $(VENV)/bin/cwltool data/small
	$(CWLTOOL) cwl/steps/convert.cwl cwl/job.yaml

test: data/small
	docker run -v `pwd`/data:/code/data:rw apertif/apercal pytest -s test/test_preflag.py
