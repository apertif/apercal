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
        logger.info('Beam ' + self.beam + ': Splitting data for quicklook')
        self.split_data()
        logger.info('Beam ' + self.beam + ': Data splitted for quicklook')

    def split_data(self):
        """
        Splits out a certain frequency range from the datasets
        """

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
        if splitfluxcalstatus:
            logger.info(
                "Beam {0}: Fluxcal has already been split".format(self.beam))
            splitfluxcalstatus = True
        else:
            if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):
                fluxcal_split = 'split(vis = "' + self.get_fluxcal_path() + '", outputvis = "' + self.get_fluxcal_path().rstrip('.MS') + '_split.MS"' + \
                    ', spw = "0:' + str(self.split_startchannel) + '~' + str(self.split_endchannel) + '", datacolumn = "data")'
                lib.run_casa([fluxcal_split], log_output=True, timeout=30000)
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
        if splitpolcalstatus:
            logger.info(
                "Beam {0}: Polcal has already been split".format(self.beam))
            splitpolcalstatus = True
        else:
            if self.polcal != '' and os.path.isdir(self.get_polcal_path()):
                polcal_split = 'split(vis = "' + self.get_polcal_path() + '", outputvis = "' + self.get_polcal_path().rstrip('.MS') + '_split.MS"' + \
                    ', spw = "0:' + str(self.split_startchannel) + '~' + str(self.split_endchannel) + '", datacolumn = "data")'
                lib.run_casa([polcal_split], log_output=True, timeout=30000)
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
        if splittargetbeamsstatus:
            logger.info("Beam {0}: Target has already been split".format(self.beam))
            splittargetbeamsstatus = True
        else:
            if self.target != '' and os.path.isdir(self.get_target_path()):
                target_split = 'split(vis = "' + self.get_target_path() + '", outputvis = "' + self.get_target_path().rstrip('.MS') + '_split.MS"' + \
                    ', spw = "0:' + str(self.split_startchannel) + '~' + str(self.split_endchannel) + '", datacolumn = "data")'
                lib.run_casa([target_split], log_output=True, timeout=30000)
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

    def reset(self):
        """
        Function to reset the current step and remove all generated data. Be careful! Deletes all data generated in
        this step!
        """
        subs_setinit.setinitdirs(self)

        logger.warning('Beam ' + self.beam + ': Deleting all raw data and their directories.')
        subs_managefiles.director(self, 'ch', self.basedir)
        try:
            subs_managefiles.director(self, 'rm', self.basedir + self.beam + '/' + self.rawsubdir)
        except:
            pass
        logger.warning('Beam ' + self.beam + ': Deleting all parameter file entries for SPLIT and PREPARE module')

        prebeam = 'prepare_B' + str(self.beam).zfill(2)
        sbeam = 'split_B' + str(self.beam).zfill(2)

        subs_param.del_param(self, prebeam + '_fluxcal_requested')
        subs_param.del_param(self, prebeam + '_fluxcal_diskstatus')
        subs_param.del_param(self, prebeam + '_fluxcal_altastatus')
        subs_param.del_param(self, prebeam + '_fluxcal_copystatus')
        subs_param.del_param(self, prebeam + '_fluxcal_rejreason')
        subs_param.del_param(self, prebeam + '_polcal_requested')
        subs_param.del_param(self, prebeam + '_polcal_diskstatus')
        subs_param.del_param(self, prebeam + '_polcal_altastatus')
        subs_param.del_param(self, prebeam + '_polcal_copystatus')
        subs_param.del_param(self, prebeam + '_polcal_rejreason')
        subs_param.del_param(self, prebeam + '_targetbeams_requested')
        subs_param.del_param(self, prebeam + '_targetbeams_diskstatus')
        subs_param.del_param(self, prebeam + '_targetbeams_altastatus')
        subs_param.del_param(self, prebeam + '_targetbeams_copystatus')
        subs_param.del_param(self, prebeam + '_targetbeams_rejreason')

        subs_param.del_param(self, sbeam + '_fluxcal_status')
        subs_param.del_param(self, sbeam + '_polcal_status')
        subs_param.del_param(self, sbeam + '_targetbeams_status')


    def reset_all(self):
        """
        Function to reset the current step and remove all generated data. Be careful! Deletes all data generated in
        this step!
        """
        subs_setinit.setinitdirs(self)
        logger.warning('Deleting all raw data products and their directories for all beams. You will need to '
                       'start with the PREPARE step again!')
        subs_managefiles.director(self, 'ch', self.basedir)
        for b in range(self.NBEAMS):

            prebeam = 'prepare_B' + str(b).zfill(2)
            sbeam = 'split_B' + str(b).zfill(2)

            if os.path.isdir(self.basedir + str(b).zfill(2) + '/' + self.rawsubdir):
                try:
                    logger.warning('Beam ' + str(b).zfill(2) + ': Deleting all raw data products.')
                    subs_managefiles.director(self, 'rm', self.basedir + str(b).zfill(2) + '/' + self.rawsubdir)
                except:
                    pass
                logger.warning('Beam ' + str(b).zfill(2) + ': Deleting all parameter file entries for PREPARE and SPLIT module.')

                subs_param.del_param(self, prebeam + '_fluxcal_requested')
                subs_param.del_param(self, prebeam + '_fluxcal_diskstatus')
                subs_param.del_param(self, prebeam + '_fluxcal_altastatus')
                subs_param.del_param(self, prebeam + '_fluxcal_copystatus')
                subs_param.del_param(self, prebeam + '_fluxcal_rejreason')
                subs_param.del_param(self, prebeam + '_polcal_requested')
                subs_param.del_param(self, prebeam + '_polcal_diskstatus')
                subs_param.del_param(self, prebeam + '_polcal_altastatus')
                subs_param.del_param(self, prebeam + '_polcal_copystatus')
                subs_param.del_param(self, prebeam + '_polcal_rejreason')
                subs_param.del_param(self, prebeam + '_targetbeams_requested')
                subs_param.del_param(self, prebeam + '_targetbeams_diskstatus')
                subs_param.del_param(self, prebeam + '_targetbeams_altastatus')
                subs_param.del_param(self, prebeam + '_targetbeams_copystatus')
                subs_param.del_param(self, prebeam + '_targetbeams_rejreason')

                subs_param.del_param(self, sbeam + '_fluxcal_status')
                subs_param.del_param(self, sbeam + '_polcal_status')
                subs_param.del_param(self, sbeam + '_targetbeams_status')
            else:
                logger.warning('Beam ' + str(b).zfill(2) + ': No raw data present.')
