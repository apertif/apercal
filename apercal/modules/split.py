import logging
import os

from apercal.modules.base import BaseModule
from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles
from apercal.subs.param import get_param_def
from apercal.subs import param as subs_param
from apercal.libs import lib

logger = logging.getLogger(__name__)


class split(BaseModule):

    """
    Split class. For the quicklook pipeline, a small chunk of bandwidth will be split to be processed by pipeline
    """
    module_name = 'SPLIT'

    split_startchannel = None
    split_endchannel = None

    def __init__(self, file_=None, **kwargs):
        self.default = lib.load_config(self, file_)
        subs_setinit.setinitdirs(self)

    def go(self):
        """
        Executes the split step with the parameters indicated in the config-file
        """
        logger.info('Splitting data for quicklook')
        self.split_data()
        logger.info('Data splitted for quicklook')

    def split_data(self):
        """
        Splits out a certain frequency range from the datasets
        """
        # if self.split:

        subs_setinit.setinitdirs(self)

        sbeam = 'split_B' + str(self.beam).zfill(2)

        splitfluxcalstatus = get_param_def(self, sbeam + '_fluxcal_status', False)
        splitpolcalstatus = get_param_def(self, sbeam + '_polcal_status', False)
        splittargetbeamsstatus = get_param_def(self, sbeam + '_targetbeams_status', False)

        logger.info('Beam ' + self.beam + ': Splitting channel ' + str(self.split_startchannel) +
                    ' until ' + str(self.split_endchannel))
        # split the flux calibrator dataset
        logger.debug("self.fluxcal = {}".format(self.fluxcal))
        logger.debug("os.path.isdir(self.get_fluxcal_path()) = {}".format(os.path.isdir(self.get_fluxcal_path())))
        if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):
            fluxcal_split = 'split(vis = "' + self.get_fluxcal_path() + '", outputvis = "' + self.get_fluxcal_path().rstrip('.MS') + '_split.MS"' + \
                ', spw = "0:' + str(self.split_startchannel) + '~' + str(self.split_endchannel) + '", datacolumn = "data")'
            lib.run_casa([fluxcal_split], log_output=True, timeout=3600)
            if os.path.isdir(self.get_fluxcal_path().rstrip('.MS') + '_split.MS'):
                subs_managefiles.director(self, 'rm', self.get_fluxcal_path())
                subs_managefiles.director(self, 'rn', self.get_fluxcal_path(), file_=self.get_fluxcal_path().rstrip('.MS') + '_split.MS')
                splitfluxcalstatus = True
            else:
                splitfluxcalstatus = False
                logger.warning('Beam ' + self.beam + ': Splitting of flux calibrator dataset not successful!')
        else:
            splitfluxcalstatus = False
            logger.warning('Beam ' + self.beam + ': Fluxcal not set or dataset not available! Cannot split flux calibrator dataset!')

        subs_param.add_param(self, sbeam + '_fluxcal_status', splitfluxcalstatus)

        # Split the polarised calibrator dataset
        logger.debug("self.polcal = {}".format(self.polcal))
        logger.debug("os.path.isdir(self.get_polcal_path()) = {}".format(os.path.isdir(self.get_polcal_path())))
        if self.polcal != '' and os.path.isdir(self.get_polcal_path()):
            polcal_split = 'split(vis = "' + self.get_polcal_path() + '", outputvis = "' + self.get_polcal_path().rstrip('.MS') + '_split.MS"' + \
                ', spw = "0:' + str(self.split_startchannel) + '~' + str(self.split_endchannel) + '", datacolumn = "data")'
            lib.run_casa([polcal_split], log_output=True, timeout=3600)
            if os.path.isdir(self.get_polcal_path().rstrip('.MS') + '_split.MS'):
                subs_managefiles.director(self, 'rm', self.get_polcal_path())
                subs_managefiles.director(self, 'rn', self.get_polcal_path(), file_=self.get_polcal_path().rstrip('.MS') + '_split.MS')
                splitpolcalstatus = True
            else:
                splitpolcalstatus = False
                logger.warning('Beam ' + self.beam + ': Splitting of polarised calibrator dataset not successful!')
        else:
            splitpolcalstatus = False
            logger.warning('Beam ' + self.beam + ': Polcal not set or dataset not available! Cannot split polarised calibrator dataset!')

        subs_param.add_param(self, sbeam + '_polcal_status', splitpolcalstatus)

        # Split the target dataset
        logger.debug("self.target = {}".format(self.target))
        logger.debug("os.path.isdir(self.get_target_path()) = {}".format(os.path.isdir(self.get_target_path())))
        if self.target != '' and os.path.isdir(self.get_target_path()):
            target_split = 'split(vis = "' + self.get_target_path() + '", outputvis = "' + self.get_target_path().rstrip('.MS') + '_split.MS"' + \
                ', spw = "0:' + str(self.split_startchannel) + '~' + str(self.split_endchannel) + '", datacolumn = "data")'
            lib.run_casa([target_split], log_output=True, timeout=3600)
            if os.path.isdir(self.get_target_path().rstrip('.MS') + '_split.MS'):
                subs_managefiles.director(self, 'rm', self.get_target_path())
                subs_managefiles.director(self, 'rn', self.get_target_path(), file_=self.get_target_path().rstrip('.MS') + '_split.MS')
                splittargetbeamsstatus = True
            else:
                splittargetbeamsstatus = False
                logger.warning('Beam ' + self.beam + ': Splitting of target dataset not successful!')
        else:
            splittargetbeamsstatus = False
            logger.warning('Beam ' + self.beam + ': Target not set or dataset not available! Cannot split target beam dataset!')

        subs_param.add_param(self, sbeam + '_targetbeams_status', splittargetbeamsstatus)