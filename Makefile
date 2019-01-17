FILE=small.tgz
URL=http://astron.nl/citt/apercal-testdata/small.tgz
VENV=$(CURDIR)/.venv2
CWLTOOL=$(VENV)/bin/cwltool --enable-ext  --no-compute-checksum --outdir=cwl/outdir --leave-tmp --cachedir=cache --leave-tmpdir --tmpdir-prefix=tmp/

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

test: data/small
	docker run -v `pwd`/data:/code/data:rw apertif/apercal pytest -s test/test_preflag.py

clean:
	rm -rf cache/* tmp/* data/small

cwl-preflag: $(VENV)/bin/cwltool data/small
	$(CWLTOOL) cwl/steps/preflag.cwl \
		--fluxcal data/small/00/raw/3C295.MS \
		--polcal data/small/00/raw/3C138.MS \
		--target data/small/00/raw/NGC807.MS

cwl-crosscal: $(VENV)/bin/cwltool data/small
	$(CWLTOOL) cwl/steps/ccal.cwl \
		--fluxcal data/small/00/raw/3C295.MS \
		--polcal data/small/00/raw/3C138.MS \
		--target data/small/00/raw/NGC807.MS

cwl-convert: $(VENV)/bin/cwltool data/small
	$(CWLTOOL) cwl/steps/convert.cwl cwl/job.yaml \
		--fluxcal data/small/00/raw/3C295.MS \
		--polcal data/small/00/raw/3C138.MS \
		--target data/small/00/raw/NGC807.MS

cwl-scal: $(VENV)/bin/cwltool data/small
	$(CWLTOOL) cwl/steps/scal.cwl \
		--fluxcal_mir data/small/00/crosscal/3C295.mir \
		--polcal_mir data/small/00/crosscal/3C138.mir \
		--target_mir data/small/00/crosscal/NGC807.mir
