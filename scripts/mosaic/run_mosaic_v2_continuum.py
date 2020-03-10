#!/usr/bin/python2

"""
Script to create continuum mosaics with the new mosaic module.
This version requires command line arguments, but only the taskid
and output location can be set. The mosaic settings cannot be changed otherwise
unless changed in the script.


Usage:
python run_mosaic_v2_continuum.py <taskid> <output_dir>

Optional arguments:
--centre_ra (str): RA coordinate of projection centre
--centre_dec (str): DEC coordinate of projection centre
--mosaic_beams (str): Comma-separated list of beams in a single string (no spaces). Default is all available beams
--primary_beam_map_dir (str): Location of the primary beam maps
--step_limit (int): The maximum number of steps the mosaic module should do
--do_validation (bool): Set to enable validation of mosaic (default False)
--use_noise_correlation (bool): Set to enable using noise correlation (default False)
--continuum_image_dir (str): Location of the continuum images (default AlTA)
--do_not_cleanup (bool): Set to enable removing most of the scratch files (default False)
"""

import time
import subprocess
import logging
import apercal.libs.lib as lib
#from apercal.pipeline.start_pipeline import start_apercal_pipeline
#from dataqa.run_qa import run_triggered_qa
from apercal.modules.mosaic_v2 import mosaic
import os
import socket
import time
import argparse


def make_mosaic(task_id, basedir, centre_ra=None, centre_dec=None, mosaic_beams=None, primary_beam_map_dir=None, step_limit=None, use_noise_correlation=False, do_validation=False, continuum_image_dir=None, do_not_cleanup=False):

    start_time = time.time()

    # configfile
    # configfile = "/home/schulz/pipeline/apercal_tests/mosaic/mosaic_v2_190428055.cfg"
    configfile = None

    # Setting up log file
    # task_id = 190822046
    logfile = os.path.join(os.getcwd(), "{0}_mosaic.log".format(
        task_id))
    lib.setup_logger('debug', logfile=logfile)
    logger = logging.getLogger(__name__)

    host_name = socket.gethostname()

    # Mosaic module
    mo = mosaic(file_=configfile)

    # Settings
    # ========

    # set the number of steps for the mosaic to go through
    mo.mosaic_step_limit = step_limit

    # set the output directory
    mo.basedir = os.path.join(basedir, '{}'.format(task_id))

    # enable continuum mosaic
    mo.mosaic_continuum_mf = True

    # set the taskid of observation to mosaic
    mo.mosaic_taskid = "{}".format(task_id)

    # set the list of beams or all
    if mosaic_beams is None:
        mo.mosaic_beams = 'all'
    else:
        mo.mosaic_beams = mosaic_beams

    # set location of continuum images, default is ALTA
    # continuum images must be located in <path>/<beam_nr>/<image_name>.fits
    if continuum_image_dir is None:
        mo.mosaic_continuum_image_origin = "ALTA"
    else:
        mo.mosaic_continuum_image_origin = continuum_image_dir
    # mo.mosaic_continuum_image_origin = "/data/pisano/190428055/continuum/raw/"

    # set the type of primary beam to be used
    mo.mosaic_primary_beam_type = 'Correct'
    # if the correct primary beam is suppose to be used
    # set the path to files (do not change)
    if primary_beam_map_dir is None:
        mo.mosaic_primary_beam_shape_files_location = "/tank/apertif/driftscans/fits_files/191023/chann_5"
    else:
        mo.mosaic_primary_beam_shape_files_location = primary_beam_map_dir
    # set the cutoff
    mo.mosaic_beam_map_cutoff = 0.1

    # set the projection centre
    if centre_ra is None and centre_dec is None:
        # using the a given beam
        mo.mosaic_projection_centre_beam = '00'
    else:
        # using ra and dec (untested)
        mo.mosaic_projection_centre_ra = centre_ra
        mo.mosaic_projection_centre_dec = centre_dec

    # type of beam for convolution
    mo.mosaic_common_beam_type = 'circular'

    # turn on noise correlation
    if use_noise_correlation:
        mo.mosaic_use_askap_based_matrix = True
    else:
        mo.mosaic_use_askap_based_matrix = False

    # run the image validation tool on the mosaic
    if do_validation:
        logger.info("Enabling mosaic image validation")
        mo.mosaic_image_validation = True
    else:
        mo.mosaic_image_validation = False

    # clean up
    mo.mosaic_clean_up_level = 1
    if do_not_cleanup:
        mo.mosaic_clean_up = False
    else:
        logger.info("Enabling cleaning up scratch files")
        mo.mosaic_clean_up = True

    # create the mosaic
    # =================
    mo.go()

    logger.info("Finished after {0:.0f}s".format(time.time() - start_time))


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description='Create continuum mosaic with standard settings')

    parser.add_argument("task_id", type=int,
                        help='Observation Number / Scan Number / TASK-ID')

    parser.add_argument("basedir", type=str,
                        help='Directory where the mosaic should be created. The taskid will be added to it')

    parser.add_argument("--centre_ra", type=str, default=None,
                        help='RA coordinate of projection centre. Works only together with --centre_dec')

    parser.add_argument("--centre_dec", type=str, default=None,
                        help='RA coordinate of projection centre. Works only together with --centre_ra')

    parser.add_argument("--mosaic_beams", type=str, default=None,
                        help='Comma-separated list of beams in a single string. Default is all available beams')

    parser.add_argument("--primary_beam_map_dir", type=str, default=None,
                        help='Location of the primary beam maps')

    parser.add_argument("--step_limit", type=int, default=None,
                        help='The maximum number of steps the mosaic module should do')

    parser.add_argument("--do_validation", action="store_true", default=False,
                        help='Set to enable validation of mosaic')

    parser.add_argument("--use_noise_correlation", action="store_true", default=False,
                        help='Set to enable using noise correlation')

    parser.add_argument("--continuum_image_dir", type=str, default='ALTA',
                        help='Location of the continuum images. Default is AlTA')

    parser.add_argument("--do_not_cleanup", action="store_true", default=False,
                        help='Set to enable removing most of the scratch files')

    args = parser.parse_args()

    make_mosaic(args.task_id, args.basedir,
                centre_ra=args.centre_ra, centre_dec=args.centre_dec, mosaic_beams=args.mosaic_beams, primary_beam_map_dir=args.primary_beam_map_dir, use_noise_correlation=args.use_noise_correlation, step_limit=args.step_limit, do_validation=args.do_validation, continuum_image_dir=args.continuum_image_dir, do_not_cleanup=args.do_not_cleanup)
