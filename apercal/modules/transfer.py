import logging

import os

from apercal.modules.base import BaseModule
from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles
from apercal.subs.param import get_param_def
from apercal.subs import param as subs_param
from apercal.libs import lib

logger = logging.getLogger(__name__)


class transfer(BaseModule):
    """
    Transfer class to combine the calibrated data chunks with full spectral resolution into one file and export to UVFITS.
    Gain tables and flags are already applied. Data is then ready to get ingested into ALTA.
    """
    module_name = 'TRANSFER'

    transferdir = None
    transfer_convert_selfcaluv2uvfits = None

    def __init__(self, file_=None, **kwargs):
        self.default = lib.load_config(self, file_)
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)

    def go(self):
        """
        Executes the continuum imaging process in the following order
        convert_lineuv2uvfits
        """
        logger.info("Starting TRANSFER module")
        self.convert_selfcaluv2uvfits()
        logger.info("TRANSFER module done")

    def convert_selfcaluv2uvfits(self):
        """
        Looks for the last self-calibrated uv-fits file, copies its gains over to the original file, applies them and coverts to UVFITS format
        """
        subs_setinit.setinitdirs(self)

        sbeam = 'selfcal_B' + str(self.beam).zfill(2)
        tbeam = 'transfer_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the conversion of the UVFITS-files

        transfertargetbeamsselfcaluv2uvfitsstatus = get_param_def(
            self, tbeam + '_targetbeams_selfcaluv2uvfits_status', False)

        if self.transfer_convert_selfcaluv2uvfits:
            subs_setinit.setinitdirs(self)
            subs_setinit.setdatasetnamestomiriad(self)
            subs_managefiles.director(
                self, 'ch', self.transferdir, verbose=True)
            if not transfertargetbeamsselfcaluv2uvfitsstatus:
                # Get the status of the selfcal for the specified beam
                selfcaltargetbeamsphasestatus = get_param_def(
                    self, sbeam + '_targetbeams_phase_status', False)
                selfcaltargetbeamsampstatus = get_param_def(
                    self, sbeam + '_targetbeams_amp_status', False)
                datasetname_amp = os.path.join(
                    self.selfcaldir, self.target).rstrip('.mir') + '_amp.mir'
                datasetname_phase = os.path.join(
                    self.selfcaldir, self.target)
                logger.debug(
                    "Setting amplitude selfcal file name: {}".format(datasetname_amp))
                logger.debug(
                    "Setting phase selfcal file name: {}".format(datasetname_phase))
                # datasetname_amp = self.get_target_path().rstrip('.mir') + '_amp.mir'
                # datasetname_phase = self.get_target_path()
                if os.path.isdir(datasetname_amp) and selfcaltargetbeamsampstatus:
                    logger.info('Beam ' + self.beam +
                                ': Using amplitude self-calibrated dataset!')
                    dataset = datasetname_amp
                elif os.path.isdir(datasetname_phase) and selfcaltargetbeamsphasestatus:
                    logger.info(
                        'Beam ' + self.beam + ': Using phase self-calibrated dataset. Amplitude calibration was not successful or not wanted!')
                    dataset = datasetname_phase
                else:
                    dataset = None

                if dataset is not None:
                    # Copy the raw dataset to the transfer directory
                    subs_managefiles.director(
                        self, 'cp', self.transferdir + '/' + self.target, file_=self.crosscaldir + '/' + self.target)
                    if selfcaltargetbeamsampstatus:
                        gpcopy = lib.miriad('gpcopy')
                        gpcopy.vis = datasetname_phase
                        gpcopy.out = self.transferdir + '/' + self.target
                        gpcopy.go()
                        uvaver = lib.miriad('uvaver')
                        uvaver.vis = self.transferdir + '/' + self.target
                        uvaver.out = self.transferdir + '/' + \
                            self.target.rstrip('.mir') + '_phase.mir'
                        uvaver.go()
                        gpcopy = lib.miriad('gpcopy')
                        gpcopy.vis = datasetname_amp
                        gpcopy.out = self.transferdir + '/' + \
                            self.target.rstrip('.mir') + '_phase.mir'
                        gpcopy.go()
                        fits = lib.miriad('fits')
                        fits.op = 'uvout'
                        fits.in_ = self.transferdir + '/' + \
                            self.target.rstrip('.mir') + '_phase.mir'
                        fits.out = self.transferdir + '/' + \
                            self.target.rstrip('.mir') + '.UVFITS'
                        fits.go()
                        if os.path.isfile(self.transferdir + '/' + self.target.rstrip('.mir') + '.UVFITS'):
                            subs_managefiles.director(
                                self, 'rm', self.transferdir + '/' + self.target)
                            subs_managefiles.director(
                                self, 'rm', self.transferdir + '/' + self.target.rstrip('.mir') + '_phase.mir')
                            transfertargetbeamsselfcaluv2uvfitsstatus = True
                        else:
                            logger.error(
                                'Beam ' + self.beam + ': Conversion was not successful. No UVFITS-file generated!')
                            transfertargetbeamsselfcaluv2uvfitsstatus = False
                    elif selfcaltargetbeamsphasestatus:
                        gpcopy = lib.miriad('gpcopy')
                        gpcopy.vis = datasetname_phase
                        gpcopy.out = self.transferdir + '/' + self.target
                        gpcopy.go()
                        fits = lib.miriad('fits')
                        fits.op = 'uvout'
                        fits.in_ = self.transferdir + '/' + self.target
                        fits.out = self.transferdir + '/' + \
                            self.target.rstrip('.mir') + '.UVFITS'
                        fits.go()
                        if os.path.isfile(self.transferdir + '/' + self.target.rstrip('.mir') + '.UVFITS'):
                            subs_managefiles.director(
                                self, 'rm', self.transferdir + '/' + self.target)
                            transfertargetbeamsselfcaluv2uvfitsstatus = True
                        else:
                            logger.error(
                                'Beam ' + self.beam + ': Conversion was not successful. No UVFITS-file generated!')
                            transfertargetbeamsselfcaluv2uvfitsstatus = False
                else:
                    logger.error(
                        'Beam ' + self.beam + ': Self-calibration was not successful. No conversion to UVFITS-format possible!')
                    transfertargetbeamsselfcaluv2uvfitsstatus = False
            else:
                logger.info(
                    'Beam ' + self.beam + ': Conversion of final calibrated data to UVFITS-format already successfully executed!')
        else:
            logger.info('Beam ' + self.beam +
                        ': Conversion of final calibrated data to UVFITS-format not selected!')

        # Save the derived parameters to the parameter file

        subs_param.add_param(self, tbeam + '_targetbeams_selfcaluv2uvfits_status',
                             transfertargetbeamsselfcaluv2uvfitsstatus)

    # def convert_lineuv2uvfits(self):
    #     """
    #     Looks for all calibrated datasets created by the line module, combines the chunks of individual beams and
    #     converts them to UVFITS format
    #     """
    #     subs_setinit.setinitdirs(self)
    #     subs_managefiles.director(self, 'ch', self.transferdir, verbose=False)
    #     beamlist = sorted(glob.glob(self.basedir + '[0-9][0-9]'))
    #     beamnames = [beam.split('/')[-1] for beam in beamlist]
    #     subs_param.add_param(self, 'transfer_input_beams', beamnames)
    #     # transferstatusarray = np.full((len(beamnames, 2), np.False))
    #     for b, beam in enumerate(beamlist):
    #         uvgluestatusarray = np.full((len(beamnames)), False)
    #         uvfitsstatusarray = np.full((len(beamnames)), False)
    #         if os.path.isfile(self.target.rstrip('.mir') + '_B' + beam.split('/')[-1] + '.UVFITS'):
    #             logger.warning('UVFITS file for beam ' + beam.split('/')[-1] + ' already exists! #')
    #         else:
    #             chunklist = sorted(glob.glob(beam + '/' + self.linesubdir + '/' + '[0-9][0-9]/[0-9][0-9]' + '.mir'))
    #             chunknames = [chunk.split('/')[-2] for chunk in chunklist]
    #             subs_param.add_param(self, 'transfer_input_beam_' + str(beamnames[b]) + '_chunks', chunknames)
    #             uvcatstatusarray = np.full((len(chunknames)), False)
    #             logger.debug('Starting combination of frequency chunks for beam ' + beam.split('/')[-1] + ' #')
    #             for c, chunk in enumerate(chunklist):
    #                 uvcat = lib.miriad('uvcat')
    #                 uvcat.vis = chunk
    #                 uvcat.out = self.transferdir + '/' + 'B' + beam.split('/')[-1] + '_' + str(c + 1)
    #                 uvcat.go()
    #                 # Check if file has been copied successfully
    #                 if os.path.isdir(self.transferdir + '/' + 'B' + beam.split('/')[-1] + '_' + str(c + 1)):
    #                     logger.debug('Chunk ' + str(chunk).zfill(2) + ' for beam ' + str(
    #                         beam.split('/')[-1]) + ' copied successfully! #')
    #                     uvcatstatusarray[c] = True
    #                 else:
    #                     logger.warning('Chunk ' + str(chunk).zfill(2) + ' for beam ' + str(
    #                         beam.split('/')[-1]) + ' NOT copied successfully! #')
    #                     uvcatstatusarray[c] = False
    #             subs_param.add_param(self, 'transfer_input_beam_' + str(beamnames[b]) + '_copy_status',
    #                                  uvcatstatusarray)
    #             uvglue = lib.miriad('uvglue')
    #             uvglue.vis = 'B' + beam.split('/')[-1]
    #             uvglue.nfiles = len(chunklist)
    #             uvglue.out = self.target.rstrip('.mir') + '_B' + beam.split('/')[-1] + '.mir'
    #             uvglue.go()
    #             if os.path.isdir(self.target.rstrip('.mir') + '_B' + beam.split('/')[-1] + '.mir'):
    #                 logger.debug('Combination of frequency chunks for beam ' + beam.split('/')[-1] + ' successful! #')
    #                 subs_managefiles.director(self, 'rm', 'B' + beam.split('/')[-1] + '*')
    #                 uvgluestatusarray[b] = True
    #             else:
    #                 logger.warning('Combination of frequency chunks for beam ' + beam.split('/')[-1] +
    #                                ' not successful! #')
    #                 uvgluestatusarray[b] = False
    #             fits = lib.miriad('fits')
    #             fits.op = 'uvout'
    #             fits.in_ = self.target.rstrip('.mir') + '_B' + beam.split('/')[-1] + '.mir'
    #             fits.out = self.target.rstrip('.mir') + '_B' + beam.split('/')[-1] + '.UVFITS'
    #             fits.go()
    #             if os.path.isfile(self.target.rstrip('.mir') + '_B' + beam.split('/')[-1] + '.UVFITS'):
    #                 logger.debug(
    #                     'Conversion of MIRIAD file to UVFITS for beam ' + beam.split('/')[-1] + ' successful! #')
    #                 subs_managefiles.director(self, 'rm',
    #                                           self.target.rstrip('.mir') + '_B' + beam.split('/')[-1] + '.mir')
    #                 uvfitsstatusarray[b] = True
    #             else:
    #                 logger.warning(
    #                     'Conversion of MIRIAD file to UVFITS for beam ' + beam.split('/')[-1] + ' NOT successful! #')
    #                 uvfitsstatusarray[b] = False
    #         subs_param.add_param(self, 'transfer_input_beams_uvglue', uvgluestatusarray)
    #         subs_param.add_param(self, 'transfer_input_beams_uvfits', uvfitsstatusarray)

    def reset(self):
        """
        Function to reset the current step and remove all generated data. Be careful! Deletes all data generated in
        this step!
        """
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)
        logger.warning('Deleting all data products ready for transfer!')
        subs_managefiles.director(self, 'ch', self.basedir)
        subs_managefiles.director(self, 'rm', self.transferdir)
