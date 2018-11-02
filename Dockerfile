FROM kernsuite/casa:kern-dev
RUN docker-apt-install \
          miriad python-pip python-numpy python-notebook \
          python-matplotlib python-astroquery python-pandas drive-casa \
          python-casacore python-ephem wget

ADD . /code
WORKDIR /code

RUN make data/small

RUN pip install .
RUN pip install -r test/requirements.txt

## disable test run until all tests are working
#RUN pytest


