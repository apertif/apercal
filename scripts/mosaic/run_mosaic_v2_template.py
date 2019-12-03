#!/usr/bin/python2

"""
Script to test the new mosaic module.

This script contains the settings necessary to make a continuum mosaic.
The settings can also be specified in an apercal configfile, but then
they need to be removed here.

--> Important note <-- 
This method creates a large number of scratch files that can/will be 
deleted in the end. However, the scratch files require significant disk
space (compared to the size of the mosaic). For a standard 40-beam mosaic,
about 30GB of disk space are necessary temporarily
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

start_time = time.time()

# set path to configfile
# note: remove settings below if configfile is used
#configfile = "/home/schulz/pipeline/apercal_tests/mosaic/mosaic_v2_190428055.cfg"
configfile = None

# Setting up log file
task_id = 190428055
logfile = os.path.join(os.getcwd(), "{0}_mosaic.log".format(
    task_id))
lib.setup_logger('debug', logfile=logfile)
logger = logging.getLogger(__name__)

# Mosaic module
mo = mosaic(file_=configfile)

# List of settings (Change as necessary)
# ======================================

# set the output directory
mo.basedir = '/data/schulz/mosaic_test/190428055/'

# enable continuum mosaic
mo.mosaic_continuum_mf = True

# set the taskid of observation to mosaic
mo.mosaic_taskid = "190428055"

# set the list of beams or all
mo.mosaic_beams = 'all'

# set location of continuum images, default is ALTA
# if local path is specified, then the
# continuum images must be located in <local_path>/<beam_nr>/<image_name>.fits
# mo.mosaic_continuum_image_origin = "/data/pisano/190428055/continuum/raw/"

# set the type of primary beam to be used
mo.mosaic_primary_beam_type = 'Correct'
# if the correct primary beam is suppose to be used
# set the path to files (do not change)
mo.mosaic_primary_beam_shape_files_location = "/data/apertif/driftscans/fits_files/191023"
# set the cutoff
mo.mosaic_beam_map_cutoff = 0.1

# set the projection centre
# using the a given beam
mo.mosaic_projection_centre_beam = '00'
# using ra and dec (untested)
#mo.mosaic_projection_centre_ra = ''
#mo.mosaic_projection_centre_dec = ''

# type of beam for convolution
mo.mosaic_common_beam_type = 'circular'

# run the image validation tool on the mosaic
mo.mosaic_image_validation = True

# remove scratch files
mo.mosaic_clean_up = True

# End of list of settings
# =======================

# create the mosaic
mo.go()

logger.info("Finished after {0:.0f}s".format(time.time()-start_time))
