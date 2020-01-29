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


def make_mosaic(task_id, basedir, centre_ra=None, centre_dec=None, primary_beam_map_dir=None):

    start_time = time.time()

    # configfile
    #configfile = "/home/schulz/pipeline/apercal_tests/mosaic/mosaic_v2_190428055.cfg"
    configfile = None

    # Setting up log file
    #task_id = 190822046
    logfile = os.path.join(os.getcwd(), "{0}_mosaic.log".format(
        task_id))
    lib.setup_logger('debug', logfile=logfile)
    logger = logging.getLogger(__name__)

    host_name = socket.gethostname()

    # Mosaic module
    mo = mosaic(file_=configfile)

    # Settings
    # ========

    # set the output directory
    #mo.basedir = '/data/schulz/mosaic_test/{}/'.format(task_id)
    mo.basedir = os.path.join(basedir, '{}'.format(task_id))

    # enable continuum mosaic
    mo.mosaic_continuum_mf = True

    # set the taskid of observation to mosaic
    mo.mosaic_taskid = "{}".format(task_id)

    # set the list of beams or all
    mo.mosaic_beams = 'all'

    # set location of continuum images, default is ALTA
    # continuum images must be located in <path>/<beam_nr>/<image_name>.fits
    # mo.mosaic_continuum_image_origin = "/data/pisano/190428055/continuum/raw/"

    # set the type of primary beam to be used
    mo.mosaic_primary_beam_type = 'Correct'
    # if the correct primary beam is suppose to be used
    # set the path to files (do not change)
    if primary_beam_map_dir is None:
        mo.mosaic_primary_beam_shape_files_location = "/data/apertif/driftscans/fits_files/191023"
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

    # run the image validation tool on the mosaic
    mo.mosaic_image_validation = True

    # clean up
    mo.mosaic_clean_up_level = 1
    mo.mosaic_clean_up = True

    # create the mosaic
    # =================
    mo.go()

    logger.info("Finished after {0:.0f}s".format(time.time()-start_time))


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

    parser.add_argument("--primary_beam_map_dir", type=str, default=None,
                        help='Location of the primary beam maps')

    # parser.add_argument("--do_validation", action="store_true", default=False,
    #                     help='Set to enable validation of mosaic')

    # parser.add_argument("--do_cleanup", action="store_true", default=False,
    #                     help='Set to enable validation of mosaic')

    args = parser.parse_args()

    make_mosaic(args.task_id, args.basedir,
                centre_ra=args.centre_ra, centre_dec=args.centre_dec, primary_beam_map_dir=args.primary_beam_map_dir)
