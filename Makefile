FILE=small.tgz
URL=http://astron.nl/citt/apercal-testdata/small.tgz

# for running apercal locally
VENV2=$(CURDIR)/.venv2
# for CWL tool
VENV3=$(CURDIR)/.venv3

CWLTOOL=$(VENV3)/bin/cwltool \
	--enable-ext  \
	--outdir=$(CURDIR)/cwl/output/
## scal step creates massive temp files, so you might want to set these
#	--tmpdir-prefix=/scratch/tmp/cwl/ \
#	--tmp-outdir-prefix=/scratch/tmp/cwl/

.PHONY: run docker test

all: run

$(VENV2):
	virtualenv -p python2 $(VENV2)

$(VENV3):
	virtualenv -p python3 $(VENV3)

$(VENV2)/bin/cwltool: $(VENV2)
	$(VENV2)/bin/pip install .
	$(VENV2)/bin/pip install -r cwl/requirements.txt
	$(VENV2)/bin/pip install -r test/requirements.txt

$(VENV3)/bin/cwltool: $(VENV3)
	$(VENV3)/bin/pip install -r cwl/requirements.txt

$(VENV3)/bin/udocker: $(VENV3)
	curl https://raw.githubusercontent.com/indigo-dc/udocker/master/udocker.py > $(VENV3)/bin/udocker
	chmod u+rx $(VENV3)/bin/udocker
	$(VENV3)/bin/udocker install

docker:
	docker build . -t apertif/apercal

data/${FILE}:
	mkdir -p data
	cd data && wget -q ${URL}

data/small: data/${FILE}
	cd data && tar zmxvf ${FILE}

run: $(VENV3)/bin/cwltool data/small
	 $(CWLTOOL) cwl/apercal.cwl cwl/job.yaml

udocker: $(VENV3)/bin/cwltool data/small $(VENV3)/bin/udocker
	 $(CWLTOOL) --user-space-docker-cmd $(VENV3)/bin/udocker cwl/apercal.cwl cwl/job.yaml

docker-shell:
	docker run -ti -v $(PWD):/code apertif/apercal bash

test: data/small
	docker run -v `pwd`/data:/code/data:rw apertif/apercal pytest -s test/test_preflag.py

clean:
	rm -rf cwl/cache/* cwl/tmp/* cwl/output/* data/small

cwl-preflag: $(VENV3)/bin/cwltool data/small
	$(CWLTOOL) cwl/steps/preflag.cwl \
		--fluxcal data/small/00/raw/3C295.MS \
		--polcal data/small/00/raw/3C138.MS \
		--target data/small/00/raw/NGC807.MS

cwl-crosscal: $(VENV3)/bin/cwltool data/small
	$(CWLTOOL) --debug cwl/steps/ccal.cwl \
		--fluxcal data/small/00/raw/3C295.MS \
		--polcal data/small/00/raw/3C138.MS \
		--target data/small/00/raw/NGC807.MS

cwl-convert: $(VENV3)/bin/cwltool data/small
	$(CWLTOOL) cwl/steps/convert.cwl cwl/job.yaml \
		--fluxcal data/small/00/raw/3C295.MS \
		--polcal data/small/00/raw/3C138.MS \
		--target data/small/00/raw/NGC807.MS

cwl-scal: $(VENV3)/bin/cwltool data/small
	$(CWLTOOL) cwl/steps/scal.cwl \
		--fluxcal_mir cwl/output/3C295.mir \
		--polcal_mir cwl/output/3C138.mir \
		--target_mir cwl/output/NGC807.mir

cwl-getdata: $(VENV3)/bin/cwltool
	$(CWLTOOL) --no-container cwl/steps/getdata.cwl \
		--obsdate 190302 \
		--obsnum 68 \
		--beamnum 0 \
		--name 3C147 \
		--irodsA /home/dijkema/.irods/.irodsA \
		--irodsenvironment /home/dijkema/.irods/irods_environment.json
