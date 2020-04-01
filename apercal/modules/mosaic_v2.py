import logging

import numpy as np
import os
import socket
import subprocess
import glob
import time

from apercal.modules.base import BaseModule
from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles
from apercal.subs import readmirhead as subs_readmirhead
from apercal.subs import param as subs_param
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

    # general settings
    mosaic_taskid = None
    mosaic_beams = None
    mosaic_name = None
    mosaic_continuum_mf = None
    mosaic_line = None
    mosaic_polarisation = None

    mosaic_step_limit = None

    mosaic_parallelisation = None
    mosaic_parallelisation_cpus = None

    # settings for external input
    mosaic_continuum_image_origin = None
    mosaic_polarisation_image_origin = None
    mosaic_primary_beam_type = None
    mosaic_primary_beam_shape_files_location = None
    mosaic_line_cube = None

    # general mosaic settings
    mosaic_gaussian_beam_map_size = 3073
    mosaic_gaussian_beam_map_cellsize = 4.0
    mosaic_gaussian_beam_map_fwhm_arcsec = 1950.0
    mosaic_beam_map_cutoff = 0.25
    mosaic_use_askap_based_matrix = False
    mosaic_common_beam_type = ''

    # continuumm-specific settings
    mosaic_continuum_subdir = None
    mosaic_continuum_images_subdir = None
    mosaic_continuum_beam_subdir = None
    mosaic_continuum_mosaic_subdir = None
    mosaic_continuum_projection_centre_ra = None
    mosaic_continuum_projection_centre_dec = None
    mosaic_continuum_projection_centre_beam = None
    mosaic_continuum_projection_centre_file = None
    mosaic_continuum_imsize = 5121
    mosaic_continuum_cellsize = 4
    mosaic_continuum_common_beam_type = ''
    mosaic_continuum_clean_up = None
    mosaic_continuum_clean_up_level = None
    mosaic_continuum_image_validation = None

    # polarisation specific settings
    mosaic_polarisation_subdir = None
    mosaic_polarisation_images_subdir = None
    mosaic_polarisation_beam_subdir = None
    mosaic_polarisation_mosaic_subdir = None
    mosaic_polarisation_projection_centre_beam = 'continuum'
    mosaic_polarisation_projection_centre_ra = None
    mosaic_polarisation_projection_centre_dec = None
    mosaic_polarisation_projection_centre_file= None
    mosaic_polarisation_imsize = 5121
    mosaic_polarisation_cellsize = 4
    mosaic_polarisation_common_beam_type = ''
    mosaic_polarisation_clean_up = None
    mosaic_polarisation_clean_up_level = None
    mosaic_polarisation_image_validation = None

    FNULL = open(os.devnull, 'w')

    def __init__(self, file_=None, **kwargs):
        self.default = lib.load_config(self, file_)

        # class variable not accessible through config
        self.mosaic_continuum_image_list = []

        if self.mosaic_common_beam_type == '':
            logger.info(
                "Type of common beam for convolving was not provided. Using circular beam")
            self.mosaic_common_beam_type = 'circular'

    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # The main function for the module
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def go(self):
        """
        Executes the mosaicing process in the following order

        mosaic_continuum_mf
        mosaic_line
        mosaic_polarisation
        """

        if self.mosaic_continuum_mf:
            start_time_continuum = time.time()
            logger.info("Starting MOSAICKING of continuum")
            self.create_mosaic_continuum_mf()
            logger.info("MOSAICKING of continuum done in ({0:.0f}s)".format(
                time.time() - start_time_continuum))

        if self.mosaic_line:
            self.abort_module(
                "Creating spectral-line mosaic is not yet possible")
            # start_time_continuum = time.time()
            # logger.info("Starting MOSAICKING of continuum")
            # self.create_mosaic_continuum_mf()
            # logger.info("MOSAICKING of continuum done in ({0:.0f}s)".format(time.time() - start_time_continuum))

        if self.mosaic_polarisation:
            start_time_polarisation = time.time()
            logger.info("Starting MOSAICKING of polarisation")
            self.create_mosaic_polarisation()
            logger.info("MOSAICKING of polarisation done in ({0:.0f}s)".format(time.time() - start_time_polarisation))


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
        return_msg = subprocess.check_call(
            alta_cmd, shell=True, stdout=self.FNULL, stderr=self.FNULL)

        return return_msg

    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Basic setup
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def mosaic_setup(self):
        """
        Function to create the base directory and beam list
        """

        # check the directory
        if self.basedir is None:
            self.basedir = os.getcwd()
            logger.info(
                "No base directory specified. Using current working directory {}".format(self.basedir))
        else:
            # check if the base directory exists
            if not os.path.exists(self.basedir):
                subs_managefiles.director(self, 'mk', self.basedir)
        # taskid will not be added to basedir to main mosaic dir
        # because mosaics can (in the future) also be created with images from different taskids
        self.mosdir = os.path.join(self.basedir, self.mossubdir)
        if not os.path.exists(self.mosdir):
            subs_managefiles.director(self, 'mk', self.mosdir)
        logger.info("Base directory is set to be: {}".format(self.mosdir))

        # subs_setinit.setinitdirs(self)

        # get the beams
        # set the number of beams to process>
        if self.mosaic_beams is None or self.mosaic_beams != '':
            if self.mosaic_beams == "all" or self.mosaic_beams is None:
                logger.info(
                    "No list of beams specified for mosaic. Using all beams")
                self.mosaic_beam_list = [str(k).zfill(2)
                                         for k in range(self.NBEAMS)]
            else:
                logger.info("Beams specified for mosaic: {}".format(
                    self.mosaic_beams))
                self.mosaic_beam_list = self.mosaic_beams.split(",")
                self.mosaic_beam_list.sort()
        else:
            error = "No beams specified for making the mosaic."
            logger.error(error)
            raise RuntimeError(error)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Create all the sub-directories for the mosaic
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def set_mosaic_subdirs(self, continuum=False):
        """
        Set the name of the subdirectories for the mosaic and create them

        """

        # Status of the continuum mf mosaic
        mosaic_continuum_create_subdirs_status = get_param_def(
            self, 'mosaic_continuum_create_subdirs_status', False)

        # Status of the polarisation mosaic
        mosaic_polarisation_create_subdirs_status = get_param_def(
            self, 'mosaic_polarisation_create_subdirs_status', False)

        if self.mosaic_continuum_mf:

            logger.info("Setting sub-directories for continuum mosaic")

            # create the directory for the continuunm mosaic
            if not self.mosaic_continuum_subdir:
                self.mosaic_continuum_subdir = 'continuum'
            self.mosaic_continuum_dir = os.path.join(
                self.mosdir, self.mosaic_continuum_subdir)
            if not os.path.exists(self.mosaic_continuum_dir):
                subs_managefiles.director(
                    self, 'mk', self.mosaic_continuum_dir)

            # create the sub-directory to store the continuum images
            if not self.mosaic_continuum_images_subdir:
                self.mosaic_continuum_images_subdir = 'images'
            self.mosaic_continuum_images_dir = os.path.join(
                self.mosdir, self.mosaic_continuum_subdir, self.mosaic_continuum_images_subdir)
            if not os.path.exists(self.mosaic_continuum_images_dir):
                subs_managefiles.director(
                    self, 'mk', self.mosaic_continuum_images_dir)

            # create the directory to store the beam maps
            if not self.mosaic_continuum_beam_subdir:
                self.mosaic_continuum_beam_subdir = 'beams'
            self.mosaic_continuum_beam_dir = os.path.join(
                self.mosdir, self.mosaic_continuum_subdir, self.mosaic_continuum_beam_subdir)
            if not os.path.exists(self.mosaic_continuum_beam_dir):
                subs_managefiles.director(
                    self, 'mk', self.mosaic_continuum_beam_dir)

            # create the directory to store the actual mosaic
            if not self.mosaic_continuum_mosaic_subdir:
                self.mosaic_continuum_mosaic_subdir = 'mosaic'
            self.mosaic_continuum_mosaic_dir = os.path.join(
                self.mosdir, self.mosaic_continuum_subdir, self.mosaic_continuum_mosaic_subdir)
            if not os.path.exists(self.mosaic_continuum_mosaic_dir):
                subs_managefiles.director(
                    self, 'mk', self.mosaic_continuum_mosaic_dir)

            logger.info("Setting sub-directories for continuum mosaic ... Done")

            mosaic_continuum_create_subdirs_status = True
        else:
            pass

        if self.mosaic_polarisation:

            logger.info("Setting sub-directories for polarisation mosaic")

            # create the directory for the polarisation mosaic
            if not self.mosaic_polarisation_subdir:
                self.mosaic_polarisation_subdir = 'polarisation'
            self.mosaic_polarisation_dir = os.path.join(
                self.mosdir, self.mosaic_polarisation_subdir)
            if not os.path.exists(self.mosaic_polarisation_dir):
                subs_managefiles.director(
                    self, 'mk', self.mosaic_polarisation_dir)

            # create the sub-directory to store the polarisation images
            if not self.mosaic_polarisation_images_subdir:
                self.mosaic_polarisation_images_subdir = 'images'
            self.mosaic_polarisation_images_dir = os.path.join(
                self.mosdir, self.mosaic_polarisation_subdir, self.mosaic_polarisation_images_subdir)
            if not os.path.exists(self.mosaic_polarisation_images_dir):
                subs_managefiles.director(
                    self, 'mk', self.mosaic_polarisation_images_dir)

            # create the directory to store the beam maps
            if not self.mosaic_polarisation_beam_subdir:
                self.mosaic_polarisation_beam_subdir = 'beams'
            self.mosaic_polarisation_beam_dir = os.path.join(
                self.mosdir, self.mosaic_polarisation_subdir, self.mosaic_polarisation_beam_subdir)
            if not os.path.exists(self.mosaic_polarisation_beam_dir):
                subs_managefiles.director(
                    self, 'mk', self.mosaic_polarisation_beam_dir)

            # create the directory to store the actual mosaic
            if not self.mosaic_polarisation_mosaic_subdir:
                self.mosaic_polarisation_mosaic_subdir = 'mosaic'
            self.mosaic_polarisation_mosaic_dir = os.path.join(
                self.mosdir, self.mosaic_polarisation_subdir, self.mosaic_polarisation_mosaic_subdir)
            if not os.path.exists(self.mosaic_polarisation_mosaic_dir):
                subs_managefiles.director(
                    self, 'mk', self.mosaic_polarisation_mosaic_dir)

            logger.info("Setting sub-directories for polarisation mosaic ... Done")

            mosaic_polarisation_create_subdirs_status = True
        else:
            pass

        subs_param.add_param(
            self, 'mosaic_continuum_create_subdirs_status', mosaic_continuum_create_subdirs_status)
        subs_param.add_param(
            self, 'mosaic_polarisation_create_subdirs_status', mosaic_polarisation_create_subdirs_status)

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

        mosaic_continuum_failed_beams = get_param_def(
            self, 'mosaic_continuum_failed_beams', [])

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
                logger.info(
                    "Assuming to get the data is on happili in the taskid directories")
                if socket.gethostname() == "happili-01":
                    # abort as it is not finished
                    self.abort_module(
                        "Using the default taskid directories to the continuum images has not been implemented yet.")
                else:
                    error = "This does not work from {}. It only works from happili 01. Abort".format(
                        socket.gethostname())
                    logger.error(error)
                    raise RuntimeError(error)
            # in case the data is on ALTA
            # ===========================
            elif self.mosaic_continuum_image_origin == "ALTA" or self.mosaic_continuum_image_origin is None:
                logger.info(
                    "Assuming to get the data from ALTA")

                # store failed beams
                failed_beams = []
                # go through the list of beams
                # but make a copy to be able to remove beams if they are not available
                for beam in self.mosaic_beam_list:
                    # /altaZone/archive/apertif_main/visibilities_default/<taskid>_AP_B0XY
                    alta_taskid_beam_dir = "/altaZone/archive/apertif_main/visibilities_default/{0}_AP_B{1}".format(
                        self.mosaic_taskid, beam.zfill(3))

                    # check that the beam is available on ALTA
                    if self.check_alta_path(alta_taskid_beam_dir) == 0:
                        logger.debug("Found beam {} of taskid {} on ALTA".format(
                            beam, self.mosaic_taskid))

                        # look for continuum image
                        # look for the image file (not perhaps the best way with the current setup)
                        continuum_image_name = ''
                        alta_beam_image_path = ''
                        for k in range(10):
                            continuum_image_name = "image_mf_{0:02d}.fits".format(
                                k)
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
                            continuum_image_beam_dir = os.path.join(
                                self.mosaic_continuum_images_dir, beam)
                            if not os.path.exists(continuum_image_beam_dir):
                                subs_managefiles.director(
                                    self, 'mk', continuum_image_beam_dir)

                            # check whether file already there:
                            if not os.path.exists(os.path.join(continuum_image_beam_dir, os.path.basename(alta_beam_image_path))):
                                # copy the continuum image to this directory
                                return_msg = self.getdata_from_alta(
                                    alta_beam_image_path, continuum_image_beam_dir)
                                if return_msg == 0:
                                    logger.debug("Getting image of beam {0} of taskid {1} ... Done".format(
                                        beam, self.mosaic_taskid))
                                else:
                                    logger.warning("Getting image of beam {0} of taskid {1} ... Failed".format(
                                        beam, self.mosaic_taskid))
                                    failed_beams.append(beam)
                            else:
                                logger.debug("Image of beam {0} of taskid {1} already on disk".format(
                                    beam, self.mosaic_taskid))
                    else:
                        logger.warning("Did not find beam {0} of taskid {1}".format(
                            beam, self.mosaic_taskid))
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

                        logger.debug(
                            "Getting continuum image of beam {}".format(beam))

                        # check that a directory with the beam exists
                        image_beam_dir = os.path.join(
                            self.mosaic_continuum_image_origin, beam, self.contsubdir)
                        if not os.path.isdir(image_beam_dir):
                            logger.warning(
                                "Did not find beam {} to get continuum image.".format(beam))
                            failed_beams.append(beam)
                            continue

                        # find the fits file
                        image_beam_fits_path = os.path.join(
                            image_beam_dir, "*.fits")
                        fits_files = glob.glob(image_beam_fits_path)
                        fits_files.sort()
                        if len(fits_files) == 0:
                            logger.warning(
                                "Did not find a continuum image for beam {}.".format(beam))
                            failed_beams.append(beam)
                            continue

                        # get the first one though there should only be one
                        fits_file = fits_files[0]

                        # create local beam dir only if it doesn't already exists
                        local_beam_dir = os.path.join(
                            self.mosaic_continuum_images_dir, beam)
                        if local_beam_dir != image_beam_dir:
                            subs_managefiles.director(
                                self, 'mk', local_beam_dir)

                            # copy the fits file to the beam directory
                            subs_managefiles.director(self, 'cp', os.path.join(
                                local_beam_dir, os.path.basename(fits_file)), file_=fits_file)
                        else:
                            logger.debug(
                                "Continuum file of beam {} is already available".format(beam))

                        logger.debug(
                            "Getting continuum image of beam {} ... Done".format(beam))
                else:
                    error = "The directory {} does not exists. Abort".format(
                        self.mosaic_continuum_image_origin)
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
        if len(mosaic_continuum_failed_beams) == 0:
            mosaic_continuum_failed_beams = failed_beams
        # or the other way round in case of a restart
        else:
            failed_beams = mosaic_continuum_failed_beams

        # check the failed beams
        if len(failed_beams) == len(self.mosaic_beam_list):
            self.abort_module("Did not find continuum images for all beams.")
        elif len(failed_beams) != 0:
            logger.warning("Could not find continuum images for beams {}. Removing those beams".format(
                str(failed_beams)))
            for beam in failed_beams:
                self.mosaic_beam_list.remove(beam)
            logger.warning("Will only process continuum images from {0} beams ({1})".format(
                len(self.mosaic_beam_list), str(self.mosaic_beam_list)))

            # setting parameter of getting continuum images to True
            mosaic_continuum_images_status = True
        else:
            logger.info("Found images for all beams")
            # setting parameter of getting continuum images to True
            mosaic_continuum_images_status = True

        subs_param.add_param(
            self, 'mosaic_continuum_failed_beams', mosaic_continuum_failed_beams)

        subs_param.add_param(
            self, 'mosaic_continuum_images_status', mosaic_continuum_images_status)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to get the polarisation images from different
    # locations depending on the config
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def get_mosaic_polarisation_images(self):
        """
        Function to get the polarisation images.

        Possible locations are
        1. The directories of the taskids on happili, but only if run from happili-01
        2. An existing directory with all fits files
        3. ALTA (default)

        Polarisation images are put into
        """

        # Status of the polarisation mosaic
        mosaic_polarisation_images_status = get_param_def(
            self, 'mosaic_polarisation_images_status', False)

        mosaic_polarisation_failed_beams = get_param_def(
            self, 'mosaic_polarisation_failed_beams', [])

        # collect here which beams failed
        failed_beams = []

        # check whether the fits files are already there:
        if not mosaic_polarisation_images_status:

            if self.mosaic_polarisation_image_origin == "happili":
                logger.info(
                    "Assuming to get the data is on happili in the taskid directories")
                if socket.gethostname() == "happili-01":
                    # abort as it is not finished
                    self.abort_module(
                        "Using the default taskid directories to the polarisation images has not been implemented yet.")
                else:
                    error = "This does not work from {}. It only works from happili 01. Abort".format(
                        socket.gethostname())
                    logger.error(error)
                    raise RuntimeError(error)
            # in case the data is on ALTA
            # ===========================
            elif self.mosaic_polarisation_image_origin == "ALTA" or self.mosaic_polarisation_image_origin is None:
                logger.info(
                    "Assuming to get the data from ALTA")

                # store failed beams
                failed_beams = []
                # go through the list of beams
                # but make a copy to be able to remove beams if they are not available
                for beam in self.mosaic_beam_list:
                    # /altaZone/archive/apertif_main/visibilities_default/<taskid>_AP_B0XY
                    alta_taskid_beam_dir = "/altaZone/archive/apertif_main/visibilities_default/{0}_AP_B{1}".format(
                        self.mosaic_taskid, beam.zfill(3))

                    # check that the beam is available on ALTA
                    if self.check_alta_path(alta_taskid_beam_dir) == 0:
                        logger.debug("Found beam {} of taskid {} on ALTA".format(
                            beam, self.mosaic_taskid))

                        # look for continuum image
                        # look for the image file (not perhaps the best way with the current setup)
                        polarisation_image_names = ["Qcube.fits","Ucube.fits","image_mf_V.fits"]
                        alta_beam_image_path = ''
                        for im in polarisation_image_names:
                            alta_beam_image_path = os.path.join(
                                alta_taskid_beam_dir, im)
                            if self.check_alta_path(alta_beam_image_path) == 0:
                                break
                            else:
                                # make empty again when no image was found
                                polarisation_image_names = ''
                                continue
                        if polarisation_image_names == '':
                            logger.warning(
                                "No image found on ALTA for beam {0} of taskid {1}".format(beam, self.mosaic_taskid))
                            failed_beams.append(beam)
                        else:
                            # create directory for beam in the image of the continuum mosaic
                            polarisation_image_beam_dir = os.path.join(
                                self.mosaic_polarisation_images_dir, beam)
                            if not os.path.exists(polarisation_image_beam_dir):
                                subs_managefiles.director(
                                    self, 'mk', polarisation_image_beam_dir)

                            # check whether file already there:
                            if not os.path.exists(os.path.join(polarisation_image_beam_dir, os.path.basename(alta_beam_image_path))):
                                # copy the continuum image to this directory
                                return_msg = self.getdata_from_alta(
                                    alta_beam_image_path, polarisation_image_beam_dir)
                                if return_msg == 0:
                                    logger.debug("Getting image of beam {0} of taskid {1} ... Done".format(
                                        beam, self.mosaic_taskid))
                                else:
                                    logger.warning("Getting image of beam {0} of taskid {1} ... Failed".format(
                                        beam, self.mosaic_taskid))
                                    failed_beams.append(beam)
                            else:
                                logger.debug("Image of beam {0} of taskid {1} already on disk".format(
                                    beam, self.mosaic_taskid))
                    else:
                        logger.warning("Did not find beam {0} of taskid {1}".format(
                            beam, self.mosaic_taskid))
                        # remove the beam
                        failed_beams.append(beam)

            # in case a directory has been specified
            # (not stable)
            # ======================================
            elif self.mosaic_polarisation_image_origin != "":
                # check that the directory exists
                logger.info(
                    "Assuming to get the data from a specific directory")
                if os.path.isdir(self.mosaic_polarisation_image_origin):

                    # go through the beams
                    for beam in self.mosaic_beam_list:

                        logger.debug(
                            "Getting polarisation images of beam {}".format(beam))

                        # check that a directory with the beam exists
                        image_beam_dir = os.path.join(
                            self.mosaic_polarisation_image_origin, beam, self.polsubdir)
                        if not os.path.isdir(image_beam_dir):
                            logger.warning(
                                "Did not find beam {} to get polarisation images.".format(beam))
                            failed_beams.append(beam)
                            continue

                        # find the fits file
                        image_beam_fits_path = os.path.join(
                            image_beam_dir, "*.fits")
                        fits_files = glob.glob(image_beam_fits_path)
                        fits_files.sort() # not needed here, but still do
                        if len(fits_files) == 0:
                            logger.warning(
                                "Did not find polarisation images for beam {}.".format(beam))
                            failed_beams.append(beam)
                            continue

                        # create local beam dir only if it doesn't already exists
                        local_beam_dir = os.path.join(
                            self.mosaic_polarisation_images_dir, beam)
                        if local_beam_dir != image_beam_dir:
                            subs_managefiles.director(
                                self, 'mk', local_beam_dir)

                            # copy the fits file to the beam directory
                            for fits_file in fits_files:
                                subs_managefiles.director(self, 'cp', os.path.join(
                                    local_beam_dir, os.path.basename(fits_file)), file_=fits_file)
                        else:
                            logger.debug(
                                "Polarisation files of beam {} is already available".format(beam))

                        logger.debug(
                            "Getting polarisation images of beam {} ... Done".format(beam))
                else:
                    error = "The directory {} does not exists. Abort".format(
                        self.mosaic_polarisation_image_origin)
                    logger.error(error)
                    raise RuntimeError(error)
            else:
                logger.info("Assuming the data is on ALTA")
                error = "Cannot get data from ALTA yet. Abort"
                logger.error(error)
                raise RuntimeError(error)

        else:
            logger.info("Polarisation image fits files are already available.")

        # assign list of failed beams to variable that will be stored
        if len(mosaic_polarisation_failed_beams) == 0:
            mosaic_polarisation_failed_beams = failed_beams
        # or the other way round in case of a restart
        else:
            failed_beams = mosaic_polarisation_failed_beams

        # check the failed beams
        if len(failed_beams) == len(self.mosaic_beam_list):
            self.abort_module("Did not find polarisation images for all beams.")
        elif len(failed_beams) != 0:
            logger.warning("Could not find polarisation images for beams {}. Removing those beams".format(
                str(failed_beams)))
            for beam in failed_beams:
                self.mosaic_beam_list.remove(beam)
            logger.warning("Will only process polarisation images from {0} beams ({1})".format(
                len(self.mosaic_beam_list), str(self.mosaic_beam_list)))

            # setting parameter of getting continuum images to True
            mosaic_polarisation_images_status = True
        else:
            logger.info("Found images for all beams")
            # setting parameter of getting continuum images to True
            mosaic_polarisation_images_status = True

        subs_param.add_param(
            self, 'mosaic_polarisation_failed_beams', mosaic_polarisation_failed_beams)

        subs_param.add_param(
            self, 'mosaic_polarisation_images_status', mosaic_polarisation_images_status)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to get the beam maps
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def get_mosaic_continuum_beams(self):
        """
        Getting the information for each beam if they are not already present
        """

        logger.info("Creating beam maps for continuum")

        mosaic_continuum_beam_status = get_param_def(
            self, 'mosaic_continuum_beam_status', False)

        if not mosaic_continuum_beam_status:

            for beam in self.mosaic_beam_list:
                logger.info("Creating continuum beam map of beam {}".format(beam))
                # change to directory of continuum images
                subs_managefiles.director(
                    self, 'ch', self.mosaic_continuum_dir)

                try:
                    mosaic_utils.create_beam(beam, self.mosaic_continuum_beam_subdir, corrtype=self.mosaic_primary_beam_type, primary_beam_path=self.mosaic_primary_beam_shape_files_location,
                                             bm_size=self.mosaic_gaussian_beam_map_size,
                                             cell=self.mosaic_gaussian_beam_map_cellsize,
                                             fwhm=self.mosaic_gaussian_beam_map_fwhm_arcsec,
                                             cutoff=self.mosaic_beam_map_cutoff)
                except Exception as e:
                    error = "Creating continuum beam map of beam {} ... Failed".format(beam)
                    logger.warning(error)
                    logger.exception(e)
                    raise RuntimeError(error)
                else:
                    logger.debug(
                        "Creating continuum beam map of beam {} ... Done".format(beam))
                    mosaic_continuum_beam_status = True
        else:
            logger.info("Continuum beam maps are already available.")

        logger.info("Creating continuum beam maps ... Done")

        subs_param.add_param(
            self, 'mosaic_continuum_beam_status', mosaic_continuum_beam_status)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to get the beam maps
    # +++++++++++++++++++++++++++++++++++++++++++++++++++

    def get_mosaic_polarisation_beams(self):
        """
        Getting the information for each beam if they are not already present
        """

        logger.info("Creating polarisation beam maps")

        mosaic_polarisation_beam_status = get_param_def(
            self, 'mosaic_polarisation_beam_status', False)

        if not mosaic_polarisation_beam_status:

            for beam in self.mosaic_beam_list:
                logger.debug("Creating polarisation beam maps of beam {}".format(beam))
                # change to directory of polarisation images
                subs_managefiles.director(
                    self, 'ch', self.mosaic_polarisation_dir)

                try:
                    mosaic_utils.create_beam(beam, self.mosaic_polarisation_beam_subdir, corrtype=self.mosaic_primary_beam_type, primary_beam_path=self.mosaic_primary_beam_shape_files_location,
                                             bm_size=self.mosaic_gaussian_beam_map_size,
                                             cell=self.mosaic_gaussian_beam_map_cellsize,
                                             fwhm=self.mosaic_gaussian_beam_map_fwhm_arcsec,
                                             cutoff=self.mosaic_beam_map_cutoff)
                except Exception as e:
                    error = "Creating polarisation beam maps of beam {} ... Failed".format(beam)
                    logger.warning(error)
                    logger.exception(e)
                    raise RuntimeError(error)
                else:
                    logger.debug(
                        "Creating polarisation beam maps of beam {} ... Done".format(beam))
                    mosaic_polarisation_beam_status = True
        else:
            logger.info("Polarisation beam maps are already available.")

        logger.info("Creating polarisation beam maps ... Done")

        subs_param.add_param(
            self, 'mosaic_polarisation_beam_status', mosaic_polarisation_beam_status)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to convert images to miriad
    # Can be moved to mosaic_utils.py
    # +++++++++++++++++++++++++++++++++++++++++++++++++++

    def convert_continuum_images_to_miriad(self):
        """
        Convert continuum fits images to miriad format

        Based on notebook function import_image(beam_num)

        At the moment the function is only successful
        if all beams were successfully.

        TODO:
            Conversion should be parallelised.
        """

        logger.info("Converting continuum fits images to miriad images")

        mosaic_continuum_convert_fits_images_status = get_param_def(
            self, 'mosaic_continuum_convert_fits_images_status', False)

        # change to directory of continuum images
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_images_dir)

        if not mosaic_continuum_convert_fits_images_status:

            # go through the list of beams
            for beam in self.mosaic_beam_list:

                logger.debug(
                    "Converting continuum fits image of beam {} to miriad image".format(beam))

                mir_map_name = '{0}/image_{0}.map'.format(beam)

                if not os.path.isdir(mir_map_name):
                    # This function will import a FITS image into Miriad placing it in the mosaicdir
                    fits = lib.miriad('fits')
                    fits.op = 'xyin'
                    fits.in_ = glob.glob(os.path.join(beam, "*.fits"))[0]
                    fits.out = '{0}/image_{0}.map'.format(beam)
                    try:
                        fits.go()
                    except Exception as e:
                        mosaic_continuum_convert_fits_images_status = False
                        error = "Converting continuum fits image of beam {} to miriad image ... Failed".format(
                            beam)
                        logger.error(error)
                        logger.exception(e)
                        raise RuntimeError(error)
                    else:
                        mosaic_continuum_convert_fits_images_status = True
                        logger.debug(
                            "Converting continuum fits image of beam {} to miriad image ... Done".format(beam))

                else:
                    logger.warning(
                        "Miriad continuum image already exists for beam {}. Did not convert from fits again".format(beam))
                    mosaic_continuum_convert_fits_images_status = True

            if mosaic_continuum_convert_fits_images_status:
                logger.info(
                    "Converting continuum fits images to miriad images ... Done")
            else:
                logger.warning(
                    "Converting continuum fits images to miriad images ... Failed for at least one beam. Please check the log")
        else:
            logger.info("Continuum images have already been converted.")

        subs_param.add_param(
            self, 'mosaic_continuum_convert_fits_images_status', mosaic_continuum_convert_fits_images_status)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to convert the Q and U cubes and the V image into MIRIAD
    # +++++++++++++++++++++++++++++++++++++++++++++++++++

    def convert_polarisation_images_to_miriad(self):
        """
        """

        mosaic_polarisation_convert_fits_images_status = get_param_def(
            self, 'mosaic_polarisation_convert_fits_images_status', False)

        # change to directory of polarisation images
        subs_managefiles.director(self, 'ch', self.mosaic_polarisation_images_dir)

        if not mosaic_polarisation_convert_fits_images_status:

            for beam in self.mosaic_beam_list:
                # Convert the Q and U cubes to MIRIAD
                try:
                    fits = lib.miriad('fits')
                    fits.op = "xyin"
                    fits.in_ = os.path.join(beam, "Qcube.fits")
                    fits.out = os.path.join(beam, "Qcube")
                    fits.go()
                    fits.in_ = os.path.join(beam, "Ucube.fits")
                    fits.out = os.path.join(beam, "Ucube")
                    fits.go()
                    fits.in_ = os.path.join(beam, "image_mf_V.fits")
                    fits.out = os.path.join(beam, "image_mf_V")
                    fits.go()
                except Exception as e:
                    mosaic_polarisation_convert_fits_images_status = False
                    error = "Converting polarisation fits images of beam {} to miriad image ... Failed".format(
                        beam)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)
                else:
                    mosaic_polarisation_convert_fits_images_status = True
                    logger.debug(
                        "Converting polarisation fits images of beam {} to miriad image ... Done".format(beam))

            if mosaic_polarisation_convert_fits_images_status:
                logger.info(
                    "Converting polarisation fits images to miriad images ... Successful")
            else:
                logger.warning(
                    "Converting polarisation fits images to miriad images ... Failed for at least one beam. Please check the log.")
        else:
            logger.info("Polarisation images have already been converted.")

        subs_param.add_param(
            self, 'mosaic_polarisation_convert_fits_images_status', mosaic_polarisation_convert_fits_images_status)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to split the Q and U cubes into single images
    # +++++++++++++++++++++++++++++++++++++++++++++++++++

    def split_polarisation_images(self):

        mosaic_polarisation_split_cubes_status = get_param_def(
            self, 'mosaic_polarisation_split_cubes_status', False)

        # change to directory of polarisation images
        subs_managefiles.director(self, 'ch', self.mosaic_polarisation_images_dir)

        if not mosaic_polarisation_split_cubes_status:

            for beam in self.mosaic_beam_list:

                # Get the needed parameters
                pbeam = 'polarisation_B' + str(beam).zfill(2)
                polbeamimagestatus = get_param_def(self, pbeam + '_targetbeams_qu_imagestatus', False)
                polbeamimagebeams = get_param_def(self, pbeam + '_targetbeams_qu_beamparams', False)
                qimages = len(polbeamimagestatus)

                # Split the Q cube into single images
                for qplane in range(qimages):
                    try:
                        imsub = lib.miriad('imsub')
                        imsub.in_ = os.path.join(beam, "Qcube")
                        imsub.out = os.path.join(beam, "Qcube_" + str(qplane).zfill(3))
                        imsub.region = 'percentage"(100,100)(' + str(qplane) + ',' + str(qplane) + ')"'
                        imsub.go()
                        # Add the right beam to the header of the Q images
                        beamparms = polbeamimagebeams[qplane, :, 0]
                        subs_readmirhead.putbeamimage(imsub.out, beamparms)
                        mosaic_polarisation_split_cubes_status = True
                    except:
                        warning = "Polarisation Q-image #{1} of beam {0} is empty or has no beam information".format(
                            beam, qplane)
                        logger.warning(warning)

                # Split the U cube into single images
                uimages = len(polbeamimagestatus)
                for uplane in range(uimages):
                    try:
                        imsub = lib.miriad('imsub')
                        imsub.in_ = os.path.join(beam, "Ucube")
                        imsub.out = os.path.join(beam, "Ucube_" + str(uplane).zfill(3))
                        imsub.region = 'percentage"(100,100)(' + str(uplane) + ',' + str(uplane) + ')"'
                        imsub.go()
                        # Add the right beam to the header of the U images
                        beamparms = polbeamimagebeams[uplane, :, 1]
                        subs_readmirhead.putbeamimage(imsub.out, beamparms)
                        mosaic_polarisation_split_cubes_status = True
                    except:
                        warning = "Polarisation U-image #{1} of beam {0} is empty or has no beam information".format(
                            beam, uplane)
                        logger.warning(warning)

        else:
            logger.info("Q- and U-polarisation images have already been split.")

        subs_param.add_param(
            self, 'mosaic_polarisation_split_cubes_status', mosaic_polarisation_split_cubes_status)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to get the projection centre based on
    # the config
    # +++++++++++++++++++++++++++++++++++++++++++++++++++

    def get_mosaic_continuum_projection_centre(self):
        """
        Getting the information for the projection center
        """

        mosaic_continuum_projection_centre_status = get_param_def(
            self, 'mosaic_continuum_projection_centre_status', False)

        mosaic_continuum_projection_centre_values = get_param_def(
            self, 'mosaic_continuum_projection_centre_values', ['', ''])

        if self.mosaic_continuum_projection_centre_ra is not None and self.mosaic_continuum_projection_centre_dec is not None:
            logger.info("Using input projection center: RA={0} and DEC={1}".format(
                self.mosaic_continuum_projection_centre_ra, self.mosaic_continuum_projection_centre_dec))
            mosaic_continuum_projection_centre_status = True
        elif self.mosaic_continuum_projection_centre_beam is not None:
            logger.info("Using pointing centre of beam {} as the projection centre".format(
                self.mosaic_continuum_projection_centre_beam))

            # change to directory of continuum images
            subs_managefiles.director(
                self, 'ch', self.mosaic_continuum_images_dir)

            # Extract central RA and Dec for Apertif pointing from a chosen beam
            if self.mosaic_continuum_projection_centre_beam in self.mosaic_beam_list:
                gethd = lib.miriad('gethd')
                gethd.in_ = '{0}/image_{0}.map/crval1'.format(
                    str(self.mosaic_continuum_projection_centre_beam).zfill(2))
                gethd.format = 'hms'
                ra_ref = gethd.go()
                gethd.in_ = '{0}/image_{0}.map/crval2'.format(
                    str(self.mosaic_continuum_projection_centre_beam).zfill(2))
                gethd.format = 'dms'
                dec_ref = gethd.go()
            else:
                error = "Failed reading projection centre from beam {}. Beam not available".format(
                    self.mosaic_continuum_projection_centre_beam)
                logger.error(error)
                raise RuntimeError(error)

            # assigning ra and dec
            self.mosaic_continuum_projection_centre_ra = ra_ref[0]
            self.mosaic_continuum_projection_centre_dec = dec_ref[0]
        elif self.mosaic_continuum_projection_centre_file != '':
            logger.info("Reading projection center from file {}".format(
                self.mosaic_continuum_projection_centre_file))

            # not available yet
            self.abort_module(
                "Reading projection center from file has not been implemented yet")
        else:
            self.abort_module("Did not recognise projection centre option")

        logger.info("Projection centre will be RA={0} and DEC={1}".format(
            self.mosaic_continuum_projection_centre_ra, self.mosaic_continuum_projection_centre_dec))

        subs_param.add_param(
            self, 'mosaic_continuum_projection_centre_status', mosaic_continuum_projection_centre_status)
        subs_param.add_param(
            self, 'mosaic_continuum_projection_centre_values', [self.mosaic_continuum_projection_centre_ra, self.mosaic_continuum_projection_centre_dec])


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to get the projection centre based on
    # the config
    # +++++++++++++++++++++++++++++++++++++++++++++++++++

    def get_mosaic_polarisation_projection_centre(self):
        """
        Getting the information for the projection center
        """

        mosaic_polarisation_projection_centre_status = get_param_def(
            self, 'mosaic_polarisation_projection_centre_status', False)

        mosaic_polarisation_projection_centre_values = get_param_def(
            self, 'mosaic_polarisation_projection_centre_values', ['', ''])

        if self.mosaic_polarisation_projection_centre_ra is not None and self.mosaic_polarisation_projection_centre_dec is not None:
            logger.info("Using input projection center: RA={0} and DEC={1}".format(
                self.mosaic_polarisation_projection_centre_ra, self.mosaic_polarisation_projection_centre_dec))
            mosaic_polarisation_projection_centre_status = True
        elif self.mosaic_polarisation_projection_centre_beam is not None:
            # change to directory of polarisation images
            subs_managefiles.director(self, 'ch', self.mosaic_polarisation_images_dir)
            if self.mosaic_polarisation_projection_centre_beam == 'continuum':
                logger.info("Using the same projection centre as for continuum")
                if subs_param.check_param(self,  'mosaic_continuum_projection_centre_values'):
                    mosaic_polarisation_projection_centre_values = subs_param.get_param_def(self, 'mosaic_continuum_projection_centre_values', ['', ''])
                    self.mosaic_polarisation_projection_centre_ra = mosaic_polarisation_projection_centre_values[0]
                    self.mosaic_polarisation_projection_centre_dec = mosaic_polarisation_projection_centre_values[1]
                    mosaic_polarisation_projection_centre_status = True
                else:
                    mosaic_polarisation_projection_centre_status = False
                    error = "Failed using the same projection centre as for continuum. Information not available!"
                    logger.error(error)
                    raise RuntimeError(error)
            else:
                logger.info("Using pointing centre of beam {} as the projection centre".format(
                    self.mosaic_polarisation_projection_centre_beam))

                # Extract central RA and Dec for Apertif pointing from a chosen beam from the Stokes V image
                if self.mosaic_polarisation_projection_centre_beam in self.mosaic_beam_list:
                    gethd = lib.miriad('gethd')
                    gethd.in_ = '{0}/image_mf_V/crval1'.format(
                        str(self.mosaic_polarisation_projection_centre_beam).zfill(2))
                    gethd.format = 'hms'
                    ra_ref = gethd.go()
                    gethd.in_ = '{0}/image_mf_V/crval2'.format(
                        str(self.mosaic_polarisation_projection_centre_beam).zfill(2))
                    gethd.format = 'dms'
                    dec_ref = gethd.go()
                else:
                    error = "Failed reading projection centre from beam {}. Beam not available".format(
                        self.mosaic_polarisation_projection_centre_beam)
                    logger.error(error)
                    raise RuntimeError(error)
                # assigning ra and dec
                self.mosaic_polarisation_projection_centre_ra = ra_ref[0]
                self.mosaic_polarisation_projection_centre_dec = dec_ref[0]
        elif self.mosaic_polarisation_projection_centre_file != '':
            logger.info("Reading projection center from file {}".format(self.mosaic_polarisation_projection_centre_file))

            # not available yet
            self.abort_module("Reading projection center from file has not been implemented yet")
        else:
            self.abort_module("Did not recognise projection centre option")

        logger.info("Projection centre will be RA={0} and DEC={1}".format(
            self.mosaic_polarisation_projection_centre_ra, self.mosaic_polarisation_projection_centre_dec))

        subs_param.add_param(self, 'mosaic_polarisation_projection_centre_status', mosaic_polarisation_projection_centre_status)
        subs_param.add_param(self, 'mosaic_polarisation_projection_centre_values', [self.mosaic_polarisation_projection_centre_ra, self.mosaic_polarisation_projection_centre_dec])


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to transfer image coordinates to beam maps
    # +++++++++++++++++++++++++++++++++++++++++++++++++++

    def transfer_continuum_coordinates(self):
        """
        Function to transfer image coordinates to beam maps

        Based on the notebook cell

        For the proper beam maps, this should be done by the
        function make the proper beam maps. Probably best to
        move this function there for the simple beam maps, too
        """

        logger.info("Transfering image coordinates to beam maps for continuum")

        mosaic_continuum_transfer_coordinates_to_beam_status = get_param_def(
            self, 'mosaic_continuum_transfer_coordinates_to_beam_status', False)

        # change to directory of continuum images
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_dir)

        if not mosaic_continuum_transfer_coordinates_to_beam_status:

            for beam in self.mosaic_beam_list:

                logger.debug("Processing beam {}".format(beam))

                # get RA
                gethd = lib.miriad('gethd')
                gethd.in_ = os.path.join(
                    self.mosaic_continuum_images_subdir, '{0}/image_{0}.map/crval1'.format(beam))
                try:
                    ra1 = gethd.go()
                except Exception as e:
                    mosaic_continuum_transfer_coordinates_to_beam_status = False
                    error = "Reading RA of beam {} failed".format(beam)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)
                else:
                    mosaic_continuum_transfer_coordinates_to_beam_status = True

                # write RA
                puthd = lib.miriad('puthd')
                puthd.in_ = os.path.join(
                    self.mosaic_continuum_beam_subdir, 'beam_{}.map/crval1'.format(beam))
                puthd.value = float(ra1[0])
                try:
                    puthd.go()
                except Exception as e:
                    mosaic_continuum_transfer_coordinates_to_beam_status = False
                    error = "Writing RA of beam {} failed".format(beam)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)
                else:
                    mosaic_continuum_transfer_coordinates_to_beam_status = True

                # get DEC
                gethd.in_ = os.path.join(
                    self.mosaic_continuum_images_subdir, '{0}/image_{0}.map/crval2'.format(beam))
                try:
                    dec1 = gethd.go()
                except Exception as e:
                    mosaic_continuum_transfer_coordinates_to_beam_status = False
                    error = "Reading DEC of beam {} failed".format(beam)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)
                else:
                    mosaic_continuum_transfer_coordinates_to_beam_status = True

                # write DEC
                puthd.in_ = os.path.join(
                    self.mosaic_continuum_beam_subdir, 'beam_{}.map/crval2'.format(beam))
                puthd.value = float(dec1[0])
                try:
                    puthd.go()
                except Exception as e:
                    mosaic_continuum_transfer_coordinates_to_beam_status = False
                    error = "Writing DEC of beam {} failed".format(beam)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)
                else:
                    mosaic_continuum_transfer_coordinates_to_beam_status = True

                logger.debug("Processing continuum beam {} ... Done".format(beam))

            if mosaic_continuum_transfer_coordinates_to_beam_status:
                logger.info("Transfering image coordinates to beam maps for continuum ... Done")
            else:
                logger.info("Transfering image coordinates to beam maps for continuum ... Failed")
        else:
            logger.info("Continuum image coordinates have already been transferred")

        subs_param.add_param(
            self, 'mosaic_continuum_transfer_coordinates_to_beam_status', mosaic_continuum_transfer_coordinates_to_beam_status)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to transfer image coordinates to beam maps
    # +++++++++++++++++++++++++++++++++++++++++++++++++++

    def transfer_polarisation_coordinates(self):
        """
        Function to transfer image coordinates to beam maps

        Based on the notebook cell

        For the proper beam maps, this should be done by the
        function make the proper beam maps. Probably best to
        move this function there for the simple beam maps, too
        """

        logger.info("Transfering image coordinates to beam maps for polarisation")

        mosaic_polarisation_transfer_coordinates_to_beam_status = get_param_def(
            self, 'mosaic_polarisation_transfer_coordinates_to_beam_status', False)

        # change to directory of polarisation images
        subs_managefiles.director(self, 'ch', self.mosaic_polarisation_dir)

        if not mosaic_polarisation_transfer_coordinates_to_beam_status:

            for beam in self.mosaic_beam_list:

                logger.debug("Processing beam {}".format(beam))

                # get RA
                gethd = lib.miriad('gethd')
                gethd.in_ = os.path.join(
                    self.mosaic_polarisation_images_subdir, '{0}/image_mf_V/crval1'.format(beam))
                try:
                    ra1 = gethd.go()
                except Exception as e:
                    mosaic_polarisation_transfer_coordinates_to_beam_status = False
                    error = "Reading RA of beam {} failed".format(beam)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)
                else:
                    mosaic_polarisation_transfer_coordinates_to_beam_status = True

                # write RA
                puthd = lib.miriad('puthd')
                puthd.in_ = os.path.join(
                    self.mosaic_polarisation_beam_subdir, 'beam_{}.map/crval1'.format(beam))
                puthd.value = float(ra1[0])
                try:
                    puthd.go()
                except Exception as e:
                    mosaic_polarisation_transfer_coordinates_to_beam_status = False
                    error = "Writing RA of beam {} failed".format(beam)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)
                else:
                    mosaic_polarisation_transfer_coordinates_to_beam_status = True

                # get DEC
                gethd.in_ = os.path.join(
                    self.mosaic_polarisation_images_subdir, '{0}/image_mf_V/crval2'.format(beam))
                try:
                    dec1 = gethd.go()
                except Exception as e:
                    mosaic_polarisation_transfer_coordinates_to_beam_status = False
                    error = "Reading DEC of beam {} failed".format(beam)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)
                else:
                    mosaic_polarisation_transfer_coordinates_to_beam_status = True

                # write DEC
                puthd.in_ = os.path.join(
                    self.mosaic_polarisation_beam_subdir, 'beam_{}.map/crval2'.format(beam))
                puthd.value = float(dec1[0])
                try:
                    puthd.go()
                except Exception as e:
                    mosaic_polarisation_transfer_coordinates_to_beam_status = False
                    error = "Writing DEC of beam {} failed".format(beam)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)
                else:
                    mosaic_polarisation_transfer_coordinates_to_beam_status = True

                logger.debug("Processing beam {} ... Done".format(beam))

            if mosaic_polarisation_transfer_coordinates_to_beam_status:
                logger.info("Transfering image coordinates to beam maps for polarisation ... Done")
            else:
                logger.info("Transfering image coordinates to beam maps for polarisation ... Failed")
        else:
            logger.info("Polarisation image coordinates have already been transfered")

        subs_param.add_param(
            self, 'mosaic_polarisation_transfer_coordinates_to_beam_status', mosaic_polarisation_transfer_coordinates_to_beam_status)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to create the template mosaic for continuum
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def create_continuum_template_mosaic(self):
        """
        Create an template mosaic to be filled in later
        """

        logger.info("Creating continuum template mosaic")

        mosaic_continuum_template_mosaic_status = get_param_def(
            self, 'mosaic_continuum_template_mosaic_status', False)

        template_continuum_mosaic_name = "mosaic_continuum_template.map"

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_mosaic_dir)

        if mosaic_continuum_template_mosaic_status and os.path.isdir(template_continuum_mosaic_name):
            logger.info("Continuum template mosaic already exists")
        else:
            # This will create a template for the mosaic using "imgen" in Miriad
            # number of pixels of mosaic maps
            imsize = self.mosaic_continuum_imsize
            # cell size in arcsec
            cell = self.mosaic_continuum_cellsize

            # create template prior to changing projection
            imgen = lib.miriad('imgen')
            imgen.out = 'mosaic_continuum_temp_preproj.map'
            imgen.imsize = imsize
            imgen.cell = cell
            imgen.object = 'level'
            imgen.spar = '0.'
            imgen.radec = '{0},{1}'.format(
                str(self.mosaic_continuum_projection_centre_ra), str(self.mosaic_continuum_projection_centre_dec))
            try:
                imgen.go()
            except Exception as e:
                error = "Error creating continuum template mosaic image"
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)

            # Now change projection to NCP
            regrid = lib.miriad('regrid')
            regrid.in_ = 'mosaic_continuum_temp_preproj.map'
            regrid.out = template_continuum_mosaic_name
            regrid.project = 'NCP'
            try:
                regrid.go()
            except Exception as e:
                error = "Error changing projection to NCP"
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)

            logger.info("Creating continuum template mosaic ... Done")
            mosaic_continuum_template_mosaic_status = True

        subs_param.add_param(
            self, 'mosaic_continuum_template_mosaic_status', mosaic_continuum_template_mosaic_status)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to create the template mosaic for polarisation
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def create_polarisation_template_mosaic(self):
        """
        Create an template mosaic to be filled in later
        """

        logger.info("Creating polarisation template mosaic")

        mosaic_polarisation_template_mosaic_status = get_param_def(
            self, 'mosaic_polarisation_template_mosaic_status', False)

        template_polarisation_mosaic_name = "mosaic_polarisation_template.map"

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_polarisation_mosaic_dir)

        if mosaic_polarisation_template_mosaic_status and os.path.isdir(template_polarisation_mosaic_name):
            logger.info("Polarisation template mosaic already exists")
        else:
            # This will create a template for the mosaic using "imgen" in Miriad
            # number of pixels of mosaic maps
            imsize = self.mosaic_polarisation_imsize
            # cell size in arcsec
            cell = self.mosaic_polarisation_cellsize

            # create template prior to changing projection
            imgen = lib.miriad('imgen')
            imgen.out = 'mosaic_polarisation_temp_preproj.map'
            imgen.imsize = imsize
            imgen.cell = cell
            imgen.object = 'level'
            imgen.spar = '0.'
            imgen.radec = '{0},{1}'.format(
                str(self.mosaic_polarisation_projection_centre_ra), str(self.mosaic_polarisation_projection_centre_dec))
            try:
                imgen.go()
            except Exception as e:
                error = "Error creating polarisation template mosaic image"
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)

            # Now change projection to NCP
            regrid = lib.miriad('regrid')
            regrid.in_ = 'mosaic_polarisation_temp_preproj.map'
            regrid.out = template_polarisation_mosaic_name
            regrid.project = 'NCP'
            try:
                regrid.go()
            except Exception as e:
                error = "Error changing projection to NCP"
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)

            logger.info("Creating polarisation template mosaic ... Done")
            mosaic_polarisation_template_mosaic_status = True

        subs_param.add_param(
            self, 'mosaic_polarisation_template_mosaic_status', mosaic_polarisation_template_mosaic_status)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to regrid continuum images based on mosaic template
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def regrid_continuum_images(self):
        """
        Function to regrid continuum images using the template mosaic
        """

        logger.info("Regridding continuum images")

        mosaic_continuum_regrid_images_status = get_param_def(
            self, 'mosaic_continuum_regrid_images_status', False)

        if not mosaic_continuum_regrid_images_status:
            # switch to continuum mosaic directory
            subs_managefiles.director(self, 'ch', self.mosaic_continuum_dir)

            # Put images on mosaic template grid
            for beam in self.mosaic_beam_list:
                logger.debug("Regridding continuum beam {}".format(beam))
                regrid = lib.miriad('regrid')
                input_file = os.path.join(self.mosaic_continuum_images_subdir, '{0}/image_{0}.map'.format(beam))
                output_file = os.path.join(self.mosaic_continuum_images_subdir, 'image_{}_regrid.map'.format(beam))
                template_continuum_mosaic_file = os.path.join(self.mosaic_continuum_mosaic_subdir, "mosaic_continuum_template.map")
                if not os.path.isdir(output_file):
                    if os.path.isdir(input_file):
                        regrid.in_ = input_file
                        regrid.out = output_file
                        regrid.tin = template_continuum_mosaic_file
                        regrid.axes = '1,2'
                        try:
                            regrid.go()
                        except Exception as e:
                            error = "Failed regridding continuum image of beam {}".format(beam)
                            logger.error(error)
                            logger.exception(e)
                            raise RuntimeError(error)
                    else:
                        error = "Did not find convolved continuum image for beam {}".format(beam)
                        logger.error(error)
                        raise RuntimeError(error)
                else:
                    logger.warning("Regridded continuum image of beam {} already exists".format(beam))

            logger.info("Regridding continuum images ... Done")
            mosaic_continuum_regrid_images_status = True
        else:
            logger.info("Continuum images have already been regridded")

        subs_param.add_param(
            self, 'mosaic_continuum_regrid_images_status', mosaic_continuum_regrid_images_status)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to regrid polarisation images based on mosaic template
    # +++++++++++++++++++++++++++++++++++++++++++++++++++

    def regrid_polarisation_images(self):
        """
        Function to regrid polarisation images using the template mosaic
        """

        logger.info("Regridding polarisation images")

        mosaic_polarisation_regrid_images_status = get_param_def(self, 'mosaic_polarisation_regrid_images_status', False)

        if not mosaic_polarisation_regrid_images_status:
            # switch to polarisation mosaic directory
            subs_managefiles.director(self, 'ch', self.mosaic_polarisation_dir)

            # Put images on mosaic template grid
            for beam in self.mosaic_beam_list:

                # Get the needed information from the param files
                pbeam = 'polarisation_B' + str(beam).zfill(2)
                polbeamimagestatus = get_param_def(self, pbeam + '_targetbeams_qu_imagestatus', False)
                qimages = len(polbeamimagestatus)
                # Do the regridding for each individual image
                for qplane in range(qimages):
                    logger.debug("Regridding Stokes Q image #{0} of beam {1}".format(qplane, beam))
                    regrid = lib.miriad('regrid')
                    input_file = os.path.join(
                        self.mosaic_polarisation_images_subdir, beam, "Qcube_" + str(qplane).zfill(3))
                    output_file = os.path.join(
                        self.mosaic_polarisation_images_subdir, "Qcube_" + str(beam).zfill(2) + '_' + str(qplane).zfill(3) + '_regrid.map')
                    template_polarisation_mosaic_file = os.path.join(
                        self.mosaic_polarisation_mosaic_subdir, "mosaic_polarisation_template.map")
                    if not os.path.isdir(output_file):
                        if os.path.isdir(input_file):
                            regrid.in_ = input_file
                            regrid.out = output_file
                            regrid.tin = template_polarisation_mosaic_file
                            regrid.axes = '1,2'
                            try:
                                regrid.go()
                            except Exception as e:
                                error = "Failed regridding Stokes Q image #{0} of beam {1}".format(
                                    qplane, beam)
                                logger.error(error)
                                logger.exception(e)
                                raise RuntimeError(error)
                        else:
                            warning = "Did not find convolved Stokes Q image #{0} for beam {1}".format(
                                qplane, beam)
                            logger.warning(warning)
                    else:
                        logger.warning(
                            "Regridded Stokes Q image #{0} of beam {1} already exists".format(qplane, beam))

                for uplane in range(qimages):
                    logger.debug("Regridding Stokes U image #{0} of beam {1}".format(uplane, beam))
                    regrid = lib.miriad('regrid')
                    input_file = os.path.join(
                        self.mosaic_polarisation_images_subdir, beam, "Ucube_" + str(uplane).zfill(3))
                    output_file = os.path.join(
                        self.mosaic_polarisation_images_subdir, "Ucube_" + str(beam).zfill(2) + '_' + str(uplane).zfill(3) + '_regrid.map')
                    template_polarisation_mosaic_file = os.path.join(
                        self.mosaic_polarisation_mosaic_subdir, "mosaic_polarisation_template.map")
                    if not os.path.isdir(output_file):
                        if os.path.isdir(input_file):
                            regrid.in_ = input_file
                            regrid.out = output_file
                            regrid.tin = template_polarisation_mosaic_file
                            regrid.axes = '1,2'
                            try:
                                regrid.go()
                            except Exception as e:
                                error = "Failed regridding Stokes U image #{0} of beam {1}".format(uplane, beam)
                                logger.error(error)
                                logger.exception(e)
                                raise RuntimeError(error)
                        else:
                            warning = "Did not find convolved Stokes U image #{0} for beam {1}".format(uplane, beam)
                            logger.warning(warning)
                    else:
                        logger.warning("Regridded Stokes U image #{0} of beam {1} already exists".format(uplane, beam))

                logger.debug("Regridding Stokes V image of beam {}".format(beam))
                regrid = lib.miriad('regrid')
                input_file = os.path.join(
                    self.mosaic_polarisation_images_subdir, '{0}/image_mf_V'.format(beam))
                output_file = os.path.join(
                    self.mosaic_polarisation_images_subdir, 'image_mf_V_{0}_regrid.map'.format(beam))
                template_polarisation_mosaic_file = os.path.join(
                    self.mosaic_polarisation_mosaic_subdir, "mosaic_polarisation_template.map")
                if not os.path.isdir(output_file):
                    if os.path.isdir(input_file):
                        regrid.in_ = input_file
                        regrid.out = output_file
                        regrid.tin = template_polarisation_mosaic_file
                        regrid.axes = '1,2'
                        try:
                            regrid.go()
                        except Exception as e:
                            error = "Failed regridding Stokes V image of beam {}".format(
                                beam)
                            logger.error(error)
                            logger.exception(e)
                            raise RuntimeError(error)
                    else:
                        error = "Did not find convolved Stokes V image for beam {}".format(
                            beam)
                        logger.error(error)
                        raise RuntimeError(error)
                else:
                    logger.warning("Regridded Stokes V image of beam {} already exists".format(beam))

            logger.info("Regridding polarisation images ... Done")
            mosaic_polarisation_regrid_images_status = True
        else:
            logger.info("polarisation images have already been regridded")

        subs_param.add_param(
            self, 'mosaic_polarisation_regrid_images_status', mosaic_polarisation_regrid_images_status)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to regrid continuum beam maps based on mosaic template
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def regrid_continuum_beam_maps(self):
        """
        Function to regrid beam images using the template mosaic
        """

        logger.info("Regridding continuum beam maps")

        mosaic_continuum_regrid_beam_maps_status = get_param_def(
            self, 'mosaic_continuum_regrid_beam_maps_status', False)

        if not mosaic_continuum_regrid_beam_maps_status:
            # switch to mosaic directory
            subs_managefiles.director(self, 'ch', self.mosaic_continuum_dir)

            # Put images on mosaic template grid
            for beam in self.mosaic_beam_list:
                input_file = os.path.join(
                    self.mosaic_continuum_beam_subdir, 'beam_{}.map'.format(beam))
                output_file = os.path.join(
                    self.mosaic_continuum_beam_subdir, 'beam_{}_mos.map'.format(beam))
                template_continuum_mosaic_file = os.path.join(
                    self.mosaic_continuum_mosaic_subdir, "mosaic_continuum_template.map")
                regrid = lib.miriad('regrid')
                if not os.path.isdir(output_file):
                    if os.path.isdir(input_file):
                        regrid.in_ = input_file
                        regrid.out = output_file
                        regrid.tin = template_continuum_mosaic_file
                        regrid.axes = '1,2'
                        try:
                            regrid.go()
                        except Exception as e:
                            error = "Failed regridding continuum beam_maps of beam {}".format(beam)
                            logger.error(error)
                            logger.exception(e)
                            raise RuntimeError(error)
                    else:
                        error = "Did not find continuum beam map for beam {}".format(beam)
                        logger.error(error)
                        raise RuntimeError(error)
                else:
                    logger.warning("Regridded continuum beam map of beam {} already exists".format(beam))

            logger.info("Regridding continuum beam maps ... Done")

            mosaic_continuum_regrid_beam_maps_status = True
        else:
            logger.info("Regridding of continuum beam maps has already been done")

        subs_param.add_param(
            self, 'mosaic_continuum_regrid_beam_maps_status', mosaic_continuum_regrid_beam_maps_status)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to regrid polarisation beam maps based on mosaic template
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def regrid_polarisation_beam_maps(self):
        """
        Function to regrid beam images using the template mosaic
        """

        logger.info("Regridding polarisation beam maps")

        mosaic_polarisation_regrid_beam_maps_status = get_param_def(
            self, 'mosaic_polarisation_regrid_beam_maps_status', False)

        if not mosaic_polarisation_regrid_beam_maps_status:
            # switch to mosaic directory
            subs_managefiles.director(self, 'ch', self.mosaic_polarisation_dir)

            # Put images on mosaic template grid
            for beam in self.mosaic_beam_list:
                input_file = os.path.join(
                    self.mosaic_polarisation_beam_subdir, 'beam_{}.map'.format(beam))
                output_file = os.path.join(
                    self.mosaic_polarisation_beam_subdir, 'beam_{}_mos.map'.format(beam))
                template_polarisation_mosaic_file = os.path.join(
                    self.mosaic_polarisation_mosaic_subdir, "mosaic_polarisation_template.map")
                regrid = lib.miriad('regrid')
                if not os.path.isdir(output_file):
                    if os.path.isdir(input_file):
                        regrid.in_ = input_file
                        regrid.out = output_file
                        regrid.tin = template_polarisation_mosaic_file
                        regrid.axes = '1,2'
                        try:
                            regrid.go()
                        except Exception as e:
                            error = "Failed regridding polarisation beam_maps of beam {}".format(beam)
                            logger.error(error)
                            logger.exception(e)
                            raise RuntimeError(error)
                    else:
                        error = "Did not find polarisation beam map for beam {}".format(beam)
                        logger.error(error)
                        raise RuntimeError(error)
                else:
                    logger.warning("Regridded polarisation beam map of beam {} already exists".format(beam))

            logger.info("Regridding polarisation beam maps ... Done")

            mosaic_polarisation_regrid_beam_maps_status = True
        else:
            logger.info("Regridding of polarisation beam maps has already been done")

        subs_param.add_param(
            self, 'mosaic_polarisation_regrid_beam_maps_status', mosaic_polarisation_regrid_beam_maps_status)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to get the common beam for the continuum images
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def get_continuum_common_beam(self):
        """
        Function to calculate a common beam to convolve images

        Based on the cell on the same synthesized beam.

        There are several options
        1. Calculate a circular beam (default)
        2. Calculate the maximum beam
        """

        mosaic_continuum_common_beam_status = get_param_def(
            self, 'mosaic_continuum_common_beam_status', False)

        mosaic_continuum_common_beam_values = get_param_def(
            self, 'mosaic_continuum_common_beam_values', np.zeros(3))

        logger.info("Calculating common beam for convolution of continuum images")

        # change to directory of continuum images
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_images_dir)

        if not mosaic_continuum_common_beam_status:
            # this is where the beam information will be stored
            bmaj = []
            bmin = []
            bpa = []

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
            bmajor = 3600. * np.degrees(bmajor)

            bminor = [float(x[0]) for x in bmin]
            bminor = 3600. * np.degrees(bminor)

            bangle = [float(x[0]) for x in bpa]
            bangle = np.degrees(bangle)

            if self.mosaic_continuum_common_beam_type == 'circular':
                logger.debug("Using circular beam")
                max_axis = np.nanmax([bmajor, bminor])
                c_beam = [1.05 * max_axis, 1.05 * max_axis, 0.]
            elif self.mosaic_continuum_common_beam_type == "elliptical":
                logger.debug("Using elliptical beam")
                c_beam = [1.05 * np.nanmax(bmajor), 1.05 *
                          np.nanmax(bminor), np.nanmedian(bangle)]
            else:
                error = "Unknown type of common beam requested. Abort"
                logger.error(error)
                raise RuntimeError(error)

            logger.debug(
                'The final, convolved, synthesized beam has bmaj, bmin, bpa of: {}'.format(str(c_beam)))

            mosaic_continuum_common_beam_status = True
            mosaic_continuum_common_beam_values = c_beam
        else:
            logger.info("Continuum common beam already available as bmaj, bmin, bpa of: {}".format(
                str(mosaic_continuum_common_beam_values)))

        subs_param.add_param(
            self, 'mosaic_continuum_common_beam_status', mosaic_continuum_common_beam_status)

        subs_param.add_param(
            self, 'mosaic_continuum_common_beam_values', mosaic_continuum_common_beam_values)

        # +++++++++++++++++++++++++++++++++++++++++++++++++++
        # Function to get the common beam for the polarisation images
        # +++++++++++++++++++++++++++++++++++++++++++++++++++

    def get_polarisation_common_beam(self):
        """
        Function to calculate a common beam to convolve images

        Based on the cell on the same synthesized beam.

        There are several options
        1. Calculate a circular beam (default)
        2. Calculate the maximum beam
        """

        mosaic_polarisation_common_beam_status = get_param_def(
            self, 'mosaic_polarisation_common_beam_status', False)

        # Get the needed information from the param files
        pbeam = 'polarisation_B' + str(self.mosaic_beam_list[0]).zfill(2)
        polbeamimagestatus = get_param_def(self, pbeam + '_targetbeams_qu_imagestatus', False)
        qimages = len(polbeamimagestatus)

        mosaic_polarisation_common_beam_values_qu = get_param_def(
            self, 'mosaic_polarisation_common_beam_values_qu', np.zeros((2, qimages, 3)))

        mosaic_polarisation_common_beam_values_v = get_param_def(
            self, 'mosaic_polarisation_common_beam_values_v', np.zeros(3))

        logger.info("Calculating common beam for convolution of polarisation images")

        # change to directory of polarisation images
        subs_managefiles.director(self, 'ch', self.mosaic_polarisation_images_dir)

        if not mosaic_polarisation_common_beam_status:

            # Calculate the common beam values for the Stokes Q images
            for qplane in range(qimages):
                # this is where the beam information will be stored
                bmaj = []
                bmin = []
                bpa = []

                # go through the beams and get the information
                for beam in self.mosaic_beam_list:
                    gethd = lib.miriad('gethd')
                    gethd.in_ = os.path.join(beam, "Qcube_" + str(qplane).zfill(3) + '/bmaj')
                    bmaj.append(gethd.go())
                    gethd.in_ = os.path.join(beam, "Qcube_" + str(qplane).zfill(3) + '/bmin')
                    bmin.append(gethd.go())
                    gethd.in_ = os.path.join(beam, "Qcube_" + str(qplane).zfill(3) + '/bpa')
                    bpa.append(gethd.go())

                # Calculate maximum bmaj and bmin and median bpa for final convolved beam shape
                bmajor = [float(x[0]) for x in bmaj]
                bmajor = 3600. * np.degrees(bmajor)

                bminor = [float(x[0]) for x in bmin]
                bminor = 3600. * np.degrees(bminor)

                bangle = [float(x[0]) for x in bpa]
                bangle = np.degrees(bangle)

                if self.mosaic_polarisation_common_beam_type == 'circular':
                    logger.debug("Using circular beam")
                    max_axis = np.nanmax([bmajor, bminor])
                    c_beam = [1.05 * max_axis, 1.05 * max_axis, 0.]
                elif self.mosaic_polarisation_common_beam_type == "elliptical":
                    logger.debug("Using elliptical beam")
                    c_beam = [1.05 * np.nanmax(bmajor), 1.05 *
                              np.nanmax(bminor), np.nanmedian(bangle)]
                else:
                    error = "Unknown type of common beam requested. Abort"
                    logger.error(error)
                    raise RuntimeError(error)

                logger.debug('The final, convolved, synthesized beam has bmaj, bmin, bpa of: {}'.format(str(c_beam)))

                mosaic_polarisation_common_beam_values_qu[0, qplane, :] = c_beam

            # Calculate the common beam values for the Stokes U images
            for uplane in range(qimages):
                # this is where the beam information will be stored
                bmaj = []
                bmin = []
                bpa = []

                # go through the beams and get the information
                for beam in self.mosaic_beam_list:
                    gethd = lib.miriad('gethd')
                    gethd.in_ = os.path.join(beam, "Ucube_" + str(uplane).zfill(3) + '/bmaj')
                    bmaj.append(gethd.go())
                    gethd.in_ = os.path.join(beam, "Ucube_" + str(uplane).zfill(3) + '/bmin')
                    bmin.append(gethd.go())
                    gethd.in_ = os.path.join(beam, "Ucube_" + str(uplane).zfill(3) + '/bpa')
                    bpa.append(gethd.go())

                # Calculate maximum bmaj and bmin and median bpa for final convolved beam shape
                bmajor = [float(x[0]) for x in bmaj]
                bmajor = 3600. * np.degrees(bmajor)

                bminor = [float(x[0]) for x in bmin]
                bminor = 3600. * np.degrees(bminor)

                bangle = [float(x[0]) for x in bpa]
                bangle = np.degrees(bangle)

                if self.mosaic_polarisation_common_beam_type == 'circular':
                    logger.debug("Using circular beam")
                    max_axis = np.nanmax([bmajor, bminor])
                    c_beam = [1.05 * max_axis, 1.05 * max_axis, 0.]
                elif self.mosaic_polarisation_common_beam_type == "elliptical":
                    logger.debug("Using elliptical beam")
                    c_beam = [1.05 * np.nanmax(bmajor), 1.05 *
                              np.nanmax(bminor), np.nanmedian(bangle)]
                else:
                    error = "Unknown type of common beam requested. Abort"
                    logger.error(error)
                    raise RuntimeError(error)

                logger.debug('The final, convolved, synthesized beam has bmaj, bmin, bpa of: {}'.format(str(c_beam)))

                mosaic_polarisation_common_beam_values_qu[1, uplane, :] = c_beam

            # Calculate the common beam values for the Stokes V images
            # this is where the beam information will be stored
            bmaj = []
            bmin = []
            bpa = []

            # go through the beams and get the information
            for beam in self.mosaic_beam_list:
                gethd = lib.miriad('gethd')
                gethd.in_ = '{0}/image_mf_V/bmaj'.format(beam)
                bmaj.append(gethd.go())
                gethd.in_ = '{0}/image_mf_V/bmin'.format(beam)
                bmin.append(gethd.go())
                gethd.in_ = '{0}/image_mf_V/bpa'.format(beam)
                bpa.append(gethd.go())

            # Calculate maximum bmaj and bmin and median bpa for final convolved beam shape
            bmajor = [float(x[0]) for x in bmaj]
            bmajor = 3600. * np.degrees(bmajor)

            bminor = [float(x[0]) for x in bmin]
            bminor = 3600. * np.degrees(bminor)

            bangle = [float(x[0]) for x in bpa]
            bangle = np.degrees(bangle)

            if self.mosaic_polarisation_common_beam_type == 'circular':
                logger.debug("Using circular beam")
                max_axis = np.nanmax([bmajor, bminor])
                c_beam = [1.05 * max_axis, 1.05 * max_axis, 0.]
            elif self.mosaic_polarisation_common_beam_type == "elliptical":
                logger.debug("Using elliptical beam")
                c_beam = [1.05 * np.nanmax(bmajor), 1.05 *
                          np.nanmax(bminor), np.nanmedian(bangle)]
            else:
                error = "Unknown type of common beam requested. Abort"
                logger.error(error)
                raise RuntimeError(error)

            logger.debug('The final, convolved, synthesized beam has bmaj, bmin, bpa of: {}'.format(str(c_beam)))

            mosaic_polarisation_common_beam_values_v = c_beam

            mosaic_polarisation_common_beam_status = True

        else:
            logger.info("Polarisation common beams already available")

        subs_param.add_param(
            self, 'mosaic_polarisation_common_beam_status', mosaic_polarisation_common_beam_status)

        subs_param.add_param(
            self, 'mosaic_polarisation_common_beam_values_qu', mosaic_polarisation_common_beam_values_qu)

        subs_param.add_param(
            self, 'mosaic_polarisation_common_beam_values_v', mosaic_polarisation_common_beam_values_v)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to convolve continuum images
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def mosaic_continuum_convolve_images(self):
        """
        Function to convolve continuum images with the common beam

        Should be executed after gridding unless a circular common beam is chosen

        Note:
            Could be moved
        """

        mosaic_continuum_convolve_images_status = get_param_def(
            self, 'mosaic_continuum_convolve_images_status', False)

        mosaic_continuum_common_beam_values = get_param_def(
            self, 'mosaic_continuum_common_beam_values', np.zeros(3))

        logger.info("Convolving continuum images with common beam with beam {}".format(
            mosaic_continuum_common_beam_values))

        # change to directory of continuum images
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_dir)

        if not mosaic_continuum_convolve_images_status:

            for beam in self.mosaic_beam_list:
                logger.info("Convolving continuum image of beam {}".format(beam))

                # output map and input map
                input_file = os.path.join(
                    self.mosaic_continuum_images_subdir, 'image_{0}_regrid.map'.format(beam))
                output_file = os.path.join(
                    self.mosaic_continuum_mosaic_subdir, 'image_{0}_mos.map'.format(beam))

                if not os.path.isdir(output_file):
                    convol = lib.miriad('convol')
                    convol.map = input_file
                    convol.out = output_file
                    convol.fwhm = '{0},{1}'.format(
                        str(mosaic_continuum_common_beam_values[0]), str(mosaic_continuum_common_beam_values[1]))
                    convol.pa = mosaic_continuum_common_beam_values[2]
                    convol.options = 'final'
                    try:
                        convol.go()
                    except Exception as e:
                        error = "Convolving continuum image of beam {} ... Failed".format(beam)
                        logger.error(error)
                        logger.exception(e)
                        raise RuntimeError(error)
                    else:
                        logger.debug("Convolving continuum image of beam {} ... Done".format(beam))
                else:
                    logger.warning("Convolved continuum image of beam {} already exists".format(beam))

                    mosaic_continuum_convolve_images_status = True

            logger.info("Convolving continuum images with common beam ... Done")
        else:
            logger.info("Continuum images have already been convolved")

        subs_param.add_param(
            self, 'mosaic_continuum_convolve_images_status', mosaic_continuum_convolve_images_status)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to convolve polarisation images
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def mosaic_polarisation_convolve_images(self):
        """
        Function to convolve polarisation images with the common beam

        Should be executed after gridding unless a circular common beam is chosen

        Note:
            Could be moved
        """

        # Get the needed information from the param files
        pbeam = 'polarisation_B' + str(self.mosaic_beam_list[0]).zfill(2)
        polbeamimagestatus = get_param_def(self, pbeam + '_targetbeams_qu_imagestatus', False)
        qimages = len(polbeamimagestatus)

        mosaic_polarisation_common_beam_values_qu = get_param_def(
            self, 'mosaic_polarisation_common_beam_values_qu', np.zeros((2, qimages, 3)))

        mosaic_polarisation_common_beam_values_v = get_param_def(
            self, 'mosaic_polarisation_common_beam_values_v', np.zeros(3))

        mosaic_polarisation_convolve_images_status = get_param_def(
            self, 'mosaic_polarisation_convolve_images_status', False)

        logger.info("Convolving polarisation images with common beams")

        # change to directory of polarisation images
        subs_managefiles.director(self, 'ch', self.mosaic_polarisation_dir)

        if not mosaic_polarisation_convolve_images_status:

            # Calculate the common beam values for the Stokes Q images
            for qplane in range(qimages):
                for beam in self.mosaic_beam_list:
                    logger.debug("Convolving Stokes Q image of beam {}".format(beam))

                    # output map and input map
                    input_file = os.path.join(
                        self.mosaic_polarisation_images_subdir, "Qcube_" + str(beam).zfill(2) + '_' + str(qplane).zfill(3) + '_regrid.map')
                    output_file = os.path.join(
                        self.mosaic_polarisation_mosaic_subdir, "Qcube_" + str(beam).zfill(2) + '_' + str(qplane).zfill(3) + '_mos.map')

                    if not os.path.isdir(output_file):
                        convol = lib.miriad('convol')
                        convol.map = input_file
                        convol.out = output_file
                        convol.fwhm = '{0},{1}'.format(
                            str(mosaic_polarisation_common_beam_values_qu[0, qplane, 0]), str(mosaic_polarisation_common_beam_values_qu[0, qplane, 1]))
                        convol.pa = mosaic_polarisation_common_beam_values_qu[0, qplane, 2]
                        convol.options = 'final'
                        try:
                            convol.go()
                        except Exception as e:
                            error = "Convolving Stokes Q image {0} of beam {1} ... Failed".format(
                                qplane, beam)
                            logger.error(error)
                            logger.exception(e)
                            raise RuntimeError(error)
                        else:
                            logger.debug("Convolving Stokes Q image {0} of beam {1} ... Done".format(qplane, beam))
                    else:
                        logger.warning(
                            "Convolved Stokes Q image {0} of beam {1} already exists".format(qplane, beam))

            # Calculate the common beam values for the Stokes Q images
            for uplane in range(qimages):
                for beam in self.mosaic_beam_list:
                    logger.info("Convolving Stokes U image of beam {}".format(beam))

                    # output map and input map
                    input_file = os.path.join(
                        self.mosaic_polarisation_images_subdir, "Ucube_" + str(beam).zfill(2) + '_' + str(uplane).zfill(3) + '_regrid.map')
                    output_file = os.path.join(
                        self.mosaic_polarisation_mosaic_subdir, "Ucube_" + str(beam).zfill(2) + '_' + str(uplane).zfill(3) + '_mos.map')

                    if not os.path.isdir(output_file):
                        convol = lib.miriad('convol')
                        convol.map = input_file
                        convol.out = output_file
                        convol.fwhm = '{0},{1}'.format(
                            str(mosaic_polarisation_common_beam_values_qu[1, uplane, 0]),
                            str(mosaic_polarisation_common_beam_values_qu[1, uplane, 1]))
                        convol.pa = mosaic_polarisation_common_beam_values_qu[1, uplane, 2]
                        convol.options = 'final'
                        try:
                            convol.go()
                        except Exception as e:
                            error = "Convolving Stokes U image {0} of beam {1} ... Failed".format(
                                uplane, beam)
                            logger.error(error)
                            logger.exception(e)
                            raise RuntimeError(error)
                        else:
                            logger.debug(
                                "Convolving Stokes U image {0} of beam {1} ... Done".format(uplane, beam))
                    else:
                        logger.warning(
                            "Convolved Stokes U image {0} of beam {1} already exists".format(uplane, beam))

            for beam in self.mosaic_beam_list:
                logger.info("Convolving Stokes V image of beam {}".format(beam))

                # output map and input map
                input_file = os.path.join(
                    self.mosaic_polarisation_images_subdir, 'image_mf_V_{}_regrid.map'.format(beam))
                output_file = os.path.join(
                    self.mosaic_polarisation_mosaic_subdir, 'image_mf_V_{}_mos.map'.format(beam))

                if not os.path.isdir(output_file):
                    convol = lib.miriad('convol')
                    convol.map = input_file
                    convol.out = output_file
                    convol.fwhm = '{0},{1}'.format(
                        str(mosaic_polarisation_common_beam_values_v[0]), str(mosaic_polarisation_common_beam_values_v[1]))
                    convol.pa = mosaic_polarisation_common_beam_values_v[2]
                    convol.options = 'final'
                    try:
                        convol.go()
                    except Exception as e:
                        error = "Convolving Stokes V image of beam {} ... Failed".format(
                            beam)
                        logger.error(error)
                        logger.exception(e)
                        raise RuntimeError(error)
                    else:
                        logger.debug("Convolving Stokes V image of beam {} ... Done".format(beam))
                else:
                    logger.warning("Convolved Stokes V image of beam {} already exists".format(beam))

            mosaic_polarisation_convolve_images_status = True

            logger.info("Convolving polarisation images with common beam ... Done")
        else:
            logger.info("Polarisation images have already been convolved")

        subs_param.add_param(
            self, 'mosaic_polarisation_convolve_images_status', mosaic_polarisation_convolve_images_status)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to get the correlation matrix
    # +++++++++++++++++++++++++++++++++++++++++++++++++++

    def get_continuum_inverted_covariance_matrix(self):
        """
        Function to get the covariance matrix

        Based on the cell that reads-in the correlation matrix
        """

        logger.info("Calculating inverse covariance matrix for continuum")

        mosaic_continuum_correlation_matrix_status = get_param_def(
            self, 'mosaic_continuum_correlation_matrix_status', False)

        mosaic_continuum_inverse_covariance_matrix = get_param_def(
            self, 'mosaic_continuum_inverse_covariance_matrix', [])

        # change to directory of continuum images
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_dir)

        correlation_matrix_file = os.path.join(self.mosaic_continuum_dir, 'correlation.txt')

        if not mosaic_continuum_correlation_matrix_status:
            logger.info("Writing continuum correlation matrix")
            mosaic_utils.create_correlation_matrix(correlation_matrix_file, use_askap_based_matrix=self.mosaic_use_askap_based_matrix)
            if os.path.isfile(correlation_matrix_file):
                mosaic_continuum_correlation_matrix_status = True
                logger.info("Writing continuum correlation matrix ... Done")
            else:
                logger.error("Writing continuum correlation matrix ... Failed")
                mosaic_continuum_correlation_matrix_status = False
        else:
            logger.info("Continuum correlation matrix already available as file on disk.")

        if mosaic_continuum_correlation_matrix_status:
            if len(mosaic_continuum_inverse_covariance_matrix) == 0:
                logger.info("Calculating inverse continuum covariance matrix ...")
                mosaic_continuum_inverse_covariance_matrix = mosaic_utils.inverted_covariance_matrix('images/{0}/image_{0}.map', correlation_matrix_file, self.NBEAMS, self.mosaic_beam_list)
                logger.info("Calculating inverse continuum covariance matrix ... Done")
            else:
                logger.info("Inverse of covariance matrix for continuum is available on disk already.")

        subs_param.add_param(
            self, 'mosaic_continuum_correlation_matrix_status', mosaic_continuum_correlation_matrix_status)

        subs_param.add_param(
            self, 'mosaic_continuum_inverse_covariance_matrix', mosaic_continuum_inverse_covariance_matrix)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to get the correlation matrix
    # +++++++++++++++++++++++++++++++++++++++++++++++++++

    def get_polarisation_inverted_covariance_matrix(self):
        """
        Function to get the covariance matrix

        Based on the cell that reads-in the correlation matrix
        """

        logger.info("Calculating inverse covariance matrix for polarisation")

        # Get the needed information from the param files
        pbeam = 'polarisation_B' + str(self.mosaic_beam_list[0]).zfill(2)
        polbeamimagestatus = get_param_def(self, pbeam + '_targetbeams_qu_imagestatus', False)
        qimages = len(polbeamimagestatus)

        mosaic_polarisation_correlation_matrix_status = get_param_def(
            self, 'mosaic_polarisation_correlation_matrix_status', False)

        mosaic_polarisation_inverse_covariance_matrix_q = get_param_def(
            self, 'mosaic_polarisation_inverse_covariance_matrix_q', [None]*qimages)

        mosaic_polarisation_inverse_covariance_matrix_u = get_param_def(
            self, 'mosaic_polarisation_inverse_covariance_matrix_u', [None]*qimages)

        mosaic_polarisation_inverse_covariance_matrix_v = get_param_def(
            self, 'mosaic_polarisation_inverse_covariance_matrix_v', [])

        mosaic_polarisation_inverse_covariance_matrix_status = get_param_def(
            self, 'mosaic_polarisation_inverse_covariance_matrix_status', False)

        subs_managefiles.director(self, 'ch', self.mosaic_polarisation_dir)

        correlation_matrix_file = os.path.join(self.mosaic_polarisation_dir, 'correlation.txt')

        mosaic_continuum_correlation_matrix_status = get_param_def(
            self, 'mosaic_continuum_correlation_matrix_status', False)

        if not mosaic_polarisation_correlation_matrix_status:
            logger.info("Writing polarisation correlation matrix")
            if mosaic_continuum_correlation_matrix_status:
                logger.info("Copying correlation matrix from continuum")
                subs_managefiles.director(self, 'cp', correlation_matrix_file,  os.path.join(self.mosaic_continuum_dir, 'correlation.txt'))
                mosaic_polarisation_correlation_matrix_status = True
            else:
                mosaic_utils.create_correlation_matrix(correlation_matrix_file, use_askap_based_matrix=self.mosaic_use_askap_based_matrix)
                if os.path.isfile(correlation_matrix_file):
                    mosaic_polarisation_correlation_matrix_status = True
                    logger.info("Writing polarisation correlation matrix ... Done")
                else:
                    logger.error("Writing polarisation correlation matrix ... Failed")
                    mosaic_polarisation_correlation_matrix_status = False
        else:
            logger.info("Polarisation correlation matrix already available as file on disk.")

        if mosaic_polarisation_correlation_matrix_status:

            logger.info("Calculating inverse polarisation covariance matrix for Stokes Q images ...")
            for qplane in range(qimages):
                if mosaic_polarisation_inverse_covariance_matrix_q[qplane] is np.ndarray:
                    logger.info("Inverse of covariance matrix for polarisation Stokes Q image {} is available on disk already.".format(qplane))
                else:
                    try:
                        mosaic_polarisation_inverse_covariance_matrix_q[qplane] = mosaic_utils.inverted_covariance_matrix('images/{0}/Qcube_' + str(qplane).zfill(3), correlation_matrix_file, self.NBEAMS, self.mosaic_beam_list)
                    except:
                        logger.warning("Could not derive inverse covariance matrix for Stokes Q plane {}!".format(qplane))
                        continue
            logger.info("Calculating inverse polarisation covariance matrix for Stokes Q images ... Done")

            logger.info("Calculating inverse polarisation covariance matrix for Stokes U images ...")
            for uplane in range(qimages):
                if mosaic_polarisation_inverse_covariance_matrix_u[uplane] == np.ndarray:
                    logger.info("Inverse of covariance matrix for polarisation Stokes U image {} is available on disk already.".format(uplane))
                else:
                    try:
                        mosaic_polarisation_inverse_covariance_matrix_u[uplane] = mosaic_utils.inverted_covariance_matrix('images/{0}/Ucube_' + str(uplane).zfill(3), correlation_matrix_file, self.NBEAMS, self.mosaic_beam_list)
                    except:
                        logger.warning("Could not derive inverse covariance matrix for Stokes U plane {}!".format(uplane))
                        continue
            logger.info("Calculating inverse polarisation covariance matrix for Stokes U images ... Done")

            if len(mosaic_polarisation_inverse_covariance_matrix_v) == 0:
                logger.info("Calculating inverse polarisation covariance matrix for Stokes V images ...")
                mosaic_polarisation_inverse_covariance_matrix_v = mosaic_utils.inverted_covariance_matrix('images/{0}/image_mf_V', correlation_matrix_file, self.NBEAMS, self.mosaic_beam_list)
                logger.info("Calculating inverse polarisation covariance matrix for Stokes V images ... Done")
            else:
                logger.info("Inverse of covariance matrix for polarisation Stokes V is available on disk already.")
        else:
            logger.error("Polarisation correlation matrix not available!")

        if all(q is None for q in mosaic_polarisation_inverse_covariance_matrix_q) and all(u is None for u in mosaic_polarisation_inverse_covariance_matrix_u) and mosaic_polarisation_inverse_covariance_matrix_v == 0:
            mosaic_polarisation_inverse_covariance_matrix_status = False
            logger.error("Not all inverted polarisation covariance matrices have been calculated successfully!")
        else:
            mosaic_polarisation_inverse_covariance_matrix_status = True


        subs_param.add_param(self, 'mosaic_polarisation_correlation_matrix_status', mosaic_polarisation_correlation_matrix_status)

        subs_param.add_param(self, 'mosaic_polarisation_inverse_covariance_matrix_q', mosaic_polarisation_inverse_covariance_matrix_q)

        subs_param.add_param(self, 'mosaic_polarisation_inverse_covariance_matrix_u', mosaic_polarisation_inverse_covariance_matrix_u)

        subs_param.add_param(self, 'mosaic_polarisation_inverse_covariance_matrix_v', mosaic_polarisation_inverse_covariance_matrix_v)

        subs_param.add_param(self, 'mosaic_polarisation_inverse_covariance_matrix_status', mosaic_polarisation_inverse_covariance_matrix_status)


    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to calculate the product of continuum beam matrix and continuum covariance matrix
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def math_continuum_multiply_beam_and_covariance_matrix(self):
        """
        Function to multiply the transpose of the continuum beam matrix by the continuum covariance matrix
        """

        logger.info("Multiplying continuum beam matrix by continuum covariance matrix")

        mosaic_continuum_product_beam_covariance_matrix_status = get_param_def(self, 'mosaic_continuum_product_beam_covariance_matrix_status', False)

        # get continuum covariance matrix from numpy file
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

        if not mosaic_continuum_product_beam_covariance_matrix_status:
            # First calculate transpose of beam matrix multiplied by the inverse covariance matrix
            # Will use *maths* in Miriad

            # Using "beams" list to account for missing beams/images
            # Only doing math where inv_cov value is non-zero
            maths = lib.miriad('maths')
            for bm in self.mosaic_beam_list:
                logger.debug("Processing beam {}".format(bm))
                # This was not in the notebook.
                # Are you it should be here ???? Yes, according to DJ
                operate = ""
                for b in self.mosaic_beam_list:
                    maths.out = os.path.join(
                        self.mosaic_continuum_mosaic_subdir, 'tmp_{}.map'.format(b))
                    # since the beam list is made of strings, need to convert to integers
                    beam_map = os.path.join(
                        self.mosaic_continuum_beam_subdir, "beam_{0}_mos.map".format(b))
                    if os.path.isdir(beam_map):
                        if inv_cov[int(b), int(bm)] != 0.:
                            operate = "'<{0}>*({1})'".format(beam_map, inv_cov[int(b), int(bm)])
                        else:
                            operate = "'<{0}>*(0)'".format(beam_map)
                        logger.debug("for beam combination {0},{1}: operate = {2}".format(bm, b, operate))
                        maths.exp = operate
                        maths.options = 'unmask'
                        maths.go()
                    else:
                        error = "Could not find continuum mosaic beam map for beam {}".format(b)
                        logger.error(error)
                        raise RuntimeError(error)
                i = 1
                while i < len(self.mosaic_beam_list):
                    if os.path.isdir(os.path.join(self.mosaic_continuum_mosaic_subdir, "tmp_{}.map".format(self.mosaic_beam_list[i-1]))) and os.path.isdir(os.path.join(self.mosaic_continuum_mosaic_subdir, "tmp_{}.map".format(self.mosaic_beam_list[i]))):
                        if i == 1:
                            operate = "'<" + self.mosaic_continuum_mosaic_subdir + "/tmp_{}.map>+<".format(str(
                                self.mosaic_beam_list[i-1]))+self.mosaic_continuum_mosaic_subdir + "/tmp_{}.map>'".format(str(self.mosaic_beam_list[i]))
                        else:
                            operate = "'<" + self.mosaic_continuum_mosaic_subdir + "/tmp_{}.map>".format(str(
                                self.mosaic_beam_list[i])) + "+<" + self.mosaic_continuum_mosaic_subdir + "/sum_{}.map>'".format(str(self.mosaic_beam_list[i-1]))
                        maths.out = self.mosaic_continuum_mosaic_subdir + \
                            '/sum_{}.map'.format(str(self.mosaic_beam_list[i]))
                        maths.exp = operate
                        maths.options = 'unmask'
                        maths.go()
                    else:
                        error = "Could not find temporary continuum maps for beam {0} or beam {1}".format(
                            self.mosaic_beam_list[i-1], self.mosaic_beam_list[i])
                        logger.error(error)
                        raise RuntimeError(error)
                    i += 1

                if os.path.isdir(os.path.join(self.mosaic_continuum_mosaic_subdir, 'sum_{}.map'.format(self.mosaic_beam_list[i-1]))):
                    subs_managefiles.director(self, 'rn', self.mosaic_continuum_mosaic_subdir + '/btci_{}.map'.format(
                        bm), file_=self.mosaic_continuum_mosaic_subdir + '/sum_{}.map'.format(str(self.mosaic_beam_list[i-1])))
                    # os.rename(,self.mosaic_continuum_mosaic_subdir+'/btci_{}.map'.format(bm))
                else:
                    error = "Could not find temporary continuum sum map for beam {}".format(
                        self.mosaic_beam_list[i-1])
                    logger.error(error)
                    raise RuntimeError(error)

                # remove the scratch files
                logger.debug("Removing scratch files")
                for fl in glob.glob(os.path.join(self.mosaic_continuum_mosaic_dir, 'tmp_*.map')):
                    subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)
                for fl in glob.glob(os.path.join(self.mosaic_continuum_mosaic_dir, 'sum_*.map')):
                    subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)

            logger.info(
                "Multiplying continuum beam matrix by continuum covariance matrix ... Done")
            mosaic_continuum_product_beam_covariance_matrix_status = True
        else:
            logger.info(
                "Multiplying continuum beam matrix by continuum covariance matrix has already been done.")

        subs_param.add_param(
            self, 'mosaic_continuum_product_beam_covariance_matrix_status', mosaic_continuum_product_beam_covariance_matrix_status)

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to calculate the product of polarisation beam matrix and polarisation covariance matrix
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def math_polarisation_multiply_beam_and_covariance_matrix(self):
        """
        Function to multiply the transpose of the polarisation beam matrix by the polarisation covariance matrix
        """

        logger.info("Multiplying polarisation beam matrices by polarisation covariance matrices")

        mosaic_polarisation_product_beam_covariance_matrix_status_q = get_param_def(self, 'mosaic_polarisation_product_beam_covariance_matrix_status_q', False)
        mosaic_polarisation_product_beam_covariance_matrix_status_u = get_param_def(self, 'mosaic_polarisation_product_beam_covariance_matrix_status_u', False)
        mosaic_polarisation_product_beam_covariance_matrix_status_v = get_param_def(self, 'mosaic_polarisation_product_beam_covariance_matrix_status_v', False)

        # Get the needed information from the param files
        pbeam = 'polarisation_B' + str(self.mosaic_beam_list[0]).zfill(2)
        polbeamimagestatus = get_param_def(self, pbeam + '_targetbeams_qu_imagestatus', False)
        qimages = len(polbeamimagestatus)

        # get polarisation covariance matrices from numpy file
        mosaic_polarisation_inverse_covariance_matrix_q = get_param_def(self, 'mosaic_polarisation_inverse_covariance_matrix_q', [None]*qimages)
        mosaic_polarisation_inverse_covariance_matrix_u = get_param_def(self, 'mosaic_polarisation_inverse_covariance_matrix_u', [None]*qimages)
        mosaic_polarisation_inverse_covariance_matrix_v = get_param_def(self, 'mosaic_polarisation_inverse_covariance_matrix_v', [])

        inv_cov_q = mosaic_polarisation_inverse_covariance_matrix_q
        inv_cov_u = mosaic_polarisation_inverse_covariance_matrix_u
        inv_cov_v = mosaic_polarisation_inverse_covariance_matrix_v

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_polarisation_dir)

        if not mosaic_polarisation_product_beam_covariance_matrix_status_q:
            # First calculate transpose of beam matrix multiplied by the inverse covariance matrix
            # Will use *maths* in Miriad
            # Using "beams" list to account for missing beams/images
            # Only doing math where inv_cov value is non-zero
            for qplane in range(qimages):
                maths = lib.miriad('maths')
                for bm in self.mosaic_beam_list:
                    logger.debug("Processing beam {}".format(bm))
                    operate = ""
                    for b in self.mosaic_beam_list:
                        maths.out = os.path.join(
                            self.mosaic_polarisation_mosaic_subdir, 'tmp_{0}_{1}.map'.format(b, str(qplane).zfill(3)))
                        # since the beam list is made of strings, need to convert to integers
                        beam_map = os.path.join(
                            self.mosaic_polarisation_beam_subdir, "beam_{0}_mos.map".format(b))
                        if os.path.isdir(beam_map):
                            if inv_cov_q[qplane][int(b), int(bm)] != 0.:
                                operate = "'<{0}>*({1})'".format(beam_map,
                                                                 inv_cov_q[qplane][int(b), int(bm)])
                            else:
                                operate = "'<{0}>*(0)'".format(beam_map)
                            logger.debug("for beam combination {0},{1}: operate = {2}".format(bm, b, operate))
                            maths.exp = operate
                            maths.options = 'unmask'
                            maths.go()
                        else:
                            error = "Could not find polarisation Stokes Q mosaic beam map for beam {0} and image plane {1}".format(b, qplane)
                            logger.error(error)
                            raise RuntimeError(error)
                    i = 1
                    while i < len(self.mosaic_beam_list):
                        if os.path.isdir(os.path.join(self.mosaic_polarisation_mosaic_subdir, 'tmp_{0}_{1}.map'.format(self.mosaic_beam_list[i-1], str(qplane).zfill(3)))) and os.path.isdir(os.path.join(self.mosaic_polarisation_mosaic_subdir, 'tmp_{0}_{1}.map'.format(self.mosaic_beam_list[i], str(qplane).zfill(3)))):
                            if i == 1:
                                operate = "'<" + self.mosaic_polarisation_mosaic_subdir + "/tmp_{0}_{1}.map>+<".format(self.mosaic_beam_list[i-1], str(qplane).zfill(3)) + self.mosaic_polarisation_mosaic_subdir + "/tmp_{0}_{1}.map>'".format(self.mosaic_beam_list[i], str(qplane).zfill(3))
                            else:
                                operate = "'<" + self.mosaic_polarisation_mosaic_subdir + "/tmp_{0}_{1}.map>".format(self.mosaic_beam_list[i], str(qplane).zfill(3)) + "+<" + self.mosaic_polarisation_mosaic_subdir + "/sum_{0}_{1}.map>'".format(str(self.mosaic_beam_list[i-1]), str(qplane).zfill(3))
                            maths.out = self.mosaic_polarisation_mosaic_subdir + '/sum_{0}_{1}.map'.format(str(self.mosaic_beam_list[i]), str(qplane).zfill(3))
                            maths.exp = operate
                            maths.options = 'unmask'
                            maths.go()
                        else:
                            error = "Could not find temporary Stokes Q maps for image plane {2} beam {0} or beam {1}".format(self.mosaic_beam_list[i-1], self.mosaic_beam_list[i], qplane)
                            logger.error(error)
                            raise RuntimeError(error)
                        i += 1

                    if os.path.isdir(os.path.join(self.mosaic_polarisation_mosaic_subdir, 'sum_{0}_{1}.map'.format(str(self.mosaic_beam_list[i-1]), str(qplane).zfill(3)))):
                        subs_managefiles.director(self, 'rn', self.mosaic_polarisation_mosaic_subdir + '/btci_Q_{0}_{1}.map'.format(bm, str(qplane).zfill(3)), file_=self.mosaic_polarisation_mosaic_subdir + '/sum_{0}_{1}.map'.format(str(self.mosaic_beam_list[i-1]), str(qplane).zfill(3)))
                    else:
                        error = "Could not find temporary Stokes Q sum map for image plane {1} and beam {0}".format(self.mosaic_beam_list[i-1], qplane)
                        logger.error(error)
                        raise RuntimeError(error)

                    # remove the scratch files
                    logger.debug("Removing Stokes Q scratch files")
                    for fl in glob.glob(os.path.join(self.mosaic_polarisation_mosaic_dir, 'tmp_*.map')):
                        subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)
                    for fl in glob.glob(os.path.join(self.mosaic_polarisation_mosaic_dir, 'sum_*.map')):
                        subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)

                logger.info(
                    "Multiplying Stokes Q beam matrix by Stokes Q covariance matrix ... Done")
                mosaic_polarisation_product_beam_covariance_matrix_status_q = True
        else:
            logger.info(
                "Multiplying Stokes Q beam matrix by Stokes Q covariance matrix has already been done.")

        if not mosaic_polarisation_product_beam_covariance_matrix_status_u:
            # First calculate transpose of beam matrix multiplied by the inverse covariance matrix
            # Will use *maths* in Miriad
            # Using "beams" list to account for missing beams/images
            # Only doing math where inv_cov value is non-zero
            for uplane in range(qimages):
                maths = lib.miriad('maths')
                for bm in self.mosaic_beam_list:
                    logger.debug("Processing beam {}".format(bm))
                    operate = ""
                    for b in self.mosaic_beam_list:
                        maths.out = os.path.join(
                            self.mosaic_polarisation_mosaic_subdir, 'tmp_{0}_{1}.map'.format(b, str(uplane).zfill(3)))
                        # since the beam list is made of strings, need to convert to integers
                        beam_map = os.path.join(
                            self.mosaic_polarisation_beam_subdir, "beam_{0}_mos.map".format(b))
                        if os.path.isdir(beam_map):
                            if inv_cov_u[uplane][int(b), int(bm)] != 0.:
                                operate = "'<{0}>*({1})'".format(beam_map,
                                                                 inv_cov_u[uplane][int(b), int(bm)])
                            else:
                                operate = "'<{0}>*(0)'".format(beam_map)
                            logger.debug("for beam combination {0},{1}: operate = {2}".format(bm, b, operate))
                            maths.exp = operate
                            maths.options = 'unmask'
                            maths.go()
                        else:
                            error = "Could not find polarisation Stokes U mosaic beam map for beam {0} and image plane {1}".format(b, uplane)
                            logger.error(error)
                            raise RuntimeError(error)
                    i = 1
                    while i < len(self.mosaic_beam_list):
                        if os.path.isdir(os.path.join(self.mosaic_polarisation_mosaic_subdir, 'tmp_{0}_{1}.map'.format(self.mosaic_beam_list[i-1], str(uplane).zfill(3)))) and os.path.isdir(os.path.join(self.mosaic_polarisation_mosaic_subdir, 'tmp_{0}_{1}.map'.format(self.mosaic_beam_list[i], str(uplane).zfill(3)))):
                            if i == 1:
                                operate = "'<" + self.mosaic_polarisation_mosaic_subdir + "/tmp_{0}_{1}.map>+<".format(self.mosaic_beam_list[i-1], str(uplane).zfill(3)) + self.mosaic_polarisation_mosaic_subdir + "/tmp_{0}_{1}.map>'".format(self.mosaic_beam_list[i], str(uplane).zfill(3))
                            else:
                                operate = "'<" + self.mosaic_polarisation_mosaic_subdir + "/tmp_{0}_{1}.map>".format(self.mosaic_beam_list[i], str(uplane).zfill(3)) + "+<" + self.mosaic_polarisation_mosaic_subdir + "/sum_{0}_{1}.map>'".format(str(self.mosaic_beam_list[i-1]), str(uplane).zfill(3))
                            maths.out = self.mosaic_polarisation_mosaic_subdir + '/sum_{0}_{1}.map'.format(str(self.mosaic_beam_list[i]), str(uplane).zfill(3))
                            maths.exp = operate
                            maths.options = 'unmask'
                            maths.go()
                        else:
                            error = "Could not find temporary Stokes U maps for image plane {2} beam {0} or beam {1}".format(self.mosaic_beam_list[i-1], self.mosaic_beam_list[i], uplane)
                            logger.error(error)
                            raise RuntimeError(error)
                        i += 1

                    if os.path.isdir(os.path.join(self.mosaic_polarisation_mosaic_subdir, 'sum_{0}_{1}.map'.format(str(self.mosaic_beam_list[i-1]), str(uplane).zfill(3)))):
                        subs_managefiles.director(self, 'rn', self.mosaic_polarisation_mosaic_subdir + '/btci_U_{0}_{1}.map'.format(bm, str(uplane).zfill(3)), file_=self.mosaic_polarisation_mosaic_subdir + '/sum_{0}_{1}.map'.format(str(self.mosaic_beam_list[i-1]), str(uplane).zfill(3)))
                    else:
                        error = "Could not find temporary Stokes U sum map for image plane {1} and beam {0}".format(self.mosaic_beam_list[i-1], uplane)
                        logger.error(error)
                        raise RuntimeError(error)

                    # remove the scratch files
                    logger.info("Removing Stokes U scratch files")
                    for fl in glob.glob(os.path.join(self.mosaic_polarisation_mosaic_dir, 'tmp_*.map')):
                        subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)
                    for fl in glob.glob(os.path.join(self.mosaic_polarisation_mosaic_dir, 'sum_*.map')):
                        subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)

                logger.info(
                    "Multiplying Stokes U beam matrix by Stokes U covariance matrix ... Done")
                mosaic_polarisation_product_beam_covariance_matrix_status_u = True
        else:
            logger.info(
                "Multiplying Stokes U beam matrix by Stokes U covariance matrix has already been done.")

        if not mosaic_polarisation_product_beam_covariance_matrix_status_v:
            # First calculate transpose of beam matrix multiplied by the inverse covariance matrix
            # Will use *maths* in Miriad
            # Using "beams" list to account for missing beams/images
            # Only doing math where inv_cov value is non-zero
            maths = lib.miriad('maths')
            for bm in self.mosaic_beam_list:
                logger.info("Processing Stokes V image of beam {}".format(bm))
                operate = ""
                for b in self.mosaic_beam_list:
                    maths.out = os.path.join(
                        self.mosaic_polarisation_mosaic_subdir, 'tmp_{}.map'.format(b))
                    beam_map = os.path.join(
                        self.mosaic_polarisation_beam_subdir, "beam_{0}_mos.map".format(b))
                    if os.path.isdir(beam_map):
                        if inv_cov_v[int(b), int(bm)] != 0.:
                            operate = "'<{0}>*({1})'".format(beam_map, inv_cov_v[int(b), int(bm)])
                        else:
                            operate = "'<{0}>*(0)'".format(beam_map)
                        logger.debug("for beam combination {0},{1}: operate = {2}".format(bm, b, operate))
                        maths.exp = operate
                        maths.options = 'unmask'
                        maths.go()
                    else:
                        error = "Could not find polaristion Stokes V mosaic beam map for beam {}".format(
                            b)
                        logger.error(error)
                        raise RuntimeError(error)
                i = 1
                while i < len(self.mosaic_beam_list):
                    if os.path.isdir(os.path.join(self.mosaic_polarisation_mosaic_subdir, "tmp_{}.map".format(self.mosaic_beam_list[i-1]))) and os.path.isdir(os.path.join(self.mosaic_polarisation_mosaic_subdir, "tmp_{}.map".format(self.mosaic_beam_list[i]))):
                        if i == 1:
                            operate = "'<" + self.mosaic_polarisation_mosaic_subdir + "/tmp_{}.map>+<".format(str(
                                self.mosaic_beam_list[i-1]))+self.mosaic_polarisation_mosaic_subdir + "/tmp_{}.map>'".format(str(self.mosaic_beam_list[i]))
                        else:
                            operate = "'<" + self.mosaic_polarisation_mosaic_subdir + "/tmp_{}.map>".format(str(
                                self.mosaic_beam_list[i])) + "+<" + self.mosaic_polarisation_mosaic_subdir + "/sum_{}.map>'".format(str(self.mosaic_beam_list[i-1]))
                        maths.out = self.mosaic_polarisation_mosaic_subdir + \
                            '/sum_{}.map'.format(str(self.mosaic_beam_list[i]))
                        maths.exp = operate
                        maths.options = 'unmask'
                        maths.go()
                    else:
                        error = "Could not find temporary polarisation Stokes V maps for beam {0} or beam {1}".format(
                            self.mosaic_beam_list[i-1], self.mosaic_beam_list[i])
                        logger.error(error)
                        raise RuntimeError(error)
                    i += 1

                if os.path.isdir(os.path.join(self.mosaic_polarisation_mosaic_subdir, 'sum_{}.map'.format(self.mosaic_beam_list[i-1]))):
                    subs_managefiles.director(self, 'rn', self.mosaic_polarisation_mosaic_subdir + '/btci_V_{}.map'.format(
                        bm), file_=self.mosaic_polarisation_mosaic_subdir + '/sum_{}.map'.format(str(self.mosaic_beam_list[i-1])))
                else:
                    error = "Could not find temporary Stokes V polarisation sum map for beam {}".format(self.mosaic_beam_list[i-1])
                    logger.error(error)
                    raise RuntimeError(error)

                # remove the scratch files
                logger.debug("Removing scratch files")
                for fl in glob.glob(os.path.join(self.mosaic_polarisation_mosaic_dir, 'tmp_*.map')):
                    subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)
                for fl in glob.glob(os.path.join(self.mosaic_polarisation_mosaic_dir, 'sum_*.map')):
                    subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)

            logger.info("Multiplying polarisation Stokes V beam matrix by polarisation Stokes V covariance matrix ... Done")
            mosaic_polarisation_product_beam_covariance_matrix_status_v = True
        else:
            logger.info("Multiplying polarisation Stokes V beam matrix by polarisation Stokes V covariance matrix has already been done.")

        subs_param.add_param(self, 'mosaic_polarisation_product_beam_covariance_matrix_status_q', mosaic_polarisation_product_beam_covariance_matrix_status_q)
        subs_param.add_param(self, 'mosaic_polarisation_product_beam_covariance_matrix_status_u', mosaic_polarisation_product_beam_covariance_matrix_status_u)
        subs_param.add_param(self, 'mosaic_polarisation_product_beam_covariance_matrix_status_v', mosaic_polarisation_product_beam_covariance_matrix_status_v)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to calculate the continuum variance map
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def math_continuum_calculate_variance_map(self):
        """
        Function to calculate the continuum variance map
        """

        logger.info("Calculating continuum variance maps")

        mosaic_continuum_variance_map_status = get_param_def(self, 'mosaic_continuum_variance_map_status', False)

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_dir)

        if not mosaic_continuum_variance_map_status:
            # Calculate variance map (using beams and noise covariance matrix over entire map)
            # This is the denominator for I(mosaic)
            maths = lib.miriad('maths')
            i = 0
            for beam in self.mosaic_beam_list:
                btci_map = os.path.join(self.mosaic_continuum_mosaic_subdir, "btci_{}.map".format(beam))
                beam_mos_map = os.path.join(self.mosaic_continuum_beam_subdir, "beam_{}_mos.map".format(beam))
                if os.path.isdir(btci_map) and os.path.isdir(beam_mos_map):
                    operate = "'<" + btci_map + ">*<" + beam_mos_map + ">'"
                    if beam != self.mosaic_beam_list[0]:
                        operate = operate[:-1] + "+<" + self.mosaic_continuum_mosaic_subdir + "/out_{}_mos.map>'".format(str(i).zfill(2))
                    i += 1
                    logger.debug("Beam {0}: operate = {1}".format(beam, operate))
                    maths.out = self.mosaic_continuum_mosaic_subdir + "/out_{}_mos.map".format(str(i).zfill(2))
                    maths.exp = operate
                    maths.options = 'unmask'
                    maths.go()
                else:
                    error = "Could not find the continuum maps for beam {0}".format(beam)
                    logger.error(error)
                    raise RuntimeError(error)

            subs_managefiles.director(self, 'rn', os.path.join(self.mosaic_continuum_mosaic_subdir, 'variance_mos.map'), file_=os.path.join(
                self.mosaic_continuum_mosaic_subdir, 'out_{}_mos.map'.format(str(i).zfill(2))))

            logger.info("Calculating continuum variance maps ... Done")

            mosaic_continuum_variance_map_status = True
        else:
            logger.info("Continuum variance maps have already been calculated.")

        subs_param.add_param(self, 'mosaic_continuum_variance_map_status', mosaic_continuum_variance_map_status)

        # +++++++++++++++++++++++++++++++++++++++++++++++++++
        # Function to calculate the continuum variance map
        # +++++++++++++++++++++++++++++++++++++++++++++++++++

    def math_polarisation_calculate_variance_map(self):
        """
        Function to calculate the continuum variance map
        """

        logger.info("Calculating polarisation variance maps")

        mosaic_polarisation_variance_map_status_q = get_param_def(self, 'mosaic_polarisation_variance_map_status_q', False)
        mosaic_polarisation_variance_map_status_u = get_param_def(self, 'mosaic_polarisation_variance_map_status_u', False)
        mosaic_polarisation_variance_map_status_v = get_param_def(self, 'mosaic_polarisation_variance_map_status_v', False)

        # Get the needed information from the param files
        pbeam = 'polarisation_B' + str(self.mosaic_beam_list[0]).zfill(2)
        polbeamimagestatus = get_param_def(self, pbeam + '_targetbeams_qu_imagestatus', False)
        qimages = len(polbeamimagestatus)

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_polarisation_dir)

        if not mosaic_polarisation_variance_map_status_q:
            logger.info("Calculating variance maps for Stokes Q")
            for qplane in range(qimages):
                # Calculate variance map (using beams and noise covariance matrix over entire map)
                # This is the denominator for I(mosaic)
                maths = lib.miriad('maths')
                i = 0
                for beam in self.mosaic_beam_list:
                    btci_map_q = os.path.join(self.mosaic_polarisation_mosaic_subdir + '/btci_Q_{0}_{1}.map'.format(beam, str(qplane).zfill(3)))
                    beam_mos_map_q = os.path.join(self.mosaic_polarisation_beam_subdir, "beam_{}_mos.map".format(beam))
                    if os.path.isdir(btci_map_q) and os.path.isdir(beam_mos_map_q):
                        operate = "'<" + btci_map_q + ">*<" + beam_mos_map_q + ">'"
                        if beam != self.mosaic_beam_list[0]:
                            operate = operate[:-1] + "+<" + self.mosaic_polarisation_mosaic_subdir + "/out_Q_{0}_{1}_mos.map>'".format(str(i).zfill(2), str(qplane).zfill(3))
                        i += 1
                        logger.debug("Beam {0}: operate = {1}".format(beam, operate))
                        maths.out = self.mosaic_polarisation_mosaic_subdir + "/out_Q_{0}_{1}_mos.map".format(str(i).zfill(2), str(qplane).zfill(3))
                        maths.exp = operate
                        maths.options = 'unmask'
                        maths.go()
                    else:
                        error = "Could not find the Stokes Q maps for beam {0} and image plane {1}".format(beam, qplane)
                        logger.error(error)
                        raise RuntimeError(error)

                subs_managefiles.director(self, 'rn', os.path.join(self.mosaic_polarisation_mosaic_subdir, 'variance_Q_{}_mos.map'.format(str(qplane).zfill(3))),
                                          file_=os.path.join(
                                              self.mosaic_polarisation_mosaic_subdir,
                                              'out_Q_{0}_{1}_mos.map'.format(str(i).zfill(2), str(qplane).zfill(3))))

                logger.info("Calculating polarisation Stokes Q variance maps ... Done")

                mosaic_polarisation_variance_map_status_q = True
        else:
            logger.info("Polarisation Stokes Q variance maps have already been calculated.")

        if not mosaic_polarisation_variance_map_status_u:
            logger.info("Calculating variance maps for Stokes U")
            for uplane in range(qimages):
                # Calculate variance map (using beams and noise covariance matrix over entire map)
                # This is the denominator for I(mosaic)
                maths = lib.miriad('maths')
                i = 0
                for beam in self.mosaic_beam_list:
                    btci_map_u = os.path.join(self.mosaic_polarisation_mosaic_subdir + '/btci_U_{0}_{1}.map'.format(beam, str(uplane).zfill(3)))
                    beam_mos_map_u = os.path.join(self.mosaic_polarisation_beam_subdir, "beam_{}_mos.map".format(beam))
                    if os.path.isdir(btci_map_u) and os.path.isdir(beam_mos_map_u):
                        operate = "'<" + btci_map_u + ">*<" + beam_mos_map_u + ">'"
                        if beam != self.mosaic_beam_list[0]:
                            operate = operate[:-1] + "+<" + self.mosaic_polarisation_mosaic_subdir + "/out_U_{0}_{1}_mos.map>'".format(str(i).zfill(2), str(uplane).zfill(3))
                        i += 1
                        logger.debug("Beam {0}: operate = {1}".format(beam, operate))
                        maths.out = self.mosaic_polarisation_mosaic_subdir + "/out_U_{0}_{1}_mos.map".format(str(i).zfill(2), str(uplane).zfill(3))
                        maths.exp = operate
                        maths.options = 'unmask'
                        maths.go()
                    else:
                        error = "Could not find the Stokes U maps for beam {0} and image plane {1}".format(beam, uplane)
                        logger.error(error)
                        raise RuntimeError(error)

                subs_managefiles.director(self, 'rn', os.path.join(self.mosaic_polarisation_mosaic_subdir, 'variance_U_{}_mos.map'.format(str(uplane).zfill(3))),
                                          file_=os.path.join(
                                              self.mosaic_polarisation_mosaic_subdir,
                                              'out_U_{0}_{1}_mos.map'.format(str(i).zfill(2), str(uplane).zfill(3))))

                logger.info("Calculating polarisation Stokes U variance maps ... Done")

                mosaic_polarisation_variance_map_status_u = True
        else:
            logger.info("Polarisation Stokes U variance maps have already been calculated.")

        if not mosaic_polarisation_variance_map_status_v:
            logger.info("Calculating variance maps for Stokes V")
            # Calculate variance map (using beams and noise covariance matrix over entire map)
            # This is the denominator for I(mosaic)
            maths = lib.miriad('maths')
            i = 0
            for beam in self.mosaic_beam_list:
                btci_map_v = os.path.join(self.mosaic_polarisation_mosaic_subdir, "btci_V_{}.map".format(beam))
                beam_mos_map_v = os.path.join(self.mosaic_polarisation_beam_subdir, "beam_{}_mos.map".format(beam))
                if os.path.isdir(btci_map_v) and os.path.isdir(beam_mos_map_v):
                    operate = "'<" + btci_map_v + ">*<" + beam_mos_map_v + ">'"
                    if beam != self.mosaic_beam_list[0]:
                        operate = operate[:-1] + "+<" + self.mosaic_polarisation_mosaic_subdir + "/out_V_{}_mos.map>'".format(str(i).zfill(2))
                    i += 1
                    logger.debug("Beam {0}: operate = {1}".format(beam, operate))
                    maths.out = self.mosaic_polarisation_mosaic_subdir + "/out_V_{}_mos.map".format(str(i).zfill(2))
                    maths.exp = operate
                    maths.options = 'unmask'
                    maths.go()
                else:
                    error = "Could not find the Stokes V maps for beam {0}".format(beam)
                    logger.error(error)
                    raise RuntimeError(error)

            subs_managefiles.director(self, 'rn', os.path.join(self.mosaic_polarisation_mosaic_subdir, 'variance_V_mos.map'), file_=os.path.join(
                self.mosaic_polarisation_mosaic_subdir, 'out_V_{}_mos.map'.format(str(i).zfill(2))))

            logger.info("Calculating Stokes V variance maps ... Done")

            mosaic_polarisation_variance_map_status_v = True
        else:
            logger.info("Stokes V variance maps have already been calculated.")

        subs_param.add_param(self, 'mosaic_polarisation_variance_map_status_q', mosaic_polarisation_variance_map_status_q)
        subs_param.add_param(self, 'mosaic_polarisation_variance_map_status_u', mosaic_polarisation_variance_map_status_u)
        subs_param.add_param(self, 'mosaic_polarisation_variance_map_status_v', mosaic_polarisation_variance_map_status_v)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to calculate the beam matrix multiplied by the covariance matrix for continuum
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def math_continuum_multiply_beam_matrix_by_covariance_matrix_and_image(self):
        """
        Function to muliply the beam matrix by covariance matrix and image for continuum
        """

        logger.info("Multiplying continuum beam matrix by continuum covariance matrix and continuum image")

        mosaic_continuum_product_beam_covariance_matrix_image_status = get_param_def(
            self, 'mosaic_continuum_product_beam_covariance_matrix_image_status', False)

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_mosaic_dir)

        if not mosaic_continuum_product_beam_covariance_matrix_image_status:
            # Calculate transpose of beam matrix multiplied by noise_cov multiplied by image from each beam for each position
            # in the final image
            maths = lib.miriad('maths')
            i = 0
            for bm in self.mosaic_beam_list:
                if os.path.isdir("image_{}_mos.map".format(bm)) and os.path.isdir("btci_{}.map".format(bm)):
                    operate = "'<" + "image_{}_mos.map>*<".format(bm) + "btci_{}.map>'".format(bm)
                    if bm != self.mosaic_beam_list[0]:
                        operate = operate[:-1] + "+<" + "mos_{}.map>'".format(str(i).zfill(2))
                    i += 1
                    maths.out = "mos_{}.map".format(str(i).zfill(2))
                    maths.exp = operate
                    maths.options = 'unmask,grow'
                    maths.go()
                else:
                    error = "Could not find the necessary files for beam {}".format(bm)
                    logger.error(error)
                    raise RuntimeError(error)

            subs_managefiles.director(
                self, 'rn', 'mosaic_im.map', file_='mos_{}.map'.format(str(i).zfill(2)))

            logger.info(
                "Multiplying continuum beam matrix by continuum covariance matrix and continuum image ... Done")

            mosaic_continuum_product_beam_covariance_matrix_image_status = True
        else:
            logger.info("Multiplication for continuum has already been done.")

        subs_param.add_param(self, 'mosaic_continuum_product_beam_covariance_matrix_image_status', mosaic_continuum_product_beam_covariance_matrix_image_status)

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to calculate the beam matrix multiplied by the covariance matrix for polarisation
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def math_polarisation_multiply_beam_matrix_by_covariance_matrix_and_image(self):
        """
        Function to muliply the beam matrix by covariance matrix and image for polarisation
        """

        mosaic_polarisation_product_beam_covariance_matrix_image_status_q = get_param_def(
            self, 'mosaic_polarisation_product_beam_covariance_matrix_image_status_q', False)

        mosaic_polarisation_product_beam_covariance_matrix_image_status_u = get_param_def(
            self, 'mosaic_polarisation_product_beam_covariance_matrix_image_status_u', False)

        mosaic_polarisation_product_beam_covariance_matrix_image_status_v = get_param_def(
            self, 'mosaic_polarisation_product_beam_covariance_matrix_image_status_v', False)

        # Get the needed information from the param files
        pbeam = 'polarisation_B' + str(self.mosaic_beam_list[0]).zfill(2)
        polbeamimagestatus = get_param_def(self, pbeam + '_targetbeams_qu_imagestatus', False)
        qimages = len(polbeamimagestatus)

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_polarisation_mosaic_dir)

        if not mosaic_polarisation_product_beam_covariance_matrix_image_status_q:
            logger.info("Multiplying Stokes Q beam matrices by Stokes Q covariance matrices and Stokes Q images")
            # Calculate transpose of beam matrix multiplied by noise_cov multiplied by image from each beam for each position
            # in the final image
            for qplane in range(qimages):
                maths = lib.miriad('maths')
                i = 0
                for bm in self.mosaic_beam_list:
                    if os.path.isdir("Qcube_{0}_{1}_mos.map".format(bm, str(qplane).zfill(3))) and os.path.isdir("btci_Q_{0}_{1}.map".format(bm, str(qplane).zfill(3))):
                        operate = "'<" + "Qcube_{0}_{1}_mos.map>*<".format(bm, str(qplane).zfill(3)) + "btci_Q_{0}_{1}.map>'".format(bm, str(qplane).zfill(3))
                        if bm != self.mosaic_beam_list[0]:
                            operate = operate[:-1] + "+<" + "mos_Q_{0}_{1}.map>'".format(str(i).zfill(2), str(qplane).zfill(3))
                        i += 1
                        maths.out = "mos_Q_{0}_{1}.map".format(str(i).zfill(2), str(qplane).zfill(3))
                        maths.exp = operate
                        maths.options = 'unmask,grow'
                        maths.go()
                    else:
                        error = "Could not find the necessary files for Stokes Q image plane {1} beam {0}".format(bm, qplane)
                        logger.error(error)
                        raise RuntimeError(error)

                subs_managefiles.director(
                    self, 'rn', 'mosaic_Q_{}_im.map'.format(str(qplane).zfill(3)), file_='mos_Q_{0}_{1}.map'.format(str(i).zfill(2), str(qplane).zfill(3)))

            logger.info(
                "Multiplying Stokes Q beam matrices by Stokes Q covariance matrices and Stokes Q images ... Done")

            mosaic_polarisation_product_beam_covariance_matrix_image_status_q = True
        else:
            logger.info("Multiplication for Stokes Q has already been done.")

        if not mosaic_polarisation_product_beam_covariance_matrix_image_status_u:
            logger.info("Multiplying Stokes U beam matrices by Stokes U covariance matrices and Stokes U images")
            # Calculate transpose of beam matrix multiplied by noise_cov multiplied by image from each beam for each position
            # in the final image
            for uplane in range(qimages):
                maths = lib.miriad('maths')
                i = 0
                for bm in self.mosaic_beam_list:
                    if os.path.isdir("Ucube_{0}_{1}_mos.map".format(bm, str(uplane).zfill(3))) and os.path.isdir("btci_U_{0}_{1}.map".format(bm, str(uplane).zfill(3))):
                        operate = "'<" + "Ucube_{0}_{1}_mos.map>*<".format(bm, str(uplane).zfill(3)) + "btci_U_{0}_{1}.map>'".format(bm, str(uplane).zfill(3))
                        if bm != self.mosaic_beam_list[0]:
                            operate = operate[:-1] + "+<" + "mos_U_{0}_{1}.map>'".format(str(i).zfill(2), str(uplane).zfill(3))
                        i += 1
                        maths.out = "mos_U_{0}_{1}.map".format(str(i).zfill(2), str(uplane).zfill(3))
                        maths.exp = operate
                        maths.options = 'unmask,grow'
                        maths.go()
                    else:
                        error = "Could not find the necessary files for Stokes U image plane {1} beam {0}".format(bm, uplane)
                        logger.error(error)
                        raise RuntimeError(error)

                subs_managefiles.director(
                    self, 'rn', 'mosaic_U_{}_im.map'.format(str(uplane).zfill(3)), file_='mos_U_{0}_{1}.map'.format(str(i).zfill(2), str(uplane).zfill(3)))

            logger.info(
                "Multiplying Stokes U beam matrices by Stokes U covariance matrices and Stokes U images ... Done")

            mosaic_polarisation_product_beam_covariance_matrix_image_status_u = True
        else:
            logger.info("Multiplication for Stokes U has already been done.")

        if not mosaic_polarisation_product_beam_covariance_matrix_image_status_v:
            # Calculate transpose of beam matrix multiplied by noise_cov multiplied by image from each beam for each position
            # in the final image
            maths = lib.miriad('maths')
            i = 0
            for bm in self.mosaic_beam_list:
                if os.path.isdir("image_mf_V_{}_mos.map".format(bm)) and os.path.isdir("btci_V_{}.map".format(bm)):
                    operate = "'<" + "image_mf_V_{}_mos.map>*<".format(bm) + "btci_V_{}.map>'".format(bm)
                    if bm != self.mosaic_beam_list[0]:
                        operate = operate[:-1] + "+<" + "mos_V_{}.map>'".format(str(i).zfill(2))
                    i += 1
                    maths.out = "mos_V_{}.map".format(str(i).zfill(2))
                    maths.exp = operate
                    maths.options = 'unmask,grow'
                    maths.go()
                else:
                    error = "Could not find the necessary files for Stokes V for beam {}".format(bm)
                    logger.error(error)
                    raise RuntimeError(error)

            subs_managefiles.director(
                self, 'rn', 'mosaic_V_im.map', file_='mos_V_{}.map'.format(str(i).zfill(2)))

            logger.info(
                "Multiplying Stokes V beam matrix by Stokes V covariance matrix and Stokes V image ... Done")

            mosaic_polarisation_product_beam_covariance_matrix_image_status_v = True
        else:
            logger.info("Multiplication for Stokes V has already been done.")

        subs_param.add_param(self, 'mosaic_polarisation_product_beam_covariance_matrix_image_status_v', mosaic_polarisation_product_beam_covariance_matrix_image_status_v)


        subs_param.add_param(self, 'mosaic_polarisation_product_beam_covariance_matrix_image_status_q', mosaic_polarisation_product_beam_covariance_matrix_image_status_q)
        subs_param.add_param(self, 'mosaic_polarisation_product_beam_covariance_matrix_image_status_u', mosaic_polarisation_product_beam_covariance_matrix_image_status_u)
        subs_param.add_param(self, 'mosaic_polarisation_product_beam_covariance_matrix_image_status_v', mosaic_polarisation_product_beam_covariance_matrix_image_status_v)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to find maximum of variance map
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def math_continuum_get_max_variance_map(self):
        """
        Function to determine the maximum of the variance map
        """

        logger.info("Getting maximum of continuum variance map")

        mosaic_continuum_get_max_variance_status = get_param_def(self, 'mosaic_continuum_get_max_variance_status', False)

        mosaic_continuum_max_variance = get_param_def(self, 'mosaic_continuum_beam_max_variance', 0.)

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_mosaic_dir)

        if not mosaic_continuum_get_max_variance_status and mosaic_continuum_max_variance == 0.:
            # Find maximum value of variance map
            imstat = lib.miriad('imstat')
            imstat.in_ = "'variance_mos.map'"
            imstat.region = "'quarter(1)'"
            imstat.axes = "'x,y'"
            try:
                a = imstat.go()
            except Exception as e:
                error = "Getting maximum of continuum varianc map ... Failed"
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)

            # Always outputs max value at same point
            var_max = a[10].lstrip().split(" ")[3]

            logger.debug("Maximum of continuum variance map is {}".format(var_max))

            logger.info("Getting maximum of continuum variance map ... Done")

            mosaic_continuum_get_max_variance_status = True
            mosaic_continuum_max_variance = var_max
        else:
            logger.info("Maximum of continuum variance map has already been determined.")

        subs_param.add_param(
            self, 'mosaic_continuum_get_max_variance_status', mosaic_continuum_get_max_variance_status)

        subs_param.add_param(
            self, 'mosaic_continuum_max_variance', mosaic_continuum_max_variance)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to find maximum of variance map
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def math_polarisation_get_max_variance_map(self):
        """
        Function to determine the maximum of the variance map for polarisation
        """

        logger.info("Getting maximum of continuum variance map")

        # Get the needed information from the param files
        pbeam = 'polarisation_B' + str(self.mosaic_beam_list[0]).zfill(2)
        polbeamimagestatus = get_param_def(self, pbeam + '_targetbeams_qu_imagestatus', False)
        qimages = len(polbeamimagestatus)

        mosaic_polarisation_get_max_variance_status_q = get_param_def(self, 'mosaic_polarisation_get_max_variance_status_q', False)
        mosaic_polarisation_max_variance_q = get_param_def(self, 'mosaic_polarisation_beam_max_variance_q', np.zeros(qimages))
        mosaic_polarisation_get_max_variance_status_u = get_param_def(self, 'mosaic_polarisation_get_max_variance_status_u', False)
        mosaic_polarisation_max_variance_u = get_param_def(self, 'mosaic_polarisation_beam_max_variance_u', np.zeros(qimages))
        mosaic_polarisation_get_max_variance_status_v = get_param_def(self, 'mosaic_polarisation_get_max_variance_status_v', False)
        mosaic_polarisation_max_variance_v = get_param_def(self, 'mosaic_polarisation_beam_max_variance_v', 0.)

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_polarisation_mosaic_dir)

        if not mosaic_polarisation_get_max_variance_status_q:
            for qplane in range(qimages):
                # Find maximum value of variance map
                imstat = lib.miriad('imstat')
                imstat.in_ = "'" + 'variance_Q_{}_mos.map'.format(str(qplane).zfill(3)) + "'"
                imstat.region = "'quarter(1)'"
                imstat.axes = "'x,y'"
                try:
                    a = imstat.go()
                except Exception as e:
                    error = "Getting maximum of Stokes Q variance map {} ... Failed".format(qplane)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)

                # Always outputs max value at same point
                var_max_q = a[10].lstrip().split(" ")[3]

                logger.debug("Maximum of Stokes Q variance map {0} is {1}".format(qplane, var_max_q))

                mosaic_polarisation_max_variance_q[qplane] = var_max_q

            logger.info("Getting maxima of Stokes Q variance maps ... Done")

            mosaic_polarisation_get_max_variance_status_q = True

        else:
            logger.info("Maximum of Stokes Q variance maps has already been determined.")

        if not mosaic_polarisation_get_max_variance_status_u:
            for uplane in range(qimages):
                # Find maximum value of variance map
                imstat = lib.miriad('imstat')
                imstat.in_ = "'" + 'variance_U_{}_mos.map'.format(str(uplane).zfill(3)) + "'"
                imstat.region = "'quarter(1)'"
                imstat.axes = "'x,y'"
                try:
                    a = imstat.go()
                except Exception as e:
                    error = "Getting maximum of Stokes U variance map {} ... Failed".format(uplane)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)

                # Always outputs max value at same point
                var_max_u = a[10].lstrip().split(" ")[3]

                logger.debug("Maximum of Stokes U variance map {0} is {1}".format(uplane, var_max_u))

                mosaic_polarisation_max_variance_u[uplane] = var_max_u

            logger.info("Getting maxima of Stokes U variance maps ... Done")

            mosaic_polarisation_get_max_variance_status_u = True

        else:
            logger.info("Maximum of Stokes U variance maps has already been determined.")

        if not mosaic_polarisation_get_max_variance_status_v and mosaic_polarisation_max_variance_v == 0.:
            # Find maximum value of variance map
            imstat = lib.miriad('imstat')
            imstat.in_ = "'variance_V_mos.map'"
            imstat.region = "'quarter(1)'"
            imstat.axes = "'x,y'"
            try:
                a = imstat.go()
            except Exception as e:
                error = "Getting maximum of Stokes V variance map ... Failed"
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)

            # Always outputs max value at same point
            var_max_v = a[10].lstrip().split(" ")[3]

            logger.debug("Maximum of Stokes V variance map is {}".format(var_max_v))

            logger.info("Getting maximum of Stokes V variance map ... Done")

            mosaic_polarisation_get_max_variance_status_v = True
            mosaic_polarisation_max_variance_v = var_max_v
        else:
            logger.info("Maximum of Stokes V variance map has already been determined.")


        subs_param.add_param(self, 'mosaic_polarisation_get_max_variance_status_q', mosaic_polarisation_get_max_variance_status_q)
        subs_param.add_param(self, 'mosaic_polarisation_get_max_variance_status_u', mosaic_polarisation_get_max_variance_status_u)
        subs_param.add_param(self, 'mosaic_polarisation_get_max_variance_status_v', mosaic_polarisation_get_max_variance_status_v)

        subs_param.add_param(self, 'mosaic_polarisation_max_variance_q', mosaic_polarisation_max_variance_q)
        subs_param.add_param(self, 'mosaic_polarisation_max_variance_u', mosaic_polarisation_max_variance_u)
        subs_param.add_param(self, 'mosaic_polarisation_max_variance_v', mosaic_polarisation_max_variance_v)


    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to divide image by variance map for continuum
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def math_continuum_divide_image_by_variance_map(self):
        """
        Function to divide the image by the variance map
        """

        logger.info("Dividing continuum image by continuum variance map")

        mosaic_continuum_divide_image_variance_status = get_param_def(self, 'mosaic_continuum_divide_image_variance_status', False)

        mosaic_continuum_max_variance = get_param_def(self, 'mosaic_continuum_beam_max_variance', 0.)

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_mosaic_dir)

        if not mosaic_continuum_divide_image_variance_status:
            # Divide image by variance map
            maths = lib.miriad('maths')
            maths.out = 'mosaic_final.map'
            maths.exp = "'<mosaic_im.map>/<variance_mos.map>'"
            maths.mask = "'<variance_mos.map>.gt.0.01*" + str(mosaic_continuum_max_variance) + "'"
            try:
                maths.go()
            except Exception as e:
                error = "Dividing image by continuum variance map ... Failed"
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)

            logger.info("Dividing image by continuum variance map ... Done")

            mosaic_continuum_divide_image_variance_status = True
        else:
            logger.info("Division for continuum image has already been performed")

        subs_param.add_param(self, 'mosaic_continuum_divide_image_variance_status', mosaic_continuum_divide_image_variance_status)

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to divide image by variance map for continuum
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def math_polarisation_divide_image_by_variance_map(self):
        """
        Function to divide the image by the variance map
        """

        logger.info("Dividing polarisation images by polarisation variance maps")

        # Get the needed information from the param files
        pbeam = 'polarisation_B' + str(self.mosaic_beam_list[0]).zfill(2)
        polbeamimagestatus = get_param_def(self, pbeam + '_targetbeams_qu_imagestatus', False)
        qimages = len(polbeamimagestatus)

        mosaic_polarisation_divide_image_variance_status_q = get_param_def(self, 'mosaic_polarisation_divide_image_variance_status_q', False)
        mosaic_polarisation_divide_image_variance_status_u = get_param_def(self, 'mosaic_polarisation_divide_image_variance_status_u', False)
        mosaic_polarisation_divide_image_variance_status_v = get_param_def(self, 'mosaic_polarisation_divide_image_variance_status_v', False)

        mosaic_polarisation_max_variance_q = get_param_def(self, 'mosaic_polarisation_beam_max_variance_q', np.zeros(qimages))
        mosaic_polarisation_max_variance_u = get_param_def(self, 'mosaic_polarisation_beam_max_variance_u', np.zeros(qimages))
        mosaic_polarisation_max_variance_v = get_param_def(self, 'mosaic_polarisation_beam_max_variance_v', 0.)

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_polarisation_mosaic_dir)

        if not mosaic_polarisation_divide_image_variance_status_q:
            for qplane in range(qimages):
                # Divide image by variance map
                maths = lib.miriad('maths')
                maths.out = 'mosaic_Q_{}_final.map'.format(str(qplane).zfill(3))
                maths.exp = "'" + "<mosaic_Q_{0}_im.map>/<variance_Q_{0}_mos.map>".format(str(qplane).zfill(3)) + "'"
                maths.mask = "'" + "<variance_Q_{}_mos.map>.gt.0.01*".format(str(qplane).zfill(3)) + str(mosaic_polarisation_max_variance_q[qplane]) + "'"
                try:
                    maths.go()
                except Exception as e:
                    error = "Dividing Stokes Q image by Stokes Q variance map for image plane {} ... Failed".format(qplane)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)

            logger.info("Dividing Stokes Q images by Stokes Q variance maps ... Done")

            mosaic_polarisation_divide_image_variance_status_q = True
        else:
            logger.info("Division for Stokes Q images has already been performed")

        if not mosaic_polarisation_divide_image_variance_status_u:
            for uplane in range(qimages):
                # Divide image by variance map
                maths = lib.miriad('maths')
                maths.out = 'mosaic_U_{}_final.map'.format(str(uplane).zfill(3))
                maths.exp = "'" + "<mosaic_U_{0}_im.map>/<variance_U_{0}_mos.map>".format(str(uplane).zfill(3)) + "'"
                maths.mask = "'" + "<variance_U_{}_mos.map>.gt.0.01*".format(str(uplane).zfill(3)) + str(mosaic_polarisation_max_variance_u[uplane]) + "'"
                try:
                    maths.go()
                except Exception as e:
                    error = "Dividing Stokes U image by Stokes U variance map for image plane {} ... Failed".format(uplane)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)

            logger.info("Dividing Stokes U images by Stokes U variance maps ... Done")

            mosaic_polarisation_divide_image_variance_status_u = True
        else:
            logger.info("Division for Stokes U images has already been performed")

        if not mosaic_polarisation_divide_image_variance_status_v:
            # Divide image by variance map
            maths = lib.miriad('maths')
            maths.out = 'mosaic_V_final.map'
            maths.exp = "'<mosaic_V_im.map>/<variance_V_mos.map>'"
            maths.mask = "'<variance_V_mos.map>.gt.0.01*" + str(mosaic_polarisation_max_variance_v) + "'"
            try:
                maths.go()
            except Exception as e:
                error = "Dividing Stokes V image by Stokes V variance map ... Failed"
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)

            logger.info("Dividing Stokes V image by Stokes V variance map ... Done")

            mosaic_polarisation_divide_image_variance_status_v = True
        else:
            logger.info("Division for Stokes V image has already been performed")

        subs_param.add_param(self, 'mosaic_polarisation_divide_image_variance_status_q', mosaic_polarisation_divide_image_variance_status_q)
        subs_param.add_param(self, 'mosaic_polarisation_divide_image_variance_status_u', mosaic_polarisation_divide_image_variance_status_u)
        subs_param.add_param(self, 'mosaic_polarisation_divide_image_variance_status_v', mosaic_polarisation_divide_image_variance_status_v)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to get continuum mosaic noise map
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def get_continuum_mosaic_noise_map(self):
        """
        Function to get the continuum mosaic noise map
        """

        logger.info("Getting continuum mosaic noise map")

        mosaic_continuum_get_mosaic_noise_map_status = get_param_def(self, 'mosaic_continuum_get_mosaic_noise_map_status', False)

        mosaic_continuum_max_variance = get_param_def(self, 'mosaic_continuum_beam_max_variance', 0.)

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_mosaic_dir)

        if not mosaic_continuum_get_mosaic_noise_map_status:
            # Produce mosaic noise map
            maths = lib.miriad('maths')
            maths.out = 'mosaic_noise.map'
            maths.exp = "'1./sqrt(<variance_mos.map>)'"
            maths.mask = "'<variance_mos.map>.gt.0.01*" + str(mosaic_continuum_max_variance) + "'"
            try:
                maths.go()
            except Exception as e:
                error = "Calculating continuum mosaic noise map ... Failed"
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)

            puthd = lib.miriad('puthd')
            puthd.in_ = 'mosaic_noise.map/bunit'
            puthd.value = 'JY/BEAM'
            try:
                puthd.go()
            except Exception as e:
                error = "Adding continuum noise map unit ... Failed"
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)

            logger.info("Getting continuum mosaic noise map ... Done")
            mosaic_continuum_get_mosaic_noise_map_status = True
        else:
            logger.info("Mosaic continuum map noise is already available")

        subs_param.add_param(self, 'mosaic_continuum_get_mosaic_noise_map_status', mosaic_continuum_get_mosaic_noise_map_status)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to get continuum mosaic noise map
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def get_polarisation_mosaic_noise_map(self):
        """
        Function to get the polarisation mosaic noise maps
        """

        logger.info("Getting polarisation mosaic noise maps")

        mosaic_polarisation_get_mosaic_noise_map_status_q = get_param_def(self, 'mosaic_polarisation_get_mosaic_noise_map_status_q', False)
        mosaic_polarisation_get_mosaic_noise_map_status_u = get_param_def(self, 'mosaic_polarisation_get_mosaic_noise_map_status_u', False)
        mosaic_polarisation_get_mosaic_noise_map_status_v = get_param_def(self, 'mosaic_polarisation_get_mosaic_noise_map_status_v', False)

        # Get the needed information from the param files
        pbeam = 'polarisation_B' + str(self.mosaic_beam_list[0]).zfill(2)
        polbeamimagestatus = get_param_def(self, pbeam + '_targetbeams_qu_imagestatus', False)
        qimages = len(polbeamimagestatus)

        mosaic_polarisation_max_variance_q = get_param_def(self, 'mosaic_polarisation_beam_max_variance_q', np.zeros(qimages))
        mosaic_polarisation_max_variance_u = get_param_def(self, 'mosaic_polarisation_beam_max_variance_u', np.zeros(qimages))
        mosaic_polarisation_max_variance_v = get_param_def(self, 'mosaic_polarisation_beam_max_variance_v', 0.)

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_polarisation_mosaic_dir)

        if not mosaic_polarisation_get_mosaic_noise_map_status_q:
            for qplane in range(qimages):
                # Produce mosaic noise map
                maths = lib.miriad('maths')
                maths.out = 'mosaic_Q_{}_noise.map'.format(str(qplane).zfill(3))
                maths.exp = "'" + "1./sqrt(<variance_Q_{}_mos.map>)".format(str(qplane).zfill(3)) + "'"
                maths.mask = "'" + "<variance_Q_{}_mos.map>.gt.0.01*".format(str(qplane).zfill(3)) + str(mosaic_polarisation_max_variance_q[qplane]) + "'"
                try:
                    maths.go()
                except Exception as e:
                    error = "Calculating Stokes Q mosaic noise map {} ... Failed".format(qplane)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)

                puthd = lib.miriad('puthd')
                puthd.in_ = 'mosaic_Q_{}_noise.map/bunit'.format(str(qplane).zfill(3))
                puthd.value = 'JY/BEAM'
                try:
                    puthd.go()
                except Exception as e:
                    error = "Adding Stokes Q noise map unit to image plane {} ... Failed".format(qplane)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)

            logger.info("Getting Stokes Q mosaic noise maps ... Done")
            mosaic_polarisation_get_mosaic_noise_map_status_q = True
        else:
            logger.info("Mosaicked Stokes Q noise maps are already available")

        if not mosaic_polarisation_get_mosaic_noise_map_status_u:
            for uplane in range(qimages):
                # Produce mosaic noise map
                maths = lib.miriad('maths')
                maths.out = 'mosaic_U_{}_noise.map'.format(str(uplane).zfill(3))
                maths.exp = "'" + "1./sqrt(<variance_U_{}_mos.map>)".format(str(uplane).zfill(3)) + "'"
                maths.mask = "'" + "<variance_U_{}_mos.map>.gt.0.01*".format(str(uplane).zfill(3)) + str(
                    mosaic_polarisation_max_variance_u[uplane]) + "'"
                try:
                    maths.go()
                except Exception as e:
                    error = "Calculating Stokes U mosaic noise map {} ... Failed".format(uplane)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)

                puthd = lib.miriad('puthd')
                puthd.in_ = 'mosaic_U_{}_noise.map/bunit'.format(str(uplane).zfill(3))
                puthd.value = 'JY/BEAM'
                try:
                    puthd.go()
                except Exception as e:
                    error = "Adding Stokes U noise map unit to image plane {} ... Failed".format(uplane)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)

            logger.info("Getting Stokes U mosaic noise maps ... Done")
            mosaic_polarisation_get_mosaic_noise_map_status_u = True
        else:
            logger.info("Mosaicked Stokes U noise maps are already available")

        if not mosaic_polarisation_get_mosaic_noise_map_status_v:
            # Produce mosaic noise map
            maths = lib.miriad('maths')
            maths.out = 'mosaic_V_noise.map'
            maths.exp = "'1./sqrt(<variance_V_mos.map>)'"
            maths.mask = "'<variance_V_mos.map>.gt.0.01*" + str(mosaic_polarisation_max_variance_v) + "'"
            try:
                maths.go()
            except Exception as e:
                error = "Calculating Stokes V mosaic noise map ... Failed"
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)

            puthd = lib.miriad('puthd')
            puthd.in_ = 'mosaic_V_noise.map/bunit'
            puthd.value = 'JY/BEAM'
            try:
                puthd.go()
            except Exception as e:
                error = "Adding Stokes V noise map unit ... Failed"
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)

            logger.info("Getting Stokes V mosaic noise map ... Done")
            mosaic_polarisation_get_mosaic_noise_map_status_v = True
        else:
            logger.info("Mosaic Stokes V map noise is already available")

        subs_param.add_param(self, 'mosaic_polarisation_get_mosaic_noise_map_status_q', mosaic_polarisation_get_mosaic_noise_map_status_q)
        subs_param.add_param(self, 'mosaic_polarisation_get_mosaic_noise_map_status_u', mosaic_polarisation_get_mosaic_noise_map_status_u)
        subs_param.add_param(self, 'mosaic_polarisation_get_mosaic_noise_map_status_v', mosaic_polarisation_get_mosaic_noise_map_status_v)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to write out the mosaic FITS files
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def write_continuum_mosaic_fits_files(self):
        """
        Function to write out the mosaic fits files
        """

        logger.info("Writing continuum mosaic fits files")

        mosaic_continuum_write_mosaic_fits_files_status = get_param_def(
            self, 'mosaic_continuum_write_mosaic_fits_files_status', False)

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_mosaic_dir)

        # set the mosaic name
        if not self.mosaic_name:
            self.mosaic_name = "{}_mosaic.fits".format(self.mosaic_taskid)

        # name of the noise map
        mosaic_continuum_noise_name = self.mosaic_name.replace(".fits", "_noise.fits")

        if not mosaic_continuum_write_mosaic_fits_files_status and not os.path.exists(self.mosaic_name):

            # Write out FITS files
            # main image
            fits = lib.miriad('fits')
            fits.op = 'xyout'
            fits.in_ = 'mosaic_final.map'
            fits.out = self.mosaic_name
            try:
                fits.go()
            except Exception as e:
                error = "Writing continuum mosaic fits file ... Failed"
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)
        else:
            logger.info("Continuum mosaic image has already been converted to fits")

        if not mosaic_continuum_write_mosaic_fits_files_status and not os.path.exists(mosaic_continuum_noise_name):
            # noise map
            fits = lib.miriad('fits')
            fits.op = 'xyout'
            fits.in_ = 'mosaic_noise.map'
            fits.out = mosaic_continuum_noise_name
            try:
                fits.go()
            except Exception as e:
                error = "Writing continuum mosaic noise map fits file ... Failed"
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)

        else:
            logger.info(
                "Continuum mosaic noise image has already been converted to fits")

        logger.info("Writing continuum mosaic fits files ... Done")
        mosaic_continuum_write_mosaic_fits_files_status = True
        subs_param.add_param(
            self, 'mosaic_continuum_write_mosaic_fits_files_status', mosaic_continuum_write_mosaic_fits_files_status)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to write out the mosaic FITS files
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def write_polarisation_mosaic_fits_files(self):
        """
        Function to write out the polarisation mosaic fits files
        """

        logger.info("Writing polarisation mosaic fits files")

        mosaic_polarisation_write_mosaic_fits_files_status_q = get_param_def(self, 'mosaic_polarisation_write_mosaic_fits_files_status_q', False)
        mosaic_polarisation_write_mosaic_fits_files_status_u = get_param_def(self, 'mosaic_polarisation_write_mosaic_fits_files_status_u', False)
        mosaic_polarisation_write_mosaic_fits_files_status_v = get_param_def(self, 'mosaic_polarisation_write_mosaic_fits_files_status_v', False)

        # Get the needed information from the param files
        pbeam = 'polarisation_B' + str(self.mosaic_beam_list[0]).zfill(2)
        polbeamimagestatus = get_param_def(self, pbeam + '_targetbeams_qu_imagestatus', False)
        qimages = len(polbeamimagestatus)

        # switch to mosaic directory
        subs_managefiles.director(self, 'ch', self.mosaic_polarisation_mosaic_dir)

        if not mosaic_polarisation_write_mosaic_fits_files_status_q:
            for qplane in range(qimages):
                # Write out FITS files
                # main image
                fits = lib.miriad('fits')
                fits.op = 'xyout'
                fits.in_ = 'mosaic_Q_{}_final.map'.format(str(qplane).zfill(3))
                mosaic_name_q = "{0}_Q_{1}_mosaic.fits".format(self.mosaic_taskid, str(qplane).zfill(3))
                fits.out = mosaic_name_q
                try:
                    fits.go()
                except Exception as e:
                    error = "Writing Stokes Q mosaic fits file for image plane {} ... Failed".format(qplane)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)
                # noise map
                fits = lib.miriad('fits')
                fits.op = 'xyout'
                fits.in_ = 'mosaic_Q_{}_noise.map'.format(str(qplane).zfill(3))
                mosaic_noise_name_q = mosaic_name_q.replace(".fits", "_noise.fits")
                fits.out = mosaic_noise_name_q
                try:
                    fits.go()
                except Exception as e:
                    error = "Writing Stokes Q mosaic noise map fits file for image plane {}... Failed".format(qplane)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)
            mosaic_polarisation_write_mosaic_fits_files_status_q = True
        else:
            logger.info("Stokes Q mosaic images and noise maps have already been converted to fits")

        if not mosaic_polarisation_write_mosaic_fits_files_status_u:
            for uplane in range(qimages):
                # Write out FITS files
                # main image
                fits = lib.miriad('fits')
                fits.op = 'xyout'
                fits.in_ = 'mosaic_U_{}_final.map'.format(str(uplane).zfill(3))
                mosaic_name_u = "{0}_U_{1}_mosaic.fits".format(self.mosaic_taskid, str(uplane).zfill(3))
                fits.out = mosaic_name_u
                try:
                    fits.go()
                except Exception as e:
                    error = "Writing Stokes U mosaic fits file for image plane {} ... Failed".format(uplane)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)
                # noise map
                fits = lib.miriad('fits')
                fits.op = 'xyout'
                fits.in_ = 'mosaic_U_{}_noise.map'.format(str(uplane).zfill(3))
                mosaic_noise_name_u = mosaic_name_u.replace(".fits", "_noise.fits")
                fits.out = mosaic_noise_name_u
                try:
                    fits.go()
                except Exception as e:
                    error = "Writing Stokes U mosaic noise map fits file for image plane {}... Failed".format(uplane)
                    logger.error(error)
                    logger.exception(e)
                    raise RuntimeError(error)
            mosaic_polarisation_write_mosaic_fits_files_status_u = True
        else:
            logger.info("Stokes U mosaic images and noise maps have already been converted to fits")

        if not mosaic_polarisation_write_mosaic_fits_files_status_v:
            # Write out FITS files
            # main image
            fits = lib.miriad('fits')
            fits.op = 'xyout'
            fits.in_ = 'mosaic_V_final.map'
            mosaic_name_v = "{0}_V_mosaic.fits".format(self.mosaic_taskid)
            fits.out = mosaic_name_v
            try:
                fits.go()
            except Exception as e:
                error = "Writing Stokes V mosaic fits file ... Failed"
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)
            # noise map
            fits = lib.miriad('fits')
            fits.op = 'xyout'
            fits.in_ = 'mosaic_V_noise.map'
            mosaic_noise_name_v = mosaic_name_v.replace(".fits", "_noise.fits")
            fits.out = mosaic_noise_name_v
            try:
                fits.go()
            except Exception as e:
                error = "Writing Stokes V mosaic noise map fits file ... Failed"
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)
            mosaic_polarisation_write_mosaic_fits_files_status_v = True
        else:
            logger.info("Stokes V mosaic images and noise maps have already been converted to fits")

        logger.info("Writing polarisation mosaic fits files ... Done")

        subs_param.add_param(self, 'mosaic_polarisation_write_mosaic_fits_files_status_q', mosaic_polarisation_write_mosaic_fits_files_status_q)
        subs_param.add_param(self, 'mosaic_polarisation_write_mosaic_fits_files_status_u', mosaic_polarisation_write_mosaic_fits_files_status_u)
        subs_param.add_param(self, 'mosaic_polarisation_write_mosaic_fits_files_status_v', mosaic_polarisation_write_mosaic_fits_files_status_v)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to run validation tool
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def run_continuum_image_validation(self):
        """
        Function to run image validation
        """

        mosaic_run_image_validation_status = get_param_def(
            self, 'mosaic_run_image_validation_status', False)

        if self.mosaic_continuum_image_validation:
            # optional step, so only do the import here
            import dataqa
            from dataqa.continuum.validation_tool import validation

            # to be sure, in case this step is run independently, set the paths
            self.set_mosaic_subdirs()

            # switch to mosaic directory
            subs_managefiles.director(
                self, 'ch', self.mosaic_continuum_mosaic_dir)

            logger.info("Running image validation")

            # Validate final continuum mosaic

            finder = 'pybdsf'
            start_time_validation = time.time()

            # set the mosaic name
            if not self.mosaic_name:
                self.mosaic_name = "{}_mosaic.fits".format(self.mosaic_taskid)

            validation.run(self.mosaic_name, finder=finder)

            logger.info("Running image validation ... Done ({0:.0f}s)".format(
                time.time() - start_time_validation))
            mosaic_run_image_validation_status = True
        else:
            logger.warning("Did not run image validation")
            mosaic_run_image_validation_status = False

        subs_param.add_param(
            self, 'mosaic_continuum_run_image_validation_status', mosaic_continuum_run_image_validation_status)


    ###############################
    ###### Support functions ######
    ###############################

    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to convert beam maps from fits to miriad
    # May not be necessary in the end.
    # +++++++++++++++++++++++++++++++++++++++++++++++++++

    def convert_continuum_beams_to_miriad(self):
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
            try:
                fits.go()
            except Exception as e:
                mosaic_continuum_convert_fits_beam_status = False
                error = "Converting fits image of beam {} to miriad image ... Failed".format(
                    beam)
                logger.error(error)
                logger.exception(e)
                raise RuntimeError(error)
            else:
                mosaic_continuum_convert_fits_beam_status = True
                logger.debug(
                    "Converting fits image of beam {} to miriad image ... Done".format(beam))

        if mosaic_continuum_convert_fits_beam_status:
            logger.info(
                "Converting fits images to miriad images ... Successful")
        else:
            logger.warning(
                "Converting fits images to miriad images ... Failed for at least one beam. Please check the log")

        subs_param.add_param(
            self, 'mosaic_continuum_convert_fits_beam_status', mosaic_continuum_convert_fits_beam_status)


    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to make the mosaic stop after a certain number of steps
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def stop_mosaic(self, step_counter):
        """
        Function to test if the mosaic processing should stop
        """
        if self.mosaic_step_limit is not None and step_counter > self.mosaic_step_limit:
            logger.warning("#### Reached the maximum number of steps requested ({}). Will stop creating mosaic.".format(
                self.mosaic_step_limit))
            return True
        else:
            return False

    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to create the continuum mosaic
    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    def create_mosaic_continuum_mf(self):
        """
        Function to create the continuum mosaic
        """
        # subs_setinit.setinitdirs(self)

        mosaic_continuum_mf_status = get_param_def(
            self, 'mosaic_continuum_mf_status', False)

        # check whether only a limited number of steps should be done
        if self.mosaic_step_limit is not None:
            logger.warning("#### Will only do the first {} steps of creating the mosaic".format(
                self.mosaic_step_limit))

        # Start the mosaicking of the stacked continuum images
        if self.mosaic_continuum_mf:
            logger.info("Creating continuum image mosaic")

            # change into the directory for the continuum mosaic
            # subs_managefiles.director(self, 'ch', os.path.join(self.mosdir, self.mosaic_continuum_subdir))

            # if no mosaic has already been created
            if not mosaic_continuum_mf_status:

                # step counter
                i = 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # setup
                # ====================================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.mosaic_setup()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # set (and create) the sub-directories
                # ====================================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.set_mosaic_subdirs(continuum=True)
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # get the continuum images
                # ========================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.get_mosaic_continuum_images()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # get the beams
                # =============
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.get_mosaic_continuum_beams()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Converting images into miriad
                # =======================================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.convert_continuum_images_to_miriad()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # set or check the projection center
                # ==================================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.get_mosaic_continuum_projection_centre()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Transfer image coordinates
                # ==========================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.transfer_continuum_coordinates()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Create a template mosaic
                # ========================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.create_continuum_template_mosaic()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Regrid images
                # =============
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.regrid_continuum_images()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Regrid beam maps
                # ================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.regrid_continuum_beam_maps()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Determing common beam for convolution
                # =====================================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.get_continuum_common_beam()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Convolve images
                # ===============
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.mosaic_continuum_convolve_images()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Get inverse covariance matrix
                # =====================================================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.get_continuum_inverted_covariance_matrix()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Calculate product of beam matrix and covariance matrix
                # ======================================================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.math_continuum_multiply_beam_and_covariance_matrix()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Calculate variance map
                # ======================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.math_continuum_calculate_variance_map()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Calculate beam matrix multiplied by covariance matrix
                # =====================================================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.math_continuum_multiply_beam_matrix_by_covariance_matrix_and_image()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Find maximum variance map
                # =========================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.math_continuum_get_max_variance_map()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Calculate divide image by variance map
                # ======================================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.math_continuum_divide_image_by_variance_map()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Calculate get mosaic noise map
                # ==============================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.get_continuum_mosaic_noise_map()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # Writing files
                # =============
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.write_continuum_mosaic_fits_files()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))

                # Save the derived parameters to the parameter file
                mosaic_continuum_mf_status = True

                # Remove scratch files
                # ====================
                if self.mosaic_continuum_clean_up:
                    logger.info("#### Step: clean up ####")
                    start_time_step = time.time()
                    self.clean_up_continuum(level=self.mosaic_continuum_clean_up_level)
                    logger.info("#### Step: clean up ... Done (after {0:.0f}s) ####".format(
                        time.time() - start_time_step))

            else:
                logger.info("Continuum image mosaic was already created")

            # Image validation
            # ================
            if self.mosaic_continuum_image_validation:
                logger.info("#### Step: mosaic validation ####")
                start_time_step = time.time()
                try:
                    self.run_continuum_image_validation()
                except Exception as e:
                    logger.warning("#### Step: mosaic validation ... Failed (after {0:.0f}s) ####".format(
                        time.time() - start_time_step))
                    logger.exception(e)
                else:
                    logger.info("#### Step: mosaic validation ... Done (after {0:.0f}s) ####".format(
                        time.time() - start_time_step))

            subs_param.add_param(
                self, 'mosaic_continuum_mf_status', mosaic_continuum_mf_status)

            logger.info("Creating continuum image mosaic ... Done")
        else:
            pass

    # +++++++++++++++++++++++++++++++++++++++++++++++++++
    # Function to create the polarisation Q, U and V mosaics
    # +++++++++++++++++++++++++++++++++++++++++++++++++++

    def create_mosaic_polarisation(self, mosaic_type=None):
        """
        Function to create the different mosaics
        """
        # subs_setinit.setinitdirs(self)

        mosaic_polarisation_status = get_param_def(
            self, 'mosaic_polarisation_status', False)

        # Start the mosaicking of the polarisation images
        if self.mosaic_polarisation:
            logger.info("Creating stokes Q, U and V mosaics")

            # change into the directory for the continuum mosaic
            # subs_managefiles.director(self, 'ch', os.path.join(self.mosdir, self.mosaic_continuum_subdir))

            # if no mosaic has already been created
            if not mosaic_polarisation_status:

                # step counter
                i = 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # setup
                # ====================================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.mosaic_setup()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # set (and create) the sub-directories
                # ====================================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.set_mosaic_subdirs(continuum=True)
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # get the polarisation images
                # ========================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.get_mosaic_polarisation_images()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # get the beams
                # =============
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.get_mosaic_polarisation_beams()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Converting images into miriad
                # =======================================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.convert_polarisation_images_to_miriad()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Split the Q and U cubes into single images and set the beam in the header
                # =======================================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.split_polarisation_images()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # set or check the projection center
                # ==================================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.get_mosaic_polarisation_projection_centre()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Transfer image coordinates
                # ==========================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.transfer_polarisation_coordinates()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Create a template mosaic
                # ========================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.create_polarisation_template_mosaic()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Regrid polarisation images
                # =============
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.regrid_polarisation_images()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Regrid polarisation beam maps
                # ================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.regrid_polarisation_beam_maps()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Determing common beam for convolution
                # =====================================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.get_polarisation_common_beam()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Convolve images
                # ===============
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.mosaic_polarisation_convolve_images()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Get inverse covariance matrix
                # =====================================================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.get_polarisation_inverted_covariance_matrix()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Calculate product of beam matrix and covariance matrix
                # ======================================================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.math_polarisation_multiply_beam_and_covariance_matrix()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Calculate variance map
                # ======================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.math_polarisation_calculate_variance_map()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Calculate beam matrix multiplied by covariance matrix
                # =====================================================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.math_polarisation_multiply_beam_matrix_by_covariance_matrix_and_image()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Find maximum variance map
                # =========================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.math_polarisation_get_max_variance_map()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Calculate divide image by variance map
                # ======================================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.math_polarisation_divide_image_by_variance_map()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Calculate get mosaic noise map
                # ==============================
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.get_polarisation_mosaic_noise_map()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1

                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                # Writing files
                # =============
                logger.info("#### Step {0} ####".format(i))
                start_time_step = time.time()
                self.write_polarisation_mosaic_fits_files()
                logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                    i, time.time() - start_time_step))
                i += 1


                # to allow the mosaic to stop earlier
                if self.stop_mosaic(i):
                    return None

                if self.mosaic_polarisation_clean_up:
                    logger.info("#### Step {0} ####".format(i))
                    start_time_step = time.time()
                    self.clean_up_polarisation(level=self.mosaic_polarisation_clean_up_level)
                    logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
                        i, time.time() - start_time_step))

        #         # Image validation
        #         # ================
        #         if self.mosaic_image_validation:
        #             logger.info("#### Step {0} ####".format(i))
        #             start_time_step = time.time()
        #             try:
        #                 self.run_image_validation()
        #             except Exception as e:
        #                 logger.warning("#### Step {0} ... Failed (after {1:.0f}s) ####".format(
        #                     i, time.time() - start_time_step))
        #                 logger.exception(e)
        #             else:
        #                 logger.info("#### Step {0} ... Done (after {1:.0f}s) ####".format(
        #                     i, time.time() - start_time_step))
        #             i += 1
        #
                # Save the derived parameters to the parameter file
                mosaic_polarisation_status = True
                subs_param.add_param(self, 'mosaic_polarisation_status', mosaic_polarisation_status)


            else:
                logger.info("Stokes Q, U and V mosaics were already created")

            logger.info("Stokes Q, U and V mosaics ... Done")
        else:
            pass


    def show(self, showall=False):
        lib.show(self, 'MOSAIC', showall)


    def clean_up_continuum(self, level=0):
        """
        Function to remove scratch files for continuum

        Args:
            level (int): level of how much should be removed
        """
        # subs_setinit.setinitdirs(self)
        logger.info("Removing scratch files for continuum")

        # to be sure, in case this step is run independently, set the paths
        self.set_mosaic_subdirs()

        # remove file from creating template mosaic
        # shutil.rmtree(mosaicdir+'mosaic_temp.map')
        subs_managefiles.director(self, 'ch', self.mosaic_continuum_mosaic_dir)
        subs_managefiles.director(
            self, 'rm', 'mosaic_temp_preproj.map', ignore_nonexistent=True)

        # Clean up files
        for fl in glob.glob('*_convol.map'):
            subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)
        # Clean up files
        for fl in glob.glob('*_regrid.map'):
            subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)

        subs_managefiles.director(
            self, 'rm', 'mosaic_im.map', ignore_nonexistent=True)

        # shutil.rmtree(mosaicdir+'mosaic_im.map')

        for fl in glob.glob('mos_*.map'):
            subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)

        for fl in glob.glob('btci_*.map'):
            subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)

        for fl in glob.glob('out_*.map'):
            subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)

        # more to remove
        if level >= 1:
            subs_managefiles.director(
                self, 'ch', self.mosaic_continuum_beam_dir)
            for fl in glob.glob('beam_??.map'):
                subs_managefiles.director(
                    self, 'rm', fl, ignore_nonexistent=True)

            subs_managefiles.director(
                self, 'ch', self.mosaic_continuum_images_dir)
            for fl in glob.glob('image_*_regrid.map'):
                subs_managefiles.director(
                    self, 'rm', fl, ignore_nonexistent=True)

            for fl in glob.glob('??'):
                subs_managefiles.director(
                    self, 'rm', fl, ignore_nonexistent=True)

        if level >= 2:
            subs_managefiles.director(
                self, 'ch', self.mosaic_continuum_beam_dir)
            for fl in glob.glob('beam_*_mos.map'):
                subs_managefiles.director(
                    self, 'rm', fl, ignore_nonexistent=True)

            subs_managefiles.director(
                self, 'ch', self.mosaic_continuum_mosaic_dir)
            for fl in glob.glob('image_*_mos.map'):
                subs_managefiles.director(
                    self, 'rm', fl, ignore_nonexistent=True)

        logger.info("Removing scratch files ... Done")

    def clean_up_polarisation(self, level=0):
        """
        Function to remove scratch files for polarisation

        Args:
            level (int): level of how much should be removed
        """
        # subs_setinit.setinitdirs(self)
        logger.info("Removing scratch files for polarisation")

        # to be sure, in case this step is run independently, set the paths
        self.set_mosaic_subdirs()

        # remove file from creating template mosaic
        # shutil.rmtree(mosaicdir+'mosaic_temp.map')
        subs_managefiles.director(self, 'ch', self.mosaic_polarisation_mosaic_dir)
        subs_managefiles.director(
            self, 'rm', 'mosaic_polarisation_temp_preproj.map', ignore_nonexistent=True)

        # Clean up files
        for fl in glob.glob('*_convol.map'):
            subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)
        # Clean up files
        for fl in glob.glob('*_regrid.map'):
            subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)

        subs_managefiles.director(
            self, 'rm', 'mosaic_*_im.map', ignore_nonexistent=True)

        # shutil.rmtree(mosaicdir+'mosaic_im.map')

        for fl in glob.glob('mos_*.map'):
            subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)

        for fl in glob.glob('btci_*.map'):
            subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)

        for fl in glob.glob('out_*.map'):
            subs_managefiles.director(self, 'rm', fl, ignore_nonexistent=True)

        # more to remove
        if level >= 1:
            subs_managefiles.director(
                self, 'ch', self.mosaic_polarisation_beam_dir)
            for fl in glob.glob('beam_??.map'):
                subs_managefiles.director(
                    self, 'rm', fl, ignore_nonexistent=True)

            subs_managefiles.director(
                self, 'ch', self.mosaic_polarisation_images_dir)
            for fl in glob.glob('image_*_regrid.map'):
                subs_managefiles.director(
                    self, 'rm', fl, ignore_nonexistent=True)

            for fl in glob.glob('??'):
                subs_managefiles.director(
                    self, 'rm', fl, ignore_nonexistent=True)

        if level >= 2:
            subs_managefiles.director(
                self, 'ch', self.mosaic_polarisation_beam_dir)
            for fl in glob.glob('beam_*_mos.map'):
                subs_managefiles.director(
                    self, 'rm', fl, ignore_nonexistent=True)

            subs_managefiles.director(
                self, 'ch', self.mosaic_polarisation_mosaic_dir)
            for fl in glob.glob('*cube_*_mos.map'):
                subs_managefiles.director(
                    self, 'rm', fl, ignore_nonexistent=True)

        logger.info("Removing scratch files for polarisation ... Done")


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
            logger.warning('Deleting all parameter file entries for MOSAIC module')

            subs_param.del_param(self, 'mosaic_continuum_create_subdirs_status')
            subs_param.del_param(self, 'mosaic_polarisation_create_subdirs_status')

            subs_param.del_param(self, 'mosaic_continuum_images_status')
            subs_param.del_param(self, 'mosaic_continuum_failed_beams')
            subs_param.del_param(self, 'mosaic_polarisation_images_status')
            subs_param.del_param(self, 'mosaic_polarisation_failed_beams')

            subs_param.del_param(self, 'mosaic_continuum_beam_status')
            subs_param.del_param(self, 'mosaic_polarisation_beam_status')

            subs_param.del_param(self, 'mosaic_continuum_convert_fits_images_status')
            subs_param.del_param(self, 'mosaic_polarisation_convert_fits_images_status')

            subs_param.del_param(self, 'mosaic_polarisation_split_cubes_status')

            subs_param.del_param(self, 'mosaic_continuum_projection_centre_status')
            subs_param.del_param(self, 'mosaic_continuum_projection_centre_values')
            subs_param.del_param(self, 'mosaic_polarisation_projection_centre_status')
            subs_param.del_param(self, 'mosaic_polarisation_projection_centre_values')

            subs_param.del_param(self, 'mosaic_continuum_transfer_coordinates_to_beam_status')
            subs_param.del_param(self, 'mosaic_polarisation_transfer_coordinates_to_beam_status')

            subs_param.del_param(self, 'mosaic_continuum_template_mosaic_status')
            subs_param.del_param(self, 'mosaic_polarisation_template_mosaic_status')

            subs_param.del_param(self, 'mosaic_continuum_regrid_images_status')
            subs_param.del_param(self, 'mosaic_polarisation_regrid_images_status')

            subs_param.del_param(self, 'mosaic_continuum_regrid_beam_maps_status')
            subs_param.del_param(self, 'mosaic_polarisation_regrid_beam_maps_status')

            subs_param.del_param(self, 'mosaic_continuum_common_beam_status')
            subs_param.del_param(self, 'mosaic_continuum_common_beam_values')
            subs_param.del_param(self, 'mosaic_polarisation_common_beam_status')
            subs_param.del_param(self, 'mosaic_polarisation_common_beam_values_qu')
            subs_param.del_param(self, 'mosaic_polarisation_common_beam_values_v')

            subs_param.del_param(self, 'mosaic_continuum_convolve_images_status')
            subs_param.del_param(self, 'mosaic_polarisation_convolve_images_status')

            subs_param.del_param(self, 'mosaic_continuum_correlation_matrix_status')
            subs_param.del_param(self, 'mosaic_continuum_inverse_covariance_matrix')
            subs_param.del_param(self, 'mosaic_polarisation_correlation_matrix_status')
            subs_param.del_param(self, 'mosaic_polarisation_inverse_covariance_matrix_q')
            subs_param.del_param(self, 'mosaic_polarisation_inverse_covariance_matrix_u')
            subs_param.del_param(self, 'mosaic_polarisation_inverse_covariance_matrix_v')
            subs_param.del_param(self, 'mosaic_polarisation_inverse_covariance_matrix_status')

            subs_param.del_param(self, 'mosaic_continuum_product_beam_covariance_matrix_status')
            subs_param.del_param(self, 'mosaic_polarisation_product_beam_covariance_matrix_status_q')
            subs_param.del_param(self, 'mosaic_polarisation_product_beam_covariance_matrix_status_u')
            subs_param.del_param(self, 'mosaic_polarisation_product_beam_covariance_matrix_status_v')

            subs_param.del_param(self, 'mosaic_continuum_variance_map_status')
            subs_param.del_param(self, 'mosaic_polarisation_variance_map_status_q')
            subs_param.del_param(self, 'mosaic_polarisation_variance_map_status_u')
            subs_param.del_param(self, 'mosaic_polarisation_variance_map_status_v')

            subs_param.del_param(self, 'mosaic_continuum_product_beam_covariance_matrix_image_status')
            subs_param.del_param(self, 'mosaic_polarisation_product_beam_covariance_matrix_image_status_q')
            subs_param.del_param(self, 'mosaic_polarisation_product_beam_covariance_matrix_image_status_u')
            subs_param.del_param(self, 'mosaic_polarisation_product_beam_covariance_matrix_image_status_v')

            subs_param.del_param(self, 'mosaic_continuum_get_max_variance_status')
            subs_param.del_param(self, 'mosaic_continuum_max_variance')
            subs_param.del_param(self, 'mosaic_polarisation_get_max_variance_status_q')
            subs_param.del_param(self, 'mosaic_polarisation_get_max_variance_status_u')
            subs_param.del_param(self, 'mosaic_polarisation_get_max_variance_status_v')
            subs_param.del_param(self, 'mosaic_polarisation_max_variance_q')
            subs_param.del_param(self, 'mosaic_polarisation_max_variance_u')
            subs_param.del_param(self, 'mosaic_polarisation_max_variance_v')

            subs_param.del_param(self, 'mosaic_continuum_divide_image_variance_status')
            subs_param.del_param(self, 'mosaic_polarisation_divide_image_variance_status_q')
            subs_param.del_param(self, 'mosaic_polarisation_divide_image_variance_status_u')
            subs_param.del_param(self, 'mosaic_polarisation_divide_image_variance_status_v')

            subs_param.del_param(self, 'mosaic_continuum_get_mosaic_noise_map_status')
            subs_param.del_param(self, 'mosaic_polarisation_get_mosaic_noise_map_status_q')
            subs_param.del_param(self, 'mosaic_polarisation_get_mosaic_noise_map_status_u')
            subs_param.del_param(self, 'mosaic_polarisation_get_mosaic_noise_map_status_v')

            subs_param.del_param(self, 'mosaic_continuum_write_mosaic_fits_files_status')
            subs_param.del_param(self, 'mosaic_polarisation_write_mosaic_fits_files_status_q')
            subs_param.del_param(self, 'mosaic_polarisation_write_mosaic_fits_files_status_u')
            subs_param.del_param(self, 'mosaic_polarisation_write_mosaic_fits_files_status_v')

            subs_param.del_param(self, 'mosaic_continuum_run_image_validation_status')
            subs_param.del_param(self, 'mosaic_polarisation_run_image_validation_status')

            subs_param.del_param(self, 'mosaic_continuum_mf_status')
            subs_param.del_param(self, 'mosaic_polarisation_status')

        else:
            logger.warning('Mosaicked data products are not present!')