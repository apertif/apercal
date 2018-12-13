import logging

import numpy as np
import pandas as pd
import os

from apercal.modules.base import BaseModule
from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles
from apercal.subs import readmirhead as subs_readmirhead
from apercal.subs import imstats as subs_imstats
from apercal.subs import param as subs_param
from apercal.subs import combim as subs_combim
from apercal.subs.param import get_param_def
from apercal.libs import lib

logger = logging.getLogger(__name__)


class mosaic(BaseModule):
    """
    Mosaic class to produce mosaics of continuum, line and polarisation images.
    """
    module_name = 'MOSAIC'

    mosdir = None
    mosaic_continuum_stack = None
    mosaic_continuum_chunks = None
    mosaic_line = None
    mosaic_polarisation = None

    def __init__(self, file_=None, **kwargs):
        self.default = lib.load_config(self, file_)
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)

    def go(self):
        """
        Executes the mosaicing process in the following order
        mosaic_continuum
        mosaic_line
        mosaic_polarisation
        """
        logger.info("Starting MOSAICKING ")
        self.mosaic_continuum_images()
        self.mosaic_continuum_chunk_images()
        self.mosaic_line_cubes()
        self.mosaic_stokes_images()
        logger.info("MOSAICKING done ")

    def mosaic_continuum_images(self):
        """Looks for all available stacked continuum images and mosaics them into one large image."""
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)

        ##########################################################################################################
        # Check if the parameter is already in the parameter file and load it otherwise create the needed arrays #
        ##########################################################################################################

        # Status of the input images for the mosaicing
        stacked_inputstatus = get_param_def(self, 'mosaic_continuum_stacked_beams_inputstatus', np.full(self.NBEAMS, False))

        # Status of the continuum imaging
        stacked_continuumstatus = get_param_def(self, 'mosaic_continuum_stacked_beams_continuumstatus',
                                                np.full(self.NBEAMS, False))

        # Status of the copy of the images
        stacked_copystatus = get_param_def(self, 'mosaic_continuum_stacked_beams_copystatus', np.full(self.NBEAMS, False))

        # Status of the convolved images
        stacked_convolstatus = get_param_def(self, 'mosaic_continuum_stacked_beams_convolstatus',
                                             np.full(self.NBEAMS, False))

        # Was the image accepted based on the synthesised beam?
        stacked_beamstatus = get_param_def(self, 'mosaic_continuum_stacked_beams_beamstatus', np.full(self.NBEAMS, False))

        # Beam sizes of the input images
        stacked_inputsynthbeamparams = get_param_def(self, 'mosaic_continuum_stacked_beams_inputsynthbeamparams',
                                                     np.full((self.NBEAMS, 3), np.nan))

        # Image statistics of the input images
        stacked_inputimagestats = get_param_def(self, 'mosaic_continuum_stacked_beams_inputimagestats',
                                                np.full((self.NBEAMS, 3), np.nan))

        # RMS of the stacked input images
        stacked_inputrms = get_param_def(self, 'mosaic_continuum_stacked_beams_inputrms', np.full(self.NBEAMS, np.nan))

        # Weights of the stacked input images (normalised to one)
        stacked_inputweights = get_param_def(self, 'mosaic_continuum_stacked_beams_inputweights',
                                             np.full(self.NBEAMS, np.nan))

        # Reason for rejecting an image
        stacked_rejreason = get_param_def(self, 'mosaic_continuum_stacked_beams_rejreason',
                                          np.full(self.NBEAMS, '', dtype='U50'))

        # Synthesised beam parameters for the final stacked continuum mosaic
        stackbeam = get_param_def(self, 'mosaic_continuum_stacked_beams_synthbeamparams', np.full(3, np.nan))

        # Status of the final stacked mosaic
        stacked_imagestatus = get_param_def(self, 'mosaic_continuum_stacked_beams_imagestatus', False)

        # Start the mosaicing of the stacked continuum images
        if self.mosaic_continuum_stack:
            logger.info(' Starting mosaicing of stacked continuum images')
            subs_managefiles.director(self, 'ch', self.mosdir + '/continuum')
            # Check if the mosaicked image is already there
            if os.path.isfile(self.target.rstrip('.mir') + '_contmosaic.fits'):
                logger.warning(' Stacked continuum mosaic already present.')
            else:
                # Check the status of the stacked continuum image
                for b in np.arange(self.NBEAMS):
                    if subs_param.check_param(self, 'continuum_B' + str(b).zfill(2) + '_stackedimagestatus'):
                        stacked_inputstatus[b] = subs_param.get_param(self, 'continuum_B' + str(b).zfill(
                            2) + '_stackedimagestatus')
                        if stacked_inputstatus[b]:
                            stacked_continuumstatus[b] = True
                            logger.debug(
                                'Continuum imaging for Beam ' + str(b).zfill(2) + ' successful. Added in mosaicing! #')
                        else:
                            stacked_continuumstatus[b] = False
                            stacked_rejreason[b] = 'Continuum imaging not successful'
                            logger.warning('Continuum imaging for Beam ' + str(b).zfill(
                                2) + ' not successful. Not added in mosaicing! #')
                    else:
                        stacked_inputstatus[b] = False
                        stacked_continuumstatus[b] = False
                        stacked_rejreason[b] = 'No data available'
                        logger.warning('No data avaialble for Beam ' + str(b).zfill(2) + '. Not added in mosaicing! #')

                # Copy the continuum images over to the mosaic directory
                for b in np.arange(self.NBEAMS):
                    if stacked_inputstatus[b]:
                        subs_managefiles.director(self, 'cp', str(b).zfill(2), file_=self.basedir + '/' + str(b).zfill(
                            2) + '/' + self.contsubdir + '/' + self.target.rstrip('.mir') + '_stack')
                        if os.path.isdir(str(b).zfill(2)):
                            stacked_copystatus[b] = True
                            logger.debug('Successfully copied continuum image for Beam ' + str(b).zfill(2) + '! #')
                        else:
                            stacked_inputstatus[b] = False
                            stacked_copystatus[b] = False
                            stacked_rejreason[b] = 'Copying of continuum image not successful'
                            logger.warning('Copying the continuum image for Beam ' + str(b).zfill(
                                2) + ' was not successful. Not added in mosaicing! #')
                    else:
                        pass

                # Get the parameters for the copied images
                for b in np.arange(self.NBEAMS):
                    if stacked_inputstatus[b]:
                        stacked_inputsynthbeamparams[b, :] = subs_readmirhead.getbeamimage(str(b).zfill(2))
                        stacked_inputimagestats[b, :] = subs_imstats.getimagestats(self, str(b).zfill(2))
                        stacked_inputrms[b] = np.nansum(subs_param.get_param(self, 'continuum_B' + str(b).zfill(
                            2) + '_imcombweights') * subs_param.get_param(self, 'continuum_B' + str(b).zfill(
                            2) + '_imcombrms'))
                    else:
                        pass

                # Calculate the common beam and make a list of accepted and rejected beams and update the parameters
                # for the parameter file
                avbeamlist = np.where(stacked_inputstatus)[0]
                notavbeamlist = np.where(not stacked_inputstatus)[0]
                avbeams = [str(x).zfill(2) for x in list(avbeamlist)]
                notavbeams = [str(x).zfill(2) for x in list(notavbeamlist)]
                beamarray = stacked_inputsynthbeamparams[avbeamlist, :]
                rejbeams, stackbeam = subs_combim.calc_synbeam(avbeams, beamarray)
                stacked_beamstatus = stacked_inputstatus
                if len(rejbeams) == 0:
                    logger.debug('No beams are rejected due to synthesised beam parameters. #')
                else:
                    for rb in rejbeams:
                        avbeams.remove(rb)
                        notavbeams.extend(rb)
                        logger.warning('Stacked image of beam ' + str(rb).zfill(
                            2) + ' was rejected due to synthesised beam parameters! #')
                        stacked_inputstatus[int(rb)] = False
                        stacked_beamstatus[int(rb)] = False
                        stacked_rejreason[int(rb)] = 'Synthesised beam parameters'
                    sorted(avbeams)
                    sorted(notavbeams)

                logger.info('Final beam size is fwhm = ' + str(stackbeam[0]) + ' arcsec , ' + str(
                    stackbeam[1]) + ' arcsec, pa = ' + str(stackbeam[2]) + ' deg')

                # Convol the individual stacked images to the same synthesised beam
                convolimages = ''
                for b in np.arange(self.NBEAMS):
                    if stacked_inputstatus[b]:
                        convol = lib.miriad('convol')
                        convol.map = str(b).zfill(2)
                        convol.fwhm = str(stackbeam[0]) + ',' + str(stackbeam[1])
                        convol.pa = str(stackbeam[2])
                        convol.out = 'c' + str(b).zfill(2)
                        convol.options = 'final'
                        convol.go()
                        if os.path.isdir('c' + str(b).zfill(2)):  # Check if the convolved image was created
                            logger.debug('Convolved image of beam ' + str(b).zfill(2) + ' created successfully! #')
                            convmin, convmax, convstd = subs_imstats.getimagestats(self, str(b).zfill(2))
                            if convstd != np.nan and convmax <= 10000 and convmin >= -10:  # Check if the image is valid
                                convolimages = convolimages + convol.out + ','
                                stacked_convolstatus[b] = True
                                logger.debug('Convolved image of beam ' + str(b).zfill(2) + ' is valid! #')
                            else:
                                stacked_inputstatus[b] = False
                                stacked_convolstatus[b] = False
                                stacked_rejreason[b] = 'Convolved image not valid'
                                logger.warning('Convolved image of beam ' + str(b).zfill(2) +
                                               ' is empty or shows high values! #')
                        else:
                            stacked_inputstatus[b] = False
                            stacked_convolstatus[b] = False
                            stacked_rejreason[b] = 'Convolved image not created'
                            logger.warning('Convolved image of beam ' + str(b).zfill(2) +
                                           ' could not successfully be created! #')
                    else:
                        pass

                # Finally combine the images using linmos
                rmsrej = stacked_inputrms
                for b in np.arange(self.NBEAMS):
                    if stacked_inputstatus[b]:
                        pass
                    else:
                        rmsrej[b] = np.nan
                stacked_inputweights = ((1 / rmsrej ** 2.0) / np.nansum((1 / rmsrej ** 2.0))) / np.nanmean(
                    ((1 / rmsrej ** 2.0) / np.nansum((1 / rmsrej ** 2.0))))
                linmosrms = list(stacked_inputrms[~np.isnan(stacked_inputrms)])
                linmos = lib.miriad('linmos')
                linmos.in_ = convolimages.rstrip(',')
                linmos.rms = ','.join(str(e) for e in linmosrms)
                linmos.out = self.target.rstrip('.mir') + '_contmosaic'
                linmos.go()

                # Check if the final image is there, is valid and convert to fits
                if os.path.isdir(self.target.rstrip('.mir') + '_contmosaic'):
                    logger.debug('Stacked continuum mosaic created successfully! #')
                    contmosmin, contmosmax, contmosstd = subs_imstats.getimagestats(self, self.target.rstrip(
                        '.mir') + '_contmosaic')
                    # Check if the image is valid
                    if contmosstd != np.nan and contmosmax <= 10000 and contmosmin >= -10:
                        logger.debug('Stacked continuum mosaic image is valid! #')
                        subs_managefiles.imagetofits(self, self.target.rstrip('.mir') + '_contmosaic',
                                                     self.target.rstrip('.mir') + '_contmosaic.fits')
                        stacked_imagestatus = True
                        for b in np.arange(self.NBEAMS):  # Remove the obsolete files
                            subs_managefiles.director(self, 'rm', self.target.rstrip('.mir') + '_contmosaic')
                            subs_managefiles.director(self, 'rm', str(b).zfill(2))
                            subs_managefiles.director(self, 'rm', 'c' + str(b).zfill(2))
                        logger.debug('Removed all obsolete files #')
                        logger.info(' Mosaicing of stacked continuum images successful!')
                    else:
                        stacked_imagestatus = False
                        logger.warning('Final stacked continuum mosaic is empty or shows high values! #')
                else:
                    stacked_imagestatus = False
                    logger.warning('Final stacked continuum mosaic could not be created! #')

            logger.info(' Mosaicing of stacked continuum images done')

            # Save the derived parameters to the parameter file

            subs_param.add_param(self, 'mosaic_continuum_stacked_beams_inputstatus', stacked_inputstatus)
            subs_param.add_param(self, 'mosaic_continuum_stacked_beams_inputsynthbeamparams',
                                 stacked_inputsynthbeamparams)
            subs_param.add_param(self, 'mosaic_continuum_stacked_beams_inputimagestats', stacked_inputimagestats)
            subs_param.add_param(self, 'mosaic_continuum_stacked_beams_inputrms', stacked_inputrms)
            subs_param.add_param(self, 'mosaic_continuum_stacked_beams_inputweights', stacked_inputweights)
            subs_param.add_param(self, 'mosaic_continuum_stacked_beams_rejreason', stacked_rejreason)
            subs_param.add_param(self, 'mosaic_continuum_stacked_beams_synthbeamparams', stackbeam)
            subs_param.add_param(self, 'mosaic_continuum_stacked_beams_imagestatus', stacked_imagestatus)
            subs_param.add_param(self, 'mosaic_continuum_stacked_beams_continuumstatus', stacked_continuumstatus)
            subs_param.add_param(self, 'mosaic_continuum_stacked_beams_copystatus', stacked_copystatus)
            subs_param.add_param(self, 'mosaic_continuum_stacked_beams_convolstatus', stacked_convolstatus)
            subs_param.add_param(self, 'mosaic_continuum_stacked_beams_beamstatus', stacked_beamstatus)

    # Continuum mosaicing of the individual chunk images
    def mosaic_continuum_chunk_images(self):
        """Mosaics the continuum images from the different frequency chunks."""
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)
        nch = len(subs_param.get_param(self, 'continuum_B00_stackstatus'))

        # Check if the parameter is already in the parameter file and load it otherwise create the needed arrays #

        # Status of the input chunk images for the mosaicing
        chunks_inputstatus = get_param_def(self, 'mosaic_continuum_chunks_beams_inputstatus', np.full((self.NBEAMS, nch),
                                                                                                      False))

        # Beam sizes of the input images
        chunks_inputsynthbeamparams = get_param_def(self, 'mosaic_continuum_chunks_beams_inputsynthbeamparams',
                                                    np.full((self.NBEAMS, nch, 3), np.nan))

        # Image statistics of the input images
        chunks_inputimagestats = get_param_def(self, 'mosaic_continuum_chunks_beams_inputimagestats',
                                               np.full((self.NBEAMS, nch, 3), np.nan))

        # RMS of the input chunk images
        chunks_inputrms = get_param_def(self, 'mosaic_continuum_chunks_beams_inputrms',
                                        np.full((self.NBEAMS, nch), np.nan))

        # Was the image accepted based on the synthesised beam?
        chunks_beamstatus = get_param_def(self, 'mosaic_continuum_chunks_beams_beamstatus', np.full((self.NBEAMS, nch),
                                                                                                    False))

        # Reason for rejecting an image
        chunks_rejreason = get_param_def(self, 'mosaic_continuum_chunks_beams_rejreason',
                                         np.full((self.NBEAMS, nch), '', dtype='U50'))

        # Weights of the individual input images (normalised to one)
        chunks_inputweights = get_param_def(self, 'mosaic_continuum_chunks_beams_inputweights', np.full((self.NBEAMS, nch),
                                                                                                        np.nan))

        # Synthesised beam parameters for the final continuum chunk mosaics
        chunks_beams = get_param_def(self, 'mosaic_continuum_chunks_beams_synthbeamparams', np.full((nch, 3),
                                                                                                    np.nan))

        # Last executed clean iteration for the continuum images
        chunks_iterations = get_param_def(self, 'mosaic_continuum_chunks_beams_iterations', np.full((self.NBEAMS, nch),
                                                                                                    np.nan))

        # Status of the input chunk images for the mosaicing
        chunks_continuumstatus = get_param_def(self, 'mosaic_continuum_chunks_beams_continuumstatus',
                                               np.full((self.NBEAMS, nch),
                                                       False))

        # Status of the copying of the individual chunk images
        chunks_copystatus = get_param_def(self, 'mosaic_continuum_chunks_beams_copystatus',
                                          np.full((self.NBEAMS, nch), False))

        # Status of the convolution of the individual chunk images
        chunks_convolstatus = get_param_def(self, 'mosaic_continuum_chunks_beams_convolstatus', np.full((self.NBEAMS, nch),
                                                                                                        False))

        # Status of the final chunk mosaics
        chunks_imagestatus = get_param_def(self, 'mosaic_continuum_chunks_beams_imagestatus',
                                           np.full(nch, False))

        # Start the mosaicing of the individual chunks
        if self.mosaic_continuum_chunks:
            logger.info(' Starting mosaicing of continuum images of individual frequency chunks')
            subs_managefiles.director(self, 'ch', self.mosdir + '/continuum')

            for c in np.arange(nch):
                # Check if a continuum image for a chunk is already present
                if os.path.isfile(self.target.rstrip('.mir') + '_contmosaic' + '_chunk_' + str(c).zfill(2) + '.fits'):
                    logger.warning(' Continuum mosaic for chunk ' + str(c).zfill(2) + ' already present.')
                else:

                    # Check for which chunks continuum imaging was successful
                    for b in np.arange(self.NBEAMS):  # Get the status from the continuum entry of the parameter file
                        if subs_param.check_param(self, 'continuum_B' + str(b).zfill(2) + '_imagestatus'):
                            chunks_inputstatus[b, c] = \
                                subs_param.get_param(self, 'continuum_B' + str(b).zfill(2) + '_imagestatus')[c, -1]
                            if chunks_inputstatus[b, c]:
                                chunks_continuumstatus[b, c] = True
                                chunks_iterations[b, c] = \
                                    subs_param.get_param(self, 'continuum_B' + str(b).zfill(2) + '_minoriterations')[c]
                                logger.debug(
                                    'Continuum imaging for frequency chunk ' + str(c).zfill(2) + ' of beam ' + str(
                                        b).zfill(2) + ' successful! Added in mosaicing! #')
                            else:
                                chunks_continuumstatus[b, c] = False
                                chunks_iterations[b, c] = np.nan
                                chunks_rejreason[b, c] = 'Continuum imaging not successful'
                                logger.warning(
                                    'Continuum imaging for frequency chunk ' + str(c).zfill(2) + ' of beam ' + str(
                                        b).zfill(2) + ' not successful! Not added in mosaicing! #')
                        else:
                            chunks_rejreason[b, c] = 'No data available'
                            logger.warning(
                                'No data availbale for chunk ' + str(c).zfill(2) + ' of beam ' + str(b).zfill(
                                    2) + '! Not added in mosaicing! #')

                    # Run through each chunk and copy the available images
                    for b in np.arange(self.NBEAMS):
                        if chunks_inputstatus[b, c]:
                            subs_managefiles.director(self, 'cp', 'C' + str(c).zfill(2) + 'B' + str(b).zfill(2),
                                                      self.basedir + str(b).zfill(
                                                          2) + '/' + self.contsubdir + '/' + 'stack' + '/' + str(
                                                          c).zfill(2) + '/' + 'image_' + str(
                                                          int(chunks_iterations[b, c])).zfill(2))
                            if os.path.isdir('C' + str(c).zfill(2) + 'B' + str(b).zfill(2)):
                                chunks_copystatus[b, c] = True
                                logger.debug('Successfully copyied image of frequency chunk ' + str(c).zfill(
                                    2) + ' of beam ' + str(b).zfill(2) + '! #')
                            else:
                                chunks_inputstatus[b, c] = False
                                chunks_copystatus[b, c] = False
                                chunks_rejreason[b, c] = 'Copy of continuum image not successful'
                                logger.warning(
                                    'Copying image of frequency chunk ' + str(c).zfill(2) + ' of beam ' + str(b).zfill(
                                        2) + ' failed! #')

                    # Get the parameters for each image
                    for b in np.arange(self.NBEAMS):
                        if chunks_inputstatus[b, c]:
                            chunks_inputsynthbeamparams[b, c, :] = subs_readmirhead.getbeamimage(
                                'C' + str(c).zfill(2) + 'B' + str(b).zfill(2))
                            chunks_inputimagestats[b, c, :] = subs_imstats.getimagestats(self, 'C' + str(c).zfill(
                                2) + 'B' + str(b).zfill(2))
                            chunks_inputrms[b, c] = \
                                subs_param.get_param(self, 'continuum_B' + str(b).zfill(2) + '_residualstats')[
                                    c, int(chunks_iterations[b, c]), 2]
                        else:
                            pass

                    # Calculate the common beam for each frequency chunk and make a list of accepted and rejected
                    # beams and update the parameters for the parameter file
                    avbeamlist = np.where(chunks_inputstatus[:, c])[0]
                    notavbeamlist = np.where(not chunks_inputstatus[:, c])[0]
                    avbeams = [str(x).zfill(2) for x in list(avbeamlist)]
                    notavbeams = [str(x).zfill(2) for x in list(notavbeamlist)]
                    beamarray = chunks_inputsynthbeamparams[avbeamlist, c, :]
                    rejbeams, chunks_beams[c, :] = subs_combim.calc_synbeam(avbeams, beamarray)
                    chunks_beamstatus[:, c] = chunks_inputstatus[:, c]
                    if len(rejbeams) == 0:
                        logger.debug(
                            'No beams are rejected due to synthesised beam parameters for chunk ' + str(c).zfill(
                                2) + '! #')
                    else:
                        for rb in rejbeams:
                            avbeams.remove(rb)
                            notavbeams.extend(rb)
                            logger.warning('Stacked image of beam ' + str(rb).zfill(2) + ' for chunk ' + str(c).zfill(
                                2) + ' was rejected due to synthesised beam parameters! #')
                            chunks_inputstatus[int(rb), c] = False
                            chunks_beamstatus[int(rb), c] = False
                            chunks_rejreason[int(rb), c] = 'Synthesised beam parameters'
                    sorted(avbeams)
                    sorted(notavbeams)

                    logger.info('Final beam size for chunk ' + str(c).zfill(2) + ' is fwhm = ' + str(
                        chunks_beams[c, 0]) + ' arcsec , ' + str(chunks_beams[c, 1]) + ' arcsec, pa = ' + str(
                        chunks_beams[c, 2]) + ' deg')

                    # Convol the individual frequency chunk images to the same synthesised beam
                    for b in np.arange(self.NBEAMS):
                        if chunks_inputstatus[b, c]:
                            convol = lib.miriad('convol')
                            convol.map = 'C' + str(c).zfill(2) + 'B' + str(b).zfill(2)
                            convol.fwhm = str(chunks_beams[c, 0]) + ',' + str(chunks_beams[c, 1])
                            convol.pa = str(chunks_beams[c, 2])
                            convol.out = 'c' + 'C' + str(c).zfill(2) + 'B' + str(b).zfill(2)
                            convol.options = 'final'
                            convol.go()
                            if os.path.isdir('c' + 'C' + str(c).zfill(2) + 'B' + str(b).zfill(
                                    2)):  # Check if the convolved image was created
                                convmin, convmax, convstd = subs_imstats.getimagestats(self, 'c' + 'C' + str(c).zfill(
                                    2) + 'B' + str(b).zfill(2))
                                # Check if the image is valid
                                if convstd != np.nan and convmax <= 10000 and convmin >= -10:
                                    chunks_convolstatus[b, c] = True
                                    logger.debug(
                                        'Convolution of image of beam ' + str(b).zfill(2) + ' for chunk ' + str(
                                            c).zfill(2) + ' successful! #')
                                else:
                                    chunks_inputstatus[b, c] = False
                                    chunks_convolstatus[b, c] = False
                                    chunks_rejreason[b, c] = 'Convolved image not valid'
                                    logger.warning(
                                        'Convolved image of beam ' + str(b).zfill(2) + ' for chunk ' + str(c).zfill(
                                            2) + ' is empty or shows high values! #')
                            else:
                                chunks_inputstatus[b, c] = False
                                chunks_convolstatus[b, c] = False
                                chunks_rejreason[b, c] = 'Convolved image not created'
                                logger.warning(
                                    'Convolved image of beam ' + str(b).zfill(2) + ' for chunk ' + str(c).zfill(
                                        2) + ' could not successfully be created! #')
                        else:
                            pass

                    # Finally combine the images using linmos
                    rmsrej = chunks_inputrms[:, c]
                    convolimages = ''
                    rms = ''
                    for b in np.arange(self.NBEAMS):
                        if chunks_inputstatus[b, c]:
                            convolimages = convolimages + 'c' + 'C' + str(c).zfill(2) + 'B' + str(b).zfill(2) + ','
                            rms = rms + str(chunks_inputrms[b, c]) + ','
                        else:
                            rmsrej[b] = np.nan
                    chunks_inputweights[:, c] = ((1.0 / np.square(rmsrej)) / np.nansum(
                        1.0 / np.square(rmsrej))) / np.nanmean(
                        ((1.0 / np.square(rmsrej)) / np.nansum(1.0 / np.square(rmsrej))))
                    linmos = lib.miriad('linmos')
                    linmos.in_ = convolimages.rstrip(',')
                    linmos.rms = rms.rstrip(',')
                    linmos.out = self.target.rstrip('.mir') + '_contmosaic' + '_chunk_' + str(c).zfill(2)
                    linmos.go()

                    # Check if the final images are there, are valid and convert them to fits
                    if os.path.isdir(self.target.rstrip('.mir') + '_contmosaic' + '_chunk_' + str(c).zfill(2)):
                        logger.debug('Continuum mosaic of chunk ' + str(c).zfill(2) + ' created successfully! #')
                        contmosmin, contmosmax, contmosstd = subs_imstats.getimagestats(self, self.target.rstrip(
                            '.mir') + '_contmosaic' + '_chunk_' + str(c).zfill(2))

                        # Check if the image is valid
                        if contmosstd != np.nan and contmosmax <= 10000 and contmosmin >= -10:
                            logger.debug('Continuum mosaic of chunk ' + str(c).zfill(2) + ' is valid! #')
                            subs_managefiles.imagetofits(self,
                                                         self.target.rstrip('.mir') + '_contmosaic' + '_chunk_' + str(
                                                             c).zfill(2),
                                                         self.target.rstrip('.mir') + '_contmosaic' + '_chunk_' + str(
                                                             c).zfill(2) + '.fits')
                            chunks_imagestatus[c] = True
                            for b in np.arange(self.NBEAMS):  # Remove the obsolete files
                                subs_managefiles.director(self, 'rm',
                                                          self.target.rstrip('.mir') + '_contmosaic' + '_chunk_' + str(
                                                              c).zfill(2))
                                subs_managefiles.director(self, 'rm', 'C' + str(c).zfill(2) + 'B' + str(b).zfill(2))
                                subs_managefiles.director(self, 'rm',
                                                          'c' + 'C' + str(c).zfill(2) + 'B' + str(b).zfill(2))
                            logger.debug('Removed all obsolete files #')
                            logger.info(' Mosaicing of continuum images successful for chunk ' + str(c).zfill(2) + '!')
                        else:
                            chunks_imagestatus[c] = False
                            logger.warning(
                                'Final continuum mosaic is empty or shows high values for chunk ' + str(c).zfill(
                                    2) + '! #')
                    else:
                        chunks_imagestatus[c] = False
                        logger.warning(
                            'Final continuum mosaic could not be created for chunk ' + str(c).zfill(2) + '! #')

            logger.info(' Mosaicing of continuum images for individual frequency chunks done')

            # Save the derived parameters to the parameter file

            subs_param.add_param(self, 'mosaic_continuum_chunks_beams_inputstatus', chunks_inputstatus)
            subs_param.add_param(self, 'mosaic_continuum_chunks_beams_inputsynthbeamparams',
                                 chunks_inputsynthbeamparams)
            subs_param.add_param(self, 'mosaic_continuum_chunks_beams_inputimagestats', chunks_inputimagestats)
            subs_param.add_param(self, 'mosaic_continuum_chunks_beams_inputrms', chunks_inputrms)
            subs_param.add_param(self, 'mosaic_continuum_chunks_beams_inputweights', chunks_inputweights)
            subs_param.add_param(self, 'mosaic_continuum_chunks_beams_iterations', chunks_iterations)
            subs_param.add_param(self, 'mosaic_continuum_chunks_beams_rejreason', chunks_rejreason)
            subs_param.add_param(self, 'mosaic_continuum_chunks_beams_synthbeamparams', chunks_beams)
            subs_param.add_param(self, 'mosaic_continuum_chunks_beams_imagestatus', chunks_imagestatus)
            subs_param.add_param(self, 'mosaic_continuum_chunks_beams_continuumstatus', chunks_continuumstatus)
            subs_param.add_param(self, 'mosaic_continuum_chunks_beams_copystatus', chunks_copystatus)
            subs_param.add_param(self, 'mosaic_continuum_chunks_beams_convolstatus', chunks_convolstatus)
            subs_param.add_param(self, 'mosaic_continuum_chunks_beams_beamstatus', chunks_beamstatus)

    # Mosaicing of line cubes #

    def mosaic_line_cubes(self):
        """Creates a mosaicked line cube of all the individual line cubes from the different beams"""
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)
        if self.mosaic_line:
            logger.error(' Mosaicing of line cubes not implemented yet')

    def mosaic_stokes_images(self):
        """Creates a mosaic of all the Stokes Q- and U-cubes from the different beams"""
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)
        if self.mosaic_polarisation:
            logger.error(' Mosaicing of Stokes cubes not implemented yet')

    def summary_continuumstacked(self):
        """
        Creates a general summary of the parameters in the parameter file generated during the mosaicing of the
        tacked continuum images. A more detailed summary can be generated by the detailed_summary_continuumstacked
        function.

        returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in the
                           notebook
        """

        # Load the parameters from the parameter file

        IS = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_inputstatus')
        WG = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_inputweights')
        RR = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_rejreason')

        # Create the data frame

        beam_indices = range(self.NBEAMS)
        beam_indices = [str(item).zfill(2) for item in beam_indices]

        df_is = pd.DataFrame(np.ndarray.flatten(IS), index=beam_indices, columns=['Image accepted?'])
        df_wg = pd.DataFrame(np.ndarray.flatten(WG), index=beam_indices, columns=['Weight'])
        df_rr = pd.DataFrame(np.ndarray.flatten(RR), index=beam_indices, columns=['Reason'])

        df = pd.concat([df_is, df_wg, df_rr], axis=1)

        return df

    def detailed_summary_continuumstacked(self):
        """
        Creates a detailed summary of the parameters in the parameter file generated during the mosaicing of the
        stacked continuum images.

        returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in the
                             notebook
        """

        # Load the parameters from the parameter file

        CS = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_continuumstatus')
        CP = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_copystatus')
        SBEAMS = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_inputsynthbeamparams')
        BS = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_beamstatus')
        CV = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_convolstatus')
        WG = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_inputweights')
        RMS = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_inputrms')
        IS = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_inputstatus')

        # Create the data frame

        beam_indices = range(self.NBEAMS)
        beam_indices = [str(item).zfill(2) for item in beam_indices]

        df_cs = pd.DataFrame(np.ndarray.flatten(CS), index=beam_indices, columns=['Continuum calibration?'])
        df_cp = pd.DataFrame(np.ndarray.flatten(CP), index=beam_indices, columns=['Copy successful?'])
        df_bmaj = pd.DataFrame(np.around(np.ndarray.flatten(SBEAMS[:, 0]), decimals=2), index=beam_indices,
                               columns=['Bmaj ["]'])
        df_bmin = pd.DataFrame(np.around(np.ndarray.flatten(SBEAMS[:, 1]), decimals=2), index=beam_indices,
                               columns=['Bmin ["]'])
        df_bpa = pd.DataFrame(np.around(np.ndarray.flatten(SBEAMS[:, 2]), decimals=2), index=beam_indices,
                              columns=['Bpa [deg]'])
        df_bs = pd.DataFrame(np.ndarray.flatten(BS), index=beam_indices, columns=['Beam parameters?'])
        df_cv = pd.DataFrame(np.ndarray.flatten(CV), index=beam_indices, columns=['Convol successful?'])
        df_wg = pd.DataFrame(np.ndarray.flatten(WG), index=beam_indices, columns=['Weight'])
        df_rms = pd.DataFrame(np.ndarray.flatten(RMS), index=beam_indices, columns=['Residual RMS'])
        df_is = pd.DataFrame(np.ndarray.flatten(IS), index=beam_indices, columns=['Image accepted?'])

        df = pd.concat([df_cs, df_cp, df_bmaj, df_bmin, df_bpa, df_bs, df_cv, df_wg, df_rms, df_is], axis=1)

        return df

    def summary_continuumchunks(self):
        """
        Creates a general summary of the parameters in the parameter file generated during the mosaicing of the chunk
        continuum images. A more detailed summary can be generated by the detailed_summary_continuumchunks function

        returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in the
                             notebook
        """

        # Load the parameters from the parameter file

        IS = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_imagestatus')
        SBEAMS = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_synthbeamparams')
        C = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_inputstatus')

        # Create the data frame

        chunks = len(subs_param.get_param(self, 'mosaic_continuum_chunks_beams_imagestatus'))
        chunk_indices = range(chunks)
        chunk_indices = [str(item).zfill(2) for item in chunk_indices]

        COM = np.full(chunks, 'Beam(s) ', dtype='U150')  # Comment for mosaicing
        for c in range(chunks):
            for b in range(self.NBEAMS):
                if C[b, c]:
                    pass
                else:
                    COM[c] = COM[c] + str(b).zfill(2) + ','
            COM[c] = COM[c].rstrip(',') + ' not accepted'

        df_is = pd.DataFrame(np.ndarray.flatten(IS), index=chunk_indices, columns=['Mosaic successful?'])
        df_bmaj = pd.DataFrame(np.around(np.ndarray.flatten(SBEAMS[:, 0]), decimals=2), index=chunk_indices,
                               columns=['Bmaj ["]'])
        df_bmin = pd.DataFrame(np.around(np.ndarray.flatten(SBEAMS[:, 1]), decimals=2), index=chunk_indices,
                               columns=['Bmin ["]'])
        df_bpa = pd.DataFrame(np.around(np.ndarray.flatten(SBEAMS[:, 2]), decimals=2), index=chunk_indices,
                              columns=['Bpa [deg]'])
        df_c = pd.DataFrame(np.ndarray.flatten(COM), index=chunk_indices, columns=['Comments'])

        df = pd.concat([df_is, df_bmaj, df_bmin, df_bpa, df_c], axis=1)

        return df

    def detailed_summary_continuumchunks(self, chunk=None):
        """
        Creates a detailed summary of the parameters in the parameter file generated during the mosaicing of the chunk
        continuum images.

        returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in the
                             notebook
        """

        # Load the parameters from the parameter file

        CS = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_continuumstatus')
        CP = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_copystatus')
        SBEAMS = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_inputsynthbeamparams')
        BMAJ = SBEAMS[:, :, 0]
        BMIN = SBEAMS[:, :, 1]
        BPA = SBEAMS[:, :, 2]
        BS = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_beamstatus')
        CV = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_convolstatus')
        WG = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_inputweights')
        RMS = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_inputrms')
        IS = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_inputstatus')
        RR = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_rejreason')

        # Create the data frame

        if chunk is None:
            chunks = len(subs_param.get_param(self, 'mosaic_continuum_chunks_beams_imagestatus'))
            chunk_indices = range(chunks)
            chunk_indices = [str(item).zfill(2) for item in chunk_indices]
        else:
            chunk_indices = [str(chunk).zfill(2)]
        beam_indices = range(self.NBEAMS)
        beam_indices = [str(item).zfill(2) for item in beam_indices]

        chunk_beam_indices = pd.MultiIndex.from_product([chunk_indices, beam_indices], names=['Chunk', 'Beam'])

        if chunk is None:
            df_cs = pd.DataFrame(np.ndarray.flatten(np.swapaxes(CS, 0, 1)), index=chunk_beam_indices,
                                 columns=['Continuum calibration?'])
            df_cp = pd.DataFrame(np.ndarray.flatten(np.swapaxes(CP, 0, 1)), index=chunk_beam_indices,
                                 columns=['Copy successful?'])
            df_bmaj = pd.DataFrame(np.around(np.ndarray.flatten(np.swapaxes(BMAJ, 0, 1)), decimals=2),
                                   index=chunk_beam_indices, columns=['Bmaj ["]'])
            df_bmin = pd.DataFrame(np.around(np.ndarray.flatten(np.swapaxes(BMIN, 0, 1)), decimals=2),
                                   index=chunk_beam_indices, columns=['Bmin ["]'])
            df_bpa = pd.DataFrame(np.around(np.ndarray.flatten(np.swapaxes(BPA, 0, 1)), decimals=2),
                                  index=chunk_beam_indices, columns=['Bpa [deg]'])
            df_bs = pd.DataFrame(np.ndarray.flatten(np.swapaxes(BS, 0, 1)), index=chunk_beam_indices,
                                 columns=['Beam parameters?'])
            df_cv = pd.DataFrame(np.ndarray.flatten(np.swapaxes(CV, 0, 1)), index=chunk_beam_indices,
                                 columns=['Convol successful?'])
            df_wg = pd.DataFrame(np.ndarray.flatten(np.swapaxes(WG, 0, 1)), index=chunk_beam_indices,
                                 columns=['Weight'])
            df_rms = pd.DataFrame(np.ndarray.flatten(np.swapaxes(RMS, 0, 1)), index=chunk_beam_indices,
                                  columns=['Residual RMS'])
            df_is = pd.DataFrame(np.ndarray.flatten(np.swapaxes(IS, 0, 1)), index=chunk_beam_indices,
                                 columns=['Image accepted?'])
            df_rr = pd.DataFrame(np.ndarray.flatten(np.swapaxes(RR, 0, 1)), index=chunk_beam_indices,
                                 columns=['Reason'])
        else:
            df_cs = pd.DataFrame(np.ndarray.flatten(CS[:, chunk]), index=chunk_beam_indices,
                                 columns=['Continuum calibration?'])
            df_cp = pd.DataFrame(np.ndarray.flatten(CP[:, chunk]), index=chunk_beam_indices,
                                 columns=['Copy successful?'])
            df_bmaj = pd.DataFrame(np.around(np.ndarray.flatten(BMAJ[:, chunk]), decimals=2), index=chunk_beam_indices,
                                   columns=['Bmaj ["]'])
            df_bmin = pd.DataFrame(np.around(np.ndarray.flatten(BMIN[:, chunk]), decimals=2), index=chunk_beam_indices,
                                   columns=['Bmin ["]'])
            df_bpa = pd.DataFrame(np.around(np.ndarray.flatten(BPA[:, chunk]), decimals=2), index=chunk_beam_indices,
                                  columns=['Bpa [deg]'])
            df_bs = pd.DataFrame(np.ndarray.flatten(BS[:, chunk]), index=chunk_beam_indices,
                                 columns=['Beam parameters?'])
            df_cv = pd.DataFrame(np.ndarray.flatten(CV[:, chunk]), index=chunk_beam_indices,
                                 columns=['Convol successful?'])
            df_wg = pd.DataFrame(np.ndarray.flatten(WG[:, chunk]), index=chunk_beam_indices, columns=['Weight'])
            df_rms = pd.DataFrame(np.ndarray.flatten(RMS[:, chunk]), index=chunk_beam_indices, columns=['Residual RMS'])
            df_is = pd.DataFrame(np.ndarray.flatten(IS[:, chunk]), index=chunk_beam_indices,
                                 columns=['Image accepted?'])
            df_rr = pd.DataFrame(np.ndarray.flatten(RR[:, chunk]), index=chunk_beam_indices, columns=['Reason'])

        df = pd.concat([df_cs, df_cp, df_bmaj, df_bmin, df_bpa, df_bs, df_cv, df_wg, df_rms, df_is, df_rr], axis=1)

        return df

    def reset(self):
        """
        Function to reset the current step and remove all generated data. Be careful! Deletes all data generated in
        this step!
        """
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)
        logger.warning(' Deleting all mosaicked data products.')
        subs_managefiles.director(self, 'ch', self.basedir)
        subs_managefiles.director(self, 'rm', self.mosdir)
        logger.warning(' Deleteing all parameter file entries for MOSAIC module')
        subs_param.del_param(self, 'mosaic_continuum_stacked_beams_inputstatus')
        subs_param.del_param(self, 'mosaic_continuum_stacked_beams_inputsynthbeamparams')
        subs_param.del_param(self, 'mosaic_continuum_stacked_beams_inputimagestats')
        subs_param.del_param(self, 'mosaic_continuum_stacked_beams_inputrms')
        subs_param.del_param(self, 'mosaic_continuum_stacked_beams_inputweights')
        subs_param.del_param(self, 'mosaic_continuum_stacked_beams_rejreason')
        subs_param.del_param(self, 'mosaic_continuum_stacked_beams_synthbeamparams')
        subs_param.del_param(self, 'mosaic_continuum_stacked_beams_imagestatus')
        subs_param.del_param(self, 'mosaic_continuum_stacked_beams_continuumstatus')
        subs_param.del_param(self, 'mosaic_continuum_stacked_beams_copystatus')
        subs_param.del_param(self, 'mosaic_continuum_stacked_beams_convolstatus')
        subs_param.del_param(self, 'mosaic_continuum_stacked_beams_beamstatus')
        subs_param.del_param(self, 'mosaic_continuum_chunks_beams_inputstatus')
        subs_param.del_param(self, 'mosaic_continuum_chunks_beams_inputsynthbeamparams')
        subs_param.del_param(self, 'mosaic_continuum_chunks_beams_inputimagestats')
        subs_param.del_param(self, 'mosaic_continuum_chunks_beams_inputrms')
        subs_param.del_param(self, 'mosaic_continuum_chunks_beams_inputweights')
        subs_param.del_param(self, 'mosaic_continuum_chunks_beams_iterations')
        subs_param.del_param(self, 'mosaic_continuum_chunks_beams_rejreason')
        subs_param.del_param(self, 'mosaic_continuum_chunks_beams_synthbeamparams')
        subs_param.del_param(self, 'mosaic_continuum_chunks_beams_imagestatus')
        subs_param.del_param(self, 'mosaic_continuum_chunks_beams_continuumstatus')
        subs_param.del_param(self, 'mosaic_continuum_chunks_beams_copystatus')
        subs_param.del_param(self, 'mosaic_continuum_chunks_beams_convolstatus')
        subs_param.del_param(self, 'mosaic_continuum_chunks_beams_beamstatus')
