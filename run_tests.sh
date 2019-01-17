#!/bin/bash -ve

docker build . -t apertif/apercal
make clean
make data/small
docker run -v `pwd`/data:/code/data:rw apertif/apercal pytest -s test/test_prepare.py
docker run -v `pwd`/data:/code/data:rw apertif/apercal pytest -s test/test_preflag.py
docker run -v `pwd`/data:/code/data:rw apertif/apercal pytest -s test/test_ccal.py
docker run -v `pwd`/data:/code/data:rw apertif/apercal pytest -s test/test_convert.py
docker run -v `pwd`/data:/code/data:rw apertif/apercal pytest -s test/test_scal.py
