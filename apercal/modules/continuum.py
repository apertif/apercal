import logging

import numpy as np
import pandas as pd
import os

from apercal.modules.base import BaseModule
from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles

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

    continuum_mfimage = None
    continuum_mfimage_imsize = None
    continuum_mfimage_cellsize = None
    continuum_mfimage_minorcycle = None
    continuum_mfimage_c1 = None
    continuum_mfimage_drinc = None
    continuum_mfimage_mindr = None
    continuum_mfimage_nsigma = None
    continuum_mf_gaussianity = None

    continuum_chunkimage = None
    continuum_chunkimage_startchannels = None
    continuum_chunkimage_endchannels = None
    continuum_chunkimage_imsize = None
    continuum_chunkimage_cellsize = None
    continuum_chunkimage_minorcycle = None
    continuum_chunkimage_minorcycle_function = None
    continuum_chunkimage_c0 = None
    continuum_chunkimage_c1 = None
    continuum_chunkimage_drinit = None
    continuum_chunkimage_dr0 = None
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
                phasestatus = subs_param.get_param(self, sbeam + '_targetbeams_phase_status')
                ampstatus = subs_param.get_param(self, sbeam + '_targetbeams_amp_status')
                if ampstatus:
                    logger.info('Beam ' + self.beam + ': Using amplitude self-calibrated dataset!')
                    dataset = '../' + self.selfcalsubdir + '/' + self.target.rstrip('.mir') + '_amp.mir'
                    startmf = True
                elif phasestatus:
                    logger.info('Beam ' + self.beam + ': Using phase self-calibrated dataset. Amplitude calibration was not successful or not wanted!')
                    dataset = '../' + self.selfcalsubdir + '/' + self.target
                    startmf = True
                else:
                    logger.error('Beam ' + self.beam + ': Self-calibration was not successful. No continuum imaging possible!')
                    startmf = False
                # Start the multi-frequency continuum imaging
                if startmf:
                    # Calculate the theoretical noise and check Stokes V for gaussianity parameter
                    gaussianity, TN = masking.get_theoretical_noise(self, dataset)
                    if gaussianity:
                        pass
                    else:
                        logger.warning('Beam ' + self.beam + ': Stokes V image shows non-gaussian distribution. Your theoretical noise value might be off!')
                    logger.info('Beam ' + self.beam + ': Theoretical noise is ' + '%.6f' % TN + ' Jy')
                    TNreached = False  # Stop self-calibration if theoretical noise is reached
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
                                        continuumtargetbeamsmsstatus = False
                                        logger.error('Beam ' + self.beam + ': Mask image for cycle ' + str(minc) + ' not found. Stopping continuum imaging!')
                                        stop = True
                                        continuumtargetbeamsmffinalminor = minc
                                        break
                                    mfclean = lib.miriad('mfclean')  # Clean the image down to the calculated threshold
                                    mfclean.map = 'map_mf_00'
                                    mfclean.beam = 'beam_mf_00'
                                    mfclean.out = 'model_mf_00'
                                    mfclean.cutoff = Cc
                                    mfclean.niters = 1000000
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
                                    currdr = dirtystats[1] / residualstats[1]
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
                                        logger.info('Beam ' + self.beam + ': Theoretical noise threshold reaached in cycle ' + str(minc) + '. Stopping iterations and creating final image!')
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
                                            raise ApercalException(msg)
                                            stop = True
                                            continuumtargetbeamsmffinalminor = minc
                                            break
                                    else:
                                        continuumtargetbeamsmfmaskstatus[minc] = False
                                        continuumtargetbeamsmfstatus = False
                                        msg = 'Beam ' + self.beam + ': Mask image for cycle ' + str(minc) + ' not found. Stopping continuum imaging!'
                                        logger.error(msg)
                                        raise ApercalException(msg)
                                        stop = True
                                        continuumtargetbeamsmffinalminor = minc
                                        break
                                    mfclean = lib.miriad('mfclean')  # Clean the image down to the calculated threshold
                                    mfclean.map = 'map_mf_00'
                                    mfclean.beam = 'beam_mf_00'
                                    mfclean.model = 'model_mf_' + str(minc - 1).zfill(2)
                                    mfclean.out = 'model_mf_' + str(minc).zfill(2)
                                    mfclean.cutoff = Cc
                                    mfclean.niters = 1000000
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
                                            raise ApercalException(msg)
                                            stop = True
                                            continuumtargetbeamsmffinalminor = minc
                                            break
                                    else:
                                        continuumtargetbeamsmfmodelstatus[minc] = False
                                        continuumtargetbeamsmfstatus = False
                                        msg = 'Beam ' + self.beam + ': Clean component image for cycle ' + str(minc) + ' not found. Stopping continuum imaging!'
                                        logger.error(msg)
                                        raise ApercalException(msg)
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
                                        continuumtargetbeamsmfimagestats[minc, :] = imstats.getimagestats(self, 'image_mf_00')
                                        if qa.checkrestoredimage(self, 'image_mf_' + str(minc).zfill(2)):
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
                                    restor.out = 'residual_mf_' + str(minc).zfill(2)
                                    restor.go()
                                    residualstats = imstats.getimagestats(self, 'residual_mf_' + str(minc).zfill(2))  # Min, max, rms of the residual image
                                    continuumtargetbeamsmfresidualstats[minc, :] = residualstats
                                    currdr = dirtystats[1] / residualstats[1]
                                    logger.info('Beam ' + self.beam + ': Dynamic range is ' + '%.3f' % currdr + ' for cycle ' + str(minc))
                            else:
                                break
                        else:
                            break
                else:
                    continuumtargetbeamsmfstatus = False
                # Final checks if continuum mf imaging was successful
                if TNreached:
                    if qa.checkimagegaussianity(self, 'residual_mf_' + str(continuumtargetbeamsmffinalminor).zfill(2), self.continuum_mf_gaussianity):
                        continuumtargetbeamsmfresidualstatus = True
                        continuumtargetbeamsmfstatus = True
                        logger.info('Beam ' + self.beam + ': Multi-frequency continuum imaging successfully done!')
                    else:
                        continuumtargetbeamsmfresidualstatus = False
                        continuumtargetbeamsmfstatus = False
                        logger.warning('Beam ' + self.beam + ': Final residual image shows non-gaussian statistics. Multi-frequency continuum imaging was not successful!')
                elif minc == continuumtargetbeamsmffinalminor:
                    logger.warning('Beam ' + self.beam + ': Multi-frequency continuum imaging did not reach theoretical noise!')
                    if qa.checkimagegaussianity(self, 'residual_mf_' + str(continuumtargetbeamsmffinalminor).zfill(2), self.continuum_mf_gaussianity):
                        self.logger.warning('Beam ' + self.beam + ': Residual image seems to show Gaussian statistics. Maybe cleaning was deep enough!')
                        continuumtargetbeamsmfresidualstatus = True
                        continuumtargetbeamsmfstatus = True
                        logger.info('Beam ' + self.beam + ': Multi-frequency continuum imaging successfully done!')
                    else:
                        continuumtargetbeamsmfresidualstatus = False
                        continuumtargetbeamsmfstatus = False
                        logger.warning('Beam ' + self.beam + ': Final residual image shows non-gaussian statistics. Multi-frequency continuum imaging was not successful!')
                else:
                    continuumtargetbeamsmfstatus = False
                    logger.warning('Beam ' + self.beam + ': Something lese happened and I dont know what')
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

        if self.continuum_chunkimage:
            logger.warning('Beam ' + self.beam + ': Individual chunk imaging not implemented yet!')


    def show(self, showall=False):
        lib.show(self, 'SELFCAL', showall)


    def summary(self):
        """
        Creates a general summary of the parameters in the parameter file generated during SELFCAL. No detailed summary
        is available for SELFCAL up to now.

        returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in the notebook
        """

        # Load the parameters from the parameter file

        MI = np.full((self.NBEAMS), False)

        for b in range(self.NBEAMS):
            subs_setinit.setinitdirs(self)
            subs_setinit.setdatasetnamestomiriad(self)
            beam = 'continuum_B' + str(b).zfill(2)
            try:
                MI[b] = subs_param.get_param(self, beam + '_targetbeams_mf_status')
            except KeyError:
                MI[b] = False

        # Create the data frame

        beam_range = range(self.NBEAMS)
        dataset_beams = [self.target[:-3] + ' Beam ' + str(b).zfill(2) for b in beam_range]
        dataset_indices = dataset_beams

        df_mfimage = pd.DataFrame(np.ndarray.flatten(MI), index=dataset_indices, columns=['MF image'])

        df = pd.concat([df_mfimage], axis=1)

        return df


    def reset(self):
        """
        Function to reset the current step and remove all generated selfcal data for the current beam. Be careful! Deletes all data generated in
        this step!
        """
        subs_managefiles.director(self, 'ch', self.basedir)
        b = self.beam
        beam = 'continuum_B' + str(b).zfill(2)
        logger.warning('Beam ' + str(b).zfill(2) + ': Deleting all continuum imaging data products.')
        subs_managefiles.director(self, 'rm', self.basedir + str(b).zfill(2) + '/' + self.contsubdir)
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


    def reset_all(self):
        """
        Function to reset the current step and remove all generated selfcal data for the all beams. Be careful! Deletes all data generated in
        this step!
        """
        subs_managefiles.director(self, 'ch', self.basedir)
        for b in range(self.NBEAMS):
            beam = 'continuum_B' + str(b).zfill(2)
            if os.path.isdir(self.basedir + str(b).zfill(2) + '/' + self.contsubdir):
                logger.warning('Beam ' + str(b).zfill(2) + ': Deleting all continuum imaging data products.')
                subs_managefiles.director(self, 'rm', self.basedir + str(b).zfill(2) + '/' + self.contsubdir)
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


    # def image_continuum(self):
    #     """
    #     Create a deep continuum image by producing a deep image of each frequency chunk and stacking. Self-calibration
    #     ains are always applied before imaging.
    #     """
    #     subs_setinit.setinitdirs(self)
    #     subs_setinit.setdatasetnamestomiriad(self)
    #     logger.info(' Starting deep continuum imaging of full dataset')
    #     subs_managefiles.director(self, 'ch', self.contdir)
    #
    #     logger.debug(' Creating individual deep images from frequency chunks')
    #     subs_managefiles.director(self, 'ch', self.contdir + '/stack')
    #
    #     nchunks = len(self.list_chunks())
    #
    #     beam = 'continuum_B' + str(self.beam).zfill(2)
    #
    #     # Number of the last executed minor iterations during imaging
    #     continuumminiters = get_param_def(self, beam + '_minoriterations', np.full(nchunks, np.nan))
    #
    #     # Stats of the created continuum images (minimum, maximum, standard deviation)
    #     continuumimagestats = get_param_def(self, beam + '_imagestats',
    #                                         np.full((nchunks, self.continuum_minorcycle, 3), np.nan))
    #
    #     # Stats of the created continuum residual images (minimum, maximum, standard deviation)
    #     continuumresidualstats = get_param_def(self, beam + '_residualstats',
    #                                            np.full((nchunks, self.continuum_minorcycle, 3), np.nan))
    #
    #     # Status if imaging completed successfully
    #     continuumstatus = get_param_def(self, beam + '_status', np.full(nchunks, False))
    #
    #     # Was the final image for each iteration created successfully?
    #     continuumimagestatus = get_param_def(self, beam + '_imagestatus',
    #                                          np.full((nchunks, self.continuum_minorcycle), False))
    #
    #     # Was the mask for each iteration created successfully?
    #     continuummaskstatus = get_param_def(self, beam + '_maskstatus',
    #                                         np.full((nchunks, self.continuum_minorcycle), False))
    #
    #     # Was the model for each iteration created successfully?
    #     continuummodelstatus = get_param_def(self, beam + '_modelstatus',
    #                                          np.full((nchunks, self.continuum_minorcycle), False))
    #
    #     # Was the residual image for each iteration created successfully?
    #     continuumresidualstatus = get_param_def(self, beam + '_residualstatus',
    #                                             np.full((nchunks, self.continuum_minorcycle), False))
    #
    #     # Threshold type for each individual cycle and chunk
    #     continuumthresholdtype = get_param_def(self, beam + '_thresholdtype',
    #                                            np.full((nchunks, self.continuum_minorcycle), ''))
    #
    #     # Masking threshold for each individual cycle and chunk
    #     continuummasklimit = get_param_def(self, beam + '_masklimit', np.full((nchunks,
    #                                                                            self.continuum_minorcycle), np.nan))
    #
    #     # Cleaning threshold for each individual cycle and chunk
    #     continuumcleanlimit = get_param_def(self, beam + '_cleanlimit', np.full((nchunks,
    #                                                                              self.continuum_minorcycle), np.nan))
    #
    #     # Cleaning threshold for each individual cycle and chunk
    #     continuumsynthbeamparams = get_param_def(self, beam + '_synthbeamparams', np.full((nchunks, 3), np.nan))
    #
    #     # Is the final image accepted for stacking
    #     continuumchunkimageacceptforstacking = get_param_def(self, beam + '_stackstatus', np.full(nchunks, False))
    #
    #     # Reason for rejecting an image
    #     continuumchunkstackrejreason = get_param_def(self, beam + '_stackrejreason',
    #                                                  np.full(nchunks, '', dtype='U50'))
    #
    #     # RMS of the final chunk images
    #     continuumimcombrms = get_param_def(self, beam + '_imcombrms', np.full(nchunks, np.nan))
    #
    #     # Weighting of the final chunk images (normalised)
    #     continuumimcombweights = get_param_def(self, beam + '_imcombweights', np.full(nchunks, np.nan))
    #
    #     # Is the final image accepted for stacking
    #     continuumstackedimagestatus = get_param_def(self, beam + '_stackedimagestatus', False)
    #
    #     ####################################
    #     # Imaging of each individual chunk #
    #     ####################################
    #
    #     for chunk in self.list_chunks():  # Produce a final image for each chunk doing an additional cleaning run
    #         logger.info(' Continuum imaging for chunk ' + chunk + ' started')
    #         majc = int(self.get_last_major_iteration(chunk))
    #         logger.debug('Last major self-calibration cycle seems to have been ' + str(majc) + ' #')
    #         # Check if a chunk could be calibrated and has data left
    #         if os.path.isfile(self.selfcaldir + '/' + chunk + '/' + chunk + '.mir/gains'):
    #             subs_managefiles.director(self, 'ch', self.contdir + '/stack/' + chunk)
    #             # Check if the chunk was already imaged
    #             if os.path.isdir(
    #                     self.contdir + '/stack/' + chunk + '/' + 'image_' + str(self.continuum_minorcycle - 1).zfill(
    #                             2)):
    #                 logger.info('Frequency chunk ' + chunk + ' has already been imaged! #')
    #             else:
    #
    #                 #######################
    #                 # Final deep cleaning #
    #                 #######################
    #
    #                 theoretical_noise = calc_theoretical_noise(
    #                     self.selfcaldir + '/' + chunk + '/' + chunk + '.mir')
    #                 logger.debug(
    #                     'Theoretical noise for chunk ' + chunk + ' is ' + str(theoretical_noise) + ' Jy/beam #')
    #                 theoretical_noise_threshold = calc_theoretical_noise_threshold(theoretical_noise,
    #                                                                                self.continuum_nsigma)
    #                 logger.debug('Your theoretical noise threshold will be ' + str(
    #                     self.continuum_nsigma) + ' times the theoretical noise corresponding to ' + str(
    #                     theoretical_noise_threshold) + ' Jy/beam #')
    #                 dr_list = calc_dr_maj(self.continuum_drinit, self.continuum_dr0, majc + 2,
    #                                       self.continuum_majorcycle_function)
    #                 logger.debug('Dynamic range limits for the selfcal major iterations were ' + str(dr_list) + ' #')
    #                 dr_minlist = self.calc_dr_min(dr_list, majc + 1, self.continuum_minorcycle,
    #                                               self.continuum_minorcycle_function)
    #                 logger.debug('Dynamic range limits for the continuum minor iterations to clean are ' + str(
    #                     dr_minlist) + ' #')
    #
    #                 #####################################
    #                 # Run the cleaning minor iterations #
    #                 #####################################
    #
    #                 cont = True  # Set the cycle continuation trigger to True (changes to False if something goes wrong)
    #                 for minc in range(self.continuum_minorcycle):
    #                     if cont:
    #
    #                         #########################
    #                         # The first minor cycle #
    #                         #########################
    #
    #                         if minc == 0:
    #
    #                             # Create the dirty image
    #                             if os.path.isdir('map_00') and os.path.isdir('beam_00'):
    #                                 logger.debug('Data for chunk ' + str(chunk) + ' has already been inverted #')
    #                                 # Calculate the image stats for later usage
    #                                 mapmin, mapmax, mapstd = subs_imstats.getimagestats(self, 'map_00')
    #                             else:
    #                                 invert = lib.miriad('invert')
    #                                 invert.vis = self.selfcaldir + '/' + chunk + '/' + chunk + '.mir'
    #                                 invert.map = 'map_00'
    #                                 invert.beam = 'beam_00'
    #                                 invert.imsize = self.continuum_image_imsize
    #                                 invert.cell = self.continuum_image_cellsize
    #                                 invert.stokes = 'ii'
    #                                 invert.slop = 1
    #                                 if self.continuum_image_robust == '':
    #                                     invert.robust = -1
    #                                 else:
    #                                     invert.robust = self.continuum_image_robust
    #                                 if self.continuum_image_centre != '':  # Use the image centre given in the cfg file
    #                                     invert.offset = self.continuum_image_centre
    #                                     invert.options = 'mfs,double,mosaic'
    #                                 else:
    #                                     if os.path.isdir(
    #                                             self.basedir + '00' + '/' + self.selfcalsubdir + '/' + self.target):
    #                                         invert.offset = subs_readmirhead.getradecsex(
    #                                             self.basedir + '00' + '/' + self.selfcalsubdir + '/' + self.target)
    #                                         invert.options = 'mfs,double,mosaic'
    #                                         logger.debug(
    #                                             'Using pointing centre of beam 00 for gridding of all beams! #')
    #                                     else:
    #                                         # Use the image centre of the individual beams for gridding (not recommended)
    #                                         invert.options = 'mfs,double,sdb'
    #                                         logger.warning('Using pointing centres of individual beams for gridding. '
    #                                                        'Not recommended for mosaicking!')
    #                                 invert.go()
    #                                 if os.path.isdir('map_00') and os.path.isdir(
    #                                         'beam_00'):  # Check if the image and beam are there
    #                                     mapmin, mapmax, mapstd = subs_imstats.getimagestats(self, 'map_00')
    #                                     if mapmax >= mapmin and mapstd != np.nan:  # Check if the dirty image is valid
    #                                         pass
    #                                     else:  # if not exit the imaging loop
    #                                         logger.error(' Dirty image for chunk ' + str(
    #                                             chunk) + ' was not created successfully!')
    #                                         cont = False
    #                                         break
    #                                 else:  # if not exit the imaging loop
    #                                     logger.error(' Dirty image and beam for chunk ' + str(
    #                                         chunk) + ' were not created successfully!')
    #                                     cont = False
    #                                     break
    #
    #                             # Copy the mask from the last selfcal loop and regrid to the common grid
    #                             if os.path.isdir('mask_00'):  # Has the mask already been copied
    #                                 continuummaskstatus[int(chunk), minc] = True
    #                                 logger.debug('Mask for chunk ' + str(
    #                                     chunk) + ' has already been copied from selfcal and regridded #')
    #                             else:  # if not look for it
    #                                 path = self.selfcaldir + '/' + chunk + '/' + str(majc).zfill(2) + '/mask_' + str(
    #                                                 self.get_last_minor_iteration(chunk, self.get_last_major_iteration(
    #                                                         chunk))).zfill(2)
    #                                 if os.path.isdir(path):  # Find the last created mask
    #                                     subs_managefiles.director(self, 'cp', 'mask_00', file_=path)
    #                                     logger.debug('Mask from last selfcal loop found! #')
    #                                 else:  # If it is not there leave the loop for this chunk
    #                                     continuummaskstatus[int(chunk), minc] = False
    #                                     logger.error('Mask from last selfcal loop not found! #')
    #                                     cont = False
    #                                     break
    #                                 regrid = lib.miriad('regrid')
    #                                 regrid.in_ = 'mask_00'
    #                                 regrid.out = 'mask_regrid'
    #                                 regrid.tin = 'map_00'
    #                                 regrid.axes = '1,2'
    #                                 regrid.go()
    #                                 subs_managefiles.director(self, 'rm', 'mask_00')
    #                                 subs_managefiles.director(self, 'rn', 'mask_00', file_='mask_regrid')
    #                                 logger.debug('Mask from last selfcal cycle copied and regridded to common grid #')
    #                                 if os.path.isdir('mask_00'):
    #                                     maskmin, maskmax, maskstd = subs_imstats.getimagestats(self, 'mask_00')
    #                                     if maskstd != np.nan:  # Check if the mask is not empty
    #                                         continuummaskstatus[int(chunk), minc] = True
    #                                     else:  # if not exit the imaging loop
    #                                         continuummaskstatus[int(chunk), minc] = False
    #                                         logger.error(
    #                                             ' Mask for chunk ' + str(chunk) + ' was not created successfully!')
    #                                         cont = False
    #                                         break
    #                                 else:  # if not exit the imaging loop
    #                                     continuummaskstatus[int(chunk), minc] = False
    #                                     logger.error(' Mask for chunk ' + str(chunk) + ' was not created successfully!')
    #                                     cont = False
    #                                     break
    #
    #                             # Now calculate the thresholds for the first minor cycles
    #                             noise_threshold = calc_noise_threshold(mapmax, minc, majc + 1, self.continuum_c0)
    #                             dynamic_range_threshold = calc_dynamic_range_threshold(mapmax, dr_minlist[minc],
    #                                                                                    self.continuum_minorcycle0_dr)
    #                             mask_threshold, mask_threshold_type = calc_mask_threshold(
    #                                 theoretical_noise_threshold, noise_threshold, dynamic_range_threshold)
    #                             logger.debug('Mask threshold for final minor cycle ' + str(minc) + ' set to ' + str(
    #                                 mask_threshold) + ' Jy/beam #')
    #                             logger.debug('Mask threshold set by ' + str(mask_threshold_type) + ' #')
    #                             continuumthresholdtype[int(chunk), minc] = str(mask_threshold_type)
    #                             continuummasklimit[int(chunk), minc] = mask_threshold
    #                             clean_cutoff = calc_clean_cutoff(mask_threshold, self.continuum_c1)
    #                             continuumcleanlimit[int(chunk), minc] = clean_cutoff
    #                             logger.debug('Clean threshold for minor cycle ' + str(minc) + ' was set to ' + str(
    #                                 clean_cutoff) + ' Jy/beam #')
    #
    #                             # Clean the dirty image down to the calculated threshold
    #                             if os.path.isdir('model_00'):  # Has the clean model already been created
    #                                 continuummodelstatus[int(chunk), minc] = True
    #                                 logger.debug('Clean model for first minor iteration of chunk ' + str(
    #                                     chunk) + ' has already been created #')
    #                             else:  # if not create it
    #                                 clean = lib.miriad('clean')  # Clean the image down to the calculated threshold
    #                                 clean.map = 'map_00'
    #                                 clean.beam = 'beam_00'
    #                                 clean.out = 'model_00'
    #                                 clean.cutoff = clean_cutoff
    #                                 clean.niters = 100000
    #                                 clean.region = '"' + 'mask(mask_' + str(minc).zfill(2) + ')' + '"'
    #                                 clean.go()
    #                                 if os.path.isdir('model_00'):  # Check if it was created successfully
    #                                     modmin, modmax, modstd = subs_imstats.getimagestats(self, 'model_00')
    #                                     # Check if the clean model is valid
    #                                     if modstd != np.nan and modmax <= 10000 and modmin >= -10:
    #                                         continuummodelstatus[int(chunk), minc] = True
    #                                     else:  # if not exit the imaging loop
    #                                         continuummodelstatus[int(chunk), minc] = False
    #                                         logger.error(' Model for first minor iteration for chunk ' + str(
    #                                             chunk) + ' is empty or shows extreme values!')
    #                                         cont = False
    #                                         break
    #                                 else:  # if not exit the imaging loop
    #                                     continuummodelstatus[int(chunk), minc] = False
    #                                     logger.error(' Clean model for first minor iteration of chunk ' + str(
    #                                         chunk) + ' was not created successfully!')
    #                                     cont = False
    #                                     break
    #                                 logger.debug('Clean model for first minor iteration of chunk ' + str(
    #                                     chunk) + ' was created successfully! #')
    #
    #                             # Now create the restored image
    #                             if os.path.isdir('image_00'):  # Check if the restored image was already created
    #                                 continuumimagestatus[int(chunk), minc] = True
    #                                 logger.debug('Restored image for first minor iteration of chunk ' + str(
    #                                     chunk) + ' has already been created #')
    #                             else:  # if not create it
    #                                 restor = lib.miriad('restor')
    #                                 restor.model = 'model_00'
    #                                 restor.beam = 'beam_00'
    #                                 restor.map = 'map_00'
    #                                 restor.out = 'image_00'
    #                                 restor.mode = 'clean'
    #                                 restor.go()
    #                                 if os.path.isdir('image_00'):  # Check if it was created successfully
    #                                     immin, immax, imstd = subs_imstats.getimagestats(self, 'image_00')
    #                                     continuumimagestats[int(chunk), minc, :] = np.array([immin, immax, imstd])
    #                                     # Check if the image is valid
    #                                     if imstd != np.nan and immax <= 10000 and immin >= -10:
    #                                         continuumimagestatus[int(chunk), minc] = True
    #                                     else:  # if not exit the imaging loop
    #                                         continuumimagestatus[int(chunk), minc] = False
    #                                         logger.error(' Restored image of first minor iteration for chunk ' + str(
    #                                             chunk) + ' is empty or shows extreme values!')
    #                                         cont = False
    #                                         break
    #                                 else:  # if not exit the imaging loop
    #                                     continuumimagestatus[int(chunk), minc] = False
    #                                     logger.error(' Restored image of first minor iteration for chunk ' + str(
    #                                         chunk) + ' was not created successfully!')
    #                                     continuumimagestats[int(chunk), minc, :] = np.array([np.nan, np.nan, np.nan])
    #                                     cont = False
    #                                     break
    #                                 logger.debug('Restored image for first minor iteration of chunk ' + str(
    #                                     chunk) + ' was created successfully! #')
    #
    #                             # Now create the residual image
    #                             if os.path.isdir('residual_00'):  # Check if the restored image was already created
    #                                 continuumresidualstatus[int(chunk), minc] = True
    #                                 logger.debug('Residual image for first minor iteration of chunk ' + str(
    #                                     chunk) + ' has already been created #')
    #                             else:  # if not create it
    #                                 restor = lib.miriad('restor')
    #                                 restor.model = 'model_00'
    #                                 restor.beam = 'beam_00'
    #                                 restor.map = 'map_00'
    #                                 restor.out = 'residual_00'
    #                                 restor.mode = 'residual'
    #                                 restor.go()
    #                                 if os.path.isdir('residual_00'):  # Check if it was created successfully
    #                                     resimin, resimax, resistd = subs_imstats.getimagestats(self, 'residual_00')
    #                                     continuumresidualstats[int(chunk), minc, :] = np.array(
    #                                         [resimin, resimax, resistd])
    #                                     # Check if the image is valid
    #                                     if resistd != np.nan and resimax <= 10000 and resimin >= -10:
    #                                         continuumresidualstatus[int(chunk), minc] = True
    #                                     else:  # if not exit the imaging loop
    #                                         continuumresidualstatus[int(chunk), minc] = False
    #                                         logger.error(' Residual image of first minor iteration for chunk ' + str(
    #                                             chunk) + ' is empty or shows extreme values!')
    #                                         cont = False
    #                                         break
    #                                 else:  # if not exit the imaging loop
    #                                     continuumresidualstatus[int(chunk), minc] = False
    #                                     logger.error(' Residual image of first minor iteration for chunk ' + str(
    #                                         chunk) + ' was not created successfully!')
    #                                     continuumresidualstats[int(chunk), minc, :] = np.array([np.nan, np.nan, np.nan])
    #                                     cont = False
    #                                     break
    #                                 logger.debug('Residual image for first minor iteration of chunk ' + str(
    #                                     chunk) + ' was created successfully! #')
    #                             logger.debug('Peak of the residual image for first minor iteration is ' + str(
    #                                 resimax) + ' Jy/beam #')
    #                             logger.debug('RMS of the residual image for first minor iteration is ' + str(
    #                                 resistd) + ' Jy/beam #')
    #                             continuumminiters[int(chunk)] = 0
    #
    #                         ####################################
    #                         # All minor cycles after the first #
    #                         ####################################
    #
    #                         else:
    #                             # Now calculate the thresholds for the current minor cycle
    #                             if os.path.isdir('map_00'):  # Check if the dirty map is there
    #                                 # Calculate the image stats for later usage
    #                                 mapmin, mapmax, mapstd = subs_imstats.getimagestats(self, 'map_00')
    #                                 if mapmax >= mapmin and mapstd != np.nan:  # Check if the dirty image is valid
    #                                     pass
    #                                 else:  # if not exit the imaging loop
    #                                     logger.error(' Dirty map for chunk ' + str(
    #                                         chunk) + ' shows extreme values! Cannot calculate thresholds!')
    #                                     cont = False
    #                                     break
    #                             else:  # if not exit the imaging loop
    #                                 logger.error(' No dirty map for chunk ' + str(chunk) + ' available!')
    #                                 cont = False
    #                                 break
    #                             noise_threshold = calc_noise_threshold(mapmax, minc, majc + 1, self.continuum_c0)
    #                             dynamic_range_threshold = calc_dynamic_range_threshold(mapmax, dr_minlist[minc],
    #                                                                                    self.continuum_minorcycle0_dr)
    #                             mask_threshold, mask_threshold_type = calc_mask_threshold(
    #                                 theoretical_noise_threshold, noise_threshold, dynamic_range_threshold)
    #                             logger.debug('Mask threshold for final minor cycle ' + str(minc) + ' set to ' + str(
    #                                 mask_threshold) + ' Jy/beam #')
    #                             continuumthresholdtype[int(chunk), minc] = str(mask_threshold_type)
    #                             continuummasklimit[int(chunk), minc] = mask_threshold
    #                             clean_cutoff = calc_clean_cutoff(mask_threshold, self.continuum_c1)
    #                             continuumcleanlimit[int(chunk), minc] = clean_cutoff
    #                             logger.debug('Clean threshold for minor cycle ' + str(minc) + ' was set to ' + str(
    #                                 clean_cutoff) + ' Jy/beam #')
    #
    #                             # Calculate the mask
    #                             if os.path.isdir('mask_' + str(minc).zfill(2)):  # Check if the mask is already there
    #                                 continuummaskstatus[int(chunk), minc] = True
    #                                 logger.debug('Mask for minor iteration ' + str(minc).zfill(2) + ' of chunk ' + str(
    #                                     chunk) + ' is already available #')
    #                             else:  # Create the mask
    #                                 maths = lib.miriad('maths')
    #                                 maths.out = 'mask_' + str(minc).zfill(2)
    #                                 maths.exp = '"<' + 'image_' + str(minc - 1).zfill(2) + '>"'
    #                                 maths.mask = '"<' + 'image_' + str(minc - 1).zfill(2) + '>.gt.' + str(
    #                                     mask_threshold) + '"'
    #                                 maths.go()
    #                                 if os.path.isdir(
    #                                         'mask_' + str(minc).zfill(2)):  # Check if the mask was created successfully
    #                                     maskmin, maskmax, maskstd = subs_imstats.getimagestats(self, 'mask_' + str(
    #                                         minc).zfill(2))  # Calculate the mask stats for viability
    #                                     if maskstd != np.nan:  # Check if mask is not empty
    #                                         continuummaskstatus[int(chunk), minc] = True
    #                                     else:  # If not stop the imaging
    #                                         continuummaskstatus[int(chunk), minc] = False
    #                                         logger.error(
    #                                             ' Mask for minor iteration ' + str(minc).zfill(2) + ' for chunk ' + str(
    #                                                 chunk) + ' is empty or shows extreme values!')
    #                                         cont = False
    #                                         break
    #                                 else:
    #                                     continuummaskstatus[int(chunk), minc] = False
    #                                     logger.error(
    #                                         ' Mask for minor iteration ' + str(minc).zfill(2) + ' for chunk ' + str(
    #                                             chunk) + ' was not created successfully!')
    #                                     cont = False
    #                                     break
    #                                 logger.debug('Mask with threshold ' + str(mask_threshold) + ' Jy/beam created #')
    #
    #                             # Clean the image with the new mask using the model from the previous iteration
    #
    #                             # Has the clean model already been created
    #                             if os.path.isdir('model_' + str(minc).zfill(2)):
    #                                 continuummodelstatus[int(chunk), minc] = True
    #                                 logger.debug(
    #                                     'Clean model for minor iteration ' + str(minc).zfill(2) + ' of chunk ' + str(
    #                                         chunk) + ' has already been created #')
    #                             else:  # if not create it
    #                                 clean = lib.miriad('clean')  # Clean the image down to the calculated threshold
    #                                 clean.map = 'map_' + str(0).zfill(2)
    #                                 clean.beam = 'beam_' + str(0).zfill(2)
    #                                 clean.model = 'model_' + str(minc - 1).zfill(2)
    #                                 clean.out = 'model_' + str(minc).zfill(2)
    #                                 clean.cutoff = clean_cutoff
    #                                 clean.niters = 100000
    #                                 clean.region = '"' + 'mask(' + 'mask_' + str(minc).zfill(2) + ')' + '"'
    #                                 clean.go()
    #                                 if os.path.isdir(
    #                                         'model_' + str(minc).zfill(2)):  # Check if it was created successfully
    #                                     modmin, modmax, modstd = subs_imstats.getimagestats(self,
    #                                                                                         'model_' + str(minc).zfill(
    #                                                                                             2))
    #                                     # Check if the clean model is valid
    #                                     if modstd != np.nan and modmax <= 10000 and modmin >= -10:
    #                                         continuummodelstatus[int(chunk), minc] = True
    #                                     else:  # if not exit the imaging loop
    #                                         continuummodelstatus[int(chunk), minc] = False
    #                                         logger.error(' Clean model for minor iteration ' + str(minc).zfill(
    #                                             2) + ' for chunk ' + str(chunk) + ' is empty or shows extreme values!')
    #                                         cont = False
    #                                         break
    #                                 else:  # if not exit the imaging loop
    #                                     continuummodelstatus[int(chunk), minc] = False
    #                                     logger.error(' Clean model for minor iteration ' + str(minc).zfill(
    #                                         2) + ' of chunk ' + str(chunk) + ' was not created successfully!')
    #                                     cont = False
    #                                     break
    #                                 logger.debug(
    #                                     'Clean model for minor iteration ' + str(minc).zfill(2) + ' of chunk ' + str(
    #                                         chunk) + ' was created successfully! #')
    #
    #                                 # Now create the restored image
    #                                 if os.path.isdir('image_' + str(minc).zfill(
    #                                         2)):  # Check if the restored image was already created
    #                                     continuumimagestatus[int(chunk), minc] = True
    #                                     logger.debug('Restored image for minor iteration ' + str(minc).zfill(
    #                                         2) + ' of chunk ' + str(chunk) + ' has already been created #')
    #                                 else:  # if not create it
    #                                     restor = lib.miriad('restor')
    #                                     restor.model = 'model_' + str(minc).zfill(2)
    #                                     restor.beam = 'beam_' + str(0).zfill(2)
    #                                     restor.map = 'map_' + str(0).zfill(2)
    #                                     restor.out = 'image_' + str(minc).zfill(2)
    #                                     restor.mode = 'clean'
    #                                     restor.go()
    #                                     if os.path.isdir(
    #                                             'image_' + str(minc).zfill(2)):  # Check if it was created successfully
    #                                         immin, immax, imstd = subs_imstats.getimagestats(self,
    #                                                                                          'image_' + str(minc).zfill(
    #                                                                                              2))
    #                                         continuumimagestats[int(chunk), minc, :] = np.array([immin, immax, imstd])
    #                                         # Check if the image is valid
    #                                         if imstd != np.nan and immax <= 10000 and immin >= -10:
    #                                             continuumimagestatus[int(chunk), minc] = True
    #                                         else:  # if not exit the imaging loop
    #                                             continuumimagestatus[int(chunk), minc] = False
    #                                             logger.error(' Restored image of minor iteration ' + str(minc).zfill(
    #                                                 2) + ' for chunk ' + str(
    #                                                 chunk) + ' is empty or shows extreme values!')
    #                                             cont = False
    #                                             break
    #                                     else:  # if not exit the imaging loop
    #                                         continuumimagestatus[int(chunk), minc] = False
    #                                         logger.error(' Restored image of minor iteration ' + str(minc).zfill(
    #                                             2) + ' for chunk ' + str(chunk) + ' was not created successfully!')
    #                                         continuumimagestats[int(chunk), minc, :] = np.array(
    #                                             [np.nan, np.nan, np.nan])
    #                                         cont = False
    #                                         break
    #                                     logger.debug('Restored image for minor iteration ' + str(minc).zfill(
    #                                         2) + ' of chunk ' + str(chunk) + ' was created successfully! #')
    #
    #                                 # Now create the residual image
    #                                 if os.path.isdir('residual_' + str(minc).zfill(
    #                                         2)):  # Check if the restored image was already created
    #                                     continuumresidualstatus[int(chunk), minc] = True
    #                                     logger.debug('Residual image for minor iteration ' + str(minc).zfill(
    #                                         2) + ' of chunk ' + str(chunk) + ' has already been created #')
    #                                 else:  # if not create it
    #                                     restor = lib.miriad('restor')
    #                                     restor.model = 'model_' + str(minc).zfill(2)
    #                                     restor.beam = 'beam_' + str(0).zfill(2)
    #                                     restor.map = 'map_' + str(0).zfill(2)
    #                                     restor.out = 'residual_' + str(minc).zfill(2)
    #                                     restor.mode = 'residual'
    #                                     restor.go()
    #                                     if os.path.isdir('residual_' + str(minc).zfill(
    #                                             2)):  # Check if it was created successfully
    #                                         resimin, resimax, resistd = subs_imstats.getimagestats(self,
    #                                                                                                'residual_' + str(
    #                                                                                                    minc).zfill(2))
    #                                         continuumresidualstats[int(chunk), minc, :] = np.array(
    #                                             [resimin, resimax, resistd])
    #                                         # Check if the image is valid
    #                                         if resistd != np.nan and resimax <= 10000 and resimin >= -10:
    #                                             continuumresidualstatus[int(chunk), minc] = True
    #                                         else:  # if not exit the imaging loop
    #                                             continuumresidualstatus[int(chunk), minc] = False
    #                                             logger.error(' Residual image for minor iteration ' + str(minc).zfill(
    #                                                 2) + ' of chunk ' + str(
    #                                                 chunk) + ' is empty or shows extreme values!')
    #                                             cont = False
    #                                             break
    #                                     else:  # if not exit the imaging loop
    #                                         continuumresidualstatus[int(chunk), minc] = False
    #                                         logger.error(' Residual image for minor iteration ' + str(minc).zfill(
    #                                             2) + ' of chunk ' + str(chunk) + ' was not created successfully!')
    #                                         continuumresidualstats[int(chunk), minc, :] = np.array(
    #                                             [np.nan, np.nan, np.nan])
    #                                         cont = False
    #                                         break
    #                                     logger.debug('Residual image for minor iteration ' + str(minc).zfill(
    #                                         2) + ' of chunk ' + str(chunk) + ' was created successfully! #')
    #                                 logger.debug('Peak of the residual image for minor iteration ' + str(minc).zfill(
    #                                     2) + ' is ' + str(resimax) + ' Jy/beam #')
    #                                 logger.debug('RMS of the residual image for minor iteration ' + str(minc).zfill(
    #                                     2) + ' is ' + str(resistd) + ' Jy/beam #')
    #                                 continuumminiters[int(chunk)] = minc
    #
    #                     #######################################
    #                     # Imaging did not finish successfully #
    #                     #######################################
    #
    #                     else:
    #                         continuumstatus[int(chunk)] = False
    #
    #                 # Create a list of files and check if all of them are there
    #                 filelist = ['map_00', 'beam_00']
    #                 iterlist = [str(iter_) for iter_ in range(self.continuum_minorcycle)]
    #                 for map_ in ['image_', 'mask_', 'model_', 'residual_']:
    #                     for n in iterlist:
    #                         filelist.append(map_ + n.zfill(2))
    #                 for f in filelist:
    #                     if os.path.isdir(self.contdir + '/stack/' + chunk + '/' + f):
    #                         continuumstatus[int(chunk)] = True
    #                     else:
    #                         continuumstatus[int(chunk)] = False
    #                         logger.warning('Continuum imaging for chunk ' + str(chunk) + ' not successful! ' + f +
    #                                        ' was not found!')
    #                         continuumchunkstackrejreason[int(chunk)] = 'Chunk {} file {} missing'.format(chunk, f)
    #                         break
    #         else:
    #             continuumchunkstackrejreason[int(chunk)] = 'Self-calibration failed'
    #             logger.error(' Chunk ' + str(
    #                 chunk) + ' could or was not successfully calibrated! No continuum imaging for this chunk possible!')
    #
    #     # Save the derived parameters to the parameter file
    #     subs_param.add_param(self, beam + '_minoriterations', continuumminiters)
    #     subs_param.add_param(self, beam + '_imagestats', continuumimagestats)
    #     subs_param.add_param(self, beam + '_residualstats', continuumresidualstats)
    #     subs_param.add_param(self, beam + '_status', continuumstatus)
    #     subs_param.add_param(self, beam + '_imagestatus', continuumimagestatus)
    #     subs_param.add_param(self, beam + '_maskstatus', continuummaskstatus)
    #     subs_param.add_param(self, beam + '_modelstatus', continuummodelstatus)
    #     subs_param.add_param(self, beam + '_residualstatus', continuumresidualstatus)
    #     subs_param.add_param(self, beam + '_thresholdtype', continuumthresholdtype)
    #     subs_param.add_param(self, beam + '_masklimit', continuummasklimit)
    #     subs_param.add_param(self, beam + '_cleanlimit', continuumcleanlimit)
    #
    #     ################################
    #     # Stacking of continuum images #
    #     ################################
    #
    #     status = subs_param.get_param(self, beam + '_status')
    #     minoriterations = subs_param.get_param(self, beam + '_minoriterations')
    #
    #     # Check if the final stacked continuum image is already available
    #     if os.path.isdir(self.contdir + '/' + self.target.rstrip('.mir') + '_stack') and os.path.isfile(
    #             self.contdir + '/' + self.target.rstrip('.mir') + '_stack.fits'):
    #         logger.info(' Final stacked continuum image is already available!')
    #     else:  # if not create it
    #
    #         # Check if the continuum imaging worked for any of the chunks
    #         if any(status):
    #             logger.info(' Stacking continuum images of individual frequency chunks')
    #             subs_managefiles.director(self, 'ch', self.contdir + '/stack')
    #             images = ''
    #
    #             # Check if continuum imaging was successful and then check the image
    #             for nch, chstat in enumerate(status):
    #                 if chstat:
    #                     lastimage = str(nch).zfill(2) + '/' + 'image_' + str(int(minoriterations[nch])).zfill(2)
    #                     lastimage_stats = subs_imstats.getimagestats(self, lastimage)
    #                     if np.isnan(lastimage_stats[2]):  # Check if the image is not blank
    #                         continuumchunkimageacceptforstacking[nch] = False
    #                         continuumchunkstackrejreason[nch] = 'Final image not valid'
    #                         logger.warning('Image from frequency chunk ' + str(nch).zfill(
    #                             2) + ' is not valid. This image is not added in stacking! #')
    #                     elif lastimage_stats[1] >= 100000.0:  # Check if the image has high amplitudes
    #                         continuumchunkimageacceptforstacking[nch] = False
    #                         continuumchunkstackrejreason[nch] = 'High amplitudes in final image'
    #                         logger.warning('Image from frequency chunk ' + str(nch).zfill(
    #                             2) + ' shows high amplitudes and is not added in stacking! #')
    #                     elif lastimage_stats[0] <= -1.0:  # Check if the image has strong negative residuals
    #                         continuumchunkimageacceptforstacking[nch] = False
    #                         continuumchunkstackrejreason[nch] = 'Strong negative residuals in final image'
    #                         logger.warning('Image from frequency chunk ' + str(nch).zfill(
    #                             2) + ' shows strong negative residuals and is not added in stacking! #')
    #                     else:
    #                         continuumchunkimageacceptforstacking[nch] = True
    #                         images = images + lastimage + ','
    #                         continuumsynthbeamparams[nch, :] = subs_readmirhead.getbeamimage(lastimage)
    #
    #                 else:  # Continuum imaging was not successful for a specific chunk
    #                     continuumchunkimageacceptforstacking[nch] = False
    #                     continuumchunkstackrejreason[nch] = 'Continuum imaging not successful'
    #                     logger.warning('Continuum imaging for chunk ' + str(nch).zfill(
    #                         2) + ' was not successful. Image of this chunk will not be added in stacking! #')
    #
    #             ########################################
    #             # Convolve the images to a common beam #
    #             ########################################
    #
    #             # Calculate the beam automatically or use the given one from the config-file
    #             if self.continuum_image_convolbeam == '':
    #
    #                 # Calculate the common beam and make a list of accepted and rejected chunks and update the
    #                 # parameters for the parameter file
    #                 avchunklist = np.where(continuumchunkimageacceptforstacking)[0]
    #                 notavchunklist = np.where(np.logical_not(continuumchunkimageacceptforstacking))[0]
    #                 avchunks = [str(x).zfill(2) for x in list(avchunklist)]
    #                 notavchunks = [str(x).zfill(2) for x in list(notavchunklist)]
    #                 beamarray = continuumsynthbeamparams[avchunklist, :]
    #                 rejchunks, stackbeam = subs_combim.calc_synbeam(avchunks, beamarray)
    #                 if len(rejchunks) == 0:
    #                     logger.debug('No chunks are rejected due to synthesised beam parameters. #')
    #                 else:
    #                     for c in rejchunks:
    #                         avchunks.remove(c)
    #                         notavchunks.extend(c)
    #                         logger.warning(
    #                             'Chunk ' + str(c).zfill(2) + ' was rejected due to synthesised beam parameters! #')
    #                         continuumchunkimageacceptforstacking[int(c)] = False
    #                         continuumchunkstackrejreason[int(c)] = 'Synthesised beam parameters'
    #                     sorted(avchunks)
    #                     sorted(notavchunks)
    #
    #             else:
    #                 beam_parameters = self.continuum_image_convolbeam.split(',')
    #                 stackbeam = np.array([beam_parameters[0], beam_parameters[1], beam_parameters[2]])
    #
    #             logger.info('Final beam size is fwhm = ' + str(stackbeam[0]) + ' arcsec , ' + str(
    #                 stackbeam[1]) + ' arcsec, pa = ' + str(stackbeam[2]) + ' deg')
    #
    #             # Now convolve the images to the calculated or given beam
    #             for nch, chstat in enumerate(continuumchunkimageacceptforstacking):
    #                 if chstat:
    #                     if os.path.exists(str(nch).zfill(2) + '/' + 'convol_' + str(int(minoriterations[nch])).zfill(
    #                             2)):  # Check if the convolved image is already available
    #                         logger.info('Convolved image for chunk ' + str(nch).zfill(2) + ' already available! #')
    #                     else:  # if not create it
    #                         convol = lib.miriad('convol')
    #                         convol.map = str(nch).zfill(2) + '/' + 'image_' + str(int(minoriterations[nch])).zfill(2)
    #                         convol.fwhm = str(stackbeam[0]) + ',' + str(stackbeam[1])
    #                         convol.pa = str(stackbeam[2])
    #                         convol.out = str(nch).zfill(2) + '/' + 'convol_' + str(int(minoriterations[nch])).zfill(2)
    #                         convol.options = 'final'
    #                         convol.go()
    #                 else:
    #                     pass
    #
    #             ###################################
    #             # Combination of convolved images #
    #             ###################################
    #
    #             finalimages = ''
    #             for nch, chstat in enumerate(continuumchunkimageacceptforstacking):
    #                 if chstat:
    #                     residualimage = str(nch).zfill(2) + '/' + 'residual_' + str(int(minoriterations[nch])).zfill(2)
    #                     finalimage = str(nch).zfill(2) + '/' + 'image_' + str(int(minoriterations[nch])).zfill(2)
    #                     rms = subs_imstats.getimagestats(self, residualimage)[2]
    #                     continuumimcombrms[nch] = rms
    #                     images = finalimages + finalimage
    #                 else:
    #                     continuumimcombrms[nch] = np.nan
    #             continuumimcombweights = (1 / continuumimcombrms ** 2.0) / np.nansum((1 / continuumimcombrms ** 2.0))
    #             imcombrms = list(continuumimcombrms[~np.isnan(continuumimcombrms)])
    #             imcomb = lib.miriad('imcomb')
    #             imcomb.in_ = images.rstrip(',')
    #             imcomb.out = self.contdir + '/' + self.target.rstrip('.mir') + '_stack'
    #             imcomb.rms = ','.join(str(e) for e in imcombrms)
    #             imcomb.options = 'fqaver'
    #             imcomb.go()
    #             subs_managefiles.director(self, 'rm', self.contdir + '/' + self.target.rstrip('.mir') + '_stack/mask')
    #             fits = lib.miriad('fits')
    #             fits.op = 'xyout'
    #             fits.in_ = self.contdir + '/' + self.target.rstrip('.mir') + '_stack'
    #             fits.out = self.contdir + '/' + self.target.rstrip('.mir') + '_stack.fits'
    #             fits.go()
    #
    #             # Check the final stacked continuum image
    #             if os.path.isdir(self.contdir + '/' + self.target.rstrip('.mir') + '_stack') and os.path.isfile(
    #                     self.contdir + '/' + self.target.rstrip(
    #                             '.mir') + '_stack.fits'):  # Check if the image file is there
    #                 stackmin, stackmax, stackstd = subs_imstats.getimagestats(self,
    #                                                                           self.contdir + '/' + self.target.rstrip(
    #                                                                               '.mir') + '_stack.fits')
    #                 if stackstd != np.nan and stackmax <= 10000 and stackmin >= -10:  # Check if the image is valid
    #                     continuumstackedimagestatus = True
    #                     logger.info(' Final deep continuum image is ' + self.contdir + '/' + self.target.rstrip(
    #                         '.mir') + '_stack.fits')
    #                 else:  # if not issue a error
    #                     continuumstackedimagestatus = False
    #                     logger.error(' Final stacked continuum image is empty or shows high values!')
    #             else:  # if not issue an error
    #                 continuumstackedimagestatus = False
    #                 logger.error(' Final stacked continuum image could not be created!')
    #
    #     # Save the derived parameters to the parameter file
    #     subs_param.add_param(self, beam + '_stackstatus', continuumchunkimageacceptforstacking)
    #     subs_param.add_param(self, beam + '_stackrejreason', continuumchunkstackrejreason)
    #     subs_param.add_param(self, beam + '_imcombrms', continuumimcombrms)
    #     subs_param.add_param(self, beam + '_imcombweights', continuumimcombweights)
    #     subs_param.add_param(self, beam + '_stackedimagestatus', continuumstackedimagestatus)
    #     subs_param.add_param(self, beam + '_synthbeamparams', continuumsynthbeamparams)
    #
    # def calc_dr_min(self, dr_maj, majc, minorcycles, func):
    #     """
    #     Function to calculate the dynamic range limits during minor cycles
    #     dr_maj (list of floats): List with dynamic range limits for major cycles. Usually from calc_dr_maj
    #     majc (int): The major cycles you want to calculate the minor cycle dynamic ranges for
    #     minorcycles (int): The number of minor cycles to use
    #     func (string): The function to follow for increasing the dynamic ranges. Currently 'square', 'power', and
    #                       'linear' is supported.
    #     returns (list of floats): A list of floats for the dynamic range limits within the minor cycles.
    #     """
    #     if majc == 0:  # Take care about the first major cycle
    #         prevdr = 0
    #     else:
    #         prevdr = dr_maj[majc - 1]
    #     # The different options to increase the minor cycle threshold
    #     if func == 'square':
    #         dr_min = [prevdr + ((dr_maj[majc] - prevdr) * (n ** 2.0)) / ((minorcycles - 1) ** 2.0) for n in
    #                   range(minorcycles)]
    #     elif func == 'power':
    #         dr_min = [prevdr + np.power((dr_maj[majc] - prevdr), (1.0 / n)) for n in range(minorcycles)][
    #                  ::-1]  # Not exactly need to work on this, but close
    #     elif func == 'linear':
    #         dr_min = [(prevdr + ((dr_maj[majc] - prevdr) / (minorcycles - 1)) * n) for n in range(minorcycles)]
    #     else:
    #         raise ApercalException('Function for minor cycles not supported')
    #     if dr_min[0] == 0:
    #         dr_min[0] = self.continuum_minorcycle0_dr
    #     else:
    #         pass
    #     return dr_min
    #
    # def list_chunks(self):
    #     """
    #     Checks how many chunk directories exist and returns a list of them
    #     """
    #     subs_setinit.setinitdirs(self)
    #     subs_setinit.setdatasetnamestomiriad(self)
    #     for n in range(100):
    #         if os.path.isdir(self.selfcaldir + '/' + str(n).zfill(2)):
    #             pass
    #         else:
    #             break  # Stop the counting loop at the directory you cannot find anymore
    #     chunks = range(n)
    #     chunkstr = [str(i).zfill(2) for i in chunks]
    #     return chunkstr
    #
    # def get_last_major_iteration(self, chunk):
    #     """
    #     Get the number of the last major iteration
    #     chunk: The frequency chunk to look into. Usually an entry generated by list_chunks
    #     return: The number of the last major clean iteration for a frequency chunk
    #     """
    #     subs_setinit.setinitdirs(self)
    #     subs_setinit.setdatasetnamestomiriad(self)
    #     for n in range(100):
    #         if os.path.isdir(self.selfcaldir + '/' + str(chunk) + '/' + str(n).zfill(2)):
    #             pass
    #         else:
    #             break  # Stop the counting loop at the file you cannot find anymore
    #     lastmajor = n - 1
    #     return lastmajor
    #
    # def get_last_minor_iteration(self, chunk, maj):
    #     """
    #     Get the number of the last minor iteration
    #     chunk: The frequency chunk to look into. Usually an entry generated by list_chunks
    #     maj: Number of the last major iteration
    #     return: The number of the last major clean iteration for a frequency chunk
    #     """
    #     subs_setinit.setinitdirs(self)
    #     subs_setinit.setdatasetnamestomiriad(self)
    #     for n in range(100):
    #         if os.path.isdir(
    #                 self.selfcaldir + '/' + str(chunk) + '/' + str(maj).zfill(2) + '/' + 'image_' + str(n).zfill(2)):
    #             pass
    #         else:
    #             break  # Stop the counting loop at the file you cannot find anymore
    #     lastminor = n - 1
    #     return lastminor
    #
    # def summary(self):
    #     """
    #     Creates a general summary of the parameters in the parameter file generated during the continuum imaging. A
    #     more detailed summary can be generated by the detailed_summary function
    #     returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in the
    #     notebook
    #     """
    #     beam = str(self.beam).zfill(2)
    #     # Load the parameters from the parameter file
    #     IT = subs_param.get_param(self, beam + '_minoriterations')
    #     ST = subs_param.get_param(self, beam + '_status')
    #     SBEAMS = subs_param.get_param(self, beam + '_synthbeamparams')
    #     STST = subs_param.get_param(self, beam + '_stackstatus')
    #     ICW = subs_param.get_param(self, beam + '_imcombweights')
    #     RR = subs_param.get_param(self, beam + '_stackrejreason')
    #
    #     # Create the data frame
    #
    #     chunk_indices = self.list_chunks()
    #
    #     df_it = pd.DataFrame(np.ndarray.flatten(IT), index=chunk_indices, columns=['Iterations'])
    #     df_st = pd.DataFrame(np.ndarray.flatten(ST), index=chunk_indices, columns=['Success?'])
    #     df_bmaj = pd.DataFrame(np.around(np.ndarray.flatten(SBEAMS[:, 0]), decimals=2), index=chunk_indices,
    #                            columns=['Bmaj ["]'])
    #     df_bmin = pd.DataFrame(np.around(np.ndarray.flatten(SBEAMS[:, 1]), decimals=2), index=chunk_indices,
    #                            columns=['Bmin ["]'])
    #     df_bpa = pd.DataFrame(np.around(np.ndarray.flatten(SBEAMS[:, 2]), decimals=2), index=chunk_indices,
    #                           columns=['Bpa [deg]'])
    #     df_icw = pd.DataFrame(np.around(np.ndarray.flatten(ICW), decimals=5), index=chunk_indices,
    #                           columns=['Image weight'])
    #
    #     df_stst = pd.DataFrame(np.ndarray.flatten(STST), index=chunk_indices, columns=['Accepted?'])
    #     df_rr = pd.DataFrame(np.ndarray.flatten(RR), index=chunk_indices, columns=['Reason'])
    #
    #     df = pd.concat([df_it, df_st, df_bmaj, df_bmin, df_bpa, df_icw, df_stst, df_rr], axis=1)
    #
    #     return df
    #
    # def detailed_summary(self):
    #     """
    #     Creates a detailed summary of the parameters in the parameter file generated during the continuum imaging
    #     returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in the
    #                          notebook
    #     """
    #
    #     beam = str(self.beam).zfill(2)
    #     # Load the parameters from the parameter file
    #     IMST = subs_param.get_param(self, beam + '_imagestats')
    #     RSST = subs_param.get_param(self, beam + '_residualstats')
    #     IMstatus = subs_param.get_param(self, beam + '_imagestatus')
    #     MAstatus = subs_param.get_param(self, beam + '_maskstatus')
    #     MOstatus = subs_param.get_param(self, beam + '_modelstatus')
    #     REstatus = subs_param.get_param(self, beam + '_residualstatus')
    #     TH = subs_param.get_param(self, beam + '_thresholdtype')
    #     MLIM = subs_param.get_param(self, beam + '_masklimit')
    #     CLIM = subs_param.get_param(self, beam + '_cleanlimit')
    #
    #     # Create the data frames
    #
    #     chunk_iter_indices = pd.MultiIndex.from_product([self.list_chunks(), np.arange(0, self.continuum_minorcycle)],
    #                                                     names=['Chunk', 'Iter #'])
    #
    #     df_th = pd.DataFrame(np.ndarray.flatten(TH), index=chunk_iter_indices, columns=['TH type'])
    #
    #     df_mastat = pd.DataFrame(np.ndarray.flatten(MAstatus), index=chunk_iter_indices,
    #                              columns=['Mask created/ valid?'])
    #     df_malim = pd.DataFrame(np.around(np.ndarray.flatten(MLIM), decimals=5), index=chunk_iter_indices,
    #                             columns=['Mask Limit'])
    #
    #     df_mostat = pd.DataFrame(np.ndarray.flatten(MOstatus), index=chunk_iter_indices,
    #                              columns=['Model created/ valid?'])
    #     df_clim = pd.DataFrame(np.around(np.ndarray.flatten(CLIM), decimals=5), index=chunk_iter_indices,
    #                            columns=['Clean Limit'])
    #
    #     df_imstat = pd.DataFrame(np.ndarray.flatten(IMstatus), index=chunk_iter_indices,
    #                              columns=['Image created/ valid?'])
    #     df_immin = pd.DataFrame(np.around(np.ndarray.flatten(IMST[:, :, 0]), decimals=5), index=chunk_iter_indices,
    #                             columns=['Image Min'])
    #     df_immax = pd.DataFrame(np.around(np.ndarray.flatten(IMST[:, :, 1]), decimals=5), index=chunk_iter_indices,
    #                             columns=['Image Max'])
    #     df_imstd = pd.DataFrame(np.around(np.ndarray.flatten(IMST[:, :, 2]), decimals=5), index=chunk_iter_indices,
    #                             columns=['Image StD'])
    #
    #     df_restat = pd.DataFrame(np.ndarray.flatten(REstatus), index=chunk_iter_indices,
    #                              columns=['Residual created/ valid?'])
    #     df_rdmin = pd.DataFrame(np.around(np.ndarray.flatten(RSST[:, :, 0]), decimals=5), index=chunk_iter_indices,
    #                             columns=['Residual Image Min'])
    #     df_rdmax = pd.DataFrame(np.around(np.ndarray.flatten(RSST[:, :, 1]), decimals=5), index=chunk_iter_indices,
    #                             columns=['Residual Image Max'])
    #     df_rdstd = pd.DataFrame(np.around(np.ndarray.flatten(RSST[:, :, 2]), decimals=5), index=chunk_iter_indices,
    #                             columns=['Residual Image StD'])
    #
    #     # Combine all the data frames into one to display
    #
    #     df = pd.concat(
    #         [df_th, df_mastat, df_malim, df_mostat, df_clim, df_imstat, df_immin, df_immax, df_imstd, df_restat,
    #          df_rdmin, df_rdmax, df_rdstd], axis=1)
    #
    #     return df
    #
    # def reset(self):
    #     """
    #     Function to reset the current step and remove all generated data including continuum parameters in the
    #     parameter file. Be careful! Deletes all data generated in this step!
    #     """
    #     subs_setinit.setinitdirs(self)
    #     subs_setinit.setdatasetnamestomiriad(self)
    #     logger.warning(' Deleting all continuum data products.')
    #     subs_managefiles.director(self, 'ch', self.contdir)
    #     subs_managefiles.director(self, 'rm', self.contdir + '/*')
    #     logger.warning(' Deleteing all parameter file entries for CONTINUUM module')
    #     beam = str(self.beam).zfill(2)
    #     subs_param.del_param(self, beam + '_imcomb_rms')
    #     subs_param.del_param(self, beam + '_minoriterations')
    #     subs_param.del_param(self, beam + '_imagestats')
    #     subs_param.del_param(self, beam + '_maskstatus')
    #     subs_param.del_param(self, beam + '_modelstatus')
    #     subs_param.del_param(self, beam + '_imagestatus')
    #     subs_param.del_param(self, beam + '_residualstatus')
    #     subs_param.del_param(self, beam + '_residualstats')
    #     subs_param.del_param(self, beam + '_status')
    #     subs_param.del_param(self, beam + '_thresholdtype')
    #     subs_param.del_param(self, beam + '_masklimit')
    #     subs_param.del_param(self, beam + '_cleanlimit')
    #     subs_param.del_param(self, beam + '_synthbeamparams')
    #     subs_param.del_param(self, beam + '_stackstatus')
    #     subs_param.del_param(self, beam + '_stackrejreason')
    #     subs_param.del_param(self, beam + '_imcombrms')
    #     subs_param.del_param(self, beam + '_imcombweights')
    #     subs_param.del_param(self, beam + '_stackedimagestatus')
