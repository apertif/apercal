import logging
from apercal.subs import setinit as subs_setinit
from apercal.libs import lib


logger = logging.getLogger(__name__)


class polarisation:
    """
    Final class to produce final data products (Deep continuum images, line cubes, and polairsation images and Faraday-cubes).
    """

    def __init__(self, file=None, **kwargs):
        self.default = lib.load_config(self, file)
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)

    def polarisation(self):
        """
        Produces individual images for Stokes Q,U, cleans them with the mask from Stokes I and combines them in a cube.
        Then uses RM-Synthesis to produce a Faraday cube and clean it.
        """
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)
        logger.info(' Polarisation imaging is going to be implemented later')
