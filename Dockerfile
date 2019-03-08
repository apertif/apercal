FROM kernsuite/casa:kern-5

RUN docker-apt-install \
          miriad python-pip python-numpy python-notebook \
          python-matplotlib python-astroquery python-pandas \
          python-casacore python-ephem wget git python-astropy aoflagger \
          pybdsf wget curl

RUN wget -qO - https://packages.irods.org/irods-signing-key.asc | apt-key add -
RUN echo "deb [arch=amd64] https://packages.irods.org/apt/ xenial main" > /etc/apt/sources.list.d/renci-irods.list

RUN docker-apt-install irods-icommands

# if we install these here a rebuild trigger by a file change will go quicker
# for now we need to install a special branch of drive-casa, otherwise casa 5 doesnt work
RUN pip install aipy pymp-pypi pyephem pycodestyle \
        git+https://github.com/timstaley/drive-casa.git@casa-release-5#egg=drive-casa

ENV LC_ALL C
ENV MIR /usr/bin
ENV MIRCAT /usr/share/miriad
ENV MIRDEF=.
RUN export MIRARCH=linux64

ADD . /code
WORKDIR /code

RUN pip install .
RUN pip install -r test/requirements.txt

