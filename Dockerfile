FROM kernsuite/base:dev
RUN docker-apt-install \
          casalite miriad python-pip python-numpy python-notebook \
          python-matplotlib python-astroquery python-pandas drive-casa \
          python-casacore python-ephem

ADD . /code
RUN pip install /code


