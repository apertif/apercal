
.PHONY: run 

data:
	cd ../data && $(MAKE)

../.venv2:
	virtualenv -p python2 ../.venv2

../.venv2/bin/cwltool: ../.venv2
	../.venv2/bin/pip install ..
	../.venv2/bin/pip install -r requirements.txt

docker:
	docker build .. -t apertif/apercal

run: ../.venv2/bin/cwltool data
	../.venv2/bin/cwltool --enable-ext apercal.cwl --ms ../data/small/00/raw/3C138.MS
