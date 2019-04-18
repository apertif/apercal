import logging

import numpy as np
import pandas as pd
import os

from apercal.modules.base import BaseModule
from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles
import glob

from apercal.libs import lib
from apercal.subs import imstats
from apercal.subs.param import get_param_def
from apercal.subs import param as subs_param
from apercal.subs import masking
from apercal.subs import qa

from apercal.exceptions import ApercalException

logger = logging.getLogger(__name__)


class continuum(BaseModule):
    """
    Continuum class to produce continuum data products (Deep continuum images of individual frequency chunks and
    stacked continuum image).
    """
    module_name = 'CONTINUUM'

    contdir = None
    selfcaldir = None

    continuum_gaussianity = None
    continuum_mfimage = None
    continuum_mfimage_imsize = None
    continuum_mfimage_cellsize = None
    continuum_mfimage_minorcycle = None
    continuum_mfimage_c1 = None
    continuum_mfimage_drinc = None
    continuum_mfimage_mindr = None
    continuum_mfimage_nsigma = None
    continuum_chunkimage = None
    continuum_chunkimage_startchannels = None
    continuum_chunkimage_endchannels = None
    continuum_chunkimage_imsize = None
    continuum_chunkimage_cellsize = None
    continuum_chunkimage_minorcycle = None
    continuum_chunkimage_c1 = None
    continuum_chunkimage_drinc = None
    continuum_chunkimage_mindr = None
    continuum_chunkimage_nsigma = None


    def __init__(self, file_=None, **kwargs):
        self.default = lib.load_config(self, file_)
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)


    def go(self):
        """
        Executes the continuum imaging process in the following order
        image_continuum
        """
        logger.info("Starting CONTINUUM IMAGING")
        self.mfimage()
        self.chunkimage()
        logger.info("CONTINUUM IMAGING done ")


    def get_target_path(self, beam=None):
        if self.subdirification:
            return '../' + self.selfcalsubdir + '/' + self.target
        else:
            return self.target


    def mfimage(self):
        """
        Creates the final deep mfs continuum image from the self-calibrated data
        """
        subs_setinit.setinitdirs(self)

        sbeam = 'selfcal_B' + str(self.beam).zfill(2)
        beam = 'continuum_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the iterative continuum imaging

        continuumtargetbeamsmfstatus = get_param_def(self, beam + '_targetbeams_mf_status', False)
        continuumtargetbeamsmfmapstatus = get_param_def(self, beam + '_targetbeams_mf_mapstatus', False)
        continuumtargetbeamsmfmapstats = get_param_def(self, beam + '_targetbeams_mf_mapstats', np.full((3), np.nan))
        continuumtargetbeamsmfbeamstatus = get_param_def(self, beam + '_targetbeams_mf_beamstatus', False)
        continuumtargetbeamsmfmaskstatus = get_param_def(self, beam + '_targetbeams_mf_maskstatus', np.full((self.continuum_mfimage_minorcycle), False))
        continuumtargetbeamsmfmaskstats = get_param_def(self, beam + '_targetbeams_mf_maskstats', np.full((self.continuum_mfimage_minorcycle, 2), np.nan))
        continuumtargetbeamsmfmodelstatus = get_param_def(self, beam + '_targetbeams_mf_modelstatus', np.full((self.continuum_mfimage_minorcycle), False))
        continuumtargetbeamsmfmodelstats = get_param_def(self, beam + '_targetbeams_mf_modelstats', np.full((self.continuum_mfimage_minorcycle, 2), np.nan))
        continuumtargetbeamsmfimagestatus = get_param_def(self, beam + '_targetbeams_mf_imagestatus', np.full((self.continuum_mfimage_minorcycle), False))
        continuumtargetbeamsmfimagestats = get_param_def(self, beam + '_targetbeams_mf_imagestats', np.full((self.continuum_mfimage_minorcycle, 3), np.nan))
        continuumtargetbeamsmfresidualstatus = get_param_def(self, beam + '_targetbeams_mf_residualstatus', False)
        continuumtargetbeamsmfresidualstats = get_param_def(self, beam + '_targetbeams_mf_residualstats', np.full((self.continuum_mfimage_minorcycle, 3), np.nan))
        continuumtargetbeamsmfmaskthreshold = get_param_def(self, beam + '_targetbeams_mf_maskthreshold', np.full((self.continuum_mfimage_minorcycle), np.nan))
        continuumtargetbeamsmfcleanthreshold = get_param_def(self, beam + '_targetbeams_mf_cleanthreshold', np.full((self.continuum_mfimage_minorcycle), np.nan))
        continuumtargetbeamsmfthresholdtype = get_param_def(self, beam + '_targetbeams_mf_thresholdtype', np.full((self.continuum_mfimage_minorcycle), 'NA'))
        continuumtargetbeamsmffinalminor = get_param_def(self, beam + '_targetbeams_mf_final_minorcycle', np.full((1), 0))

        if self.continuum_mfimage:
            subs_setinit.setinitdirs(self)
            subs_setinit.setdatasetnamestomiriad(self)
            subs_managefiles.director(self, 'ch', self.contdir)
            if not continuumtargetbeamsmfstatus:
                logger.info('Beam ' + self.beam + ': Multi-frequency continuum imaging')
                # Get the status of the selfcal for the specified beam
                selfcaltargetbeamsphasestatus = get_param_def(self, sbeam + '_targetbeams_phase_status', False)
                selfcaltargetbeamsampstatus = get_param_def(self, sbeam + '_targetbeams_amp_status', False)
                selfcaltargetbeamsphasestatus = True # Remove after fix
                datasetname_amp = self.get_target_path().rstrip('.mir') + '_amp.mir'
                datasetname_phase = self.get_target_path()
                if os.path.isdir(datasetname_amp) and selfcaltargetbeamsampstatus:
                    logger.info('Beam ' + self.beam + ': Using amplitude self-calibrated dataset!')
                    dataset = datasetname_amp
                elif os.path.isdir(datasetname_phase) and selfcaltargetbeamsphasestatus:
                    logger.info('Beam ' + self.beam + ': Using phase self-calibrated dataset. Amplitude calibration was not successful or not wanted!')
                    dataset = datasetname_phase
                else:
                    msg = 'Beam ' + self.beam + ': Self-calibration was not successful. No continuum imaging possible!'
                    logger.error(msg)
                    raise ApercalException(msg)

                # Start the multi-frequency continuum imaging
                # Calculate the theoretical noise and check Stokes V for gaussianity parameter
                gaussianity, TN = masking.get_theoretical_noise(self, dataset, self.continuum_gaussianity)
                if gaussianity:
                    pass
                else:
                    logger.warning('Beam ' + self.beam + ': Stokes V image shows non-gaussian distribution. Your theoretical noise value might be off!')
                logger.info('Beam ' + self.beam + ': Theoretical noise is ' + '%.6f' % TN + ' Jy')
                TNreached = False  # Stop continuum imaging if theoretical noise is reached
                stop = False
                for minc in range(self.continuum_mfimage_minorcycle):
                    if not stop:
                        if not TNreached:
                            if minc == 0:  # Create a new dirty image after the self-calibration
                                invert = lib.miriad('invert')  # Create the dirty image
                                invert.vis = dataset
                                invert.map = 'map_mf_00'
                                invert.beam = 'beam_mf_00'
                                invert.imsize = self.continuum_mfimage_imsize
                                invert.cell = self.continuum_mfimage_cellsize
                                invert.stokes = 'i'
                                invert.options = 'mfs,sdb,double'
                                invert.slop = 1
                                invert.robust = -2
                                invert.go()
                                # Check if dirty image and beam is there and ok
                                if os.path.isdir('map_mf_00') and os.path.isdir('beam_mf_00'):
                                    continuumtargetbeamsmfbeamstatus = True
                                    continuumtargetbeamsmfmapstats[:] = imstats.getimagestats(self, 'map_mf_00')
                                    if qa.checkdirtyimage(self, 'map_mf_00'):
                                        continuumtargetbeamsmfmapstatus = True
                                    else:
                                        continuumtargetbeamsmfmapstatus = False
                                        continuumtargetbeamsmfstatus = False
                                        logger.error('Beam ' + self.beam + ': Dirty image for continuum imaging is invalid. Stopping imaging!')
                                        stop = True
                                        continuumtargetbeamsmffinalminor = minc
                                        break
                                else:
                                    continuumtargetbeamsmfbeamstatus = False
                                    continuumtargetbeamsmfstatus = False
                                    logger.error('Beam ' + self.beam + ': Dirty image or beam for continuum imaging not found. Stopping imaging!')
                                    stop = True
                                    continuumtargetbeamsmffinalminor = minc
                                    break
                                dirtystats = imstats.getimagestats(self, 'map_mf_00')  # Min, max, rms of the dirty image
                                TNdr = masking.calc_theoretical_noise_dr(dirtystats[1], TN, self.continuum_mfimage_nsigma)  # Theoretical noise dynamic range
                                TNth = masking.calc_theoretical_noise_threshold(dirtystats[1], TNdr)
                                maskth = dirtystats[1]/np.nanmax([self.continuum_mfimage_drinc, self.continuum_mfimage_mindr])
                                continuumtargetbeamsmfthresholdtype[0] = 'DR'
                                continuumtargetbeamsmfmaskthreshold[0] = maskth
                                Cc = masking.calc_clean_cutoff(maskth, self.continuum_mfimage_c1)  # Clean cutoff
                                continuumtargetbeamsmfcleanthreshold[0] = Cc
                                beampars = masking.get_beam(self, invert.map, invert.beam)
                                masking.create_mask(self, 'map_mf_00', 'mask_mf_00', maskth, TN, beampars=beampars, rms_map=False)
                                # Check if mask is there and ok
                                if os.path.isdir('mask_mf_00'):
                                    continuumtargetbeamsmfmaskstats[minc, :] = imstats.getmaskstats(self, 'mask_mf_00', self.continuum_mfimage_imsize)
                                    if qa.checkmaskimage(self, 'mask_mf_00'):
                                        continuumtargetbeamsmfmaskstatus[minc] = True
                                    else:
                                        continuumtargetbeamsmfmaskstatus[minc] = False
                                        continuumtargetbeamsmfstatus = False
                                        logger.error('Beam ' + self.beam + ': Mask image for cycle ' + str(minc) + ' is invalid. Stopping continuum imaging!')
                                        stop = True
                                        continuumtargetbeamsmffinalminor = minc
                                        break
                                else:
                                    continuumtargetbeamsmfmaskstatus[minc] = False
                                    continuumtargetbeamsmfstatus = False
                                    logger.error('Beam ' + self.beam + ': Mask image for cycle ' + str(minc) + ' not found. Stopping continuum imaging!')
                                    stop = True
                                    continuumtargetbeamsmffinalminor = minc
                                    break
                                mfclean = lib.miriad('mfclean')  # Clean the image down to the calculated threshold
                                mfclean.map = 'map_mf_00'
                                mfclean.beam = 'beam_mf_00'
                                mfclean.out = 'model_mf_00'
                                mfclean.cutoff = Cc
                                mfclean.niters = 25000
                                mfclean.region = '"' + 'mask(mask_mf_00)' + '"'
                                mfclean.go()
                                # Check if clean component image is there and ok
                                if os.path.isdir('model_mf_00'):
                                    continuumtargetbeamsmfmodelstats[minc, :] = imstats.getmodelstats(self, 'model_mf_00')
                                    if qa.checkmodelimage(self, 'model_mf_00'):
                                        continuumtargetbeamsmfmodelstatus[minc] = True
                                    else:
                                        continuumtargetbeamsmfmodelstatus[minc] = False
                                        continuumtargetbeamsmfstatus = False
                                        logger.error('Beam ' + self.beam + ': Clean component image for cycle ' + str(minc) + ' is invalid. Stopping continuum imaging!')
                                        stop = True
                                        continuumtargetbeamsmffinalminor = minc
                                        break
                                else:
                                    continuumtargetbeamsmfmodelstatus[minc] = False
                                    continuumtargetbeamsmfstatus = False
                                    logger.error('Beam ' + self.beam + ': Clean component image for cycle ' + str(minc) + ' not found. Stopping continuum imaging!')
                                    stop = True
                                    continuumtargetbeamsmffinalminor = minc
                                    break
                                restor = lib.miriad('restor')  # Create the restored image
                                restor.model = 'model_mf_00'
                                restor.beam = 'beam_mf_00'
                                restor.map = 'map_mf_00'
                                restor.out = 'image_mf_00'
                                restor.mode = 'clean'
                                restor.go()
                                # Check if restored image is there and ok
                                if os.path.isdir('image_mf_00'):
                                    continuumtargetbeamsmfimagestats[minc, :] = imstats.getimagestats(self, 'image_mf_00')
                                    if qa.checkrestoredimage(self, 'image_mf_00'):
                                        continuumtargetbeamsmfimagestatus[minc] = True
                                    else:
                                        continuumtargetbeamsmfimagestatus[minc] = False
                                        continuumtargetbeamsmfstatus = False
                                        logger.error('Beam ' + self.beam + ': Restored image for cycle ' + str(minc) + ' is invalid. Stopping continuum imaging!')
                                        stop = True
                                        continuumtargetbeamsmffinalminor = minc
                                        break
                                else:
                                    continuumtargetbeamsmfimagestatus[minc] = False
                                    continuumtargetbeamsmfstatus = False
                                    logger.error('Beam ' + self.beam + ': Restored image for cycle ' + str(minc) + ' not found. Stopping continuum imaging!')
                                    stop = True
                                    continuumtargetbeamsmffinalminor = minc
                                    break
                                restor.mode = 'residual'  # Create the residual image
                                restor.out = 'residual_mf_00'
                                restor.go()
                                residualstats = imstats.getimagestats(self, 'residual_mf_00')  # Min, max, rms of the residual image
                                continuumtargetbeamsmfresidualstats[minc, :] = residualstats
                                currdr = dirtystats[1] / residualstats[2]
                                logger.info('Beam ' + self.beam + ': Dynamic range is ' + '%.3f' % currdr + ' for cycle ' + str(minc))
                                continuumtargetbeamsmffinalminor = minc
                            else:
                                residualstats = imstats.getimagestats(self, 'residual_mf_' + str(minc-1).zfill(2))  # Min, max, rms of the residual image
                                maskth = residualstats[1]/self.continuum_mfimage_drinc
                                if TNth >= maskth:
                                    maskth = TNth
                                    TNreached = True
                                    continuumtargetbeamsmfthresholdtype[minc] = 'TN'
                                    continuumtargetbeamsmfmaskthreshold[minc] = maskth
                                    logger.info('Beam ' + self.beam + ': Theoretical noise threshold reached in cycle ' + str(minc) + '. Stopping iterations and creating final image!')
                                else:
                                    TNreached = False
                                    continuumtargetbeamsmfthresholdtype[minc] = 'DR'
                                    continuumtargetbeamsmfmaskthreshold[minc] = maskth
                                Cc = masking.calc_clean_cutoff(maskth, self.continuum_mfimage_c1)  # Clean cutoff
                                continuumtargetbeamsmfcleanthreshold[minc] = Cc
                                masking.create_mask(self, 'image_mf_' + str(minc-1).zfill(2), 'mask_mf_' + str(minc).zfill(2), maskth, TN, beampars=None)
                                # Check if mask is there and ok
                                if os.path.isdir('mask_mf_' + str(minc).zfill(2)):
                                    continuumtargetbeamsmfmaskstats[minc, :] = imstats.getmaskstats(self, 'mask_mf_' + str(minc).zfill(2), self.continuum_mfimage_imsize)
                                    if qa.checkmaskimage(self, 'mask_mf_' + str(minc).zfill(2)):
                                        continuumtargetbeamsmfmaskstatus[minc] = True
                                    else:
                                        continuumtargetbeamsmfmaskstatus[minc] = False
                                        continuumtargetbeamsmfstatus = False
                                        msg = 'Beam ' + self.beam + ': Mask image for cycle ' + str(minc) + ' is invalid. Stopping continuum imaging!'
                                        logger.error(msg)
                                        stop = True
                                        continuumtargetbeamsmffinalminor = minc
                                        break
                                else:
                                    continuumtargetbeamsmfmaskstatus[minc] = False
                                    continuumtargetbeamsmfstatus = False
                                    msg = 'Beam ' + self.beam + ': Mask image for cycle ' + str(minc) + ' not found. Stopping continuum imaging!'
                                    logger.error(msg)
                                    stop = True
                                    continuumtargetbeamsmffinalminor = minc
                                    break
                                mfclean = lib.miriad('mfclean')  # Clean the image down to the calculated threshold
                                mfclean.map = 'map_mf_00'
                                mfclean.beam = 'beam_mf_00'
                                mfclean.model = 'model_mf_' + str(minc - 1).zfill(2)
                                mfclean.out = 'model_mf_' + str(minc).zfill(2)
                                mfclean.cutoff = Cc
                                mfclean.niters = 25000
                                mfclean.region = '"' + 'mask(mask_mf_' + str(minc).zfill(2) + ')' + '"'
                                mfclean.go()
                                # Check if clean component image is there and ok
                                if os.path.isdir('model_mf_' + str(minc).zfill(2)):
                                    continuumtargetbeamsmfmodelstats[minc, :] = imstats.getmodelstats(self, 'model_mf_' + str(minc).zfill(2))
                                    if qa.checkmodelimage(self, 'model_mf_' + str(minc).zfill(2)):
                                        continuumtargetbeamsmfmodelstatus[minc] = True
                                    else:
                                        continuumtargetbeamsmfmodelstatus[minc] = False
                                        continuumtargetbeamsmfstatus = False
                                        msg = 'Beam ' + self.beam + ': Clean component image for cycle ' + str(minc) + ' is invalid. Stopping continuum imaging!'
                                        logger.error(msg)
                                        stop = True
                                        continuumtargetbeamsmffinalminor = minc
                                        break
                                else:
                                    continuumtargetbeamsmfmodelstatus[minc] = False
                                    continuumtargetbeamsmfstatus = False
                                    msg = 'Beam ' + self.beam + ': Clean component image for cycle ' + str(minc) + ' not found. Stopping continuum imaging!'
                                    logger.error(msg)
                                    stop = True
                                    continuumtargetbeamsmffinalminor = minc
                                    break
                                restor = lib.miriad('restor')  # Create the restored image
                                restor.model = 'model_mf_' + str(minc).zfill(2)
                                restor.beam = 'beam_mf_00'
                                restor.map = 'map_mf_00'
                                restor.out = 'image_mf_' + str(minc).zfill(2)
                                restor.mode = 'clean'
                                restor.go()
                                # Check if restored image is there and ok
                                if os.path.isdir('image_mf_' + str(minc).zfill(2)):
                                    continuumtargetbeamsmfimagestats[minc, :] = imstats.getimagestats(self, 'image_mf_' + str(minc).zfill(2))
                                    if qa.checkrestoredimage(self, 'image_mf_' + str(minc).zfill(2)):
                                        continuumtargetbeamsmfimagestatus[minc] = True
                                        continuumtargetbeamsmffinalminor = minc
                                    else:
                                        continuumtargetbeamsmfimagestatus[minc] = False
                                        continuumtargetbeamsmfstatus = False
                                        logger.error('Beam ' + self.beam + ': Restored image for cycle ' + str(minc) + ' is invalid. Stopping continuum imaging!')
                                        stop = True
                                        continuumtargetbeamsmffinalminor = minc
                                        break
                                else:
                                    continuumtargetbeamsmfimagestatus[minc] = False
                                    continuumtargetbeamsmfstatus = False
                                    logger.error('Beam ' + self.beam + ': Restored image for cycle ' + str(minc) + ' not found. Stopping continuum imaging!')
                                    stop = True
                                    continuumtargetbeamsmffinalminor = minc
                                    break
                                restor.mode = 'residual'  # Create the residual image
                                restor.out = 'residual_mf_' + str(minc).zfill(2)
                                restor.go()
                                residualstats = imstats.getimagestats(self, 'residual_mf_' + str(minc).zfill(2))  # Min, max, rms of the residual image
                                continuumtargetbeamsmfresidualstats[minc, :] = residualstats
                                currdr = dirtystats[1] / residualstats[2]
                                logger.info('Beam ' + self.beam + ': Dynamic range is ' + '%.3f' % currdr + ' for cycle ' + str(minc))
                        else:
                            break
                    else:
                        break
                else:
                    continuumtargetbeamsmfstatus = False
                # Final checks if continuum mf imaging was successful
                if continuumtargetbeamsmfstatus:
                    if TNreached:
                        if qa.checkimagegaussianity(self, 'residual_mf_' + str(continuumtargetbeamsmffinalminor).zfill(2), self.continuum_gaussianity):
                            continuumtargetbeamsmfresidualstatus = True
                            continuumtargetbeamsmfstatus = True
                            subs_managefiles.imagetofits(self, 'image_mf_' + str(continuumtargetbeamsmffinalminor).zfill(2), 'image_mf_' + str(continuumtargetbeamsmffinalminor).zfill(2) + '.fits')
                            logger.info('Beam ' + self.beam + ': Multi-frequency continuum imaging successfully done!')
                        else:
                            continuumtargetbeamsmfresidualstatus = False
                            continuumtargetbeamsmfstatus = False
                            logger.warning('Beam ' + self.beam + ': Final residual image shows non-gaussian statistics. Multi-frequency continuum imaging was not successful!')
                    elif minc == continuumtargetbeamsmffinalminor:
                        logger.warning('Beam ' + self.beam + ': Multi-frequency continuum imaging did not reach theoretical noise!')
                        if qa.checkimagegaussianity(self, 'residual_mf_' + str(continuumtargetbeamsmffinalminor).zfill(2), self.continuum_gaussianity):
                            self.logger.warning('Beam ' + self.beam + ': Residual image seems to show Gaussian statistics. Maybe cleaning was deep enough!')
                            continuumtargetbeamsmfresidualstatus = True
                            continuumtargetbeamsmfstatus = True
                            subs_managefiles.imagetofits(self, 'image_mf_' + str(continuumtargetbeamsmffinalminor).zfill(2), 'image_mf_' + str(continuumtargetbeamsmffinalminor).zfill(2) + '.fits')
                            logger.info('Beam ' + self.beam + ': Multi-frequency continuum imaging successfully done!')
                        else:
                            continuumtargetbeamsmfresidualstatus = False
                            continuumtargetbeamsmfstatus = False
                            logger.warning('Beam ' + self.beam + ': Final residual image shows non-gaussian statistics. Multi-frequency continuum imaging was not successful!')
                else:
                    continuumtargetbeamsmfstatus = False
                    logger.warning('Beam ' + self.beam + ': Something else happened and I dont know what')
            else:
                logger.info('Beam ' + self.beam + ': Multi-frequency continuum image was already successfully created!')
        else:
            logger.info('Beam ' + self.beam + ': Multi-frequency continuum imaging not selected!')

        # Save the derived parameters to the parameter file

        subs_param.add_param(self, beam + '_targetbeams_mf_status', continuumtargetbeamsmfstatus)
        subs_param.add_param(self, beam + '_targetbeams_mf_mapstatus', continuumtargetbeamsmfmapstatus)
        subs_param.add_param(self, beam + '_targetbeams_mf_mapstats', continuumtargetbeamsmfmapstats)
        subs_param.add_param(self, beam + '_targetbeams_mf_beamstatus', continuumtargetbeamsmfbeamstatus)
        subs_param.add_param(self, beam + '_targetbeams_mf_maskstatus', continuumtargetbeamsmfmaskstatus)
        subs_param.add_param(self, beam + '_targetbeams_mf_maskstats', continuumtargetbeamsmfmaskstats)
        subs_param.add_param(self, beam + '_targetbeams_mf_modelstatus', continuumtargetbeamsmfmodelstatus)
        subs_param.add_param(self, beam + '_targetbeams_mf_modelstats', continuumtargetbeamsmfmodelstats)
        subs_param.add_param(self, beam + '_targetbeams_mf_imagestatus', continuumtargetbeamsmfimagestatus)
        subs_param.add_param(self, beam + '_targetbeams_mf_imagestats', continuumtargetbeamsmfimagestats)
        subs_param.add_param(self, beam + '_targetbeams_mf_residualstatus', continuumtargetbeamsmfresidualstatus)
        subs_param.add_param(self, beam + '_targetbeams_mf_residualstats', continuumtargetbeamsmfresidualstats)
        subs_param.add_param(self, beam + '_targetbeams_mf_maskthreshold', continuumtargetbeamsmfmaskthreshold)
        subs_param.add_param(self, beam + '_targetbeams_mf_cleanthreshold', continuumtargetbeamsmfcleanthreshold)
        subs_param.add_param(self, beam + '_targetbeams_mf_thresholdtype', continuumtargetbeamsmfthresholdtype)
        subs_param.add_param(self, beam + '_targetbeams_mf_final_minorcycle', continuumtargetbeamsmffinalminor)

    def chunkimage(self):
        """
        Creates the final deep mfs continuum image from the self-calibrated data
        """
        subs_setinit.setinitdirs(self)

        sbeam = 'selfcal_B' + str(self.beam).zfill(2)
        beam = 'continuum_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the iterative continuum chunk imaging

        nchunks = len(np.asarray(self.continuum_chunkimage_startchannels))

        continuumtargetbeamschunkallstatus = get_param_def(self, beam + '_targetbeams_chunkall_status', False)
        continuumtargetbeamschunkstatus = get_param_def(self, beam + '_targetbeams_chunk_status', np.full((nchunks), False))
        continuumtargetbeamschunkmapstatus = get_param_def(self, beam + '_targetbeams_chunk_mapstatus', np.full((nchunks), False))
        continuumtargetbeamschunkmapstats = get_param_def(self, beam + '_targetbeams_chunk_mapstats', np.full((nchunks, 3), np.nan))
        continuumtargetbeamschunkbeamstatus = get_param_def(self, beam + '_targetbeams_chunk_beamstatus', np.full((nchunks), False))
        continuumtargetbeamschunkmaskstatus = get_param_def(self, beam + '_targetbeams_chunk_maskstatus', np.full((nchunks, self.continuum_mfimage_minorcycle), False))
        continuumtargetbeamschunkmaskstats = get_param_def(self, beam + '_targetbeams_chunk_maskstats', np.full((nchunks, self.continuum_mfimage_minorcycle, 2), np.nan))
        continuumtargetbeamschunkmodelstatus = get_param_def(self, beam + '_targetbeams_chunk_modelstatus', np.full((nchunks, self.continuum_mfimage_minorcycle), False))
        continuumtargetbeamschunkmodelstats = get_param_def(self, beam + '_targetbeams_chunk_modelstats', np.full((nchunks, self.continuum_mfimage_minorcycle, 2), np.nan))
        continuumtargetbeamschunkimagestatus = get_param_def(self, beam + '_targetbeams_chunk_imagestatus', np.full((nchunks, self.continuum_mfimage_minorcycle), False))
        continuumtargetbeamschunkimagestats = get_param_def(self, beam + '_targetbeams_chunk_imagestats', np.full((nchunks, self.continuum_mfimage_minorcycle, 3), np.nan))
        continuumtargetbeamschunkresidualstatus = get_param_def(self, beam + '_targetbeams_chunk_residualstatus', np.full((nchunks), False))
        continuumtargetbeamschunkresidualstats = get_param_def(self, beam + '_targetbeams_chunk_residualstats', np.full((nchunks, self.continuum_mfimage_minorcycle, 3), np.nan))
        continuumtargetbeamschunkmaskthreshold = get_param_def(self, beam + '_targetbeams_chunk_maskthreshold', np.full((nchunks, self.continuum_mfimage_minorcycle), np.nan))
        continuumtargetbeamschunkcleanthreshold = get_param_def(self, beam + '_targetbeams_chunk_cleanthreshold', np.full((nchunks, self.continuum_mfimage_minorcycle), np.nan))
        continuumtargetbeamschunkthresholdtype = get_param_def(self, beam + '_targetbeams_chunk_thresholdtype', np.full((nchunks, self.continuum_mfimage_minorcycle), 'NA'))
        continuumtargetbeamschunkfinalminor = get_param_def(self, beam + '_targetbeams_chunk_final_minorcycle', np.full((nchunks), 0))


        if self.continuum_chunkimage:
            subs_setinit.setinitdirs(self)
            subs_setinit.setdatasetnamestomiriad(self)
            subs_managefiles.director(self, 'ch', self.contdir)
            if not continuumtargetbeamschunkallstatus:
                logger.info('Beam ' + self.beam + ': Individual chunk continuum imaging')
                # Get the status of the selfcal for the specified beam
                selfcaltargetbeamsphasestatus = get_param_def(self, sbeam + '_targetbeams_phase_status', False)
                selfcaltargetbeamsampstatus = get_param_def(self, sbeam + '_targetbeams_amp_status', False)
#                selfcaltargetbeamsphasestatus = True  # Remove after fix
                datasetname_amp = self.get_target_path().rstrip('.mir') + '_amp.mir'
                datasetname_phase = self.get_target_path()
                if os.path.isdir(datasetname_amp) and selfcaltargetbeamsampstatus:
                    logger.info('Beam ' + self.beam + ': Using amplitude self-calibrated dataset!')
                    dataset = datasetname_amp
                elif os.path.isdir(datasetname_phase) and selfcaltargetbeamsphasestatus:
                    logger.info('Beam ' + self.beam + ': Using phase self-calibrated dataset. Amplitude calibration was not successful or not wanted!')
                    dataset = datasetname_phase
                else:
                    msg = 'Beam ' + self.beam + ': Self-calibration was not successful. No continuum imaging possible!'
                    logger.error(msg)
                    raise ApercalException(msg)

                # Start the chunk continuum imaging

                # Convert the startchannel and enchannel strings to an array
                startchanarray = np.asarray(self.continuum_chunkimage_startchannels)
                endchanarray = np.asarray(self.continuum_chunkimage_endchannels)
                nchunks = len(startchanarray)
                for chunk in range(nchunks):
                    if not continuumtargetbeamschunkstatus[chunk]:
                        cn = 'Chunk ' + str(chunk).zfill(2) + ': '
                        # Calculate the theoretical noise and check Stokes V for gaussianity parameter for each chunk
                        try:
                            gaussianity, TN = masking.get_theoretical_noise(self, dataset, self.continuum_gaussianity, startchan=startchanarray[chunk], endchan=endchanarray[chunk])
                        except Exception as e:
                            logger.info("Imaging chunk " + str(chunk) + " failed, probably all flagged.")
                            continue
                        if gaussianity:
                            pass
                        else:
                            logger.warning('Beam ' + self.beam + ': ' + cn + 'Stokes V image shows non-gaussian distribution. Your theoretical noise value might be off!')
                        logger.info('Beam ' + self.beam + ': ' + cn + 'Theoretical noise is ' + '%.6f' % TN + ' Jy')
                        TNreached = False  # Stop continuum imaging if theoretical noise is reached
                        stop = False
                        for minc in range(self.continuum_chunkimage_minorcycle):
                            if not stop:
                                if not TNreached:
                                    if minc == 0:  # Create a new dirty image after the self-calibration
                                        invert = lib.miriad('invert')  # Create the dirty image
                                        invert.vis = dataset
                                        invert.map = 'map_C' + str(chunk).zfill(2) + '_00'
                                        invert.beam = 'beam_C' + str(chunk).zfill(2) + '_00'
                                        invert.imsize = self.continuum_chunkimage_imsize
                                        invert.cell = self.continuum_chunkimage_cellsize
                                        invert.stokes = 'i'
                                        invert.options = 'mfs,double'
                                        invert.line = 'channel,1,' + str(startchanarray[chunk] + 1) + ',' + str(endchanarray[chunk] - startchanarray[chunk] + 1) + ',' + str(endchanarray[chunk] - startchanarray[chunk] + 1)
                                        invert.slop = 1
                                        invert.robust = -2
                                        invert.go()
                                        # Check if dirty image and beam is there and ok
                                        if os.path.isdir('map_C' + str(chunk).zfill(2) + '_00') and os.path.isdir('beam_C' + str(chunk).zfill(2) + '_00'):
                                            continuumtargetbeamschunkbeamstatus[chunk] = True
                                            continuumtargetbeamschunkmapstats[chunk, :] = imstats.getimagestats(self, 'map_C' + str(chunk).zfill(2) + '_00')
                                            if qa.checkdirtyimage(self, 'map_C' + str(chunk).zfill(2) + '_00'):
                                                continuumtargetbeamschunkmapstatus[chunk] = True
                                            else:
                                                continuumtargetbeamschunkmapstatus[chunk] = False
                                                continuumtargetbeamschunkstatus[chunk] = False
                                                logger.error('Beam ' + self.beam + ': ' + cn + 'Dirty image for continuum imaging is invalid. Stopping imaging!')
                                                stop = True
                                                continuumtargetbeamschunkfinalminor[chunk] = minc
                                                break
                                        else:
                                            continuumtargetbeamschunkbeamstatus[chunk] = False
                                            continuumtargetbeamschunkstatus[chunk] = False
                                            logger.error('Beam ' + self.beam + ': ' + cn + 'Dirty image or beam for continuum imaging not found. Stopping imaging!')
                                            stop = True
                                            continuumtargetbeamschunkfinalminor[chunk] = minc
                                            break
                                        dirtystats = imstats.getimagestats(self, 'map_C' + str(chunk).zfill(2) + '_00')  # Min, max, rms of the dirty image
                                        TNdr = masking.calc_theoretical_noise_dr(dirtystats[1], TN, self.continuum_chunkimage_nsigma)  # Theoretical noise dynamic range
                                        TNth = masking.calc_theoretical_noise_threshold(dirtystats[1], TNdr)
                                        maskth = dirtystats[1] / np.nanmax([self.continuum_chunkimage_drinc, self.continuum_chunkimage_mindr])
                                        continuumtargetbeamschunkthresholdtype[chunk, 0] = 'DR'
                                        continuumtargetbeamschunkmaskthreshold[chunk, 0] = maskth
                                        Cc = masking.calc_clean_cutoff(maskth, self.continuum_chunkimage_c1)  # Clean cutoff
                                        continuumtargetbeamschunkcleanthreshold[chunk, 0] = Cc
                                        beampars = masking.get_beam(self, invert.map, invert.beam)
                                        masking.create_mask(self, 'map_C' + str(chunk).zfill(2) + '_00', 'mask_C' + str(chunk).zfill(2) + '_00', maskth, TN, beampars=beampars, rms_map=False)
                                        # Check if mask is there and ok
                                        if os.path.isdir('mask_C' + str(chunk).zfill(2) + '_00'):
                                            continuumtargetbeamschunkmaskstats[chunk, minc, :] = imstats.getmaskstats(self, 'mask_C' + str(chunk).zfill(2) + '_00', self.continuum_chunkimage_imsize)
                                            if qa.checkmaskimage(self, 'mask_C' + str(chunk).zfill(2) + '_00'):
                                                 continuumtargetbeamschunkmaskstatus[chunk, minc] = True
                                            else:
                                                continuumtargetbeamschunkmaskstatus[chunk, minc] = False
                                                continuumtargetbeamschunkstatus[chunk] = False
                                                logger.error('Beam ' + self.beam + ': ' + cn + 'Mask image for cycle ' + str(minc) + ' is invalid. Stopping continuum imaging!')
                                                stop = True
                                                continuumtargetbeamschunkfinalminor[chunk] = minc
                                                break
                                        else:
                                            continuumtargetbeamschunkmaskstatus[chunk, minc] = False
                                            continuumtargetbeamschunkstatus[chunk] = False
                                            logger.error('Beam ' + self.beam + ': ' + cn + 'Mask image for cycle ' + str(minc) + ' not found. Stopping continuum imaging!')
                                            stop = True
                                            continuumtargetbeamschunkfinalminor[chunk] = minc
                                            break
                                        clean = lib.miriad('clean')  # Clean the image down to the calculated threshold
                                        clean.map = 'map_C' + str(chunk).zfill(2) + '_00'
                                        clean.beam = 'beam_C' + str(chunk).zfill(2) + '_00'
                                        clean.out = 'model_C' + str(chunk).zfill(2) + '_00'
                                        clean.cutoff = Cc
                                        clean.niters = 10000
                                        clean.region = '"' + 'mask(mask_C' + str(chunk).zfill(2) + '_00)' + '"'
                                        clean.go()
                                        # Check if clean component image is there and ok
                                        if os.path.isdir('model_C' + str(chunk).zfill(2) + '_00'):
                                            continuumtargetbeamschunkmodelstats[chunk, minc, :] = imstats.getmodelstats(self, 'model_C' + str(chunk).zfill(2) + '_00')
                                            if qa.checkmodelimage(self, 'model_C' + str(chunk).zfill(2) + '_00'):
                                                continuumtargetbeamschunkmodelstatus[chunk, minc] = True
                                            else:
                                                continuumtargetbeamschunkmodelstatus[chunk, minc] = False
                                                continuumtargetbeamschunkstatus[chunk] = False
                                                logger.error('Beam ' + self.beam + ': ' + cn + ' Clean component image for cycle ' + str(minc) + ' is invalid. Stopping continuum imaging!')
                                                stop = True
                                                continuumtargetbeamschunkfinalminor[chunk] = minc
                                                break
                                        else:
                                            continuumtargetbeamschunkmodelstatus[chunk, minc] = False
                                            continuumtargetbeamschunkstatus[chunk] = False
                                            logger.error('Beam ' + self.beam + ':  ' + cn + 'Clean component image for cycle ' + str(minc) + ' not found. Stopping continuum imaging!')
                                            stop = True
                                            continuumtargetbeamschunkfinalminor[chunk] = minc
                                            break
                                        restor = lib.miriad('restor')  # Create the restored image
                                        restor.model = 'model_C' + str(chunk).zfill(2) + '_00'
                                        restor.beam = 'beam_C' + str(chunk).zfill(2) + '_00'
                                        restor.map = 'map_C' + str(chunk).zfill(2) + '_00'
                                        restor.out = 'image_C' + str(chunk).zfill(2) + '_00'
                                        restor.mode = 'clean'
                                        restor.go()
                                        # Check if restored image is there and ok
                                        if os.path.isdir('image_C' + str(chunk).zfill(2) + '_00'):
                                            continuumtargetbeamschunkimagestats[chunk, minc, :] = imstats.getimagestats(self, 'image_C' + str(chunk).zfill(2) + '_00')
                                            if qa.checkrestoredimage(self, 'image_C' + str(chunk).zfill(2) + '_00'):
                                                continuumtargetbeamschunkimagestatus[chunk, minc] = True
                                            else:
                                                continuumtargetbeamschunkimagestatus[chunk, minc] = False
                                                continuumtargetbeamschunkstatus[chunk] = False
                                                logger.error('Beam ' + self.beam + ': ' + cn + 'Restored image for cycle ' + str(minc) + ' is invalid. Stopping continuum imaging!')
                                                stop = True
                                                continuumtargetbeamschunkfinalminor[chunk] = minc
                                                break
                                        else:
                                            continuumtargetbeamschunkimagestatus[chunk, minc] = False
                                            continuumtargetbeamschunkstatus[chunk] = False
                                            logger.error('Beam ' + self.beam + ': ' + cn + 'Restored image for cycle ' + str(minc) + ' not found. Stopping continuum imaging!')
                                            stop = True
                                            continuumtargetbeamschunkfinalminor[chunk] = minc
                                            break
                                        restor.mode = 'residual'  # Create the residual image
                                        restor.out = 'residual_C' + str(chunk).zfill(2) + '_00'
                                        restor.go()
                                        residualstats = imstats.getimagestats(self, 'image_C' + str(chunk).zfill(2) + '_00')  # Min, max, rms of the residual image
                                        continuumtargetbeamschunkresidualstats[chunk, minc, :] = residualstats
                                        currdr = dirtystats[1] / residualstats[2]
                                        logger.info('Beam ' + self.beam + ': ' + cn + 'Dynamic range is ' + '%.3f' % currdr + ' for cycle ' + str(minc))
                                        continuumtargetbeamschunkfinalminor[chunk] = minc
                                    else:
                                        residualstats = imstats.getimagestats(self, 'residual_C' + str(chunk).zfill(2) + '_' + str(minc-1).zfill(2))  # Min, max, rms of the residual image
                                        maskth = residualstats[1]/self.continuum_chunkimage_drinc
                                        if TNth >= maskth:
                                            maskth = TNth
                                            TNreached = True
                                            continuumtargetbeamschunkthresholdtype[chunk, minc] = 'TN'
                                            continuumtargetbeamschunkmaskthreshold[chunk, minc] = maskth
                                            logger.info('Beam ' + self.beam + ': ' + cn + 'Theoretical noise threshold reached in cycle ' + str(minc) + '. Stopping iterations and creating final image!')
                                        else:
                                            TNreached = False
                                            continuumtargetbeamschunkthresholdtype[chunk, minc] = 'DR'
                                            continuumtargetbeamschunkmaskthreshold[chunk, minc] = maskth
                                        Cc = masking.calc_clean_cutoff(maskth, self.continuum_chunkimage_c1)  # Clean cutoff
                                        continuumtargetbeamschunkcleanthreshold[chunk, minc] = Cc
                                        masking.create_mask(self, 'image_C' + str(chunk).zfill(2) + '_' + str(minc-1).zfill(2), 'mask_C' + str(chunk).zfill(2) + '_' + str(minc).zfill(2), maskth, TN, beampars=None)
                                        # Check if mask is there and ok
                                        if os.path.isdir('mask_C' + str(chunk).zfill(2) + '_' + str(minc).zfill(2)):
                                            continuumtargetbeamschunkmaskstats[chunk, minc, :] = imstats.getmaskstats(self, 'mask_C' + str(chunk).zfill(2) + '_' + str(minc).zfill(2), self.continuum_chunkimage_imsize)
                                            if qa.checkmaskimage(self, 'mask_C' + str(chunk).zfill(2) + '_' + str(minc).zfill(2)):
                                                continuumtargetbeamschunkmaskstatus[chunk, minc] = True
                                            else:
                                                continuumtargetbeamschunkmaskstatus[chunk, minc] = False
                                                continuumtargetbeamschunkstatus[chunk] = False
                                                msg = 'Beam ' + self.beam + ': ' + cn + 'Mask image for cycle ' + str(minc) + ' is invalid. Stopping continuum imaging!'
                                                logger.error(msg)
                                                stop = True
                                                continuumtargetbeamschunkfinalminor[chunk] = minc
                                                break
                                        else:
                                            continuumtargetbeamschunkmaskstatus[chunk, minc] = False
                                            continuumtargetbeamschunkstatus[chunk] = False
                                            msg = 'Beam ' + self.beam + ': ' + cn + 'Mask image for cycle ' + str(minc) + ' not found. Stopping continuum imaging!'
                                            logger.error(msg)
                                            stop = True
                                            continuumtargetbeamschunkfinalminor[chunk] = minc
                                            break
                                        clean = lib.miriad('clean')  # Clean the image down to the calculated threshold
                                        clean.map = 'map_C' + str(chunk).zfill(2) + '_00'
                                        clean.beam = 'beam_C' + str(chunk).zfill(2) + '_00'
                                        clean.model = 'model_C' + str(chunk).zfill(2) + '_' + str(minc - 1).zfill(2)
                                        clean.out = 'model_C' + str(chunk).zfill(2) + '_' + str(minc).zfill(2)
                                        clean.cutoff = Cc
                                        clean.niters = 10000
                                        clean.region = '"' + 'mask(mask_C' + str(chunk).zfill(2) + '_' + str(minc).zfill(2) + ')' + '"'
                                        clean.go()
                                        # Check if clean component image is there and ok
                                        if os.path.isdir('model_C' + str(chunk).zfill(2) + '_' + str(minc).zfill(2)):
                                            continuumtargetbeamschunkmodelstats[chunk, minc, :] = imstats.getmodelstats(self, 'model_C' + str(chunk).zfill(2) + '_' + str(minc).zfill(2))
                                            if qa.checkmodelimage(self, 'model_C' + str(chunk).zfill(2) + '_' + str(minc).zfill(2)):
                                                continuumtargetbeamschunkmodelstatus[chunk, minc] = True
                                            else:
                                                continuumtargetbeamschunkmodelstatus[chunk, minc] = False
                                                continuumtargetbeamschunkstatus[chunk] = False
                                                msg = 'Beam ' + self.beam + ': ' + cn + 'Clean component image for cycle ' + str(minc) + ' is invalid. Stopping continuum imaging!'
                                                logger.error(msg)
                                                stop = True
                                                continuumtargetbeamschunkfinalminor[chunk] = minc
                                                break
                                        else:
                                            continuumtargetbeamschunkmodelstatus[chunk, minc] = False
                                            continuumtargetbeamschunkstatus[chunk] = False
                                            msg = 'Beam ' + self.beam + ': ' + cn + 'Clean component image for cycle ' + str(minc) + ' not found. Stopping continuum imaging!'
                                            logger.error(msg)
                                            stop = True
                                            continuumtargetbeamschunkfinalminor[chunk] = minc
                                            break
                                        restor = lib.miriad('restor')  # Create the restored image
                                        restor.model = 'model_C' + str(chunk).zfill(2) + '_' + str(minc).zfill(2)
                                        restor.beam = 'beam_C' + str(chunk).zfill(2) + '_00'
                                        restor.map = 'map_C' + str(chunk).zfill(2) + '_00'
                                        restor.out = 'image_C' + str(chunk).zfill(2) + '_' + str(minc).zfill(2)
                                        restor.mode = 'clean'
                                        restor.go()
                                        # Check if restored image is there and ok
                                        if os.path.isdir('image_C' + str(chunk).zfill(2) + '_' + str(minc).zfill(2)):
                                            continuumtargetbeamschunkimagestats[chunk, minc, :] = imstats.getimagestats(self, 'image_C' + str(chunk).zfill(2) + '_' + str(minc).zfill(2))
                                            if qa.checkrestoredimage(self, 'image_C' + str(chunk).zfill(2) + '_' + str(minc).zfill(2)):
                                                continuumtargetbeamschunkimagestatus[chunk, minc] = True
                                                continuumtargetbeamschunkfinalminor[chunk] = minc
                                            else:
                                                continuumtargetbeamschunkimagestatus[chunk, minc] = False
                                                continuumtargetbeamschunkstatus[chunk] = False
                                                logger.error('Beam ' + self.beam + ': ' + cn + 'Restored image for cycle ' + str(minc) + ' is invalid. Stopping continuum imaging!')
                                                stop = True
                                                continuumtargetbeamschunkfinalminor[chunk] = minc
                                                break
                                        else:
                                            continuumtargetbeamschunkimagestatus[chunk, minc] = False
                                            continuumtargetbeamschunkstatus[chunk] = False
                                            logger.error('Beam ' + self.beam + ': ' + cn + 'Restored image for cycle ' + str(minc) + ' not found. Stopping continuum imaging!')
                                            stop = True
                                            continuumtargetbeamschunkfinalminor[chunk] = minc
                                            break
                                        restor.mode = 'residual'  # Create the residual image
                                        restor.out = 'residual_C' + str(chunk).zfill(2) + '_' + str(minc).zfill(2)
                                        restor.go()
                                        residualstats = imstats.getimagestats(self, 'residual_C' + str(chunk).zfill(2) + '_' + str(minc).zfill(2))  # Min, max, rms of the residual image
                                        continuumtargetbeamschunkresidualstats[chunk, minc, :] = residualstats
                                        currdr = dirtystats[1] / residualstats[2]
                                        logger.info('Beam ' + self.beam + ': ' + cn + 'Dynamic range is ' + '%.3f' % currdr + ' for cycle ' + str(minc))
                                else:
                                    break
                            else:
                                break
                        if TNreached and continuumtargetbeamschunkimagestatus[chunk, continuumtargetbeamschunkfinalminor[chunk]]:
                            logger.info('Beam ' + self.beam + ': ' + cn + 'Chunk successfully imaged!')
                            subs_managefiles.imagetofits(self, 'image_C' + str(chunk).zfill(2) + '_' + str(continuumtargetbeamschunkfinalminor[chunk]).zfill(2), 'image_C' + str(chunk).zfill(2) + '_' + str(continuumtargetbeamschunkfinalminor[chunk]).zfill(2) + '.fits')
                            continuumtargetbeamschunkstatus[chunk] = True
                        else:
                            logger.info('Beam ' + self.beam + ': ' + cn + 'Theoretical noise not reached or final restored image invalid! Imaging for this chunk was not successful!')
                            continuumtargetbeamschunkstatus[chunk] = False
                    else:
                        logger.info('Beam ' + self.beam + ': ' + cn + 'Chunk already successfully imaged. Skipping imaging for this chunk!')
                        continuumtargetbeamschunkstatus[chunk] = True
                if np.all(continuumtargetbeamschunkstatus):
                    logger.info('Beam ' + self.beam + ': ' + cn + 'All continuum chunks were successfully imaged!')
                    continuumtargetbeamschunkallstatus = True
                else:
                    logger.warning('Beam ' + self.beam + ': ' + cn + 'Some continuum chunks were not successfully imaged!')
                    continuumtargetbeamschunkallstatus = False
            else:
                logger.info('Beam ' + self.beam + ': All chunks were already successfully imaged!')

        # Save the derived parameters to the parameter file

        subs_param.add_param(self, beam + '_targetbeams_chunkall_status', continuumtargetbeamschunkallstatus)
        subs_param.add_param(self, beam + '_targetbeams_chunk_status', continuumtargetbeamschunkstatus)
        subs_param.add_param(self, beam + '_targetbeams_chunk_mapstatus', continuumtargetbeamschunkmapstatus)
        subs_param.add_param(self, beam + '_targetbeams_chunk_mapstats', continuumtargetbeamschunkmapstats)
        subs_param.add_param(self, beam + '_targetbeams_chunk_beamstatus', continuumtargetbeamschunkbeamstatus)
        subs_param.add_param(self, beam + '_targetbeams_chunk_maskstatus', continuumtargetbeamschunkmaskstatus)
        subs_param.add_param(self, beam + '_targetbeams_chunk_maskstats', continuumtargetbeamschunkmaskstats)
        subs_param.add_param(self, beam + '_targetbeams_chunk_modelstatus', continuumtargetbeamschunkmodelstatus)
        subs_param.add_param(self, beam + '_targetbeams_chunk_modelstats', continuumtargetbeamschunkmodelstats)
        subs_param.add_param(self, beam + '_targetbeams_chunk_imagestatus', continuumtargetbeamschunkimagestatus)
        subs_param.add_param(self, beam + '_targetbeams_chunk_imagestats', continuumtargetbeamschunkimagestats)
        subs_param.add_param(self, beam + '_targetbeams_chunk_residualstatus', continuumtargetbeamschunkresidualstatus)
        subs_param.add_param(self, beam + '_targetbeams_chunk_residualstats', continuumtargetbeamschunkresidualstats)
        subs_param.add_param(self, beam + '_targetbeams_chunk_maskthreshold', continuumtargetbeamschunkmaskthreshold)
        subs_param.add_param(self, beam + '_targetbeams_chunk_cleanthreshold', continuumtargetbeamschunkcleanthreshold)
        subs_param.add_param(self, beam + '_targetbeams_chunk_thresholdtype', continuumtargetbeamschunkthresholdtype)
        subs_param.add_param(self, beam + '_targetbeams_chunk_final_minorcycle', continuumtargetbeamschunkfinalminor)


    def show(self, showall=False):
        lib.show(self, 'CONTINUUM', showall)


    def summary(self):
        """
        Creates a general summary of the parameters in the parameter file generated during CONTINUUM. No detailed summary
        is available for CONTINUUM up to now.

        returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in the notebook
        """

        # Load the parameters from the parameter file

        nchunks = len(np.asarray(self.continuum_chunkimage_startchannels))

        MI = np.full((self.NBEAMS), False)
        CI = np.full((self.NBEAMS, nchunks), False)

        for b in range(self.NBEAMS):
            subs_setinit.setinitdirs(self)
            subs_setinit.setdatasetnamestomiriad(self)
            beam = 'continuum_B' + str(b).zfill(2)
            try:
                MI[b] = subs_param.get_param_def(self, beam + '_targetbeams_mf_status', False)
            except KeyError:
                MI[b] = False
            try:
                CI[b,:] = subs_param.get_param_def(self, beam + '_targetbeams_chunk_status', False)
            except KeyError:
                CI[b,:] = False

        # Create the data frame

        beam_range = range(self.NBEAMS)
        dataset_beams = [self.target[:-3] + ' Beam ' + str(b).zfill(2) for b in beam_range]
        dataset_indices = dataset_beams

        df = pd.DataFrame(np.ndarray.flatten(MI), index=dataset_indices, columns=['MF image'])
        for chunk in range(nchunks):
            df_chunkimage = pd.DataFrame(np.ndarray.flatten(CI[:,chunk]), index=dataset_indices, columns=['Chunk ' + str(chunk)])
            df = pd.concat([df, df_chunkimage], axis=1)

        return df


    def reset(self, steps='all'):
        """
        Function to reset the current step and remove all generated continuum data for the current beam. Be careful! Deletes all data generated in
        this step!
        """
        subs_managefiles.director(self, 'ch', self.basedir)
        b = self.beam
        beam = 'continuum_B' + str(b).zfill(2)
        if steps == 'all' or steps == 'mf':
            logger.warning('Beam ' + str(b).zfill(2) + ': Deleting all multi-frequency continuum imaging data products.')
            subs_managefiles.director(self, 'rm', self.basedir + str(b).zfill(2) + '/' + self.contsubdir + '/*_mf_*')
            subs_param.del_param(self, beam + '_targetbeams_mf_status')
            subs_param.del_param(self, beam + '_targetbeams_mf_mapstatus')
            subs_param.del_param(self, beam + '_targetbeams_mf_mapstats')
            subs_param.del_param(self, beam + '_targetbeams_mf_beamstatus')
            subs_param.del_param(self, beam + '_targetbeams_mf_maskstatus')
            subs_param.del_param(self, beam + '_targetbeams_mf_maskstats')
            subs_param.del_param(self, beam + '_targetbeams_mf_modelstatus')
            subs_param.del_param(self, beam + '_targetbeams_mf_modelstats')
            subs_param.del_param(self, beam + '_targetbeams_mf_imagestatus')
            subs_param.del_param(self, beam + '_targetbeams_mf_imagestats')
            subs_param.del_param(self, beam + '_targetbeams_mf_residualstatus')
            subs_param.del_param(self, beam + '_targetbeams_mf_residualstats')
            subs_param.del_param(self, beam + '_targetbeams_mf_maskthreshold')
            subs_param.del_param(self, beam + '_targetbeams_mf_cleanthreshold')
            subs_param.del_param(self, beam + '_targetbeams_mf_thresholdtype')
            subs_param.del_param(self, beam + '_targetbeams_mf_final_minorcycle')
        if steps == 'all' or steps == 'chunks':
            logger.warning('Beam ' + str(b).zfill(2) + ': Deleting all chunk continuum imaging data products.')
            subs_managefiles.director(self, 'rm', self.basedir + str(b).zfill(2) + '/' + self.contsubdir + '/*_C*_*')
            subs_param.del_param(self, beam + '_targetbeams_chunkall_status')
            subs_param.del_param(self, beam + '_targetbeams_chunk_status')
            subs_param.del_param(self, beam + '_targetbeams_chunk_mapstatus')
            subs_param.del_param(self, beam + '_targetbeams_chunk_mapstats')
            subs_param.del_param(self, beam + '_targetbeams_chunk_beamstatus')
            subs_param.del_param(self, beam + '_targetbeams_chunk_maskstatus')
            subs_param.del_param(self, beam + '_targetbeams_chunk_maskstats')
            subs_param.del_param(self, beam + '_targetbeams_chunk_modelstatus')
            subs_param.del_param(self, beam + '_targetbeams_chunk_modelstats')
            subs_param.del_param(self, beam + '_targetbeams_chunk_imagestatus')
            subs_param.del_param(self, beam + '_targetbeams_chunk_imagestats')
            subs_param.del_param(self, beam + '_targetbeams_chunk_residualstatus')
            subs_param.del_param(self, beam + '_targetbeams_chunk_residualstats')
            subs_param.del_param(self, beam + '_targetbeams_chunk_maskthreshold')
            subs_param.del_param(self, beam + '_targetbeams_chunk_cleanthreshold')
            subs_param.del_param(self, beam + '_targetbeams_chunk_thresholdtype')
            subs_param.del_param(self, beam + '_targetbeams_chunk_final_minorcycle')


    def reset_all(self, steps='all'):
        """
        Function to reset the current step and remove all generated continuum data for the all beams. Be careful! Deletes all data generated in
        this step!
        """
        subs_managefiles.director(self, 'ch', self.basedir)
        for b in range(self.NBEAMS):
            beam = 'continuum_B' + str(b).zfill(2)
            if os.path.isdir(self.basedir + str(b).zfill(2) + '/' + self.contsubdir):
                if steps == 'all' or steps == 'mf':
                    logger.warning('Beam ' + str(b).zfill(2) + ': Deleting all multi-frequency continuum imaging data products.')
                    subs_managefiles.director(self, 'rm', self.basedir + str(b).zfill(2) + '/' + self.contsubdir + '/*_mf_*')
                    subs_param.del_param(self, beam + '_targetbeams_mf_status')
                    subs_param.del_param(self, beam + '_targetbeams_mf_mapstatus')
                    subs_param.del_param(self, beam + '_targetbeams_mf_mapstats')
                    subs_param.del_param(self, beam + '_targetbeams_mf_beamstatus')
                    subs_param.del_param(self, beam + '_targetbeams_mf_maskstatus')
                    subs_param.del_param(self, beam + '_targetbeams_mf_maskstats')
                    subs_param.del_param(self, beam + '_targetbeams_mf_modelstatus')
                    subs_param.del_param(self, beam + '_targetbeams_mf_modelstats')
                    subs_param.del_param(self, beam + '_targetbeams_mf_imagestatus')
                    subs_param.del_param(self, beam + '_targetbeams_mf_imagestats')
                    subs_param.del_param(self, beam + '_targetbeams_mf_residualstatus')
                    subs_param.del_param(self, beam + '_targetbeams_mf_residualstats')
                    subs_param.del_param(self, beam + '_targetbeams_mf_maskthreshold')
                    subs_param.del_param(self, beam + '_targetbeams_mf_cleanthreshold')
                    subs_param.del_param(self, beam + '_targetbeams_mf_thresholdtype')
                    subs_param.del_param(self, beam + '_targetbeams_mf_final_minorcycle')
                if steps == 'all' or steps == 'chunks':
                    logger.warning('Beam ' + str(b).zfill(2) + ': Deleting all chunk continuum imaging data products.')
                    subs_managefiles.director(self, 'rm', self.basedir + str(b).zfill(2) + '/' + self.contsubdir + '/*_C*_*')
                    subs_param.del_param(self, beam + '_targetbeams_chunkall_status')
                    subs_param.del_param(self, beam + '_targetbeams_chunk_status')
                    subs_param.del_param(self, beam + '_targetbeams_chunk_mapstatus')
                    subs_param.del_param(self, beam + '_targetbeams_chunk_mapstats')
                    subs_param.del_param(self, beam + '_targetbeams_chunk_beamstatus')
                    subs_param.del_param(self, beam + '_targetbeams_chunk_maskstatus')
                    subs_param.del_param(self, beam + '_targetbeams_chunk_maskstats')
                    subs_param.del_param(self, beam + '_targetbeams_chunk_modelstatus')
                    subs_param.del_param(self, beam + '_targetbeams_chunk_modelstats')
                    subs_param.del_param(self, beam + '_targetbeams_chunk_imagestatus')
                    subs_param.del_param(self, beam + '_targetbeams_chunk_imagestats')
                    subs_param.del_param(self, beam + '_targetbeams_chunk_residualstatus')
                    subs_param.del_param(self, beam + '_targetbeams_chunk_residualstats')
                    subs_param.del_param(self, beam + '_targetbeams_chunk_maskthreshold')
                    subs_param.del_param(self, beam + '_targetbeams_chunk_cleanthreshold')
                    subs_param.del_param(self, beam + '_targetbeams_chunk_thresholdtype')
                    subs_param.del_param(self, beam + '_targetbeams_chunk_final_minorcycle')
