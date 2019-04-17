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
        rmsynthesis
        vimaging
        """
        logger.info("Starting POLARISATION IMAGING")
        self.quimaging()
#        self.rmsynthesis()
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

        pbeam = 'polarisation_B' + str(self.beam).zfill(2)
        sbeam = 'selfcal_B' + str(self.beam).zfill(2)
        cbeam = 'continuum_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the polarisation imaging

#        continuumtargetbeamsmfstatus = get_param_def(self, beam + '_targetbeams_mf_status', False)
#        continuumtargetbeamsmfmapstatus = get_param_def(self, beam + '_targetbeams_mf_mapstatus', False)
#        continuumtargetbeamsmfmapstats = get_param_def(self, beam + '_targetbeams_mf_mapstats', np.full((3), np.nan))
#        continuumtargetbeamsmfbeamstatus = get_param_def(self, beam + '_targetbeams_mf_beamstatus', False)
#        continuumtargetbeamsmfmaskstatus = get_param_def(self, beam + '_targetbeams_mf_maskstatus', np.full((self.continuum_mfimage_minorcycle), False))
#        continuumtargetbeamsmfmaskstats = get_param_def(self, beam + '_targetbeams_mf_maskstats', np.full((self.continuum_mfimage_minorcycle, 2), np.nan))
#        continuumtargetbeamsmfmodelstatus = get_param_def(self, beam + '_targetbeams_mf_modelstatus', np.full((self.continuum_mfimage_minorcycle), False))
#        continuumtargetbeamsmfmodelstats = get_param_def(self, beam + '_targetbeams_mf_modelstats', np.full((self.continuum_mfimage_minorcycle, 2), np.nan))
#        continuumtargetbeamsmfimagestatus = get_param_def(self, beam + '_targetbeams_mf_imagestatus', np.full((self.continuum_mfimage_minorcycle), False))
#        continuumtargetbeamsmfimagestats = get_param_def(self, beam + '_targetbeams_mf_imagestats', np.full((self.continuum_mfimage_minorcycle, 3), np.nan))
#        continuumtargetbeamsmfresidualstatus = get_param_def(self, beam + '_targetbeams_mf_residualstatus', False)
#        continuumtargetbeamsmfresidualstats = get_param_def(self, beam + '_targetbeams_mf_residualstats', np.full((self.continuum_mfimage_minorcycle, 3), np.nan))
#        continuumtargetbeamsmfmaskthreshold = get_param_def(self, beam + '_targetbeams_mf_maskthreshold', np.full((self.continuum_mfimage_minorcycle), np.nan))
#        continuumtargetbeamsmfcleanthreshold = get_param_def(self, beam + '_targetbeams_mf_cleanthreshold', np.full((self.continuum_mfimage_minorcycle), np.nan))
#        continuumtargetbeamsmfthresholdtype = get_param_def(self, beam + '_targetbeams_mf_thresholdtype', np.full((self.continuum_mfimage_minorcycle), 'NA'))
#        continuumtargetbeamsmffinalminor = get_param_def(self, beam + '_targetbeams_mf_final_minorcycle', np.full((1), 0))

        if self.polarisation_qu:
            subs_setinit.setinitdirs(self)
            subs_setinit.setdatasetnamestomiriad(self)
            subs_managefiles.director(self, 'ch', self.poldir)
            logger.info('Beam ' + self.beam + ': Stokes Q-/U-imaging')
            # Get the status of the continuum imaging
#            continuumtargetbeamsmfstatus = get_param_def(self, cbeam + '_targetbeams_mf_status', False)
            continuumtargetbeamsmfstatus = True # Remove after fix
            if continuumtargetbeamsmfstatus:
                # Copy over the last mask from the mf continuum imaging to use for the whole polarisation imaging
                continuumtargetbeamsmffinalminor = 2 # Remove after fix
#                continuumtargetbeamsmffinalminor = subs_param.get_param(self, cbeam + '_targetbeams_mf_final_minorcycle')
                subs_managefiles.director(self, 'cp', 'mask_QU', self.contdir + '/mask_mf_' + str(continuumtargetbeamsmffinalminor).zfill(2))
                # Get the status of the selfcal for the specified beam
                selfcaltargetbeamsampstatus = get_param_def(self, sbeam + '_targetbeams_amp_status', False)
                selfcaltargetbeamsphasestatus = get_param_def(self, sbeam + '_targetbeams_phase_status', False)
                if selfcaltargetbeamsampstatus:
                    datasetname = self.get_target_path().rstrip('.mir') + '_amp.mir'
                elif selfcaltargetbeamsphasestatus:
                    datasetname = self.get_target_path()
                else:
                    logger.error('Beam ' + self.beam + ': Amplitude nor phase self-calibration was successful! Not creating polarisation images!')
                datasetname = self.get_target_path() # remove after fix
                # Iterate over the subbands to create Q and U images
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
                    except:
                        logger.warning('Beam ' + self.beam + ': No Stokes Q data for subband ' + str(subband).zfill(3) + ' !')
                    # Check if map was created successfully get the std and clean it
                    if os.path.isdir('map_Q_' + str(subband).zfill(3)):
                        immin, immax, imstd = imstats.getimagestats(self, 'map_Q_' + str(subband).zfill(3))
                        clean = lib.miriad('clean')  # Clean the image down to the calculated threshold
                        clean.map = 'map_Q_' + str(subband).zfill(3)
                        clean.beam = 'beam_Q_' + str(subband).zfill(3)
                        clean.out = 'model_Q_' + str(subband).zfill(3)
                        clean.cutoff = imstd * self.polarisation_qu_clean_sigma
                        clean.niters = 10000
                        clean.region = '"' + 'mask(mask_QU)' + '"'
                        clean.go()
                        restor = lib.miriad('restor')  # Create the restored image
                        restor.model = 'model_Q_' + str(subband).zfill(3)
                        restor.beam = 'beam_Q_' + str(subband).zfill(3)
                        restor.map = 'map_Q_' + str(subband).zfill(3)
                        restor.out = 'image_Q_' + str(subband).zfill(3)
                        restor.mode = 'clean'
                        restor.go()
                    if os.path.isdir('image_Q_' + str(subband).zfill(3)):
                        subs_managefiles.imagetofits(self, 'image_Q_' + str(subband).zfill(3), 'image_Q_' + str(subband).zfill(3) + '.qmap.fits')
                    # Do everything for Stokes U as well
                    try:
                        invert = lib.miriad('invert')  # Create the dirty image
                        invert.vis = datasetname
                        invert.map = 'map_U_' + str(subband).zfill(3)
                        invert.beam = 'beam_U_' + str(subband).zfill(3)
                        invert.imsize = self.polarisation_qu_imsize
                        invert.cell = self.polarisation_qu_cellsize
                        invert.stokes = 'u'
                        invert.line = 'channel,1,' + str(subband + 1) + ',1,1'
                        invert.slop = 1
                        invert.robust = -2
                        invert.go()
                    except:
                        logger.warning('Beam ' + self.beam + ': No Stokes U data for subband ' + str(subband).zfill(3) + ' !')
                    # Check if map was created successfully get the std and clean it
                    if os.path.isdir('map_U_' + str(subband).zfill(3)):
                        immin, immax, imstd = imstats.getimagestats(self, 'map_U_' + str(subband).zfill(3))
                        clean = lib.miriad('clean')  # Clean the image down to the calculated threshold
                        clean.map = 'map_U_' + str(subband).zfill(3)
                        clean.beam = 'beam_U_' + str(subband).zfill(3)
                        clean.out = 'model_U_' + str(subband).zfill(3)
                        clean.cutoff = imstd * self.polarisation_qu_clean_sigma
                        clean.niters = 10000
                        clean.region = '"' + 'mask(mask_QU)' + '"'
                        clean.go()
                        restor = lib.miriad('restor')  # Create the restored image
                        restor.model = 'model_U_' + str(subband).zfill(3)
                        restor.beam = 'beam_U_' + str(subband).zfill(3)
                        restor.map = 'map_U_' + str(subband).zfill(3)
                        restor.out = 'image_U_' + str(subband).zfill(3)
                        restor.mode = 'clean'
                        restor.go()
                    if os.path.isdir('image_U_' + str(subband).zfill(3)):
                        subs_managefiles.imagetofits(self, 'image_U_' + str(subband).zfill(3), 'image_U_' + str(subband).zfill(3) + '.umap.fits')
            else:
                logger.error('Beam ' + self.beam + ': Polarisation imaging not possible. Continuum imaging was not successful or not executed!')


    def show(self, showall=False):
        lib.show(self, 'POLARISATION', showall)