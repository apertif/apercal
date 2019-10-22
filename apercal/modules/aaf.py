import logging
import os

from apercal.modules.base import BaseModule
from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles
from apercal.subs.param import get_param_def
from apercal.subs import param as subs_param
from apercal.libs import lib

from aaf import antialias_ms

logger = logging.getLogger(__name__)


class aaf(BaseModule):

    """
    AAF class. For running the AAF filter on Apertif data
    """
    module_name = 'AAF'

    aaf_apply = None
    aaf_tolerance = None

    def __init__(self, file_=None, **kwargs):
        self.default = lib.load_config(self, file_)
        subs_setinit.setinitdirs(self)

    def go(self):
        """
        Executes the AAF step with the parameters indicated in the config-file
        """
        logger.info('Beam ' + self.beam + ': Running AAF')
        self.aaf_run()
        logger.info('Beam ' + self.beam + ': Running AAF ... Done')

    def aaf_run(self):
        """
        Runs AAF on the datasets
        """

        subs_setinit.setinitdirs(self)

        abeam = 'aaf_B' + str(self.beam).zfill(2)

        # to keeep track on what the aaf filter was performed
        aaf_fluxcal_status = get_param_def(
            self, abeam + '_fluxcal_status', False)
        aaf_polcal_status = get_param_def(
            self, abeam + '_polcal_status', False)
        aaf_targetbeams_status = get_param_def(
            self, abeam + '_targetbeams_status', False)

        if self.aaf_apply:
            # check if aaf was run on fluxcal
            if aaf_fluxcal_status:
                logger.info(
                    "Beam {}: AAF was alreay performed on flux calibrator".format(self.beam))
            else:
                if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):
                    logger.info("Running AAF on flux calibrator")
                    try:
                        antialias_ms(self.get_fluxcal_path(),
                                     self.aaf_tolerance)
                    except Exception as e:
                        logger.error(
                            "Running AAF on flux calibrator ... Failed")
                        logger.exception(e)
                    else:
                        logger.info("Running AAF on flux calibrator ... Done")
                        aaf_fluxcal_status = True
                else:
                    aaf_fluxcal_status = False
                    logger.warning(
                        'Beam ' + self.beam + ': Fluxcal not set or dataset not available! Cannot perform AAF on flux calibrator dataset!')

            # check if aaf was run on polcal
            if aaf_polcal_status:
                logger.info(
                    "Beam {}: AAF was alreay performed on pol calibrator".format(self.beam))
            else:
                if self.polcal != '' and os.path.isdir(self.get_polcal_path()):
                    logger.info("Running AAF on pol calibrator")
                    try:
                        antialias_ms(self.get_polcal_path(),
                                     self.aaf_tolerance)
                    except Exception as e:
                        logger.error(
                            "Running AAF on pol calibrator ... Failed")
                        logger.exception(e)
                    else:
                        logger.info("Running AAF on pol calibrator ... Done")
                        aaf_polcal_status = True
                else:
                    aaf_polcal_status = False
                    logger.warning(
                        'Beam ' + self.beam + ': Polcal not set or dataset not available! Cannot perform AAF on pol calibrator dataset!')

            # check if aaf was run on target
            if aaf_targetbeams_status:
                logger.info(
                    "Beam {}: AAF was alreay performed on target".format(self.beam))
            else:
                if self.target != '' and os.path.isdir(self.get_target_path()):
                    logger.info("Running AAF on target")
                    try:
                        antialias_ms(self.get_target_path(),
                                     self.aaf_tolerance)
                    except Exception as e:
                        logger.error("Running AAF on target ... Failed")
                        logger.exception(e)
                    else:
                        logger.info("Running AAF on target ... Done")
                        aaf_targetbeams_status = True
                else:
                    aaf_targetbeams_status = False
                    logger.warning(
                        'Beam ' + self.beam + ': Target not set or dataset not available! Cannot perform AAF on target dataset!')
        else:
            aaf_fluxcal_status = False
            aaf_polcal_status
            aaf_targetbeams_status = False
            logger.info(
                "Beam {}: Did not perform AAF on datasets".format(self.beam))

        subs_param.add_param(
            self, abeam + '_fluxcal_status', aaf_fluxcal_status)
        subs_param.add_param(
            self, abeam + '_polcal_status', aaf_polcal_status)
        subs_param.add_param(
            self, abeam + '_targetbeams_status', aaf_targetbeams_status)

    def reset(self):
        """
        Function to reset the current step and remove all generated data. Be careful! Deletes all data generated in
        this step!
        """
        subs_setinit.setinitdirs(self)

        logger.warning('Beam ' + self.beam +
                       ': Deleting all raw data and their directories. You will need to '
                       'start with the PREPARE step again!')
        subs_managefiles.director(self, 'ch', self.basedir)
        try:
            subs_managefiles.director(
                self, 'rm', self.basedir + self.beam + '/' + self.rawsubdir)
        except:
            pass
        logger.warning('Beam ' + self.beam +
                       ': Deleting all parameter file entries for AAF and PREPARE module')

        prebeam = 'prepare_B' + str(self.beam).zfill(2)
        abeam = 'aaf_B' + str(self.beam).zfill(2)

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

        subs_param.del_param(self, abeam + '_fluxcal_status')
        subs_param.del_param(self, abeam + '_polcal_status')
        subs_param.del_param(self, abeam + '_targetbeams_status')

    # def reset_all(self):
    #     """
    #     Function to reset the current step and remove all generated data. Be careful! Deletes all data generated in
    #     this step!
    #     """
    #     subs_setinit.setinitdirs(self)
    #     logger.warning('Deleting all raw data products and their directories for all beams. You will need to '
    #                    'start with the PREPARE step again!')
    #     subs_managefiles.director(self, 'ch', self.basedir)
    #     for b in range(self.NBEAMS):

    #         prebeam = 'prepare_B' + str(b).zfill(2)
    #         sbeam = 'split_B' + str(b).zfill(2)

    #         if os.path.isdir(self.basedir + str(b).zfill(2) + '/' + self.rawsubdir):
    #             try:
    #                 logger.warning('Beam ' + str(b).zfill(2) +
    #                                ': Deleting all raw data products.')
    #                 subs_managefiles.director(
    #                     self, 'rm', self.basedir + str(b).zfill(2) + '/' + self.rawsubdir)
    #             except:
    #                 pass
    #             logger.warning('Beam ' + str(b).zfill(2) +
    #                            ': Deleting all parameter file entries for PREPARE and SPLIT module.')

    #             subs_param.del_param(self, prebeam + '_fluxcal_requested')
    #             subs_param.del_param(self, prebeam + '_fluxcal_diskstatus')
    #             subs_param.del_param(self, prebeam + '_fluxcal_altastatus')
    #             subs_param.del_param(self, prebeam + '_fluxcal_copystatus')
    #             subs_param.del_param(self, prebeam + '_fluxcal_rejreason')
    #             subs_param.del_param(self, prebeam + '_polcal_requested')
    #             subs_param.del_param(self, prebeam + '_polcal_diskstatus')
    #             subs_param.del_param(self, prebeam + '_polcal_altastatus')
    #             subs_param.del_param(self, prebeam + '_polcal_copystatus')
    #             subs_param.del_param(self, prebeam + '_polcal_rejreason')
    #             subs_param.del_param(self, prebeam + '_targetbeams_requested')
    #             subs_param.del_param(self, prebeam + '_targetbeams_diskstatus')
    #             subs_param.del_param(self, prebeam + '_targetbeams_altastatus')
    #             subs_param.del_param(self, prebeam + '_targetbeams_copystatus')
    #             subs_param.del_param(self, prebeam + '_targetbeams_rejreason')

    #             subs_param.del_param(self, sbeam + '_fluxcal_status')
    #             subs_param.del_param(self, sbeam + '_polcal_status')
    #             subs_param.del_param(self, sbeam + '_targetbeams_status')
    #         else:
    #             logger.warning('Beam ' + str(b).zfill(2) +
    #                            ': No raw data present.')
