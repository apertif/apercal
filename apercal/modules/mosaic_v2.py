import logging

import numpy as np
import os
import socket
import subprocess
import glob
import copy

from apercal.modules.base import BaseModule
from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles
from apercal.subs import readmirhead as subs_readmirhead
from apercal.subs import imstats as subs_imstats
from apercal.subs import convim as subs_convim
from apercal.subs import param as subs_param
from apercal.subs import combim as subs_combim
from apercal.subs.param import get_param_def
from apercal.libs import lib
import apercal.subs.mosaic_utils as mosaic_utils

logger = logging.getLogger(__name__)


class mosaic(BaseModule):
    """
    New mosaic class to produce mosaics.

    Implementation is based on scripts written by DJ Pisano.
    Currently, the module can only create mosaics of continuum and polarisation images.
    Line mosaics are not yet possible.

    It also only works for a single pointing but will be updated to be able to use different
    pointings

    The directory structure for the continuum mosaic is going to look like this:
        basedir
         |-> mosaic
          |-> continuum (for the continuum mosaic)
           |-> images (location of the continuum images, fits and miriad)
            |-> 01 (location of fits images)
            |-> ...
            |-> 39
           |-> beams  (location of the beam images)
           |-> mosaic (location of the output mosaic)
    """

    module_name = 'MOSAIC'

    mosdir = None

    mosaic_taskid = None
    mosaic_beams = None
    mosaic_name = None
    mosaic_continuum_image_origin = None
    mosaic_polarisation_input_origin = None
    #mosaic_projection_centre_type = None
    mosaic_projection_centre_ra = None
    mosaic_projection_centre_dec = None
    mosaic_projection_centre_beam = None
    mosaic_projection_centre_file = None
    mosaic_primary_beam_type = None
    mosaic_primary_beam_shape_files_location = None
    mosaic_common_beam_type = ''
    mosaic_continuum_mf = None
    mosaic_polarisation_v = None
    mosaic_clean_up = None

    mosaic_continuum_subdir = None
    mosaic_continuum_images_subdir = None
    mosaic_continuum_beam_subdir = None
    mosaic_continuum_mosaic_subdir = None
    mosaic_continuum_imsize = 5121
    mosaic_continuum_cellsize = 4

    FNULL = open(os.devnull, 'w')

    def __init__(self, file_=None, **kwargs):
        self.default = lib.load_config(self, file_)
        
        # check the directory
        if self.basedir is None:
            self.basedir = os.getcwd()
            logger.info("No base directory specified. Using current working directory {}".format(self.basedir))
        else:
            # check if the base directory exists
            if not os.path.exists(self.basedir):
                subs_managefiles.director(self, 'mk', self.basedir)
        # taskid will not be added to basedir to main mosaic dir
        # because mosaics can also be created with images from different taskids
        self.mosdir = self.basedir

        subs_setinit.setinitdirs(self)
            
        # get the beams
        # set the number of beams to process>
        if self.mosaic_beams is None or self.mosaic_beams != '':
            if self.mosaic_beams == "all" or self.mosaic_beams is None:
                logger.info("No list of beams specified for mosaic. Using all beams")
                self.mosaic_beam_list = [str(k).zfill(2)
                                             for k in range(self.NBEAMS)]
            else:
                logger.info("Beams specified for mosaic: {}".format(self.mosaic_beams))
                self.mosaic_beam_list = self.mosaic_beams.split(",")
        else:
            error = "No beams specified for making the mosaic."
            logger.error(error)
            raise RuntimeError(error)

        self.mosaic_continuum_image_list = []

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # The main function for the module
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def go(self):
        """
        Executes the mosaicing process in the following order

        mosaic_continuum_mf
        mosaic_continuum_chunk
        mosaic_continuum_line
        mosaic_continuum_polarisationqu
        mosaic_continuum_polarisationv
        """
        logger.info("Starting MOSAICKING ")
        self.create_mosaic_continuum_mf()
        logger.info("MOSAICKING done ")

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Just a small helper function to abort the module
    # when unfinished features are being executed
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def abort_module(self, abort_msg):
        """
        Simple function to abort the module
        """

        logger.error(abort_msg)
        logger.error("ABORT")
        raise RuntimeError(abort_msg)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to check if path on ALTA exist
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def check_alta_path(self, alta_path):
        """
        Function to quickly check the path exists on ALTA
        """
        alta_cmd = "ils {}".format(alta_path)
        logger.debug(alta_cmd)
        return_msg = subprocess.call(alta_cmd, shell=True,
                                stdout=self.FNULL, stderr=self.FNULL)
        return return_msg

    def getdata_from_alta(self, alta_file_name, output_path):
        """
        Function to get files from ALTA

        Could be done by getdata_alta package, too.
        """

        # set the irod files location
        irods_status_file = os.path.join(
            os.getcwd(), "transfer_{}_img-icat.irods-status".format(os.path.basename(alta_file_name).split(".")[0]))
        irods_status_lf_file = os.path.join(
            os.getcwd(), "transfer_{}_img-icat.lf-irods-status".format(os.path.basename(alta_file_name).split(".")[0]))

        # get the file from alta
        alta_cmd = "iget -rfPIT -X {0} --lfrestart {1} --retries 5 {2} {3}/".format(
            irods_status_file, irods_status_lf_file, alta_file_name, output_path)
        logger.debug(alta_cmd)
        return_msg = subprocess.check_call(alta_cmd, shell=True, stdout=self.FNULL, stderr=self.FNULL)

        return return_msg

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Create all the sub-directories for the mosaic
    # +++++++++++++++++++++++++++++++++++++++++++++++++++           
    def set_mosaic_subdirs(self, continuum=False):
        """
        Set the name of the subdirectories for the mosaic and create them

        """

        logger.info("Creating sub-directories for mosaic")

        # Status of the continuum mf mosaic
        mosaic_create_subdirs_status = get_param_def(
            self, 'mosaic_create_subdirs_status', False)

        if self.mosaic_continuum_mf:
            # create the directory for the continuunm mosaic
            if not self.mosaic_continuum_subdir:
                self.mosaic_continuum_subdir = 'continuum'
            self.mosaic_continuum_dir = os.path.join(self.mosdir, self.mosaic_continuum_subdir)
            if not os.path.exists(self.mosaic_continuum_dir):
                subs_managefiles.director(self, 'mk', self.mosaic_continuum_dir)

            # create the sub-directory to store the continuum images
            if not self.mosaic_continuum_images_subdir:
                self.mosaic_continuum_images_subdir = 'images'
            self.mosaic_continuum_images_dir = os.path.join(
                self.mosdir, self.mosaic_continuum_subdir, self.mosaic_continuum_images_subdir)
            if not os.path.exists(self.mosaic_continuum_images_dir):
                subs_managefiles.director(self, 'mk', self.mosaic_continuum_images_dir)

            # create the directory to store the beam maps
            if not self.mosaic_continuum_beam_subdir:
                self.mosaic_continuum_beam_subdir = 'beams'
            self.mosaic_continuum_beam_dir = os.path.join(
                self.mosdir, self.mosaic_continuum_subdir, self.mosaic_continuum_beam_subdir)
            if not os.path.exists(self.mosaic_continuum_beam_dir):
                subs_managefiles.director(self, 'mk', self.mosaic_continuum_beam_dir)

            # create the directory to store the actual mosaic
            if not self.mosaic_continuum_mosaic_subdir:
                self.mosaic_continuum_mosaic_subdir = 'mosaic'
            self.mosaic_continuum_mosaic_dir = os.path.join(
                self.mosdir, self.mosaic_continuum_subdir, self.mosaic_continuum_mosaic_subdir)
            if not os.path.exists(self.mosaic_continuum_mosaic_dir):
                subs_managefiles.director(self, 'mk', self.mosaic_continuum_mosaic_dir)
        
            logger.info("Creating sub-directories for mosaic ... Done")
            
            mosaic_create_subdirs_status = True
        else:
            pass
            
        subs_param.add_param(
            self, 'mosaic_create_subdirs_status', mosaic_create_subdirs_status)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to get the continuum images from different
    # locations depending on the config
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def get_mosaic_continuum_images(self):
        """
        Function to get the continuum images.

        Possible locations are
        1. The directories of the taskids on happili, but only if run from happili-01
        2. An existing directory with all fits files
        3. ALTA (default)

        Continuum images are put into
        """

        # Status of the continuum mf mosaic
        mosaic_continuum_images_status = get_param_def(
            self, 'mosaic_continuum_images_status', False)
        
        mosaic_failed_beams = get_param_def(
            self, 'mosaic_failed_beams', [])

        # collect here which beams failed
        failed_beams = []

        # check whether the fits files are already there:
        if not mosaic_continuum_images_status:

            # Maybe there should be an additional test of whether the continuum fits files are already there

            # # in case the data is in temporary storage as long as there is no ingest.
            # if self.mosaic_continuum_image_files_dir == "ALTA_temp":
            #     logger.info(
            #         "Assuming the data is on ALTA in temporary storage")

            #     # top-level temporary ALTA directory
            #     main_alta_temp_dir = "/altaZone/home/apertif_main/early_results/temp_storage/"

            #     # directory of the taskid on ALTA temporary storage
            #     alta_taskid_dir = os.path.join(
            #         main_alta_temp_dir, self.mosaic_taskid)

            #     # check that the directory exists (perhaps not the best way to do it)
            #     try:
            #         self.check_alta_path(alta_taskid_dir)
            #     except Exception as e:
            #         logger.error(
            #             "Could not find taskid on ALTA temporary storage. Abort")
            #         logger.exception(e)
            #         raise Exception(e)

            #     # get the data for each beam
            #     for beam in self.mosaic_beam_list:

            #         logger.info("Getting continuum image of beam {} from ALTA".format(beam))

            #         # Check first that the beam is available from ALTA
            #         alta_beam_dir = os.path.join(alta_taskid_dir, beam)
            #         try:
            #             self.check_alta_path(alta_beam_dir)
            #         except Exception as e:
            #             logger.warning(
            #                 "Beam {} not available on ALTA".format(beam))
            #             failed_beams.append(beam)
            #             continue

            #         # look for the image file (not perhaps the best way with the current setup)
            #         continuum_image_name = ''
            #         alta_beam_image_path = ''
            #         for k in range(10):
            #             continuum_image_name = "image_mf_{02d}.fits".format(k)
            #             alta_beam_image_path = os.path.join(
            #                 alta_beam_dir, continuum_image_name)
            #             try:
            #                 self.check_alta_path(alta_beam_image_path)
            #             except:
            #                 # if the last image was not found, set path back to empty
            #                 if k == 10:
            #                     continuum_image_name = ''
            #                 continue
            #             else:
            #                 break
            #         if continuum_image_name == '':
            #             logger.warning(
            #                 "Beam {} not available on ALTA".format(beam))
            #             failed_beams.append(beam)
            #             continue

            #         # Create the local directory for the beam
            #         local_beam_dir = os.path.join(
            #             self.mosaic_continuum_images_dir, beam)
            #         subs_managefiles.director(self, 'mk', local_beam_dir)

            #         # set the irod files location
            #         irods_status_file = os.path.join(
            #             self.mosaic_continuum_dir, "{}_img-icat.irods-status".format(continuum_image_name.split(".")[0]))
            #         irods_status_lf_file = os.path.join(
            #             self.mosaic_continuum_subdir, "{}_img-icat.lf-irods-status".format(continuum_image_name.split(".")[0]))

            #         # get the file from alta
            #         alta_cmd = "iget -rfPIT -X {0} --lfrestart {1} --retries 5 {2} {3}".format(
            #             irods_status_file, irods_status_lf_file, alta_beam_image_path, local_beam_dir)
            #         logger.debug(alta_cmd)
            #         try:
            #             subprocess.check_call(alta_cmd, shell=True, stdout=self.FNULL, stderr=self.FNULL)
            #         except Exception as e:
            #             logger.warning("Getting continuum image of beam {} from ALTA ... Failed".format(beam))
            #             failed_beams.append(beam)
            #             continue
            #         else:
            #             logger.info("Getting continuum image of beam {} from ALTA ... Done".format(beam))

            # in case the data is distributed over the Happilis
            # (not finished)
            # =================================================
            if self.mosaic_continuum_image_origin == "happili":
                logger.info("Assuming to get the data is on happili in the taskid directories")
                if socket.gethostname() == "happili-01":
                    # abort as it is not finished
                    self.abort_module("Using the default taskid directories to the continuum images has not been implemented yet.")
                else:
                    error = "This does not work from {}. It only works from happili 01. Abort".format(socket.gethostname())
                    logger.error(error)
                    raise RuntimeError(error)
            # in case the data is on ALTA
            # ===========================
            elif self.mosaic_continuum_image_origin == "alta" or self.mosaic_continuum_image_origin is None:
                logger.info(
                    "Assuming to get the data from ALTA")

                # store failed beams
                failed_beams = []
                # go through the list of beams
                # but make a copy to be able to remove beams if they are not available
                for beam in self.mosaic_beam_list:
                    # /altaZone/archive/apertif_main/visibilities_default/<taskid>_AP_B0XY
                    alta_taskid_beam_dir = "/altaZone/archive/apertif_main/visibilities_default/{0}_AP_B{1}".format(self.mosaic_taskid, beam.zfill(3))

                    # check that the beam is available on ALTA
                    if self.check_alta_path(alta_taskid_beam_dir) == 0:
                        logger.info("Found beam {} of taskid {} on ALTA".format(beam, self.mosaic_taskid))

                        # look for continuum image
                        # look for the image file (not perhaps the best way with the current setup)
                        continuum_image_name = ''
                        alta_beam_image_path = ''
                        for k in range(10):
                            continuum_image_name = "image_mf_{0:02d}.fits".format(k)
                            alta_beam_image_path = os.path.join(
                                alta_taskid_beam_dir, continuum_image_name)
                            if self.check_alta_path(alta_beam_image_path) == 0:
                                break
                            else:
                                # make empty again when no image was found
                                continuum_image_name = ''
                                continue
                        if continuum_image_name == '':
                            logger.warning(
                                "No image found on ALTA for beam {0} of taskid {1}".format(beam, self.mosaic_taskid))
                            failed_beams.append(beam)
                        else:
                            # create directory for beam in the image of the continuum mosaic
                            continuum_image_beam_dir = os.path.join(self.mosaic_continuum_images_dir, beam)
                            if not os.path.exists(continuum_image_beam_dir):
                                subs_managefiles.director(self, 'mk', continuum_image_beam_dir)
                            
                            # check whether file already there:
                            if not os.path.exists(os.path.join(continuum_image_beam_dir, os.path.basename(alta_beam_image_path))):
                                # copy the continuum image to this directory
                                return_msg = self.getdata_from_alta(alta_beam_image_path, continuum_image_beam_dir)
                                if return_msg == 0:
                                    logger.info("Getting image of beam {0} of taskid {1} ... Done".format(beam, self.mosaic_taskid))
                                else:
                                    logger.warning("Getting image of beam {0} of taskid {1} ... Failed".format(beam, self.mosaic_taskid))
                                    failed_beams.append(beam)
                            else:
                                logger.info("Image of beam {0} of taskid {1} already on disk".format(beam, self.mosaic_taskid))
                    else:
                        logger.warning("Did not find beam {0} of taskid {1}".format(beam, self.mosaic_taskid))
                        # remove the beam
                        failed_beams.append(beam)

            # in case a directory has been specified
            # (not stable)
            # ======================================
            elif self.mosaic_continuum_image_origin != "":
                # check that the directory exists
                logger.info(
                    "Assuming to get the data from a specific directory")
                if os.path.isdir(self.mosaic_continuum_image_origin):
                    
                    # go through the beams
                    for beam in self.mosaic_beam_list:

                        logger.info("Getting continuum image of beam {}".format(beam))

                        # check that a directory with the beam exists
                        image_beam_dir = os.path.join(self.mosaic_continuum_image_origin, beam)
                        if not os.path.isdir(image_beam_dir):
                            logger.warning("Did not find beam {} to get continuum image.".format(beam))
                            failed_beams.append(beam)
                            continue

                        # find the fits file
                        image_beam_fits_path = os.path.join(image_beam_dir, "image_mf_??.fits")
                        fits_files = glob.glob(image_beam_fits_path)
                        fits_files.sort()
                        if len(fits_files) == 0:
                            logger.warning(
                                "Did not find a continuum image 'image_mf_??.fits' for beam {}.".format(beam))
                            failed_beams.append(beam)
                            continue
                        
                        # get the highest number, though there should only be one
                        fits_file = fits_files[-1]

                        # create local beam dir only if it doesn't already exists
                        local_beam_dir = os.path.join(self.mosaic_continuum_images_dir, beam)
                        if local_beam_dir != image_beam_dir:
                            subs_managefiles.director(self, 'mk', local_beam_dir)

                            # copy the fits file to the beam directory
                            subs_managefiles.director(self, 'cp', os.path.join(local_beam_dir,os.path.basename(fits_file)), file_=fits_file)
                        else:
                            logger.info("Continuum file of beam {} is already available".format(beam))

                        logger.info("Getting continuum image of beam {} ... Done".format(beam))
                else:
                    error = "The directory {} does not exists. Abort".format(self.mosaic_continuum_image_files_dir)
                    logger.error(error)
                    raise RuntimeError(error)
            else:
                logger.info("Assuming the data is on ALTA")
                error = "Cannot get data from ALTA yet. Abort"
                logger.error(error)
                raise RuntimeError(error)
    
        else:
            logger.info("Continuum image fits files are already available.")

        # assign list of failed beams to variable that will be stored
        if len(mosaic_failed_beams) == 0:
            mosaic_failed_beams = failed_beams
        # or the other way round in case of a restart
        else:
            failed_beams = mosaic_failed_beams

        # check the failed beams
        if len(failed_beams) == len(self.mosaic_beam_list):
            self.abort_module("Did not find continuum images for all beams.")
        elif len(failed_beams) != 0:
            logger.warning("Could not find continuum images for beams {}. Removing those beams".format(str(failed_beams)))
            for beam in failed_beams:
                self.mosaic_beam_list.remove(beam)
            logger.warning("Will only process continuum images from {0} beams ({1})".format(len(self.mosaic_beam_list), str(self.mosaic_beam_list)))

            # setting parameter of getting continuum images to True
            mosaic_continuum_images_status = True
        else:
            logger.info("Found images for all beams")
            # setting parameter of getting continuum images to True
            mosaic_continuum_images_status = True
        
        subs_param.add_param(
            self, 'mosaic_failed_beams', mosaic_failed_beams)

        subs_param.add_param(
            self, 'mosaic_continuum_images_status', mosaic_continuum_images_status)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to get the beam maps
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def get_mosaic_continuum_beams(self):
        """
        Getting the information for each beam if they are not already present
        """

        logger.info("Creating beam maps")

        mosaic_continuum_beam_status = get_param_def(
            self, 'mosaic_continuum_beam_status', False)

        if not mosaic_continuum_beam_status:
            
            for beam in self.mosaic_beam_list:
                logger.info("Creating map of beam {}".format(beam))
                # change to directory of continuum images
                subs_managefiles.director(self, 'ch', self.mosaic_continuum_dir)

                try:
                    mosaic_utils.create_beam(beam, self.mosaic_continuum_beam_subdir, corrtype=self.mosaic_primary_beam_type, primary_beam_path=self.mosaic_primary_beam_shape_files_location)
                except Exception as e:
                    error = "Creating map of beam {} ... Failed".format(beam)
                    logger.warning(error)
                    logger.exception(e)
                    raise RuntimeError(error)
                else:
                    logger.info("Creating map of beam {} ... Done".format(beam))
                    mosaic_continuum_beam_status = True
        else:
            logger.info("Beam maps are already available.")

        logger.info("Creating beam maps ... Done")

        subs_param.add_param(
            self, 'mosaic_continuum_beam_status', mosaic_continuum_beam_status)
    
    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to get the projection centre based on
    # the config
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def get_mosaic_projection_centre(self):
        """
        Getting the information for the projection center
        """

        mosaic_projection_centre_status = get_param_def(
            self, 'mosaic_projection_centre_status', False)
        
        mosaic_projection_centre_values = get_param_def(
            self, 'mosaic_projection_centre_values', ['', ''])

        if self.mosaic_projection_centre_ra is not None and self.mosaic_projection_centre_dec is not None:
            logger.info("Using input projection center: RA={0} and DEC={1}".format(self.mosaic_projection_centre_ra, self.mosaic_projection_centre_dec))
            mosaic_projection_centre_status = True
        elif self.mosaic_projection_centre_beam is not None:
            logger.info("Using pointing centre of beam {} as the projection centre".format(self.mosaic_projection_centre_beam))
            
            # change to directory of continuum images
            subs_managefiles.director(self, 'ch', self.mosaic_continuum_images_dir)

            # Extract central RA and Dec for Apertif pointing from a chosen beam
            if self.mosaic_projection_centre_beam in self.mosaic_beam_list:
                gethd = lib.miriad('gethd')
                gethd.in_ = '{0}/image_{0}.map/crval1'.format(str(self.mosaic_projection_centre_beam).zfill(2))
                gethd.format = 'hms'
                ra_ref=gethd.go()
                gethd.in_ = '{0}/image_{0}.map/crval2'.format(str(self.mosaic_projection_centre_beam).zfill(2))
                gethd.format = 'dms'
                dec_ref=gethd.go()
            else:
                error = "Failed reading projection centre from beam {}. Beam not available".format(self.mosaic_projection_centre_beam)
                logger.error(error)
                raise RuntimeError(error)

            # assigning ra and dec
            self.mosaic_projection_centre_ra = ra_ref[0]
            self.mosaic_projection_centre_dec = dec_ref[0]
        elif self.mosaic_projection_centre_file != '':
            logger.info("Reading projection center from file {}".format(self.mosaic_projection_centre_file))

            # not available yet
            self.abort_module(
                "Reading projection center from file has not been implemented yet")
        else:
            self.abort_module("Did not recognise projection centre option")

        logger.info("Projection centre will be RA={0} and DEC={1}".format(self.mosaic_projection_centre_ra, self.mosaic_projection_centre_dec))

        subs_param.add_param(
            self, 'mosaic_projection_centre_status', mosaic_projection_centre_status)
        subs_param.add_param(
            self, 'mosaic_projection_centre_values', [self.mosaic_projection_centre_ra, self.mosaic_projection_centre_dec])
    
    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to convert images to miriad
    # Can be moved to mosaic_utils.py
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def convert_images_to_miriad(self):
        """
        Convert continuum fits images to miriad format

        Based on notebook function import_image(beam_num)

        At the moment the function is only successful
        if all beams were successfully.

        TODO:
            Conversion should be parallelised.
        """

        logger.info("Converting fits images to miriad images")

        mosaic_continuum_convert_fits_images_status = get_param_def(
            self, 'mosaic_continuum_convert_fits_images_status', False)

        # change to directory of continuum images
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_images_dir)

        if not mosaic_continuum_convert_fits_images_status:

            # go through the list of beams
            for beam in self.mosaic_beam_list:

                logger.info("Converting fits image of beam {} to miriad image".format(beam))

                mir_map_name = '{0}/image_{0}.map'.format(beam)

                if not os.path.isdir(mir_map_name):
                    # This function will import a FITS image into Miriad placing it in the mosaicdir
                    fits = lib.miriad('fits')
                    fits.op = 'xyin'
                    #fits.in_ = '{}/image_mf_00.fits'.format(beam)
                    fits.in_ = glob.glob(os.path.join(beam,"image_mf_0?.fits"))[0]
                    fits.out = '{0}/image_{0}.map'.format(beam)
                    fits.inp()
                    try:
                        fits.go()
                    except Exception as e:
                        mosaic_continuum_convert_fits_images_status = False
                        error = "Converting fits image of beam {} to miriad image ... Failed".format(beam)
                        logger.error(error)
                        logger.exception(e)
                        raise RuntimeError(error)
                    else:
                        mosaic_continuum_convert_fits_images_status = True
                        logger.debug("Converting fits image of beam {} to miriad image ... Done".format(beam))
                
                else:
                    logger.warning("Miriad continuum image already exists for beam {}. Did not convert from fits again".format(beam))
                    mosaic_continuum_convert_fits_images_status = True

            if mosaic_continuum_convert_fits_images_status:
                logger.info("Converting fits images to miriad images ... Successful")
            else:
                logger.warning("Converting fits images to miriad images ... Failed for at least one beam. Please check the log")
        else:
            logger.info("Images have already been converted.")
            
        subs_param.add_param(
            self, 'mosaic_continuum_convert_fits_images_status', mosaic_continuum_convert_fits_images_status)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to convert beam maps from fits to miriad
    # May not be necessary in the end.
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def convert_beams_to_miriad(self):
        """
        Convert beam fits images to miriad format

        Based on notebook function import_beam(beam_num)

        At the moment the function is only successful
        if all beams were successfully.

        TODO:
            Conversion should be parallelised.
            Could be moved to submodule taking care of creating beam maps
        """

        logger.info("Converting fits beam images to miriad images")

        mosaic_continuum_convert_fits_beam_status = get_param_def(
            self, 'mosaic_continuum_convert_fits_beam_status', False)

        # change to directory of continuum images
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_beam_dir)

        for beam in self.mosaic_beam_list:
            # This function will import the FITS image of a beam into Miriad format, placing it in the mosaicdir
            fits = lib.miriad('fits')
            fits.op = 'xyin'
            fits.in_ = 'beam_{}.fits'.format(beam)
            fits.out = 'beam_{}.map'.format(beam)
            fits.inp()
            try:
                fits.go()
            except Exception as e:
                mosaic_continuum_convert_fits_beam_status = False
                error="Converting fits image of beam {} to miriad image ... Failed".format(beam)
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)
            else:
                mosaic_continuum_convert_fits_beam_status = True
                logger.debug("Converting fits image of beam {} to miriad image ... Done".format(beam))

        if mosaic_continuum_convert_fits_beam_status:
            logger.info("Converting fits images to miriad images ... Successful")
        else:
            logger.warning("Converting fits images to miriad images ... Failed for at least one beam. Please check the log")
            
        subs_param.add_param(
            self, 'mosaic_continuum_convert_fits_beam_status', mosaic_continuum_convert_fits_beam_status)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to get the image noise for a specific beam
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def get_beam_noise(self, beam):
        """
        Function to get the image noise for a specific beam

        Based on beam_noise(beam_num) from the notebook)            
        """

        # change to directory of continuum images
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_images_dir)

        sigest = lib.miriad('sigest')
        sigest.in_ = '{0}/image_{0}.map'.format(str(beam).zfill(2))

        return sigest.go()

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to transfer image coordinates to beam maps
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def transfer_coordinates(self):
        """
        Function to transfer image coordinates to beam maps

        Based on the notebook cell

        For the proper beam maps, this should be done by the 
        function make the proper beam maps. Probably best to
        move this function there for the simple beam maps, too
        """

        logger.info("Transfer image coordinates to beam maps")

        mosaic_transfer_coordinates_to_beam_status = get_param_def(
            self, 'mosaic_transfer_coordinates_to_beam_status', False)

        # change to directory of continuum images
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_dir)

        if not mosaic_transfer_coordinates_to_beam_status:

            for beam in self.mosaic_beam_list:

                logger.info("Processing beam {}".format(beam))

                # get RA
                gethd = lib.miriad('gethd')
                gethd.in_ = os.path.join(self.mosaic_continuum_images_subdir,'{0}/image_{0}.map/crval1'.format(beam))
                try:
                    ra1=gethd.go()
                except Exception as e:
                    mosaic_transfer_coordinates_to_beam_status = False
                    error = "Reading RA of beam {} failed".format(beam)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)
                else:
                    mosaic_transfer_coordinates_to_beam_status = True
            
                # write RA
                puthd = lib.miriad('puthd')
                puthd.in_ = os.path.join(self.mosaic_continuum_beam_subdir,'beam_{}.map/crval1'.format(beam))
                puthd.value = float(ra1[0])
                try:
                    puthd.go()
                except Exception as e:
                    mosaic_transfer_coordinates_to_beam_status = False
                    error = "Writing RA of beam {} failed".format(beam)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)
                else:
                    mosaic_transfer_coordinates_to_beam_status = True
            
                # get DEC
                gethd.in_ = os.path.join(self.mosaic_continuum_images_subdir,'{0}/image_{0}.map/crval2'.format(beam))
                try:
                    dec1=gethd.go()
                except Exception as e:
                    mosaic_transfer_coordinates_to_beam_status = False
                    error = "Reading DEC of beam {} failed".format(beam)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)
                else:
                    mosaic_transfer_coordinates_to_beam_status = True
                
                # write DEC
                puthd.in_ = os.path.join(self.mosaic_continuum_beam_subdir,'beam_{}.map/crval2'.format(beam))
                puthd.value = float(dec1[0])
                try:
                    puthd.go()
                except Exception as e:
                    mosaic_transfer_coordinates_to_beam_status = False
                    error = "Writing DEC of beam {} failed".format(beam)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)
                else:
                    mosaic_transfer_coordinates_to_beam_status = True

                logger.info("Processing beam {} ... Done".format(beam))

            if mosaic_transfer_coordinates_to_beam_status:
                logger.info("Transfer image coordinates to beam maps ... Done")
            else:
                logger.info("Transfer image coordinates to beam maps ... Failed")
        else:
            logger.info("Image coordinates have already been transferred")

        subs_param.add_param(
            self, 'mosaic_transfer_coordinates_to_beam_status', mosaic_transfer_coordinates_to_beam_status)        

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to calculate a common beam to convolve images
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def get_common_beam(self):
        """
        Function to calculate a common beam to convolve images

        Based on the cell on the same synthesized beam.

        There are several options
        1. Calculate a circular beam (default)
        2. Calculate the maximum beam
        """

        logger.info("Calculate common beam for convolution")

        mosaic_common_beam_status = get_param_def(
            self, 'mosaic_common_beam_status', False)
        
        mosaic_common_beam_values = get_param_def(
            self, 'mosaic_common_beam_values', np.zeros(3))

        # change to directory of continuum images
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_images_dir)

        if not mosaic_common_beam_status:
            # this is where the beam information will be stored
            bmaj=[]
            bmin=[]
            bpa=[]

            # go through the beams and get the information
            for beam in self.mosaic_beam_list:
                gethd = lib.miriad('gethd')
                gethd.in_ = '{0}/image_{0}.map/bmaj'.format(beam)
                bmaj.append(gethd.go())
                gethd.in_ = '{0}/image_{0}.map/bmin'.format(beam)
                bmin.append(gethd.go())
                gethd.in_ = '{0}/image_{0}.map/bpa'.format(beam)
                bpa.append(gethd.go())
                
            # Calculate maximum bmaj and bmin and median bpa for final convolved beam shape
            bmajor = [float(x[0]) for x in bmaj]
            bmajor = 3600.*np.degrees(bmajor)

            bminor = [float(x[0]) for x in bmin]
            bminor = 3600.*np.degrees(bminor)

            bangle = [float(x[0]) for x in bpa]
            bangle = np.degrees(bangle)

            if self.mosaic_common_beam_type == 'circular' or self.mosaic_common_beam_type == '':
                max_axis = np.nanmax([bmajor, bminor])
                c_beam = [1.05*max_axis,1.05*max_axis,0.]
            elif self.mosaic_common_beam_type == "elliptical":    
                c_beam = [1.05*np.nanmax(bmajor),1.05*np.nanmax(bminor),np.nanmedian(bangle)]
            else:
                error = "Unknown type of common beam requested. Abort"
                logger.error(error)
                raise RuntimeError(error)

            logger.info('The final, convolved, synthesized beam has bmaj, bmin, bpa of: {}'.format(str(c_beam)))
            
            mosaic_common_beam_status = True
            mosaic_common_beam_values = c_beam
        else:
            logger.info("Common beam already available as bmaj, bmin, bpa of: {}".format(str(mosaic_common_beam_values)))

        subs_param.add_param(
            self, 'mosaic_common_beam_status', mosaic_common_beam_status)  
        
        subs_param.add_param(
            self, 'mosaic_common_beam_values', mosaic_common_beam_values)  
    
    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to create template mosaic
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def create_template_mosaic(self):
        """
        Create an template mosaic to be filled in later
        """

        logger.info("Creating template mosaic")

        mosaic_template_mosaic_status = get_param_def(
            self, 'mosaic_template_mosaic_status', False)

        template_mosaic_name = "mosaic_template.map"

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_mosaic_dir)
        
        if mosaic_template_mosaic_status and os.path.isdir(template_mosaic_name):
            logger.info("Template mosaic already exists")
        else:
            # This will create a template for the mosaic using "imgen" in Miriad
            # number of pixels of mosaic maps
            imsize=self.mosaic_continuum_imsize
            # cell size in arcsec
            cell=self.mosaic_continuum_cellsize

            # create template prior to changing projection
            imgen = lib.miriad('imgen')
            imgen.out = 'mosaic_temp_preproj.map'
            imgen.imsize = imsize
            imgen.cell = cell
            imgen.object = 'level'
            imgen.spar = '0.'
            imgen.radec = '{0},{1}'.format(str(self.mosaic_projection_centre_ra),str(self.mosaic_projection_centre_dec))
            imgen.inp()
            try:
                imgen.go()
            except Exception as e:
                error = "Error creating template mosaic image"
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)
                
            # Now change projection to NCP
            regrid = lib.miriad('regrid')
            regrid.in_ = 'mosaic_temp_preproj.map'
            regrid.out = template_mosaic_name
            regrid.project='NCP'
            try:
                regrid.go()
            except Exception as e:
                error = "Error changing projection to NCP"
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)

            # remove (moved to cleanup function)
            #shutil.rmtree(mosaicdir+'mosaic_temp.map')
            #subs_managefiles.director(self, 'rm', 'mosaic_temp_preproj.map')

            logger.info("Creating template mosaic ... Done")
            mosaic_template_mosaic_status = True

        subs_param.add_param(
            self, 'mosaic_template_mosaic_status', mosaic_template_mosaic_status) 

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to regrid images based on mosaic template
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def regrid_images(self):
        """
        Function to regrid images using the template mosaic
        """

        logger.info("Regridding images")

        mosaic_regrid_images_status = get_param_def(
            self, 'mosaic_regrid_images_status', False)

        if not mosaic_regrid_images_status:
            # switch to mosaic directory
            subs_managefiles.director(self, 'ch', self.mosaic_continuum_dir)

            # Put images on mosaic template grid
            for beam in self.mosaic_beam_list:
                logger.info("Regridding beam {}".format(beam))
                regrid = lib.miriad('regrid')
                input_file = os.path.join(self.mosaic_continuum_images_subdir, '{0}/image_{0}.map'.format(beam))
                output_file = os.path.join(self.mosaic_continuum_images_subdir, 'image_{}_regrid.map'.format(beam))
                template_mosaic_file = os.path.join(self.mosaic_continuum_mosaic_subdir, "mosaic_template.map")
                if not os.path.isdir(output_file):
                    if os.path.isdir(input_file):
                        regrid.in_ = input_file
                        regrid.out = output_file
                        regrid.tin = template_mosaic_file
                        regrid.axes = '1,2'
                        regrid.inp()
                        try:
                            regrid.go()
                        except Exception as e:
                            error = "Failed regridding image of beam {}".format(beam)
                            logger.error(error)
                            logger.exception(e)
                            raise RuntimeError(error)
                    else:
                        error = "Did not find convolved image for beam {}".format(beam)
                        logger.error(error)
                        raise RuntimeError(error)
                else:
                    logger.warning("Regridded image of beam {} already exists".format(beam))
                
            logger.info("Regridding images ... Done")
            mosaic_regrid_images_status = True
        else:
            logger.info("Images have already been regridded")

        subs_param.add_param(
            self, 'mosaic_regrid_images_status', mosaic_regrid_images_status)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to regrid beam maps based on mosaic template
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def regrid_beam_maps(self):
        """
        Function to regrid beam images using the template mosaic
        """

        logger.info("Regridding beam maps")

        mosaic_regrid_beam_maps_status = get_param_def(
            self, 'mosaic_regrid_beam_maps_status', False)

        if not mosaic_regrid_beam_maps_status:
            # switch to mosaic directory
            subs_managefiles.director(self, 'ch', self.mosaic_continuum_dir)

            # Put images on mosaic template grid
            for beam in self.mosaic_beam_list:
                input_file = os.path.join(
                    self.mosaic_continuum_images_subdir, '{0}/image_{0}.map'.format(beam))
                output_file = os.path.join(
                    self.mosaic_continuum_images_subdir, 'image_{}_regrid.map'.format(beam))
                template_mosaic_file = os.path.join(
                    self.mosaic_continuum_mosaic_subdir, "mosaic_template.map")
                regrid = lib.miriad('regrid')
                if not os.path.isdir(output_file):
                    if os.path.isdir(input_file):
                        regrid.in_ = input_file
                        regrid.out = output_file
                        regrid.tin = template_mosaic_file
                        regrid.axes = '1,2'  
                        regrid.inp()
                        try:
                            regrid.go()
                        except Exception as e:
                            error = "Failed regridding beam_maps of beam {}".format(beam)
                            logger.error(error)
                            logger.exception(e)
                            raise RuntimeError(error)
                    else:
                        error = "Did not find beam map for beam {}".format(beam)
                        logger.error(error)
                        raise RuntimeError(error)
                else:
                    logger.warning("Regridded beam map of beam {} already exists".format(beam))

            logger.info("Regridding beam maps ... Done")

            mosaic_regrid_beam_maps_status = True
        else:
            logger.info("Regridding of beam maps has already been done")

        subs_param.add_param(
            self, 'mosaic_regrid_beam_maps_status', mosaic_regrid_beam_maps_status)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to convolve images
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def mosaic_convolve_images(self):
        """
        Function to convolve images with the common beam

        Should be executed after gridding

        Note:
            Could be moved
        """


        mosaic_convolve_images_status = get_param_def(
            self, 'mosaic_convolve_images_status', False)

        mosaic_common_beam_values = get_param_def(
            self, 'mosaic_common_beam_values', np.zeros(3))

        logger.info("Convolving images with common beam with beam {}".format(mosaic_common_beam_values))

        # change to directory of continuum images
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_dir)

        if not mosaic_convolve_images_status:

            for beam in self.mosaic_beam_list:
                logger.info("Convolving image of beam {}".format(beam))

                if not os.path.isdir(os.path.join(
                    self.mosaic_continuum_mosaic_subdir, 'image_{0}_mos.map'.format(beam))):
                    convol = lib.miriad('convol')
                    convol.map = os.path.join(
                        self.mosaic_continuum_images_subdir, 'image_{0}_regrid.map'.format(beam))
                    convol.out = os.path.join(
                        self.mosaic_continuum_mosaic_subdir, 'image_{0}_mos.map'.format(beam))
                    convol.fwhm = '{0},{1}'.format(str(mosaic_common_beam_values[0]), str(mosaic_common_beam_values[1]))
                    convol.pa = mosaic_common_beam_values[2]
                    convol.options = 'final'
                    convol.inp()
                    try:
                        convol.go()
                    except Exception as e:
                        error = "Convolving image of beam {} ... Failed".format(beam)
                        logger.error(error)
                        logger.exception(e)
                        raise RuntimeError(error)
                    else:
                        logger.info("Convolving image of beam {} ... Done".format(beam))
                else:
                    logger.warning("Convolved image of beam {} already exists".format(beam))
            
            mosaic_common_beam_values = True

            logger.info("Convolving images with common beam ... Done")
        else:
            logger.info("Images have already been convolved")

        subs_param.add_param(
            self, 'mosaic_convolve_images_status', mosaic_common_beam_values)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to get the correlation matrix
    # This should go to mosaic_utils
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def get_inverted_covariance_matrix(self):
        """
        Function to get the covariance matrix

        Based on the cell that reads-in the correlation matrix
        """

        logger.info("Calculating inverse covariance matrix")

        mosaic_continuum_write_covariance_matrix_status = get_param_def(
            self, 'mosaic_continuum_write_covariance_matrix_status', False)

        mosaic_continuum_read_covariance_matrix_status = get_param_def(
            self, 'mosaic_continuum_read_covariance_matrix_status', False)

        #mosaic_continuum_inverse_covariance_matrix = []
        mosaic_continuum_inverse_covariance_matrix = get_param_def(
            self, 'mosaic_continuum_inverse_covariance_matrix', [])

        noise_cov = get_param_def(
            self, 'mosaic_continuum_noise_covariance_matrix', [])


        correlation_matrix_file = os.path.join(self.mosaic_continuum_dir,'correlation.txt')

        if not mosaic_continuum_write_covariance_matrix_status:

            logger.info("Writing covariance matrix")
            try:
                mosaic_utils.create_correlation_matrix(correlation_matrix_file)
            except Exception as e:
                warning = "Writing covariance matrix ... Failed"
                logger.warning(warning)
                logger.exception(e)
            else:
                logger.info("Writing covariance matrix ... Done")
                mosaic_continuum_write_covariance_matrix_status = True
        else:
            logger.info("Covariance matrix already available on file.")


        if len(mosaic_continuum_inverse_covariance_matrix) == 0:
            
            logger.info("Reading covariance matrix")
            # Read in noise correlation matrix 
            try:
                noise_cor=np.loadtxt(correlation_matrix_file,dtype=np.float64)
            except Exception as e:
                warning = "Reading covariance matrix ... Failed"
                logger.warning(warning)
                logger.exception(e)
            else:
                mosaic_continuum_read_covariance_matrix_status = True

            logger.info("Getting covariance matrix ...")

            # Initialize covariance matrix
            noise_cov=copy.deepcopy(noise_cor)

            # Measure noise in the image for each beam
            # same size as the correlation matrix
            sigma_beam=np.zeros(self.NBEAMS,np.float64)

            # number of beams used to go through beam list using indices
            # no need to use indices because the beams are indices themselves
            n_beams = len(self.mosaic_beam_list)
            #for bm in range(n_beams):
            for bm in self.mosaic_beam_list:
                noise_val = self.get_beam_noise(bm)
                sigma_beam[int(bm)]=float(noise_val[4].lstrip('Estimated rms is '))
                logger.info("Beam {0}: {1}".format(bm, sigma_beam[int(bm)]))
            
            # write the matrix
            # take into account that there are not always 40 beams
            # for k in range(n_beams):
            #     for m in range(n_beams):
            for k in self.mosaic_beam_list:
                for m in self.mosaic_beam_list:
                    a = int(k)
                    b = int(m)
                    #logger.debug("noise_cor[{0},{1}]={2}".format(a,b,noise_cor[a,b]))
                    noise_cov[a,b]=noise_cor[a,b]*sigma_beam[a]*sigma_beam[b]  # The noise covariance matrix is 
                    #logger.debug("noise_cov[{0},{1}]={2}".format(a,b,noise_cov[a,b]))
            
            logger.info("Getting covariance matrix ... Done")
        
            # Only the inverse of this matrix is ever used:
            logger.info("Getting inverse of covariance matrix")
            mosaic_continuum_inverse_covariance_matrix = np.linalg.inv(noise_cov)
            logger.info("Getting inverse of covariance matrix ... Done")
            
            logger.info("Calculating inverse covariance matrix ... Done")
        else:
            logger.info("Inverse of covariance matrix is already available")

        subs_param.add_param(
            self, 'mosaic_continuum_write_covariance_matrix_status', mosaic_continuum_write_covariance_matrix_status)
        
        subs_param.add_param(
            self, 'mosaic_continuum_read_covariance_matrix_status', mosaic_continuum_read_covariance_matrix_status)

        subs_param.add_param(
            self, 'mosaic_continuum_inverse_covariance_matrix', mosaic_continuum_inverse_covariance_matrix)
        
        subs_param.add_param(
            self, 'mosaic_continuum_noise_covariance_matrix', noise_cov)


        #return inv_cov

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to calculate the product of beam matrix and covariance matrix
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def math_multiply_beam_and_covariance_matrix(self):
        """
        Function to multiply the transpose of the beam matrix by the covariance matrix
        """

        logger.info("Multiplying beam matrix by covariance matrix")

        mosaic_product_beam_covariance_matrix_status = get_param_def(
            self, 'mosaic_product_beam_covariance_matrix_status', False)

        # get covariance matrix from numpy file
        mosaic_continuum_inverse_covariance_matrix = get_param_def(
            self, 'mosaic_continuum_inverse_covariance_matrix', [])
        if len(mosaic_continuum_inverse_covariance_matrix) == 0:
            error = "Inverse covariance matrix is not available"
            logger.error(error)
            raise RuntimeError(error)
        else:
            inv_cov = mosaic_continuum_inverse_covariance_matrix

        # switch to mosaic directory
        # important because previous step switched to a different dir
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_dir)

        if not mosaic_product_beam_covariance_matrix_status:
            # First calculate transpose of beam matrix multiplied by the inverse covariance matrix
            # Will use *maths* in Miriad

            # Using "beams" list to account for missing beams/images
            # Only doing math where inv_cov value is non-zero
            maths = lib.miriad('maths')
            for bm in self.mosaic_beam_list:
                logger.info("Processing beam {}".format(bm))
                # This was not in the notebook.
                # Are you it should be here ???? Yes, according to DJ
                operate = ""
                for b in self.mosaic_beam_list:
                    maths.out = os.path.join(self.mosaic_continuum_mosaic_subdir,'tmp_{}.map'.format(b))
                    # since the beam list is made of strings, need to convert to integers
                    beam_map = os.path.join(self.mosaic_continuum_beam_subdir, "beam_{0}_mos.map".format(b))
                    if os.path.isdir(beam_map):
                        if inv_cov[int(b),int(bm)]!=0.:
                            #operate+="<"+self.mosaic_continuum_beam_subdir+"/beam_{0}_mos.map>*{1}+".format(b,inv_cov[int(b),int(bm)])
                            operate="'<{0}>*({1})'".format(beam_map,inv_cov[int(b),int(bm)])
                        else:
                            operate="'<{0}>*0'".format(beam_map)
                        logger.debug("for beam combination {0},{1}: operate = {2}".format(bm, b, operate))
                        maths.exp = operate
                        maths.options='unmask'
                        maths.inp()
                        maths.go()
                    else:
                        error = "Could not find mosaic beam map for beam {}".format(b)
                        logger.error(error)
                        raise RuntimeError(error)
                i=1
                while i<len(self.mosaic_beam_list):
                    if os.path.isdir(os.path.join(self.mosaic_continuum_mosaic_subdir, "tmp_{}.map".format(self.mosaic_beam_list[i-1]))) and os.path.isdir(os.path.join(self.mosaic_continuum_mosaic_subdir, "tmp_{}.map".format(self.mosaic_beam_list[i]))):
                        if i==1:
                            operate = "'<"+self.mosaic_continuum_mosaic_subdir+"/tmp_{}.map>+<".format(str(self.mosaic_beam_list[i-1]))+self.mosaic_continuum_mosaic_subdir+"/tmp_{}.map>'".format(str(self.mosaic_beam_list[i]))
                        else:
                            operate="'<"+self.mosaic_continuum_mosaic_subdir+"/tmp_{}.map>".format(str(self.mosaic_beam_list[i]))+"+<"+self.mosaic_continuum_mosaic_subdir+"/sum_{}.map>'".format(str(self.mosaic_beam_list[i-1]))
                        maths.out = self.mosaic_continuum_mosaic_subdir+'/sum_{}.map'.format(str(self.mosaic_beam_list[i]))
                        maths.exp = operate
                        maths.options='unmask'
                        maths.inp()
                        maths.go()
                    else:
                        error = "Could not find temporary maps for beam {0} or beam {1}".format(self.mosaic_beam_list[i-1], self.mosaic_beam_list[i])
                        logger.error(error)
                        raise RuntimeError(error)
                    i+=1
                
                if os.path.isdir(os.path.join(self.mosaic_continuum_mosaic_subdir, 'sum_{}.map'.format(self.mosaic_beam_list[i-1]))):
                    subs_managefiles.director(self, 'rn', self.mosaic_continuum_mosaic_subdir+'/btci_{}.map'.format(bm), file_=self.mosaic_continuum_mosaic_subdir+'/sum_{}.map'.format(str(self.mosaic_beam_list[i-1])))
                    #os.rename(,self.mosaic_continuum_mosaic_subdir+'/btci_{}.map'.format(bm))
                else:
                    error = "Could not find temporary sum map for beam {}".format(self.mosaic_beam_list[i-1])
                    logger.error(error)
                    raise RuntimeError(error)

                # remove the scratch files
                logger.info("Removing scratch files")
                for fl in glob.glob(os.path.join(self.mosaic_continuum_mosaic_dir,'tmp_*.map')):
                    subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)
                for fl in glob.glob(os.path.join(self.mosaic_continuum_mosaic_dir,'sum_*.map')):
                    subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)

            logger.info("Multiplying beam matrix by covariance matrix ... Done")
            mosaic_product_beam_covariance_matrix_status = True
        else:
            logger.info("Multiplying beam matrix by covariance matrix has already been done.")

        subs_param.add_param(
            self, 'mosaic_product_beam_covariance_matrix_status', mosaic_product_beam_covariance_matrix_status) 
    
    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to calculate the variance map
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def math_calculate_variance_map(self):
        """
        Function to calculate the variance map
        """

        logger.info("Calculate variance map")

        mosaic_variance_map_status = get_param_def(
            self, 'mosaic_variance_map_status', False)

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_dir)

        if not mosaic_variance_map_status:
            # Calculate variance map (using beams and noise covariance matrix over entire map)
            # This is the denominator for I(mosaic)
            maths = lib.miriad('maths')
            i=0
            for beam in self.mosaic_beam_list:
                btci_map = os.path.join(self.mosaic_continuum_mosaic_subdir,"btci_{}.map".format(beam))
                beam_mos_map = os.path.join(self.mosaic_continuum_beam_subdir,"beam_{}_mos.map".format(beam))
                if os.path.isdir(btci_map) and os.path.isdir(beam_mos_map):
                    operate="'<"+btci_map+">*<"+beam_mos_map+">'"
                    if beam != self.mosaic_beam_list[0]:
                        operate=operate[:-1]+"+<"+self.mosaic_continuum_mosaic_subdir+"/out_{}_mos.map>'".format(str(i).zfill(2))
                    i+=1
                    logger.debug("Beam {0}: operate = {1}".format(beam, operate))
                    maths.out = self.mosaic_continuum_mosaic_subdir+"/out_{}_mos.map".format(str(i).zfill(2))
                    maths.exp = operate
                    maths.options='unmask'
                    maths.inp()
                    maths.go()
                else:
                    error = "Could not find the maps for beam {0}".format(beam)
                    logger.error(error)
                    raise RuntimeError(error)

            subs_managefiles.director(self, 'rn', os.path.join(self.mosaic_continuum_mosaic_subdir,'variance_mos.map'), file_=os.path.join(self.mosaic_continuum_mosaic_subdir, 'out_{}_mos.map'.format(str(i).zfill(2))))
            #os.rename(mosaicdir+'out_{}_mos.map'.format(str(i).zfill(2)),mosaicdir+'variance_mos.map')

            logger.info("Calculate variance map ... Done")

            mosaic_variance_map_status = True
        else:
            logger.info("Variance map has already been calculated.")

        subs_param.add_param(
            self, 'mosaic_variance_map_status', mosaic_variance_map_status)
        
    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to calculate the beam  matrix multiplied by the covariance matrix
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def math_multiply_beam_matrix_by_covariance_matrx_and_image(self):
        """
        Function to muliply the beam matrix by covariance matrix and image 
        """

        logger.info("Multiplying beam matrix by covariance matrix and image")

        mosaic_product_beam_covariance_matrix_image_status = get_param_def(
            self, 'mosaic_product_beam_covariance_matrix_image_status', False)

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_mosaic_dir)

        if not mosaic_product_beam_covariance_matrix_image_status:
            # Calculate transpose of beam matrix multiplied by noise_cov multiplied by image from each beam for each position
            # in the final image
            maths = lib.miriad('maths')
            i=0
            for bm in self.mosaic_beam_list:
                if os.path.isdir("image_{}_mos.map".format(bm)) and os.path.isdir("btci_{}.map".format(bm)):
                    operate="'<"+"image_{}_mos.map>*<".format(bm)+"btci_{}.map>'".format(bm)
                    if bm!=self.mosaic_beam_list[0]:
                        operate=operate[:-1]+"+<"+"mos_{}.map>'".format(str(i).zfill(2))
                    i+=1
                    maths.out = "mos_{}.map".format(str(i).zfill(2))
                    maths.exp = operate
                    maths.options='unmask,grow'
                    maths.inp()
                    maths.go()
                else:
                    error = "Could not find the necessary files for beam {}".format(bm)
                    logger.error(error)
                    raise RuntimeError(error)
            
            subs_managefiles.director(self, 'rn', 'mosaic_im.map', file_='mos_{}.map'.format(str(i).zfill(2)))
            #os.rename('mos_{}.map'.format(str(i).zfill(2)),'mosaic_im.map')

            logger.info("Multiplying beam matrix by covariance matrix and image ... Done")

            mosaic_product_beam_covariance_matrix_image_status = True
        else:
            logger.info("Multiplication has already been done.")

        subs_param.add_param(
            self, 'mosaic_product_beam_covariance_matrix_image_status', mosaic_product_beam_covariance_matrix_image_status)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to find maximum of variance map
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def math_get_max_variance_map(self):
        """
        Function to determine the maximum of the variance map
        """

        logger.info("Getting maximum of variance map")

        mosaic_get_max_variance_status = get_param_def(
            self, 'mosaic_get_max_variance_status', False)

        mosaic_max_variance = get_param_def(
            self, 'mosaic_beam_max_variance', 0.)

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_mosaic_dir)

        if not mosaic_get_max_variance_status and mosaic_max_variance == 0.:
            # Find maximum value of variance map
            imstat = lib.miriad('imstat')
            imstat.in_="'variance_mos.map'"
            imstat.region="'quarter(1)'"
            imstat.axes="'x,y'"
            try:
                a=imstat.go()
            except Exception as e:
                error = "Getting maximum of varianc map ... Failed"
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)

            # Always outputs max value at same point
            var_max=a[10].lstrip().split(" ")[3]

            logger.info("Maximum of variance map is {}".format(var_max))

            logger.info("Getting maximum of variance map ... Done")

            mosaic_get_max_variance_status = True
            mosaic_max_variance = var_max
        else:
            logger.info("Maximum of variance map has already been determined.")

        subs_param.add_param(
            self, 'mosaic_get_max_variance_status', mosaic_get_max_variance_status)
        
        subs_param.add_param(
            self, 'mosaic_max_variance', mosaic_max_variance)
    
    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to divide image by variance map
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def math_divide_image_by_variance_map(self):
        """
        Function to divide the image by the variance map
        """

        logger.info("Dividing image by variance map")

        mosaic_divide_image_variance_status = get_param_def(
            self, 'mosaic_divide_image_variance_status', False)

        mosaic_max_variance = get_param_def(
            self, 'mosaic_beam_max_variance', 0.)

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_mosaic_dir)

        if not mosaic_divide_image_variance_status:
            # Divide image by variance map
            maths = lib.miriad('maths')
            maths.out = 'mosaic_final.map'
            maths.exp="'<mosaic_im.map>/<variance_mos.map>'"
            maths.mask="'<variance_mos.map>.gt.0.01*"+str(mosaic_max_variance)+"'"
            maths.inp()
            try:
                maths.go()
            except Exception as e:
                error = "Dividing image by variance map ... Failed"
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)

            logger.info("Dividing image by variance map ... Done")

            mosaic_divide_image_variance_status = True
        else:
            logger.info("Division has already been performed")

        subs_param.add_param(
            self, 'mosaic_divide_image_variance_status', mosaic_divide_image_variance_status)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to get mosaic noise map
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def get_mosaic_noise_map(self):
        """
        Function to get the mosaic noise map
        """

        logger.info("Getting mosaic noise map")

        mosaic_get_mosaic_noise_map_status = get_param_def(
            self, 'mosaic_get mosaic_noise_map_status', False)

        mosaic_max_variance = get_param_def(
            self, 'mosaic_beam_max_variance', 0.)

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_mosaic_dir)

        # Produce mosaic noise map
        maths = lib.miriad('maths')
        maths.out = 'mosaic_noise.map'
        maths.exp="'1./sqrt(<variance_mos.map>)'"
        maths.mask="'<variance_mos.map>.gt.0.01*"+str(mosaic_max_variance)+"'"
        maths.inp()
        try:
            maths.go()
        except Exception as e:
            error = "Calculating mosaic noise map ... Failed"
            logger.error(error)
            logger.exception(e)
            raise RuntimeError(error)

        puthd = lib.miriad('puthd')
        puthd.in_='mosaic_noise.map/bunit'
        puthd.value='JY/BEAM'
        try:
            puthd.go()
        except Exception as e:
            error = "Adding noise map unit ... Failed"
            logger.error(error)
            logger.exception(e)
            raise RuntimeError(error)

        mosaic_get_mosaic_noise_map_status = True
        subs_param.add_param(
            self, 'mosaic_get_mosaic_noise_map_status', mosaic_get_mosaic_noise_map_status)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to write out the mosaic FITS files
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def write_mosaic_fits_files(self):
        """
        Function to write out the mosaic fits files
        """

        logger.info("Writing mosaic fits files")

        mosaic_write_mosaic_fits_files_status = get_param_def(
            self, 'mosaic_write_mosaic_fits_files_status', False)

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_mosaic_dir)

        # set the mosaic name
        if not self.mosaic_name:
            self.mosaic_name = "{}_mosaic.fits".format(self.mosaic_taskid)
        
        # name of the noise map    
        mosaic_noise_name = self.mosaic_name.replace(".fits", "_noise.fits")


        # Write out FITS files
        # main image
        fits = lib.miriad('fits')
        fits.op='xyout'
        fits.in_='mosaic_final.map'
        fits.out=self.mosaic_name
        fits.inp()
        try:
            fits.go()
        except Exception as e:
            error = "Writing mosaic fits file ... Failed"
            logger.error(error)
            logger.exception(e)
            raise RuntimeError(error)

        # noise map
        fits.in_='mosaic_noise.map'
        fits.out=mosaic_noise_name
        fits.inp()
        try:
            fits.go()          
        except Exception as e:
            error = "Writing mosaic noise mape fits file ... Failed"
            logger.error(error)
            logger.exception(e)
            raise RuntimeError(error)

        logger.info("Writing mosaic fits files ... Done")

        mosaic_write_mosaic_fits_files_status = True
        subs_param.add_param(
            self, 'mosaic_write_mosaic_fits_files_status', mosaic_write_mosaic_fits_files_status)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to run validation tool
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def run_image_validation(self):
        """
        Function to run image validation
        """

        mosaic_run_image_validation_status = get_param_def(
            self, 'mosaic_run_image_validation_status', False)

        if self.mosaic_run_image_validation:
            # optional step, so only do the import here
            import dataqa
            from dataqa.continuum.validation_tool import validation

            logger.info("Running image validation")

            # Validate final continuum mosaic

            finder = 'pybdsf'
            start_time_validation = time.time()

            validation.run(self.mosaic_name, finder=finder)
            
            logger.info("Writing mosaic fits files ... Done ({0:.0f}s)".format(time.time() - start_time_validation))
        else:
            logger.warning("Did not run image validation")

        mosaic_run_image_validation_status = True
        subs_param.add_param(
            self, 'mosaic_run_image_validation_status', mosaic_run_image_validation_status)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++ 
    # Function to create the continuum mosaic
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def create_mosaic_continuum_mf(self):
        """
        Function to create the continuum mosaic
        """
        subs_setinit.setinitdirs(self)
        
        mosaic_continuummf_status = get_param_def(self, 'mosaic_continuum_mf_status', False)
        
        # Start the mosaicking of the stacked continuum images
        if self.mosaic_continuum_mf:
            logger.info("Creating continuum image mosaic")

            subs_setinit.setinitdirs(self)
            subs_setinit.setdatasetnamestomiriad(self)

            # set the name of the sub-directories if they were not specified
            self.set_mosaic_subdirs(continuum=True)

            # change into the directory for the continuum mosaic
            subs_managefiles.director(self, 'ch', os.path.join(self.mosdir, self.mosaic_continuum_subdir))

            # if no mosaic has already been created
            if not mosaiccontinuummfstatus:

                # get the continuum images
                # ========================
                logger.info("Getting continuum images for continuum mosaic")
                self.get_mosaic_continuum_images()

                # get the beams
                # =============
                logger.info("Getting beam information for continuum mosaic")
                self.get_mosaic_continuum_beams()

                # set or check the projection center
                # ==================================
                self.get_mosaic_projection_centre()

                # Converting images into miriad
                # =======================================
                self.convert_images_to_miriad()
                
                # Transfer image coordinates
                # ==========================
                self.transfer_coordinates()
                
                # Create a template mosaic
                # ========================
                self.create_template_mosaic()
                
                # Regrid images
                # =============
                self.regrid_images()

                # Regrid beam maps
                # ================
                self.regrid_beam_maps()
                
                # Determing common beam for convolution
                # =====================================
                self.get_common_beam()

                # Convolve images
                # ===============
                self.mosaic_convolve_images()

                # Calculate product of beam matrix and covariance matrix
                # ======================================================
                self.math_multiply_beam_and_covariance_matrix()

                # Calculate variance map
                # ======================
                self.math_calculate_variance_map()

                # Calculate beam matrix multiplied by covariance matrix
                # =====================================================
                self.math_multiply_beam_matrix_by_covariance_matrx_and_image()

                # Find maximum variance map
                # =========================
                self.math_get_max_variance_map()

                # Calculate divide image by variance map
                # ======================================
                self.math_divide_image_by_variance_map()

                # Calculate get mosaic noise map
                # ==============================
                self.get_mosaic_noise_map()

                # Writing files
                # =============
                self.write_mosaic_fits_files()

                # Save the derived parameters to the parameter file
                mosaic_continuummf_status = True
            
                if self.mosaic_clean_up:
                    self.clean_up()
            else:
                logger.info("Continuum image mosaic was already created")

            logger.info("Creating continuum image mosaic ... Done")
        else:
            pass

        subs_param.add_param(
            self, 'mosaic_continuum_mf_status', mosaic_continuummf_status)

    def show(self, showall=False):
        lib.show(self, 'MOSAIC', showall)

    def clean_up (self):
        """
        Function to remove scratch files
        """
        #subs_setinit.setinitdirs(self)
        logger.info("Removing scratch files")

        # remove file from creating template mosaic
        #shutil.rmtree(mosaicdir+'mosaic_temp.map')
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_mosaic_dir)
        subs_managefiles.director(self, 'rm', 'mosaic_temp_preproj.map', ignore_nonexistent=True)

        # Clean up files
        for fl in glob.glob('*_convol.map'):
            subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)
        # Clean up files
        for fl in glob.glob('*_regrid.map'):
            subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)
        subs_param.del_param(
            self, 'mosaic_regrid_images_status')
        subs_param.del_param(
            self, 'mosaic_regrid_beam_maps_status')
        subs_param.del_param(
            self, 'mosaic_convolve_images_status')
        
        subs_managefiles.director(
            self, 'rm', 'mosaic_im.map', ignore_nonexistent=True)

        #shutil.rmtree(mosaicdir+'mosaic_im.map')

        for fl in glob.glob('mos_*.map'):
            subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)
            
        for fl in glob.glob('btci_*.map'):
            subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)

        logger.info("Removing scratch files ... Done")
            
    def reset(self):
        """
        Function to reset the current step and remove all generated data. Be careful! Deletes all data generated in
        this step!
        """
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)
        if os.path.isdir(self.mosdir):
            logger.warning('Deleting all mosaicked data products.')
            subs_managefiles.director(self, 'ch', self.basedir)
            subs_managefiles.director(self, 'rm', self.mosdir)
            logger.warning(
                'Deleting all parameter file entries for MOSAIC module')
            subs_param.del_param(self, 'mosaic_continuum_mf_status')
            subs_param.del_param(self, 'mosaic_continuum_mf_continuumstatus')
            subs_param.del_param(self, 'mosaic_continuum_mf_copystatus')
            subs_param.del_param(self, 'mosaic_continuum_mf_convolstatus')
            subs_param.del_param(
                self, 'mosaic_continuum_mf_continuumbeamparams')
            subs_param.del_param(
                self, 'mosaic_continuum_mf_continuumimagestats')
        else:
            logger.warning('Mosaicked data products are not present!')

    # Continuum mosaicing of the individual chunk images
    # def mosaic_continuum_chunk_images(self):
    #     """Mosaics the continuum images from the different frequency chunks."""
    #     subs_setinit.setinitdirs(self)
    #     subs_setinit.setdatasetnamestomiriad(self)
    #     nch = len(subs_param.get_param(self, 'continuum_B00_stackstatus'))
    #
    #     # Check if the parameter is already in the parameter file and load it otherwise create the needed arrays #
    #
    #     # Status of the input chunk images for the mosaicing
    #     chunks_inputstatus = get_param_def(self, 'mosaic_continuum_chunks_beams_inputstatus', np.full((self.NBEAMS, nch),
    #                                                                                                   False))
    #
    #     # Beam sizes of the input images
    #     chunks_inputsynthbeamparams = get_param_def(self, 'mosaic_continuum_chunks_beams_inputsynthbeamparams',
    #                                                 np.full((self.NBEAMS, nch, 3), np.nan))
    #
    #     # Image statistics of the input images
    #     chunks_inputimagestats = get_param_def(self, 'mosaic_continuum_chunks_beams_inputimagestats',
    #                                            np.full((self.NBEAMS, nch, 3), np.nan))
    #
    #     # RMS of the input chunk images
    #     chunks_inputrms = get_param_def(self, 'mosaic_continuum_chunks_beams_inputrms',
    #                                     np.full((self.NBEAMS, nch), np.nan))
    #
    #     # Was the image accepted based on the synthesised beam?
    #     chunks_beamstatus = get_param_def(self, 'mosaic_continuum_chunks_beams_beamstatus', np.full((self.NBEAMS, nch),
    #                                                                                                 False))
    #
    #     # Reason for rejecting an image
    #     chunks_rejreason = get_param_def(self, 'mosaic_continuum_chunks_beams_rejreason',
    #                                      np.full((self.NBEAMS, nch), '', dtype='U50'))
    #
    #     # Weights of the individual input images (normalised to one)
    #     chunks_inputweights = get_param_def(self, 'mosaic_continuum_chunks_beams_inputweights', np.full((self.NBEAMS, nch),
    #                                                                                                     np.nan))
    #
    #     # Synthesised beam parameters for the final continuum chunk mosaics
    #     chunks_beams = get_param_def(self, 'mosaic_continuum_chunks_beams_synthbeamparams', np.full((nch, 3),
    #                                                                                                 np.nan))
    #
    #     # Last executed clean iteration for the continuum images
    #     chunks_iterations = get_param_def(self, 'mosaic_continuum_chunks_beams_iterations', np.full((self.NBEAMS, nch),
    #                                                                                                 np.nan))
    #
    #     # Status of the input chunk images for the mosaicing
    #     chunks_continuumstatus = get_param_def(self, 'mosaic_continuum_chunks_beams_continuumstatus',
    #                                            np.full((self.NBEAMS, nch),
    #                                                    False))
    #
    #     # Status of the copying of the individual chunk images
    #     chunks_copystatus = get_param_def(self, 'mosaic_continuum_chunks_beams_copystatus',
    #                                       np.full((self.NBEAMS, nch), False))
    #
    #     # Status of the convolution of the individual chunk images
    #     chunks_convolstatus = get_param_def(self, 'mosaic_continuum_chunks_beams_convolstatus', np.full((self.NBEAMS, nch),
    #                                                                                                     False))
    #
    #     # Status of the final chunk mosaics
    #     chunks_imagestatus = get_param_def(self, 'mosaic_continuum_chunks_beams_imagestatus',
    #                                        np.full(nch, False))
    #
    #     # Start the mosaicing of the individual chunks
    #     if self.mosaic_continuum_chunks:
    #         logger.info(' Starting mosaicing of continuum images of individual frequency chunks')
    #         subs_managefiles.director(self, 'ch', self.mosdir + '/continuum')
    #
    #         for c in np.arange(nch):
    #             # Check if a continuum image for a chunk is already present
    #             if os.path.isfile(self.target.rstrip('.mir') + '_contmosaic' + '_chunk_' + str(c).zfill(2) + '.fits'):
    #                 logger.warning(' Continuum mosaic for chunk ' + str(c).zfill(2) + ' already present.')
    #             else:
    #
    #                 # Check for which chunks continuum imaging was successful
    #                 for b in np.arange(self.NBEAMS):  # Get the status from the continuum entry of the parameter file
    #                     if subs_param.check_param(self, 'continuum_B' + str(b).zfill(2) + '_imagestatus'):
    #                         chunks_inputstatus[b, c] = \
    #                             subs_param.get_param(self, 'continuum_B' + str(b).zfill(2) + '_imagestatus')[c, -1]
    #                         if chunks_inputstatus[b, c]:
    #                             chunks_continuumstatus[b, c] = True
    #                             chunks_iterations[b, c] = \
    #                                 subs_param.get_param(self, 'continuum_B' + str(b).zfill(2) + '_minoriterations')[c]
    #                             logger.debug(
    #                                 'Continuum imaging for frequency chunk ' + str(c).zfill(2) + ' of beam ' + str(
    #                                     b).zfill(2) + ' successful! Added in mosaicing! #')
    #                         else:
    #                             chunks_continuumstatus[b, c] = False
    #                             chunks_iterations[b, c] = np.nan
    #                             chunks_rejreason[b, c] = 'Continuum imaging not successful'
    #                             logger.warning(
    #                                 'Continuum imaging for frequency chunk ' + str(c).zfill(2) + ' of beam ' + str(
    #                                     b).zfill(2) + ' not successful! Not added in mosaicing! #')
    #                     else:
    #                         chunks_rejreason[b, c] = 'No data available'
    #                         logger.warning(
    #                             'No data availbale for chunk ' + str(c).zfill(2) + ' of beam ' + str(b).zfill(
    #                                 2) + '! Not added in mosaicing! #')
    #
    #                 # Run through each chunk and copy the available images
    #                 for b in np.arange(self.NBEAMS):
    #                     if chunks_inputstatus[b, c]:
    #                         subs_managefiles.director(self, 'cp', 'C' + str(c).zfill(2) + 'B' + str(b).zfill(2),
    #                                                   self.basedir + str(b).zfill(
    #                                                       2) + '/' + self.contsubdir + '/' + 'stack' + '/' + str(
    #                                                       c).zfill(2) + '/' + 'image_' + str(
    #                                                       int(chunks_iterations[b, c])).zfill(2))
    #                         if os.path.isdir('C' + str(c).zfill(2) + 'B' + str(b).zfill(2)):
    #                             chunks_copystatus[b, c] = True
    #                             logger.debug('Successfully copyied image of frequency chunk ' + str(c).zfill(
    #                                 2) + ' of beam ' + str(b).zfill(2) + '! #')
    #                         else:
    #                             chunks_inputstatus[b, c] = False
    #                             chunks_copystatus[b, c] = False
    #                             chunks_rejreason[b, c] = 'Copy of continuum image not successful'
    #                             logger.warning(
    #                                 'Copying image of frequency chunk ' + str(c).zfill(2) + ' of beam ' + str(b).zfill(
    #                                     2) + ' failed! #')
    #
    #                 # Get the parameters for each image
    #                 for b in np.arange(self.NBEAMS):
    #                     if chunks_inputstatus[b, c]:
    #                         chunks_inputsynthbeamparams[b, c, :] = subs_readmirhead.getbeamimage(
    #                             'C' + str(c).zfill(2) + 'B' + str(b).zfill(2))
    #                         chunks_inputimagestats[b, c, :] = subs_imstats.getimagestats(self, 'C' + str(c).zfill(
    #                             2) + 'B' + str(b).zfill(2))
    #                         chunks_inputrms[b, c] = \
    #                             subs_param.get_param(self, 'continuum_B' + str(b).zfill(2) + '_residualstats')[
    #                                 c, int(chunks_iterations[b, c]), 2]
    #                     else:
    #                         pass
    #
    #                 # Calculate the common beam for each frequency chunk and make a list of accepted and rejected
    #                 # beams and update the parameters for the parameter file
    #                 avbeamlist = np.where(chunks_inputstatus[:, c])[0]
    #                 notavbeamlist = np.where(not chunks_inputstatus[:, c])[0]
    #                 avbeams = [str(x).zfill(2) for x in list(avbeamlist)]
    #                 notavbeams = [str(x).zfill(2) for x in list(notavbeamlist)]
    #                 beamarray = chunks_inputsynthbeamparams[avbeamlist, c, :]
    #                 rejbeams, chunks_beams[c, :] = subs_combim.calc_synbeam(avbeams, beamarray)
    #                 chunks_beamstatus[:, c] = chunks_inputstatus[:, c]
    #                 if len(rejbeams) == 0:
    #                     logger.debug(
    #                         'No beams are rejected due to synthesised beam parameters for chunk ' + str(c).zfill(
    #                             2) + '! #')
    #                 else:
    #                     for rb in rejbeams:
    #                         avbeams.remove(rb)
    #                         notavbeams.extend(rb)
    #                         logger.warning('Stacked image of beam ' + str(rb).zfill(2) + ' for chunk ' + str(c).zfill(
    #                             2) + ' was rejected due to synthesised beam parameters! #')
    #                         chunks_inputstatus[int(rb), c] = False
    #                         chunks_beamstatus[int(rb), c] = False
    #                         chunks_rejreason[int(rb), c] = 'Synthesised beam parameters'
    #                 sorted(avbeams)
    #                 sorted(notavbeams)
    #
    #                 logger.info('Final beam size for chunk ' + str(c).zfill(2) + ' is fwhm = ' + str(
    #                     chunks_beams[c, 0]) + ' arcsec , ' + str(chunks_beams[c, 1]) + ' arcsec, pa = ' + str(
    #                     chunks_beams[c, 2]) + ' deg')
    #
    #                 # Convol the individual frequency chunk images to the same synthesised beam
    #                 for b in np.arange(self.NBEAMS):
    #                     if chunks_inputstatus[b, c]:
    #                         convol = lib.miriad('convol')
    #                         convol.map = 'C' + str(c).zfill(2) + 'B' + str(b).zfill(2)
    #                         convol.fwhm = str(chunks_beams[c, 0]) + ',' + str(chunks_beams[c, 1])
    #                         convol.pa = str(chunks_beams[c, 2])
    #                         convol.out = 'c' + 'C' + str(c).zfill(2) + 'B' + str(b).zfill(2)
    #                         convol.options = 'final'
    #                         convol.go()
    #                         if os.path.isdir('c' + 'C' + str(c).zfill(2) + 'B' + str(b).zfill(
    #                                 2)):  # Check if the convolved image was created
    #                             convmin, convmax, convstd = subs_imstats.getimagestats(self, 'c' + 'C' + str(c).zfill(
    #                                 2) + 'B' + str(b).zfill(2))
    #                             # Check if the image is valid
    #                             if convstd != np.nan and convmax <= 10000 and convmin >= -10:
    #                                 chunks_convolstatus[b, c] = True
    #                                 logger.debug(
    #                                     'Convolution of image of beam ' + str(b).zfill(2) + ' for chunk ' + str(
    #                                         c).zfill(2) + ' successful! #')
    #                             else:
    #                                 chunks_inputstatus[b, c] = False
    #                                 chunks_convolstatus[b, c] = False
    #                                 chunks_rejreason[b, c] = 'Convolved image not valid'
    #                                 logger.warning(
    #                                     'Convolved image of beam ' + str(b).zfill(2) + ' for chunk ' + str(c).zfill(
    #                                         2) + ' is empty or shows high values! #')
    #                         else:
    #                             chunks_inputstatus[b, c] = False
    #                             chunks_convolstatus[b, c] = False
    #                             chunks_rejreason[b, c] = 'Convolved image not created'
    #                             logger.warning(
    #                                 'Convolved image of beam ' + str(b).zfill(2) + ' for chunk ' + str(c).zfill(
    #                                     2) + ' could not successfully be created! #')
    #                     else:
    #                         pass
    #
    #                 # Finally combine the images using linmos
    #                 rmsrej = chunks_inputrms[:, c]
    #                 convolimages = ''
    #                 rms = ''
    #                 for b in np.arange(self.NBEAMS):
    #                     if chunks_inputstatus[b, c]:
    #                         convolimages = convolimages + 'c' + 'C' + str(c).zfill(2) + 'B' + str(b).zfill(2) + ','
    #                         rms = rms + str(chunks_inputrms[b, c]) + ','
    #                     else:
    #                         rmsrej[b] = np.nan
    #                 chunks_inputweights[:, c] = ((1.0 / np.square(rmsrej)) / np.nansum(
    #                     1.0 / np.square(rmsrej))) / np.nanmean(
    #                     ((1.0 / np.square(rmsrej)) / np.nansum(1.0 / np.square(rmsrej))))
    #                 linmos = lib.miriad('linmos')
    #                 linmos.in_ = convolimages.rstrip(',')
    #                 linmos.rms = rms.rstrip(',')
    #                 linmos.out = self.target.rstrip('.mir') + '_contmosaic' + '_chunk_' + str(c).zfill(2)
    #                 linmos.go()
    #
    #                 # Check if the final images are there, are valid and convert them to fits
    #                 if os.path.isdir(self.target.rstrip('.mir') + '_contmosaic' + '_chunk_' + str(c).zfill(2)):
    #                     logger.debug('Continuum mosaic of chunk ' + str(c).zfill(2) + ' created successfully! #')
    #                     contmosmin, contmosmax, contmosstd = subs_imstats.getimagestats(self, self.target.rstrip(
    #                         '.mir') + '_contmosaic' + '_chunk_' + str(c).zfill(2))
    #
    #                     # Check if the image is valid
    #                     if contmosstd != np.nan and contmosmax <= 10000 and contmosmin >= -10:
    #                         logger.debug('Continuum mosaic of chunk ' + str(c).zfill(2) + ' is valid! #')
    #                         subs_managefiles.imagetofits(self,
    #                                                      self.target.rstrip('.mir') + '_contmosaic' + '_chunk_' + str(
    #                                                          c).zfill(2),
    #                                                      self.target.rstrip('.mir') + '_contmosaic' + '_chunk_' + str(
    #                                                          c).zfill(2) + '.fits')
    #                         chunks_imagestatus[c] = True
    #                         for b in np.arange(self.NBEAMS):  # Remove the obsolete files
    #                             subs_managefiles.director(self, 'rm',
    #                                                       self.target.rstrip('.mir') + '_contmosaic' + '_chunk_' + str(
    #                                                           c).zfill(2))
    #                             subs_managefiles.director(self, 'rm', 'C' + str(c).zfill(2) + 'B' + str(b).zfill(2))
    #                             subs_managefiles.director(self, 'rm',
    #                                                       'c' + 'C' + str(c).zfill(2) + 'B' + str(b).zfill(2))
    #                         logger.debug('Removed all obsolete files #')
    #                         logger.info(' Mosaicing of continuum images successful for chunk ' + str(c).zfill(2) + '!')
    #                     else:
    #                         chunks_imagestatus[c] = False
    #                         logger.warning(
    #                             'Final continuum mosaic is empty or shows high values for chunk ' + str(c).zfill(
    #                                 2) + '! #')
    #                 else:
    #                     chunks_imagestatus[c] = False
    #                     logger.warning(
    #                         'Final continuum mosaic could not be created for chunk ' + str(c).zfill(2) + '! #')
    #
    #         logger.info(' Mosaicing of continuum images for individual frequency chunks done')
    #
    #         # Save the derived parameters to the parameter file
    #
    #         subs_param.add_param(self, 'mosaic_continuum_chunks_beams_inputstatus', chunks_inputstatus)
    #         subs_param.add_param(self, 'mosaic_continuum_chunks_beams_inputsynthbeamparams',
    #                              chunks_inputsynthbeamparams)
    #         subs_param.add_param(self, 'mosaic_continuum_chunks_beams_inputimagestats', chunks_inputimagestats)
    #         subs_param.add_param(self, 'mosaic_continuum_chunks_beams_inputrms', chunks_inputrms)
    #         subs_param.add_param(self, 'mosaic_continuum_chunks_beams_inputweights', chunks_inputweights)
    #         subs_param.add_param(self, 'mosaic_continuum_chunks_beams_iterations', chunks_iterations)
    #         subs_param.add_param(self, 'mosaic_continuum_chunks_beams_rejreason', chunks_rejreason)
    #         subs_param.add_param(self, 'mosaic_continuum_chunks_beams_synthbeamparams', chunks_beams)
    #         subs_param.add_param(self, 'mosaic_continuum_chunks_beams_imagestatus', chunks_imagestatus)
    #         subs_param.add_param(self, 'mosaic_continuum_chunks_beams_continuumstatus', chunks_continuumstatus)
    #         subs_param.add_param(self, 'mosaic_continuum_chunks_beams_copystatus', chunks_copystatus)
    #         subs_param.add_param(self, 'mosaic_continuum_chunks_beams_convolstatus', chunks_convolstatus)
    #         subs_param.add_param(self, 'mosaic_continuum_chunks_beams_beamstatus', chunks_beamstatus)
    #
    # # Mosaicing of line cubes #
    #
    # def mosaic_line_cubes(self):
    #     """Creates a mosaicked line cube of all the individual line cubes from the different beams"""
    #     subs_setinit.setinitdirs(self)
    #     subs_setinit.setdatasetnamestomiriad(self)
    #     if self.mosaic_line:
    #         logger.error(' Mosaicing of line cubes not implemented yet')
    #
    # def mosaic_stokes_images(self):
    #     """Creates a mosaic of all the Stokes Q- and U-cubes from the different beams"""
    #     subs_setinit.setinitdirs(self)
    #     subs_setinit.setdatasetnamestomiriad(self)
    #     if self.mosaic_polarisation:
    #         logger.error(' Mosaicing of Stokes cubes not implemented yet')
    #
    # def summary_continuumstacked(self):
    #     """
    #     Creates a general summary of the parameters in the parameter file generated during the mosaicing of the
    #     tacked continuum images. A more detailed summary can be generated by the detailed_summary_continuumstacked
    #     function.
    #
    #     returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in the
    #                        notebook
    #     """
    #
    #     # Load the parameters from the parameter file
    #
    #     IS = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_inputstatus')
    #     WG = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_inputweights')
    #     RR = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_rejreason')
    #
    #     # Create the data frame
    #
    #     beam_indices = range(self.NBEAMS)
    #     beam_indices = [str(item).zfill(2) for item in beam_indices]
    #
    #     df_is = pd.DataFrame(np.ndarray.flatten(IS), index=beam_indices, columns=['Image accepted?'])
    #     df_wg = pd.DataFrame(np.ndarray.flatten(WG), index=beam_indices, columns=['Weight'])
    #     df_rr = pd.DataFrame(np.ndarray.flatten(RR), index=beam_indices, columns=['Reason'])
    #
    #     df = pd.concat([df_is, df_wg, df_rr], axis=1)
    #
    #     return df
    #
    # def detailed_summary_continuumstacked(self):
    #     """
    #     Creates a detailed summary of the parameters in the parameter file generated during the mosaicing of the
    #     stacked continuum images.
    #
    #     returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in the
    #                          notebook
    #     """
    #
    #     # Load the parameters from the parameter file
    #
    #     CS = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_continuumstatus')
    #     CP = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_copystatus')
    #     SBEAMS = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_inputsynthbeamparams')
    #     BS = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_beamstatus')
    #     CV = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_convolstatus')
    #     WG = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_inputweights')
    #     RMS = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_inputrms')
    #     IS = subs_param.get_param(self, 'mosaic_continuum_stacked_beams_inputstatus')
    #
    #     # Create the data frame
    #
    #     beam_indices = range(self.NBEAMS)
    #     beam_indices = [str(item).zfill(2) for item in beam_indices]
    #
    #     df_cs = pd.DataFrame(np.ndarray.flatten(CS), index=beam_indices, columns=['Continuum calibration?'])
    #     df_cp = pd.DataFrame(np.ndarray.flatten(CP), index=beam_indices, columns=['Copy successful?'])
    #     df_bmaj = pd.DataFrame(np.around(np.ndarray.flatten(SBEAMS[:, 0]), decimals=2), index=beam_indices,
    #                            columns=['Bmaj ["]'])
    #     df_bmin = pd.DataFrame(np.around(np.ndarray.flatten(SBEAMS[:, 1]), decimals=2), index=beam_indices,
    #                            columns=['Bmin ["]'])
    #     df_bpa = pd.DataFrame(np.around(np.ndarray.flatten(SBEAMS[:, 2]), decimals=2), index=beam_indices,
    #                           columns=['Bpa [deg]'])
    #     df_bs = pd.DataFrame(np.ndarray.flatten(BS), index=beam_indices, columns=['Beam parameters?'])
    #     df_cv = pd.DataFrame(np.ndarray.flatten(CV), index=beam_indices, columns=['Convol successful?'])
    #     df_wg = pd.DataFrame(np.ndarray.flatten(WG), index=beam_indices, columns=['Weight'])
    #     df_rms = pd.DataFrame(np.ndarray.flatten(RMS), index=beam_indices, columns=['Residual RMS'])
    #     df_is = pd.DataFrame(np.ndarray.flatten(IS), index=beam_indices, columns=['Image accepted?'])
    #
    #     df = pd.concat([df_cs, df_cp, df_bmaj, df_bmin, df_bpa, df_bs, df_cv, df_wg, df_rms, df_is], axis=1)
    #
    #     return df
    #
    # def summary_continuumchunks(self):
    #     """
    #     Creates a general summary of the parameters in the parameter file generated during the mosaicing of the chunk
    #     continuum images. A more detailed summary can be generated by the detailed_summary_continuumchunks function
    #
    #     returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in the
    #                          notebook
    #     """
    #
    #     # Load the parameters from the parameter file
    #
    #     IS = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_imagestatus')
    #     SBEAMS = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_synthbeamparams')
    #     C = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_inputstatus')
    #
    #     # Create the data frame
    #
    #     chunks = len(subs_param.get_param(self, 'mosaic_continuum_chunks_beams_imagestatus'))
    #     chunk_indices = range(chunks)
    #     chunk_indices = [str(item).zfill(2) for item in chunk_indices]
    #
    #     COM = np.full(chunks, 'Beam(s) ', dtype='U150')  # Comment for mosaicing
    #     for c in range(chunks):
    #         for b in range(self.NBEAMS):
    #             if C[b, c]:
    #                 pass
    #             else:
    #                 COM[c] = COM[c] + str(b).zfill(2) + ','
    #         COM[c] = COM[c].rstrip(',') + ' not accepted'
    #
    #     df_is = pd.DataFrame(np.ndarray.flatten(IS), index=chunk_indices, columns=['Mosaic successful?'])
    #     df_bmaj = pd.DataFrame(np.around(np.ndarray.flatten(SBEAMS[:, 0]), decimals=2), index=chunk_indices,
    #                            columns=['Bmaj ["]'])
    #     df_bmin = pd.DataFrame(np.around(np.ndarray.flatten(SBEAMS[:, 1]), decimals=2), index=chunk_indices,
    #                            columns=['Bmin ["]'])
    #     df_bpa = pd.DataFrame(np.around(np.ndarray.flatten(SBEAMS[:, 2]), decimals=2), index=chunk_indices,
    #                           columns=['Bpa [deg]'])
    #     df_c = pd.DataFrame(np.ndarray.flatten(COM), index=chunk_indices, columns=['Comments'])
    #
    #     df = pd.concat([df_is, df_bmaj, df_bmin, df_bpa, df_c], axis=1)
    #
    #     return df
    #
    # def detailed_summary_continuumchunks(self, chunk=None):
    #     """
    #     Creates a detailed summary of the parameters in the parameter file generated during the mosaicing of the chunk
    #     continuum images.
    #
    #     returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in the
    #                          notebook
    #     """
    #
    #     # Load the parameters from the parameter file
    #
    #     CS = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_continuumstatus')
    #     CP = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_copystatus')
    #     SBEAMS = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_inputsynthbeamparams')
    #     BMAJ = SBEAMS[:, :, 0]
    #     BMIN = SBEAMS[:, :, 1]
    #     BPA = SBEAMS[:, :, 2]
    #     BS = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_beamstatus')
    #     CV = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_convolstatus')
    #     WG = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_inputweights')
    #     RMS = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_inputrms')
    #     IS = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_inputstatus')
    #     RR = subs_param.get_param(self, 'mosaic_continuum_chunks_beams_rejreason')
    #
    #     # Create the data frame
    #
    #     if chunk is None:
    #         chunks = len(subs_param.get_param(self, 'mosaic_continuum_chunks_beams_imagestatus'))
    #         chunk_indices = range(chunks)
    #         chunk_indices = [str(item).zfill(2) for item in chunk_indices]
    #     else:
    #         chunk_indices = [str(chunk).zfill(2)]
    #     beam_indices = range(self.NBEAMS)
    #     beam_indices = [str(item).zfill(2) for item in beam_indices]
    #
    #     chunk_beam_indices = pd.MultiIndex.from_product([chunk_indices, beam_indices], names=['Chunk', 'Beam'])
    #
    #     if chunk is None:
    #         df_cs = pd.DataFrame(np.ndarray.flatten(np.swapaxes(CS, 0, 1)), index=chunk_beam_indices,
    #                              columns=['Continuum calibration?'])
    #         df_cp = pd.DataFrame(np.ndarray.flatten(np.swapaxes(CP, 0, 1)), index=chunk_beam_indices,
    #                              columns=['Copy successful?'])
    #         df_bmaj = pd.DataFrame(np.around(np.ndarray.flatten(np.swapaxes(BMAJ, 0, 1)), decimals=2),
    #                                index=chunk_beam_indices, columns=['Bmaj ["]'])
    #         df_bmin = pd.DataFrame(np.around(np.ndarray.flatten(np.swapaxes(BMIN, 0, 1)), decimals=2),
    #                                index=chunk_beam_indices, columns=['Bmin ["]'])
    #         df_bpa = pd.DataFrame(np.around(np.ndarray.flatten(np.swapaxes(BPA, 0, 1)), decimals=2),
    #                               index=chunk_beam_indices, columns=['Bpa [deg]'])
    #         df_bs = pd.DataFrame(np.ndarray.flatten(np.swapaxes(BS, 0, 1)), index=chunk_beam_indices,
    #                              columns=['Beam parameters?'])
    #         df_cv = pd.DataFrame(np.ndarray.flatten(np.swapaxes(CV, 0, 1)), index=chunk_beam_indices,
    #                              columns=['Convol successful?'])
    #         df_wg = pd.DataFrame(np.ndarray.flatten(np.swapaxes(WG, 0, 1)), index=chunk_beam_indices,
    #                              columns=['Weight'])
    #         df_rms = pd.DataFrame(np.ndarray.flatten(np.swapaxes(RMS, 0, 1)), index=chunk_beam_indices,
    #                               columns=['Residual RMS'])
    #         df_is = pd.DataFrame(np.ndarray.flatten(np.swapaxes(IS, 0, 1)), index=chunk_beam_indices,
    #                              columns=['Image accepted?'])
    #         df_rr = pd.DataFrame(np.ndarray.flatten(np.swapaxes(RR, 0, 1)), index=chunk_beam_indices,
    #                              columns=['Reason'])
    #     else:
    #         df_cs = pd.DataFrame(np.ndarray.flatten(CS[:, chunk]), index=chunk_beam_indices,
    #                              columns=['Continuum calibration?'])
    #         df_cp = pd.DataFrame(np.ndarray.flatten(CP[:, chunk]), index=chunk_beam_indices,
    #                              columns=['Copy successful?'])
    #         df_bmaj = pd.DataFrame(np.around(np.ndarray.flatten(BMAJ[:, chunk]), decimals=2), index=chunk_beam_indices,
    #                                columns=['Bmaj ["]'])
    #         df_bmin = pd.DataFrame(np.around(np.ndarray.flatten(BMIN[:, chunk]), decimals=2), index=chunk_beam_indices,
    #                                columns=['Bmin ["]'])
    #         df_bpa = pd.DataFrame(np.around(np.ndarray.flatten(BPA[:, chunk]), decimals=2), index=chunk_beam_indices,
    #                               columns=['Bpa [deg]'])
    #         df_bs = pd.DataFrame(np.ndarray.flatten(BS[:, chunk]), index=chunk_beam_indices,
    #                              columns=['Beam parameters?'])
    #         df_cv = pd.DataFrame(np.ndarray.flatten(CV[:, chunk]), index=chunk_beam_indices,
    #                              columns=['Convol successful?'])
    #         df_wg = pd.DataFrame(np.ndarray.flatten(WG[:, chunk]), index=chunk_beam_indices, columns=['Weight'])
    #         df_rms = pd.DataFrame(np.ndarray.flatten(RMS[:, chunk]), index=chunk_beam_indices, columns=['Residual RMS'])
    #         df_is = pd.DataFrame(np.ndarray.flatten(IS[:, chunk]), index=chunk_beam_indices,
    #                              columns=['Image accepted?'])
    #         df_rr = pd.DataFrame(np.ndarray.flatten(RR[:, chunk]), index=chunk_beam_indices, columns=['Reason'])
    #
    #     df = pd.concat([df_cs, df_cp, df_bmaj, df_bmin, df_bpa, df_bs, df_cv, df_wg, df_rms, df_is, df_rr], axis=1)
    #
    #     return df
    #
    # def reset(self):
    #     """
    #     Function to reset the current step and remove all generated data. Be careful! Deletes all data generated in
    #     this step!
    #     """
    #     subs_setinit.setinitdirs(self)
    #     subs_setinit.setdatasetnamestomiriad(self)
    #     logger.warning(' Deleting all mosaicked data products.')
    #     subs_managefiles.director(self, 'ch', self.basedir)
    #     subs_managefiles.director(self, 'rm', self.mosdir)
    #     logger.warning(' Deleteing all parameter file entries for MOSAIC module')
    #     subs_param.del_param(self, 'mosaic_continuum_stacked_beams_inputstatus')
    #     subs_param.del_param(self, 'mosaic_continuum_stacked_beams_inputsynthbeamparams')
    #     subs_param.del_param(self, 'mosaic_continuum_stacked_beams_inputimagestats')
    #     subs_param.del_param(self, 'mosaic_continuum_stacked_beams_inputrms')
    #     subs_param.del_param(self, 'mosaic_continuum_stacked_beams_inputweights')
    #     subs_param.del_param(self, 'mosaic_continuum_stacked_beams_rejreason')
    #     subs_param.del_param(self, 'mosaic_continuum_stacked_beams_synthbeamparams')
    #     subs_param.del_param(self, 'mosaic_continuum_stacked_beams_imagestatus')
    #     subs_param.del_param(self, 'mosaic_continuum_stacked_beams_continuumstatus')
    #     subs_param.del_param(self, 'mosaic_continuum_stacked_beams_copystatus')
    #     subs_param.del_param(self, 'mosaic_continuum_stacked_beams_convolstatus')
    #     subs_param.del_param(self, 'mosaic_continuum_stacked_beams_beamstatus')
    #     subs_param.del_param(self, 'mosaic_continuum_chunks_beams_inputstatus')
    #     subs_param.del_param(self, 'mosaic_continuum_chunks_beams_inputsynthbeamparams')
    #     subs_param.del_param(self, 'mosaic_continuum_chunks_beams_inputimagestats')
    #     subs_param.del_param(self, 'mosaic_continuum_chunks_beams_inputrms')
    #     subs_param.del_param(self, 'mosaic_continuum_chunks_beams_inputweights')
    #     subs_param.del_param(self, 'mosaic_continuum_chunks_beams_iterations')
    #     subs_param.del_param(self, 'mosaic_continuum_chunks_beams_rejreason')
    #     subs_param.del_param(self, 'mosaic_continuum_chunks_beams_synthbeamparams')
    #     subs_param.del_param(self, 'mosaic_continuum_chunks_beams_imagestatus')
    #     subs_param.del_param(self, 'mosaic_continuum_chunks_beams_continuumstatus')
    #     subs_param.del_param(self, 'mosaic_continuum_chunks_beams_copystatus')
    #     subs_param.del_param(self, 'mosaic_continuum_chunks_beams_convolstatus')
    #     subs_param.del_param(self, 'mosaic_continuum_chunks_beams_beamstatus')
