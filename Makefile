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


# bootstrap the python2 environment
$(VENV2):
	virtualenv -p python2 $(VENV2)


# bootstrap the python3 environment
$(VENV3):
	virtualenv -p python3 $(VENV3)


# install cwltool in the Python3 environment
$(VENV2)/bin/cwltool: $(VENV2)
	$(VENV2)/bin/pip install .
	$(VENV2)/bin/pip install -r cwl/requirements.txt
	$(VENV2)/bin/pip install -r test/requirements.txt


# install cwltool in the Python2 environment
$(VENV3)/bin/cwltool: $(VENV3)
	$(VENV3)/bin/pip install -r cwl/requirements.txt


# install udocker. Should only be used if Docker and/or Singularity are not available
$(VENV3)/bin/udocker: $(VENV3)
	curl https://raw.githubusercontent.com/indigo-dc/udocker/master/udocker.py > $(VENV3)/bin/udocker
	chmod u+rx $(VENV3)/bin/udocker
	$(VENV3)/bin/udocker install


# Build the Docker Image
docker:
	docker build . -t apertif/apercal


# Download the test data
data/${FILE}:
	mkdir -p data
	cd data && wget -q ${URL}


# extract the test data
data/small: data/${FILE}
	cd data && tar zmxvf ${FILE}


# run the pipeline with the test data
run: $(VENV3)/bin/cwltool data/small
	 $(CWLTOOL) cwl/apercal.cwl \
		--fluxcal data/small/00/raw/3C295.MS \
		--polcal data/small/00/raw/3C138.MS \
		--target data/small/00/raw/NGC807.MS


# Run the pipeline with data from the archive. Note that you need proper alta credentials for this
run-archive: $(VENV3)/bin/cwltool data/small
	 $(CWLTOOL) cwl/apercal_archive.cwl \
	 	cwl/job.yaml


# Run the pipeline using uDocker
udocker: $(VENV3)/bin/cwltool data/small $(VENV3)/bin/udocker
	 $(CWLTOOL) \
	 	--user-space-docker-cmd $(VENV3)/bin/udocker \
	 	cwl/apercal.cwl \
		--fluxcal data/small/00/raw/3C295.MS \
		--polcal data/small/00/raw/3C138.MS \
		--target data/small/00/raw/NGC807.MS


# Open a shell into the apercal docker container
docker-shell:
	docker run -ti -v $(PWD):/code apertif/apercal bash


# Run the test suite
test: data/small
	docker run -v `pwd`/data:/code/data:rw apertif/apercal pytest -s test/test_preflag.py


# Clean up CWL tmp files and the test data
clean:
	rm -rf cwl/cache/* cwl/tmp/* cwl/output/* data/small


# Run the CWLified preflag step only
cwl-preflag: $(VENV3)/bin/cwltool data/small
	$(CWLTOOL) cwl/steps/preflag.cwl \
		--fluxcal data/small/00/raw/3C295.MS \
		--polcal data/small/00/raw/3C138.MS \
		--target data/small/00/raw/NGC807.MS


# Run the CWLified crosscal step only
cwl-crosscal: $(VENV3)/bin/cwltool data/small
	$(CWLTOOL) --debug cwl/steps/ccal.cwl \
		--fluxcal data/small/00/raw/3C295.MS \
		--polcal data/small/00/raw/3C138.MS \
		--target data/small/00/raw/NGC807.MS


# Run the CWLifified convert step only
cwl-convert: $(VENV3)/bin/cwltool data/small
	$(CWLTOOL) cwl/steps/convert.cwl \
		--fluxcal data/small/00/raw/3C295.MS \
		--polcal data/small/00/raw/3C138.MS \
		--target data/small/00/raw/NGC807.MS


# Run the CWLifified scal step only
cwl-scal: $(VENV3)/bin/cwltool data/small
	$(CWLTOOL) cwl/steps/scal.cwl \
		--fluxcal_mir cwl/output/3C295.mir \
		--polcal_mir cwl/output/3C138.mir \
		--target_mir cwl/output/NGC807.mir


# Run the CWLifified continuum step only
cwl-continuum: $(VENV3)/bin/cwltool data/small
	$(CWLTOOL) cwl/steps/continuum.cwl \
		--target_mir cwl/output/NGC807.mir


# Run the CWLifified getdata step only
cwl-getdata: $(VENV3)/bin/cwltool
	$(CWLTOOL) cwl/steps/getdata.cwl \
		--obsdate 190302 \
		--obsnum 68 \
		--beamnum 0 \
		--name 3C147 \
		--irods /home/dijkema/.irods \
