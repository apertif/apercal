
.PHONY: run 

VENV=$(CURDIR)/../.venv2

data:
	cd ../data && $(MAKE)

$(VENV):
	virtualenv -p python2 ../.venv2

$(VENV)/bin/cwltool: ../.venv2
	$(VENV)/bin/pip install ..
	$(VENV)/bin/pip install -r requirements.txt

docker:
	docker build .. -t apertif/apercal

run: ../.venv2/bin/cwltool data

	PATH=$(VENV)/bin/:$(PATH) $(VENV)/bin/cwltool --enable-ext --no-container apercal.cwl job.yaml
