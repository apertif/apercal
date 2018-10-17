import ConfigParser
import logging
import os

from apercal.subs import setinit as subs_setinit


class polarisation:
    """
    Final class to produce final data products (Deep continuum images, line cubes, and polairsation images and Faraday-cubes).
    """

    def __init__(self, file=None, **kwargs):
        logging.basicConfig(level=logging.DEBUG)
        self.logger = logging.getLogger('POLARISATION')
        config = ConfigParser.ConfigParser()  # Initialise the config parser
        if file != None:
            config.readfp(open(file))
            self.logger.info('### Configuration file ' + file + ' successfully read! ###')
        else:
            config.readfp(open(os.path.realpath(__file__).rstrip('calibrate.pyc') + 'default.cfg'))
            self.logger.info('### No configuration file given or file not found! Using default values! ###')
        for s in config.sections():
            for o in config.items(s):
                setattr(self, o[0], eval(o[1]))
        self.default = config  # Save the loaded config file as defaults for later usage
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)

    def polarisation(self):
        """
        Produces individual images for Stokes Q,U, cleans them with the mask from Stokes I and combines them in a cube.
        Then uses RM-Synthesis to produce a Faraday cube and clean it.
        """
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)
        self.logger.info('### Polarisation imaging is going to be implemented later ###')
