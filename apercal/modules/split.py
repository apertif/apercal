import glob
import logging
import pandas as pd
import os
import numpy as np

from apercal.modules.base import BaseModule
from apercal.subs import irods as subs_irods
from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles
from apercal.subs.param import get_param_def
from apercal.subs import param as subs_param
from apercal.libs import lib

logger = logging.getLogger(__name__)


class split(BaseModule):

    """
    Split class. For the quicklook pipeline, a small chunk of bandwidth will be split
    """
    module_name = 'SPLIT'

    # split_date = None
    # split_obsnum_fluxcal = None
    # split_obsnum_polcal = None
    # split_obsnum_target = None
    # split_target_beams = None
    # split_bypass_alta = None
    # split_flip_ra = False
    split = None
    split_startchannel = None
    split_endchannel = None

    def __init__(self, file_=None, **kwargs):
        self.default = lib.load_config(self, file_)
        subs_setinit.setinitdirs(self)

    def go(self):
        """
        Executes the complete prepare step with the parameters indicated in the config-file in the following order:
        copyobs
        """
        logger.info('Preparing data for calibration')
        self.split_data()
        logger.info('Data prepared for calibration')

    def split_data(self):
        """
        Splits out a certain frequency range from the datasets for the quicklook pipeline
        """
        if self.split:
            logger.info('Splitting channel ' + str(self.split_startchannel) +
                        ' until ' + str(self.split_endchannel))
            # split the flux calibrator dataset
            logger.debug("self.fluxcal = {}".format(self.fluxcal))
            logger.debug("os.path.isdir(self.get_fluxcal_path()) = {}".format(
                os.path.isdir(self.get_fluxcal_path())))
            if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):
                fluxcal_split = 'split(vis = "' + self.get_fluxcal_path() + '", outputvis = "' + self.get_fluxcal_path().rstrip('.MS') + '_split.MS"' + \
                    ', spw = "0:' + str(self.split_startchannel) + '~' + str(
                    self.split_endchannel) + '", datacolumn = "data")'
                lib.run_casa([fluxcal_split], log_output=True, timeout=3600)
                if os.path.isdir(self.get_fluxcal_path().rstrip('.MS') + '_split.MS'):
                    subs_managefiles.director(
                        self, 'rm', self.get_fluxcal_path())
                    subs_managefiles.director(self, 'rn', self.get_fluxcal_path(
                    ), file_=self.get_fluxcal_path().rstrip('.MS') + '_split.MS')
                else:
                    logger.warning(
                        'Splitting of flux calibrator dataset not successful!')
            else:
                logger.warning(
                    'Fluxcal not set or dataset not available! Cannot split flux calibrator dataset!')
            # Split the polarised calibrator dataset
            logger.debug("self.polcal = {}".format(self.polcal))
            logger.debug("os.path.isdir(self.get_polcal_path()) = {}".format(
                os.path.isdir(self.get_polcal_path())))
            if self.polcal != '' and os.path.isdir(self.get_polcal_path()):
                polcal_split = 'split(vis = "' + self.get_polcal_path() + '", outputvis = "' + self.get_polcal_path().rstrip('.MS') + '_split.MS"' + \
                    ', spw = "0:' + str(self.split_startchannel) + '~' + str(
                    self.split_endchannel) + '", datacolumn = "data")'
                lib.run_casa([polcal_split], log_output=True, timeout=3600)
                if os.path.isdir(self.get_polcal_path().rstrip('.MS') + '_split.MS'):
                    subs_managefiles.director(
                        self, 'rm', self.get_polcal_path())
                    subs_managefiles.director(self, 'rn', self.get_polcal_path(
                    ), file_=self.get_polcal_path().rstrip('.MS') + '_split.MS')
                else:
                    logger.warning(
                        'Splitting of polarised calibrator dataset not successful!')
            else:
                logger.warning(
                    'Polcal not set or dataset not available! Cannot split polarised calibrator dataset!')
            # Split the target dataset
            logger.debug("self.target = {}".format(self.target))
            logger.debug("os.path.isdir(self.get_target_path()) = {}".format(
                os.path.isdir(self.get_target_path())))
            if self.target != '' and os.path.isdir(self.get_target_path()):
                target_split = 'split(vis = "' + self.get_target_path() + '", outputvis = "' + self.get_target_path().rstrip('.MS') + '_split.MS"' + \
                    ', spw = "0:' + str(self.split_startchannel) + '~' + str(
                    self.split_endchannel) + '", datacolumn = "data")'
                lib.run_casa([target_split], log_output=True, timeout=3600)
                if os.path.isdir(self.get_target_path().rstrip('.MS') + '_split.MS'):
                    subs_managefiles.director(
                        self, 'rm', self.get_target_path())
                    subs_managefiles.director(self, 'rn', self.get_target_path(
                    ), file_=self.get_target_path().rstrip('.MS') + '_split.MS')
                else:
                    logger.warning(
                        'Splitting of target dataset not successful!')
            else:
                logger.warning(
                    'Target not set or dataset not available! Cannot split target dataset!')
        else:
            pass
