FROM kernsuite/casa:kern-dev

RUN docker-apt-install \
          miriad python-pip python-numpy python-notebook \
          python-matplotlib python-astroquery python-pandas \
          python-casacore python-ephem wget git python-astropy aoflagger \
          pybdsf

# if we install these here a rebuild trigger by a file change will go quicker
# for now we need to install a special branch of drive-casa, otherwise casa 5 doesnt work
RUN pip install aipy pymp-pypi pyephem pycodestyle \
        git+https://github.com/timstaley/drive-casa.git@casa-release-5#egg=drive-casa

ADD . /code
WORKDIR /code

ENV MIR /usr/bin
ENV MIRCAT /usr/share/miriad
ENV MIRDEF=.
RUN export MIRARCH=linux64

RUN pip install .
RUN pip install -r test/requirements.txt

