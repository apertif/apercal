import logging

import numpy as np
import os
import astropy.io.fits as pyfits
import glob
import aipy

from apercal.modules.base import BaseModule
from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles

from apercal.libs import lib
from apercal.subs import imstats
from apercal.subs.param import get_param_def
from apercal.subs import param as subs_param
from apercal.subs import readmirhead
from apercal.subs import masking
from apercal.subs import qa

logger = logging.getLogger(__name__)


class polarisation(BaseModule):
    """
    Polarisation class to create Stokes Q-, U-, and V-images and perform RM-Synthesis.
    """
    module_name = 'POLARISATION'

    poldir = None
    contdir = None
    selfcaldir = None

    polarisation_qu = None
    polarisation_qu_startsubband = None
    polarisation_qu_endsubband = None
    polarisation_qu_nsubband = None
    polarisation_qu_imsize = None
    polarisation_qu_cellsize = None
    polarisation_qu_clean_sigma = None
    polarisation_qu_cube = None
    polarisation_qu_cube_delete = None
    polarisation_v = None
    polarisation_v_imsize = None
    polarisation_v_cellsize = None
    polarisation_v_clean_sigma = None


    def __init__(self, file_=None, **kwargs):
        self.default = lib.load_config(self, file_)
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)

    def go(self):
        """
        Executes the polarisation imaging process in the following order
        quimaging
        qucube
        vimaging
        """
        logger.info("Starting POLARISATION IMAGING")
        self.quimaging()
        self.qucube()
        self.vimaging()
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

        nsbs = (self.polarisation_qu_endsubband - self.polarisation_qu_startsubband) + 1

        polarisationtargetbeamsqustatus = get_param_def(self, pbeam + '_targetbeams_qu_status', False)
        polarisationtargetbeamsqumapstatus = get_param_def(self, pbeam + '_targetbeams_qu_mapstatus', np.full((nsbs/self.polarisation_qu_nsubband, 2), False))
        polarisationtargetbeamsqubeamstatus = get_param_def(self, pbeam + '_targetbeams_qu_beamstatus', np.full((nsbs/self.polarisation_qu_nsubband, 2), False))
        polarisationtargetbeamsqumodelstatus = get_param_def(self, pbeam + '_targetbeams_qu_modelstatus', np.full((nsbs/self.polarisation_qu_nsubband, 2), False))
        polarisationtargetbeamsquimagestatus = get_param_def(self, pbeam + '_targetbeams_qu_imagestatus', np.full((nsbs/self.polarisation_qu_nsubband, 2), False))
        polarisationtargetbeamsquimagestats = get_param_def(self, pbeam + '_targetbeams_qu_imagestats', np.full((nsbs/self.polarisation_qu_nsubband, 3, 2), np.nan))
        polarisationtargetbeamsqubeamparams = get_param_def(self, pbeam + '_targetbeams_qu_beamparams', np.full((nsbs/self.polarisation_qu_nsubband, 3, 2), np.nan))

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
                    for s,subband in enumerate(range(self.polarisation_qu_startsubband, self.polarisation_qu_endsubband + 1, self.polarisation_qu_nsubband)):
                        try:
                            invert = lib.miriad('invert')  # Create the dirty image
                            invert.vis = datasetname
                            invert.map = 'map_Q_' + str(s).zfill(3)
                            invert.beam = 'beam_Q_' + str(s).zfill(3)
                            invert.imsize = self.polarisation_qu_imsize
                            invert.cell = self.polarisation_qu_cellsize
                            invert.stokes = 'q'
                            invert.line = 'channel,1,' + str(subband+1) + ',' + str(self.polarisation_qu_nsubband) + ',1'
                            invert.slop = 1
                            invert.robust = -2
                            invert.go()
                            if not maskregrid:  # Regrid the mask from continuum mf
                                regrid = lib.miriad('regrid')
                                regrid.in_ = 'mask_QU'
                                regrid.out = 'mask_QU_regrid'
                                regrid.axes = '1,2'
                                regrid.tin = 'map_Q_' + str(s).zfill(3)
                                regrid.go()
                                if os.path.isdir('mask_QU_regrid'):
                                    subs_managefiles.director(self, 'rm', 'mask_QU')
                                    subs_managefiles.director(self, 'rn', 'mask_QU', file_='mask_QU_regrid')
                                    # blank the corners of the mask
                                    masking.blank_corners(self, 'mask_QU', self.polarisation_qu_imsize)
                                    maskregrid = True
                                else:
                                    logger.warning('Beam ' + self.beam + ': Mask could not be successfully regridded! Aborting Q-/U-imaging')
                                    break
                            # Check the dirty map
                            if os.path.isdir('map_Q_' + str(s).zfill(3)):
                                polarisationtargetbeamsqumapstatus[s, 0] = True
                                if qa.checkdirtyimage(self, 'map_Q_' + str(s).zfill(3)):
                                    polarisationtargetbeamsqumapstatus[s, 0] = True
                                else:
                                    polarisationtargetbeamsqumapstatus[s, 0] = False
                            else:
                                polarisationtargetbeamsqumapstatus[s, 0] = False
                            # Check the beam
                            if os.path.isdir('beam_Q_' + str(s).zfill(3)):
                                polarisationtargetbeamsqubeamstatus[s, 0] = True
                            else:
                                polarisationtargetbeamsqubeamstatus[s, 0] = False
                            # Check if map was created successfully get the std and clean it
                            if os.path.isdir('map_Q_' + str(s).zfill(3)) and os.path.isdir('beam_Q_' + str(s).zfill(3)):
                                immin, immax, imstd = imstats.getimagestats(self, 'map_Q_' + str(s).zfill(3))
                                clean = lib.miriad('clean')  # Clean the image down to the calculated threshold
                                clean.map = 'map_Q_' + str(s).zfill(3)
                                clean.beam = 'beam_Q_' + str(s).zfill(3)
                                clean.out = 'model_Q_' + str(s).zfill(3)
                                clean.cutoff = imstd * self.polarisation_qu_clean_sigma
                                clean.niters = 10000
                                clean.region = '"' + 'mask(mask_QU)' + '"'
                                clean.go()
                                if os.path.isdir('model_Q_' + str(s).zfill(3)):
                                    if qa.checkmodelpolimage(self, 'model_Q_' + str(s).zfill(3)):
                                        polarisationtargetbeamsqumodelstatus[s, 0] = True
                                    else:
                                        polarisationtargetbeamsqumodelstatus[s, 0] = False
                                # Create the restored image
                                if polarisationtargetbeamsqumodelstatus[s, 0]:
                                    restor = lib.miriad('restor')  # Create the restored image
                                    restor.model = 'model_Q_' + str(s).zfill(3)
                                    restor.beam = 'beam_Q_' + str(s).zfill(3)
                                    restor.map = 'map_Q_' + str(s).zfill(3)
                                    restor.out = 'image_Q_' + str(s).zfill(3)
                                    restor.mode = 'clean'
                                    restor.go()
                                    if os.path.isdir('image_Q_' + str(s).zfill(3)):
                                        if qa.checkrestoredpolimage(self, 'image_Q_' + str(s).zfill(3)):
                                            polarisationtargetbeamsquimagestatus[s, 0] = True
                                        else:
                                            polarisationtargetbeamsquimagestatus[s, 0] = False
                                else:
                                    polarisationtargetbeamsquimagestatus[s, 0] = False
                            if polarisationtargetbeamsquimagestatus[s, 0]:
                                polarisationtargetbeamsquimagestats[s, :, 0] = imstats.getimagestats(self, 'image_Q_' + str(s).zfill(3))
                                polarisationtargetbeamsqubeamparams[s, :, 0] = readmirhead.getbeamimage('image_Q_' + str(s).zfill(3))
                            else:
                                continue
                        except RuntimeError:
                            polarisationtargetbeamsqumapstatus[s, 0] = False
                            polarisationtargetbeamsqubeamstatus[s, 0] = False
                            polarisationtargetbeamsqumodelstatus[s, 0] = False
                            polarisationtargetbeamsquimagestatus[s, 0] = False
                            polarisationtargetbeamsquimagestats[s, :, 0] = [np.nan, np.nan, np.nan]
                            polarisationtargetbeamsqubeamparams[s, :, 0] = [np.nan, np.nan, np.nan]
                            logger.warning('Beam ' + self.beam + ': No Stokes Q data for image ' + str(s).zfill(3) + '!')
                        # Do the same for Stokes U
                    for s, subband in enumerate(range(self.polarisation_qu_startsubband, self.polarisation_qu_endsubband + 1, self.polarisation_qu_nsubband)):
                        try:
                            invert = lib.miriad('invert')  # Create the dirty image
                            invert.vis = datasetname
                            invert.map = 'map_U_' + str(s).zfill(3)
                            invert.beam = 'beam_U_' + str(s).zfill(3)
                            invert.imsize = self.polarisation_qu_imsize
                            invert.cell = self.polarisation_qu_cellsize
                            invert.stokes = 'u'
                            invert.line = 'channel,1,' + str(subband+1) + ',' + str(self.polarisation_qu_nsubband) + ',1'
                            invert.slop = 1
                            invert.robust = -2
                            invert.go()
                            if not maskregrid:  # Regrid the mask from continuum mf
                                regrid = lib.miriad('regrid')
                                regrid.in_ = 'mask_QU'
                                regrid.out = 'mask_QU_regrid'
                                regrid.axes = '1,2'
                                regrid.tin = 'map_U_' + str(s).zfill(3)
                                regrid.go()
                                if os.path.isdir('mask_QU_regrid'):
                                    subs_managefiles.director(self, 'rm', 'mask_QU')
                                    subs_managefiles.director(self, 'rn', 'mask_QU', file_='mask_QU_regrid')
                                    # blank the corners of the mask
                                    masking.blank_corners(self, 'mask_QU', self.polarisation_qu_imsize)
                                    maskregrid = True
                                else:
                                    logger.warning('Beam ' + self.beam + ': Mask could not be successfully regridded! Aborting Q-/U-imaging')
                                    break
                            # Check the dirty map
                            if os.path.isdir('map_U_' + str(s).zfill(3)):
                                polarisationtargetbeamsqumapstatus[s, 1] = True
                                if qa.checkdirtyimage(self, 'map_U_' + str(s).zfill(3)):
                                    polarisationtargetbeamsqumapstatus[s, 1] = True
                                else:
                                    polarisationtargetbeamsqumapstatus[s, 1] = False
                            else:
                                polarisationtargetbeamsqumapstatus[s, 1] = False
                            # Check the beam
                            if os.path.isdir('beam_U_' + str(s).zfill(3)):
                                polarisationtargetbeamsqubeamstatus[s, 1] = True
                            else:
                                polarisationtargetbeamsqubeamstatus[s, 1] = False
                            # Check if map was created successfully get the std and clean it
                            if os.path.isdir('map_U_' + str(s).zfill(3)) and os.path.isdir('beam_U_' + str(s).zfill(3)):
                                immin, immax, imstd = imstats.getimagestats(self, 'map_U_' + str(s).zfill(3))
                                clean = lib.miriad('clean')  # Clean the image down to the calculated threshold
                                clean.map = 'map_U_' + str(s).zfill(3)
                                clean.beam = 'beam_U_' + str(s).zfill(3)
                                clean.out = 'model_U_' + str(s).zfill(3)
                                clean.cutoff = imstd * self.polarisation_qu_clean_sigma
                                clean.niters = 10000
                                clean.region = '"' + 'mask(mask_QU)' + '"'
                                clean.go()
                                if os.path.isdir('model_U_' + str(s).zfill(3)):
                                    if qa.checkmodelpolimage(self, 'model_U_' + str(s).zfill(3)):
                                        polarisationtargetbeamsqumodelstatus[s, 1] = True
                                    else:
                                        polarisationtargetbeamsqumodelstatus[s, 1] = False
                                # Create the restored image
                                if polarisationtargetbeamsqumodelstatus[s, 1]:
                                    restor = lib.miriad('restor')  # Create the restored image
                                    restor.model = 'model_U_' + str(s).zfill(3)
                                    restor.beam = 'beam_U_' + str(s).zfill(3)
                                    restor.map = 'map_U_' + str(s).zfill(3)
                                    restor.out = 'image_U_' + str(s).zfill(3)
                                    restor.mode = 'clean'
                                    restor.go()
                                    if os.path.isdir('image_U_' + str(s).zfill(3)):
                                        if qa.checkrestoredpolimage(self, 'image_U_' + str(s).zfill(3)):
                                            polarisationtargetbeamsquimagestatus[s, 1] = True
                                        else:
                                            polarisationtargetbeamsquimagestatus[s, 1] = False
                                else:
                                    polarisationtargetbeamsquimagestatus[s, 1] = False
                            if polarisationtargetbeamsquimagestatus[s, 1]:
                                polarisationtargetbeamsquimagestats[s, :, 1] = imstats.getimagestats(self, 'image_U_' + str(s).zfill(3))
                                polarisationtargetbeamsqubeamparams[s, :, 1] = readmirhead.getbeamimage('image_U_' + str(s).zfill(3))
                            else:
                                continue
                        except RuntimeError:
                            polarisationtargetbeamsqumapstatus[s, 1] = False
                            polarisationtargetbeamsqubeamstatus[s, 1] = False
                            polarisationtargetbeamsqumodelstatus[s, 1] = False
                            polarisationtargetbeamsquimagestatus[s, 1] = False
                            polarisationtargetbeamsquimagestats[s, :, 1] = [np.nan, np.nan, np.nan]
                            polarisationtargetbeamsqubeamparams[s, :, 1] = [np.nan, np.nan, np.nan]
                            logger.warning('Beam ' + self.beam + ': No Stokes U data for image ' + str(s).zfill(3) + '!')
                    # Check the results of the imaging
                    nQimages = np.sum(polarisationtargetbeamsquimagestatus[:, 0])
                    nUimages = np.sum(polarisationtargetbeamsquimagestatus[:, 1])
                    logger.info('Beam ' + self.beam + ': ' + str(nQimages) + '/' + str(nsbs/self.polarisation_qu_nsubband) + ' Stokes Q-images were created successfully!')
                    logger.info('Beam ' + self.beam + ': ' + str(nUimages) + '/' + str(nsbs/self.polarisation_qu_nsubband) + ' Stokes U-images were created successfully!')
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


    def qucube(self):
        """
        Combines the created Q- and U-images into a cube
        """
        subs_setinit.setinitdirs(self)

        pbeam = 'polarisation_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the creation of the cubes

        nsbs = (self.polarisation_qu_endsubband - self.polarisation_qu_startsubband) + 1

        polarisationtargetbeamsqucubeQ = get_param_def(self, pbeam + '_targetbeams_qu_cubeQ', False)
        polarisationtargetbeamsqucubeU = get_param_def(self, pbeam + '_targetbeams_qu_cubeU', False)

        if self.polarisation_qu_cube:
            subs_setinit.setinitdirs(self)
            subs_setinit.setdatasetnamestomiriad(self)
            subs_managefiles.director(self, 'ch', self.poldir)
            if not polarisationtargetbeamsqucubeQ:
                # Create a three dimensional array with NaNs for the Q cube
                qcube = np.full((nsbs/self.polarisation_qu_nsubband, self.polarisation_qu_imsize, self.polarisation_qu_imsize), np.nan)
                # Insert the images into the cube
                polarisationtargetbeamsquimagestatus = get_param_def(self, pbeam + '_targetbeams_qu_imagestatus', np.full((nsbs / self.polarisation_qu_nsubband, 2), False))
                for q in range(nsbs/self.polarisation_qu_nsubband):
                    if os.path.isdir('image_Q_' + str(q).zfill(3)) and polarisationtargetbeamsquimagestatus[q, 0]:
                        subs_managefiles.imagetofits(self, 'image_Q_' + str(q).zfill(3), 'image_Q_' + str(q).zfill(3) + '.fits', remove=False)
                        qimage = pyfits.open('image_Q_' + str(q).zfill(3) + '.fits')
                        qdata = qimage[0].data
                        qcube[q,:,:] = np.squeeze(qdata)
                    else:
                        pass
                # Get some information from the selfcal dataset
                uvq = aipy.miriad.UV(self.selfcaldir + '/' + self.target)
                chan1 = uvq['sfreq'] * 1E9
                chandelt = uvq['sdf'] * 1E9
                qfiles = glob.glob('image_Q_*.fits')
                if len(qfiles) > 0:
                    qfirst = pyfits.open(qfiles[0])
                    qfirst_hdr = qfirst[0].header
                    qfirst_hdr['NAXIS'] = 3
                    qfirst_hdr['CRVAL3'] = chan1 + ((self.polarisation_qu_nsubband-1.0)/2.0) * chandelt
                    qfirst_hdr['CDELT3'] = self.polarisation_qu_nsubband * chandelt
                    qfirst[0].header = qfirst_hdr
                    qfirst[0].data = qcube
                    qfirst.writeto('Qcube.fits')
                    qfirst.close()
                    if os.path.isfile('Qcube.fits'):
                        logger.info('Beam ' + self.beam + ': Stokes Q-cube created successfully!')
                        polarisationtargetbeamsqucubeQ = True
                    else:
                        logger.error('Beam ' + self.beam + ': Stokes Q-cube was not created successfully!')
                        polarisationtargetbeamsqucubeQ = False
                else:
                    logger.error('Beam ' + self.beam + ': No Q-files available! Cannot create Q-cube!')
                    polarisationtargetbeamsqucubeQ = False
            else:
                logger.info('Beam ' + self.beam + ': Q-cube was already created successfully!')

            if not polarisationtargetbeamsqucubeU:
                # Create a three dimensional array with NaNs for the U cube
                ucube = np.full((nsbs / self.polarisation_qu_nsubband, self.polarisation_qu_imsize, self.polarisation_qu_imsize), np.nan)
                # Insert the images into the cube
                polarisationtargetbeamsquimagestatus = get_param_def(self, pbeam + '_targetbeams_qu_imagestatus', np.full((nsbs / self.polarisation_qu_nsubband, 2), False))
                for u in range(nsbs / self.polarisation_qu_nsubband):
                    if os.path.isdir('image_U_' + str(u).zfill(3)) and polarisationtargetbeamsquimagestatus[u, 1]:
                        subs_managefiles.imagetofits(self, 'image_U_' + str(u).zfill(3), 'image_U_' + str(u).zfill(3) + '.fits', remove=False)
                        uimage = pyfits.open('image_U_' + str(u).zfill(3) + '.fits')
                        udata = uimage[0].data
                        ucube[u, :, :] = np.squeeze(udata)
                    else:
                        pass
                # Get some information from the selfcal dataset
                uvu = aipy.miriad.UV(self.selfcaldir + '/' + self.target)
                chan1 = uvu['sfreq'] * 1E9
                chandelt = uvu['sdf'] * 1E9
                ufiles = glob.glob('image_U_*.fits')
                if len(ufiles) > 0:
                    ufirst = pyfits.open(ufiles[0])
                    ufirst_hdr = ufirst[0].header
                    ufirst_hdr['NAXIS'] = 3
                    ufirst_hdr['CRVAL3'] = chan1 + ((self.polarisation_qu_nsubband - 1.0) / 2.0) * chandelt
                    ufirst_hdr['CDELT3'] = self.polarisation_qu_nsubband * chandelt
                    ufirst[0].header = ufirst_hdr
                    ufirst[0].data = ucube
                    ufirst.writeto('Ucube.fits')
                    ufirst.close()
                    if os.path.isfile('Ucube.fits'):
                        logger.info('Beam ' + self.beam + ': Stokes U-cube created successfully!')
                        polarisationtargetbeamsqucubeU = True
                    else:
                        logger.error('Beam ' + self.beam + ': Stokes U-cube was not created successfully!')
                        polarisationtargetbeamsqucubeU = False
                else:
                    logger.error('Beam ' + self.beam + ': No U-files available! Cannot create Q-cube!')
                    polarisationtargetbeamsqucubeU = False
            else:
                logger.info('Beam ' + self.beam + ': U-cube was already created successfully!')
            if polarisationtargetbeamsqucubeQ and polarisationtargetbeamsqucubeU and self.polarisation_qu_cube_delete:
                subs_managefiles.director(self, 'rm', 'beam_Q_*')
                subs_managefiles.director(self, 'rm', 'beam_U_*')
                subs_managefiles.director(self, 'rm', 'image_Q_*')
                subs_managefiles.director(self, 'rm', 'image_U_*')
                subs_managefiles.director(self, 'rm', 'map_Q_*')
                subs_managefiles.director(self, 'rm', 'map_U_*')
                subs_managefiles.director(self, 'rm', 'model_Q_*')
                subs_managefiles.director(self, 'rm', 'model_U_*')
                subs_managefiles.director(self, 'rm', 'mask_QU')

        # Save the derived parameters to the parameter file

        subs_param.add_param(self, pbeam + '_targetbeams_qu_cubeQ', polarisationtargetbeamsqucubeQ)
        subs_param.add_param(self, pbeam + '_targetbeams_qu_cubeU', polarisationtargetbeamsqucubeU)


    def vimaging(self):
        """
        Creates a mfs Stokes V image
        """
        subs_setinit.setinitdirs(self)

        sbeam = 'selfcal_B' + str(self.beam).zfill(2)
        cbeam = 'continuum_B' + str(self.beam).zfill(2)
        pbeam = 'polarisation_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the polarisation imaging

        polarisationtargetbeamsvstatus = get_param_def(self, pbeam + '_targetbeams_v_status', False)
        polarisationtargetbeamsvmapstatus = get_param_def(self, pbeam + '_targetbeams_v_mapstatus', False)
        polarisationtargetbeamsvbeamstatus = get_param_def(self, pbeam + '_targetbeams_v_beamstatus', False)
        polarisationtargetbeamsvmodelstatus = get_param_def(self, pbeam + '_targetbeams_v_modelstatus', False)
        polarisationtargetbeamsvimagestatus = get_param_def(self, pbeam + '_targetbeams_v_imagestatus', False)
        polarisationtargetbeamsvimagestats = get_param_def(self, pbeam + '_targetbeams_v_imagestats', np.full((3), np.nan))
        polarisationtargetbeamsvbeamparams = get_param_def(self, pbeam + '_targetbeams_v_beamparams', np.full((3), np.nan))

        if self.polarisation_v:
            subs_setinit.setinitdirs(self)
            subs_setinit.setdatasetnamestomiriad(self)
            subs_managefiles.director(self, 'ch', self.poldir)
            if not polarisationtargetbeamsvstatus:
                logger.info('Beam ' + self.beam + ': Stokes V-imaging')
                # Get the status of the continuum imaging
                continuumtargetbeamsmfstatus = get_param_def(self, cbeam + '_targetbeams_mf_status', False)
                if continuumtargetbeamsmfstatus:
                    # Copy over the last mask from the mf continuum imaging to use for the whole polarisation imaging
                    continuumtargetbeamsmffinalminor = subs_param.get_param(self, cbeam + '_targetbeams_mf_final_minorcycle')
                    subs_managefiles.director(self, 'cp', 'mask_mf_V', file_=self.contdir + '/mask_mf_' + str(continuumtargetbeamsmffinalminor).zfill(2))
                    # Get the status of the selfcal for the specified beam
                    selfcaltargetbeamsampstatus = get_param_def(self, sbeam + '_targetbeams_amp_status', False)
                    selfcaltargetbeamsphasestatus = get_param_def(self, sbeam + '_targetbeams_phase_status', False)
                    selfcaltargetbeamsphasestatus = True
                    if selfcaltargetbeamsampstatus:
                        datasetname = self.get_target_path().rstrip('.mir') + '_amp.mir'
                    elif selfcaltargetbeamsphasestatus:
                        datasetname = self.get_target_path()
                    else:
                        logger.error('Beam ' + self.beam + ': Amplitude nor phase self-calibration was successful! Not creating Stokes V images!')
                    # Iterate over the subbands to create Q images
                    maskregridv = False
                    try:
                        invert = lib.miriad('invert')  # Create the dirty image
                        invert.vis = datasetname
                        invert.map = 'map_mf_V'
                        invert.beam = 'beam_mf_V'
                        invert.imsize = self.polarisation_v_imsize
                        invert.cell = self.polarisation_v_cellsize
                        invert.stokes = 'v'
                        invert.options = 'mfs,sdb,double'
                        invert.slop = 1
                        invert.robust = -2
                        invert.go()
                    except RuntimeError:
                        polarisationtargetbeamsvmapstatus = False
                        polarisationtargetbeamsvbeamstatus = False
                        polarisationtargetbeamsvmodelstatus = False
                        polarisationtargetbeamsvimagestatus = False
                        polarisationtargetbeamsvimagestats[:] = [np.nan, np.nan, np.nan]
                        polarisationtargetbeamsvbeamparams[:] = [np.nan, np.nan, np.nan]
                        logger.warning('Beam ' + self.beam + ': No Stokes V data available!')
                    if not maskregridv:  # Regrid the mask from continuum mf
                        regrid = lib.miriad('regrid')
                        regrid.in_ = 'mask_mf_V'
                        regrid.out = 'mask_mf_V_regrid'
                        regrid.axes = '1,2'
                        regrid.tin = 'map_mf_V'
                        regrid.go()
                        if os.path.isdir('mask_mf_V_regrid'):
                            subs_managefiles.director(self, 'rm', 'mask_mf_V')
                            subs_managefiles.director(self, 'rn', 'mask_mf_V', file_='mask_mf_V_regrid')
                            # blank the corners of the mask
                            masking.blank_corners(self, 'mask_mf_V', self.polarisation_qu_imsize)
                            maskregridv = True
                        else:
                            logger.warning('Beam ' + self.beam + ': Mask could not be successfully regridded! Aborting V-imaging')
                    # Check the dirty map
                    if os.path.isdir('map_mf_V'):
                        polarisationtargetbeamsvmapstatus = True
                        if qa.checkdirtyimage(self, 'map_mf_V'):
                            polarisationtargetbeamsvmapstatus = True
                        else:
                            polarisationtargetbeamsvmapstatus = False
                    else:
                        polarisationtargetbeamsvmapstatus = False
                    # Check the beam
                    if os.path.isdir('beam_mf_V'):
                        polarisationtargetbeamsvbeamstatus = True
                    else:
                        polarisationtargetbeamsvbeamstatus = False
                    # Check if map was created successfully get the std and clean it
                    if os.path.isdir('map_mf_V') and os.path.isdir('beam_mf_V'):
                        immin, immax, imstd = imstats.getimagestats(self, 'map_mf_V')
                        mfclean = lib.miriad('mfclean')  # Clean the image down to the calculated threshold
                        mfclean.map = 'map_mf_V'
                        mfclean.beam = 'beam_mf_V'
                        mfclean.out = 'model_mf_V'
                        mfclean.cutoff = imstd * self.polarisation_v_clean_sigma
                        mfclean.niters = 25000
                        mfclean.region = '"' + 'mask(mask_mf_V)' + '"'
                        mfclean.go()
                        if os.path.isdir('model_mf_V'):
                            if qa.checkmodelpolimage(self, 'model_mf_V'):
                                polarisationtargetbeamsvmodelstatus = True
                            else:
                                polarisationtargetbeamsvmodelstatus = False
                        # Create the restored image
                        if polarisationtargetbeamsvmodelstatus:
                            restor = lib.miriad('restor')  # Create the restored image
                            restor.model = 'model_mf_V'
                            restor.beam = 'beam_mf_V'
                            restor.map = 'map_mf_V'
                            restor.out = 'image_mf_V'
                            restor.mode = 'clean'
                            restor.go()
                            if os.path.isdir('image_mf_V'):
                                if qa.checkrestoredpolimage(self, 'image_mf_V'):
                                    polarisationtargetbeamsvimagestatus = True
                                else:
                                    polarisationtargetbeamsvimagestatus = False
                        else:
                            polarisationtargetbeamsvimagestatus = False
                    if polarisationtargetbeamsvimagestatus:
                        polarisationtargetbeamsvimagestats[:] = imstats.getimagestats(self, 'image_mf_V')
                        polarisationtargetbeamsvbeamparams[:] = readmirhead.getbeamimage('image_mf_V')
                        subs_managefiles.imagetofits(self, 'image_mf_V', 'image_mf_V.fits')
                        logger.info('Beam ' + self.beam + ': Stokes V-imaging successful!')
                else:
                    logger.error('Beam ' + self.beam + ': Stokes V imaging not possible. Continuum imaging was not successful or not executed!')
            else:
                logger.info('Beam ' + self.beam + ': V-imaging was already successfully executed before!')

        subs_param.add_param(self, pbeam + '_targetbeams_v_status', polarisationtargetbeamsvstatus)
        subs_param.add_param(self, pbeam + '_targetbeams_v_mapstatus', polarisationtargetbeamsvmapstatus)
        subs_param.add_param(self, pbeam + '_targetbeams_v_beamstatus', polarisationtargetbeamsvbeamstatus)
        subs_param.add_param(self, pbeam + '_targetbeams_v_modelstatus', polarisationtargetbeamsvmodelstatus)
        subs_param.add_param(self, pbeam + '_targetbeams_v_imagestatus', polarisationtargetbeamsvimagestatus)
        subs_param.add_param(self, pbeam + '_targetbeams_v_imagestats', polarisationtargetbeamsvimagestats)
        subs_param.add_param(self, pbeam + '_targetbeams_v_beamparams', polarisationtargetbeamsvbeamparams)


    def show(self, showall=False):
        lib.show(self, 'POLARISATION', showall)


    def reset(self):
        """
        Function to reset the current step and remove all generated polarisation data for the current beam. Be careful! Deletes all data generated in
        this step!
        """
        subs_managefiles.director(self, 'ch', self.basedir)
        b = self.beam
        pbeam = 'polarisation_B' + str(b).zfill(2)
        if os.path.isdir(self.basedir + str(b).zfill(2) + '/' + self.polsubdir):
            logger.warning('Beam ' + str(b).zfill(2) + ': Deleting all polarisation data.')
            subs_managefiles.director(self, 'rm', self.basedir + str(b).zfill(2) + '/' + self.polsubdir)
            logger.warning('Beam ' + str(b).zfill(2) + ': Deleting all parameter file entries for POLARISATION module.')
            subs_param.del_param(self, pbeam + '_targetbeams_qu_status')
            subs_param.del_param(self, pbeam + '_targetbeams_qu_mapstatus')
            subs_param.del_param(self, pbeam + '_targetbeams_qu_beamstatus')
            subs_param.del_param(self, pbeam + '_targetbeams_qu_modelstatus')
            subs_param.del_param(self, pbeam + '_targetbeams_qu_imagestatus')
            subs_param.del_param(self, pbeam + '_targetbeams_qu_imagestats')
            subs_param.del_param(self, pbeam + '_targetbeams_qu_beamparams')
            subs_param.del_param(self, pbeam + '_targetbeams_qu_cubeQ')
            subs_param.del_param(self, pbeam + '_targetbeams_qu_cubeU')
            subs_param.del_param(self, pbeam + '_targetbeams_v_status')
            subs_param.del_param(self, pbeam + '_targetbeams_v_mapstatus')
            subs_param.del_param(self, pbeam + '_targetbeams_v_beamstatus')
            subs_param.del_param(self, pbeam + '_targetbeams_v_modelstatus')
            subs_param.del_param(self, pbeam + '_targetbeams_v_imagestatus')
            subs_param.del_param(self, pbeam + '_targetbeams_v_imagestats')
            subs_param.del_param(self, pbeam + '_targetbeams_v_beamparams')

        else:
            logger.warning('Beam ' + str(b).zfill(2) + ': No polarisation data present.')


    def reset_all(self):
        """
        Function to reset the current step and remove all generated polarisation data for the all beams. Be careful! Deletes all data generated in
        this step!
        """
        subs_managefiles.director(self, 'ch', self.basedir)
        for b in range(self.NBEAMS):
            pbeam = 'polarisation_B' + str(b).zfill(2)
            if os.path.isdir(self.basedir + str(b).zfill(2) + '/' + self.polsubdir):
                logger.warning('Beam ' + str(b).zfill(2) + ': Deleting all polarisation data.')
                subs_managefiles.director(self, 'rm', self.basedir + str(b).zfill(2) + '/' + self.polsubdir)
                logger.warning('Beam ' + str(b).zfill(2) + ': Deleting all parameter file entries for POLARISATION module.')
                subs_param.del_param(self, pbeam + '_targetbeams_qu_status')
                subs_param.del_param(self, pbeam + '_targetbeams_qu_mapstatus')
                subs_param.del_param(self, pbeam + '_targetbeams_qu_beamstatus')
                subs_param.del_param(self, pbeam + '_targetbeams_qu_modelstatus')
                subs_param.del_param(self, pbeam + '_targetbeams_qu_imagestatus')
                subs_param.del_param(self, pbeam + '_targetbeams_qu_imagestats')
                subs_param.del_param(self, pbeam + '_targetbeams_qu_beamparams')
                subs_param.del_param(self, pbeam + '_targetbeams_qu_cubeQ')
                subs_param.del_param(self, pbeam + '_targetbeams_qu_cubeU')
                subs_param.del_param(self, pbeam + '_targetbeams_v_status')
                subs_param.del_param(self, pbeam + '_targetbeams_v_mapstatus')
                subs_param.del_param(self, pbeam + '_targetbeams_v_beamstatus')
                subs_param.del_param(self, pbeam + '_targetbeams_v_modelstatus')
                subs_param.del_param(self, pbeam + '_targetbeams_v_imagestatus')
                subs_param.del_param(self, pbeam + '_targetbeams_v_imagestats')
                subs_param.del_param(self, pbeam + '_targetbeams_v_beamparams')
            else:
                logger.warning('Beam ' + str(b).zfill(2) + ': No polarisation data present.')