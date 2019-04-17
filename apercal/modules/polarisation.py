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
from apercal.subs import readmirhead
from apercal.subs import masking
from apercal.subs import qa

from apercal.exceptions import ApercalException

logger = logging.getLogger(__name__)


class polarisation(BaseModule):
    """
    Polarisation class to create Stokes Q-, U-, and V-images and perform RM-Synthesis.
    """
    module_name = 'POLARISATION'

    poldir = None
    contdir = None
    selfcaldir = None

    def __init__(self, file_=None, **kwargs):
        self.default = lib.load_config(self, file_)
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)

    def go(self):
        """
        Executes the polarisation imaging process in the following order
        quimaging
        vimaging
        """
        logger.info("Starting POLARISATION IMAGING")
        self.quimaging()
#        self.vimaging()
        logger.info("POLARISATION IMAGING done ")

    def get_target_path(self, beam=None):
        if self.subdirification:
            return '../' + self.selfcalsubdir + '/' + self.target
        else:
            return self.target


    def quimaging(self):
        """
        Creates a Q-, and U-image from each subband from the self-calibrated data
        """
        subs_setinit.setinitdirs(self)

        sbeam = 'selfcal_B' + str(self.beam).zfill(2)
        cbeam = 'continuum_B' + str(self.beam).zfill(2)
        pbeam = 'polarisation_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the polarisation imaging

        polarisationtargetbeamsqustatus = get_param_def(self, pbeam + '_targetbeams_qu_status', False)
        polarisationtargetbeamsqumapstatus = get_param_def(self, pbeam + '_targetbeams_qu_mapstatus', np.full((384, 2), False))
        polarisationtargetbeamsqubeamstatus = get_param_def(self, pbeam + '_targetbeams_qu_beamstatus', np.full((384, 2), False))
        polarisationtargetbeamsqumodelstatus = get_param_def(self, pbeam + '_targetbeams_qu_modelstatus', np.full((384, 2), False))
        polarisationtargetbeamsquimagestatus = get_param_def(self, pbeam + '_targetbeams_qu_imagestatus', np.full((384, 2), False))
        polarisationtargetbeamsquimagestats = get_param_def(self, pbeam + '_targetbeams_qu_imagestats', np.full((384, 3, 2), np.nan))
        polarisationtargetbeamsqubeamparams = get_param_def(self, pbeam + '_targetbeams_qu_beamparams', np.full((384, 3, 2), np.nan))

        if self.polarisation_qu:
            subs_setinit.setinitdirs(self)
            subs_setinit.setdatasetnamestomiriad(self)
            subs_managefiles.director(self, 'ch', self.poldir)
            if not polarisationtargetbeamsqustatus:
                logger.info('Beam ' + self.beam + ': Stokes Q-/U-imaging')
                # Get the status of the continuum imaging
                continuumtargetbeamsmfstatus = get_param_def(self, cbeam + '_targetbeams_mf_status', False)
                if continuumtargetbeamsmfstatus:
                    # Copy over the last mask from the mf continuum imaging to use for the whole polarisation imaging
                    continuumtargetbeamsmffinalminor = subs_param.get_param(self, cbeam + '_targetbeams_mf_final_minorcycle')
                    subs_managefiles.director(self, 'cp', 'mask_QU', file_=self.contdir + '/mask_mf_' + str(continuumtargetbeamsmffinalminor).zfill(2))
                    # Get the status of the selfcal for the specified beam
                    selfcaltargetbeamsampstatus = get_param_def(self, sbeam + '_targetbeams_amp_status', False)
                    selfcaltargetbeamsphasestatus = get_param_def(self, sbeam + '_targetbeams_phase_status', False)
                    selfcaltargetbeamsphasestatus = True
                    if selfcaltargetbeamsampstatus:
                        datasetname = self.get_target_path().rstrip('.mir') + '_amp.mir'
                    elif selfcaltargetbeamsphasestatus:
                        datasetname = self.get_target_path()
                    else:
                        logger.error('Beam ' + self.beam + ': Amplitude nor phase self-calibration was successful! Not creating polarisation images!')
                    # Iterate over the subbands to create Q images
                    maskregrid = False
                    for subband in range(self.polarisation_qu_startsubband, self.polarisation_qu_endsubband + 1, 1):
                        try:
                            invert = lib.miriad('invert')  # Create the dirty image
                            invert.vis = datasetname
                            invert.map = 'map_Q_' + str(subband).zfill(3)
                            invert.beam = 'beam_Q_' + str(subband).zfill(3)
                            invert.imsize = self.polarisation_qu_imsize
                            invert.cell = self.polarisation_qu_cellsize
                            invert.stokes = 'q'
                            invert.line = 'channel,1,' + str(subband+1) + ',1,1'
                            invert.slop = 1
                            invert.robust = -2
                            invert.go()
                            if not maskregrid:  # Regrid the mask from continuum mf
                                regrid = lib.miriad('regrid')
                                regrid.in_ = 'mask_QU'
                                regrid.out = 'mask_QU_regrid'
                                regrid.axes = '1,2'
                                regrid.tin = 'map_Q_' + str(subband).zfill(3)
                                regrid.go()
                                if os.path.isdir('mask_QU_regrid'):
                                    subs_managefiles.director(self, 'mv', 'mask_QU', file_='mask_QU_regrid')
                                    maskregrid = True
                                else:
                                    logger.warning('Beam ' + self.beam + ': Mask could not be successfully regridded! Aborting Q-/U-imaging')
                                    break
                            # Check the dirty map
                            if os.path.isdir('map_Q_' + str(subband).zfill(3)):
                                polarisationtargetbeamsqumapstatus[subband, 0] = True
                                if qa.checkdirtyimage(self, 'map_Q_' + str(subband).zfill(3)):
                                    polarisationtargetbeamsqumapstatus[subband, 0] = True
                                else:
                                    polarisationtargetbeamsqumapstatus[subband, 0] = False
                            else:
                                polarisationtargetbeamsqumapstatus[subband, 0] = False
                            # Check the beam
                            if os.path.isdir('beam_Q_' + str(subband).zfill(3)):
                                polarisationtargetbeamsqubeamstatus[subband, 0] = True
                            else:
                                polarisationtargetbeamsqubeamstatus[subband, 0] = False
                            # Check if map was created successfully get the std and clean it
                            if os.path.isdir('map_Q_' + str(subband).zfill(3)) and os.path.isdir('beam_Q_' + str(subband).zfill(3)):
                                immin, immax, imstd = imstats.getimagestats(self, 'map_Q_' + str(subband).zfill(3))
                                clean = lib.miriad('clean')  # Clean the image down to the calculated threshold
                                clean.map = 'map_Q_' + str(subband).zfill(3)
                                clean.beam = 'beam_Q_' + str(subband).zfill(3)
                                clean.out = 'model_Q_' + str(subband).zfill(3)
                                clean.cutoff = imstd * self.polarisation_qu_clean_sigma
                                clean.niters = 10000
                                clean.region = '"' + 'mask(mask_QU)' + '"'
                                clean.go()
                                if os.path.isdir('model_Q_' + str(subband).zfill(3)):
                                    if qa.checkmodelimage(self, 'model_Q_' + str(subband).zfill(3)):
                                        polarisationtargetbeamsqumodelstatus[subband, 0] = True
                                    else:
                                        polarisationtargetbeamsqumodelstatus[subband, 0] = False
                                # Create the restored image
                                if polarisationtargetbeamsqumodelstatus[subband, 0]:
                                    restor = lib.miriad('restor')  # Create the restored image
                                    restor.model = 'model_Q_' + str(subband).zfill(3)
                                    restor.beam = 'beam_Q_' + str(subband).zfill(3)
                                    restor.map = 'map_Q_' + str(subband).zfill(3)
                                    restor.out = 'image_Q_' + str(subband).zfill(3)
                                    restor.mode = 'clean'
                                    restor.go()
                                    if os.path.isdir('image_Q_' + str(subband).zfill(3)):
                                        if qa.checkrestoredimage(self, 'image_Q_' + str(subband).zfill(3)):
                                            polarisationtargetbeamsquimagestatus[subband, 0] = True
                                        else:
                                            polarisationtargetbeamsquimagestatus[subband, 0] = False
                                else:
                                    polarisationtargetbeamsquimagestatus[subband, 0] = False
                            if polarisationtargetbeamsquimagestatus[subband, 0]:
                                polarisationtargetbeamsquimagestats[subband, :, 0] = imstats.getimagestats(self, 'image_Q_' + str(subband).zfill(3))
                                polarisationtargetbeamsqubeamparams[subband, :, 0] = readmirhead.getbeamimage('image_Q_' + str(subband).zfill(3))
                            else:
                                continue
                        except RuntimeError:
                            polarisationtargetbeamsqumapstatus[subband, 0] = False
                            polarisationtargetbeamsqubeamstatus[subband, 0] = False
                            polarisationtargetbeamsqumodelstatus[subband, 0] = False
                            polarisationtargetbeamsquimagestatus[subband, 0] = False
                            polarisationtargetbeamsquimagestats[subband, :, 0] = [np.nan, np.nan, np.nan]
                            polarisationtargetbeamsqubeamparams[subband, :, 0] = [np.nan, np.nan, np.nan]
                            logger.warning('Beam ' + self.beam + ': No Stokes Q data for subband ' + str(subband).zfill(3) + '!')
                        # Do the same for Stokes U
                        try:
                            invert = lib.miriad('invert')  # Create the dirty image
                            invert.vis = datasetname
                            invert.map = 'map_U_' + str(subband).zfill(3)
                            invert.beam = 'beam_U_' + str(subband).zfill(3)
                            invert.imsize = self.polarisation_qu_imsize
                            invert.cell = self.polarisation_qu_cellsize
                            invert.stokes = 'u'
                            invert.line = 'channel,1,' + str(subband+1) + ',1,1'
                            invert.slop = 1
                            invert.robust = -2
                            invert.go()
                            if not maskregrid:  # Regrid the mask from continuum mf
                                regrid = lib.miriad('regrid')
                                regrid.in_ = 'mask_QU'
                                regrid.out = 'mask_QU_regrid'
                                regrid.axes = '1,2'
                                regrid.tin = 'map_U_' + str(subband).zfill(3)
                                regrid.go()
                                if os.path.isdir('mask_QU_regrid'):
                                    subs_managefiles.director(self, 'mv', 'mask_QU', file_='mask_QU_regrid')
                                    maskregrid = True
                                else:
                                    logger.warning('Beam ' + self.beam + ': Mask could not be successfully regridded! Aborting Q-/U-imaging')
                                    break
                            # Check the dirty map
                            if os.path.isdir('map_U_' + str(subband).zfill(3)):
                                polarisationtargetbeamsqumapstatus[subband, 1] = True
                                if qa.checkdirtyimage(self, 'map_U_' + str(subband).zfill(3)):
                                    polarisationtargetbeamsqumapstatus[subband, 1] = True
                                else:
                                    polarisationtargetbeamsqumapstatus[subband, 1] = False
                            else:
                                polarisationtargetbeamsqumapstatus[subband, 1] = False
                            # Check the beam
                            if os.path.isdir('beam_U_' + str(subband).zfill(3)):
                                polarisationtargetbeamsqubeamstatus[subband, 1] = True
                            else:
                                polarisationtargetbeamsqubeamstatus[subband, 1] = False
                            # Check if map was created successfully get the std and clean it
                            if os.path.isdir('map_U_' + str(subband).zfill(3)) and os.path.isdir('beam_U_' + str(subband).zfill(3)):
                                immin, immax, imstd = imstats.getimagestats(self, 'map_U_' + str(subband).zfill(3))
                                clean = lib.miriad('clean')  # Clean the image down to the calculated threshold
                                clean.map = 'map_U_' + str(subband).zfill(3)
                                clean.beam = 'beam_U_' + str(subband).zfill(3)
                                clean.out = 'model_U_' + str(subband).zfill(3)
                                clean.cutoff = imstd * self.polarisation_qu_clean_sigma
                                clean.niters = 10000
                                clean.region = '"' + 'mask(mask_QU)' + '"'
                                clean.go()
                                if os.path.isdir('model_U_' + str(subband).zfill(3)):
                                    if qa.checkmodelimage(self, 'model_U_' + str(subband).zfill(3)):
                                        polarisationtargetbeamsqumodelstatus[subband, 1] = True
                                    else:
                                        polarisationtargetbeamsqumodelstatus[subband, 1] = False
                                # Create the restored image
                                if polarisationtargetbeamsqumodelstatus[subband, 1]:
                                    restor = lib.miriad('restor')  # Create the restored image
                                    restor.model = 'model_U_' + str(subband).zfill(3)
                                    restor.beam = 'beam_U_' + str(subband).zfill(3)
                                    restor.map = 'map_U_' + str(subband).zfill(3)
                                    restor.out = 'image_U_' + str(subband).zfill(3)
                                    restor.mode = 'clean'
                                    restor.go()
                                    if os.path.isdir('image_U_' + str(subband).zfill(3)):
                                        if qa.checkrestoredimage(self, 'image_U_' + str(subband).zfill(3)):
                                            polarisationtargetbeamsquimagestatus[subband, 1] = True
                                        else:
                                            polarisationtargetbeamsquimagestatus[subband, 1] = False
                                else:
                                    polarisationtargetbeamsquimagestatus[subband, 1] = False
                            if polarisationtargetbeamsquimagestatus[subband, 1]:
                                polarisationtargetbeamsquimagestats[subband, :, 1] = imstats.getimagestats(self, 'image_U_' + str(subband).zfill(3))
                                polarisationtargetbeamsqubeamparams[subband, :, 1] = readmirhead.getbeamimage('image_U_' + str(subband).zfill(3))
                            else:
                                continue
                        except RuntimeError:
                            polarisationtargetbeamsqumapstatus[subband, 1] = False
                            polarisationtargetbeamsqubeamstatus[subband, 1] = False
                            polarisationtargetbeamsqumodelstatus[subband, 1] = False
                            polarisationtargetbeamsquimagestatus[subband, 1] = False
                            polarisationtargetbeamsquimagestats[subband, :, 1] = [np.nan, np.nan, np.nan]
                            polarisationtargetbeamsqubeamparams[subband, :, 1] = [np.nan, np.nan, np.nan]
                            logger.warning('Beam ' + self.beam + ': No Stokes U data for subband ' + str(subband).zfill(3) + '!')
                    # Check the results of the imaging
                    nQimages = np.sum(polarisationtargetbeamsquimagestatus[:, 0])
                    nUimages = np.sum(polarisationtargetbeamsquimagestatus[:, 1])
                    logger.info('Beam ' + self.beam + ': ' + str(nQimages) + '/384 Stokes Q-images were created successfully!')
                    logger.info('Beam ' + self.beam + ': ' + str(nUimages) + '/384 Stokes U-images were created successfully!')
                    if nQimages != 0 and nUimages != 0:
                        polarisationtargetbeamsqustatus = True
                        logger.info('Beam ' + self.beam + ': Q-/U-imaging successful!')
                    else:
                        polarisationtargetbeamsqustatus = False
                        logger.info('Beam ' + self.beam + ': Q-/U-imaging not successful! No Q- or U-images were produced successfully!')
                else:
                    logger.error('Beam ' + self.beam + ': Polarisation imaging not possible. Continuum imaging was not successful or not executed!')
            else:
                logger.info('Beam ' + self.beam + ': Q-/U-imaging was already successfully executed before!')

        # Save the derived parameters to the parameter file

        subs_param.add_param(self, pbeam + '_targetbeams_qu_status', polarisationtargetbeamsqustatus)
        subs_param.add_param(self, pbeam + '_targetbeams_qu_mapstatus', polarisationtargetbeamsqumapstatus)
        subs_param.add_param(self, pbeam + '_targetbeams_qu_beamstatus', polarisationtargetbeamsqubeamstatus)
        subs_param.add_param(self, pbeam + '_targetbeams_qu_modelstatus', polarisationtargetbeamsqumodelstatus)
        subs_param.add_param(self, pbeam + '_targetbeams_qu_imagestatus', polarisationtargetbeamsquimagestatus)
        subs_param.add_param(self, pbeam + '_targetbeams_qu_imagestats', polarisationtargetbeamsquimagestats)
        subs_param.add_param(self, pbeam + '_targetbeams_qu_beamparams', polarisationtargetbeamsqubeamparams)


    def show(self, showall=False):
        lib.show(self, 'POLARISATION', showall)