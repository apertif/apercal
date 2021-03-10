#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Nov 12 15:59:25 2020

@author: kutkin
"""

import logging

import os

from apercal.modules.base import BaseModule
from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles
from apercal.subs.param import get_param_def
from apercal.subs import param as subs_param
from apercal.libs import lib

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class compress(BaseModule):
    """
    Compress visibilities with dysco
    """
    module_name = 'COMPRESS'

    compress_bitrate = None

    def __init__(self, file_=None, **kwargs):
        self.default = lib.load_config(self, file_)
        subs_setinit.setinitdirs(self)

    def go(self):
        # os.chdir(self.get_target_path() + '/..')
        self.backup_vis()
        self.compress()
        self.delete_vis()
        self.decompress()

    def compress(self, bitrate=12):
        logger.info("Compressing with bitrate %d", bitrate)
        self.vis = self.get_target_path()
        self.vis_comp = self.get_target_path().rstrip('.MS') + '_compressed.MS'
        cmd = 'singularity exec /home/kutkin/lofar-pipeline.sif DPPP steps=[] msout.overwrite=true msout.storagemanager=dysco msin={} msout={} msout.storagemanager.databitrate={}'.\
            format(self.vis, self.vis_comp, bitrate)
        logger.debug(cmd)
        os.system(cmd)

    def decompress(self):
        logger.info("Decompressing")
        self.vis = self.get_target_path()
        self.vis_comp = self.get_target_path().rstrip('.MS') + '_compressed.MS'
        cmd = 'singularity exec /home/kutkin/lofar-pipeline.sif DPPP steps=[] msin={} msout={} msout.overwrite=true'.\
            format(self.vis_comp, self.vis)
        logger.debug(cmd)
        os.system(cmd)

    def backup_vis(self):
        vis = self.get_target_path()
        if os.path.exists('{0}.bak'.format(vis)):
            logger.debug('The data backup exists')
            return
        else:
            logger.info('Backing up the data before compression')
            os.system('cp -r {0} {0}.bak'.format(vis))

    def delete_vis(self):
        cmd = 'rm -rf {}'.format(self.get_target_path())
        logging.debug('Deleting data: %s', cmd)
        os.system(cmd)