__author__ = "Bradley Frank, Bjoern Adebahr"
__copyright__ = "ASTRON"
__email__ = "frank@astron.nl, adebahr@astron.nl"

import lib
import logging
import numpy as np
import os
import ConfigParser

####################################################################################################

class wselfcal:
    '''
    wselfcal: SelfCal class for getting the adaptive selfcal routine going
    '''
    def __init__(self, file=None, **kwargs):
        self.logger = logging.getLogger('selfcal')
        logger = self.logger
        config = ConfigParser.ConfigParser() # Initialise the config parser
        if file != None:
            config.readfp(open(file))
            logger.info('Configuration file ' + file + ' successfully read!')
        else:
            config.readfp(open(os.path.realpath(__file__).rstrip('test.pyc') + 'default.cfg'))
            logger.info('No configuration file given or file not found! Using default values for selfcal!')
        for s in config.sections():
            for o in config.items(s):
                setattr(self, o[0], o[1])