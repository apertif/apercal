import os
import logging

from apercal.libs import lib
from apercal.subs import setinit as subs_setinit

logger = logging.getLogger(__name__)


def imagetofits(self, mirimage, fitsimage):
    """
    Converts a MIRIAD image to a FITS image
    mirimage: The MIRIAD image to convert
    fitsimage: The converted FITS image
    """
    subs_setinit.setinitdirs(self)
    fits = lib.miriad('fits')
    fits.op = 'xyout'
    fits.in_ = mirimage
    fits.out = fitsimage
    fits.go()
    if os.path.isfile(fitsimage):
        director(self, 'rm', mirimage)


def director(self, option, dest, file=None, verbose=True):
    """
    director: Function to move, remove, and copy files and directories
    option: 'mk', 'ch', 'mv', 'rm', and 'cp' are supported
    dest: Destination of a file or directory to move to
    file: Which file to move or copy, otherwise None
    """
    subs_setinit.setinitdirs(self)
    if option == 'mk':
        if os.path.exists(dest):
            pass
        else:
            os.makedirs(dest)
            if verbose == True:
                logger.debug('Creating directory ' + str(dest) + ' #')
    elif option == 'ch':
        if os.getcwd() == dest:
            pass
        else:
            self.lwd = os.getcwd()  # Save the former working directory in a variable
            try:
                os.chdir(dest)
            except:
                os.makedirs(dest)
                if verbose == True:
                    logger.debug('Creating directory ' + str(dest) + ' #')
                os.chdir(dest)
            self.cwd = os.getcwd()  # Save the current working directory in a variable
            if verbose == True:
                logger.debug('Moved to directory ' + str(dest) + ' #')
    elif option == 'mv':  # Move
        if os.path.exists(dest):
            lib.basher("mv " + str(file) + " " + str(dest))
        else:
            os.mkdir(dest)
            lib.basher("mv " + str(file) + " " + str(dest))
    elif option == 'rn':  # Rename
        lib.basher("mv " + str(file) + " " + str(dest))
    elif option == 'cp':  # Copy
        lib.basher("cp -r " + str(file) + " " + str(dest))
    elif option == 'rm':  # Remove
        lib.basher("rm -r " + str(dest))
    else:
        logger.warning(' Option not supported! Only mk, ch, mv, rm, rn, and cp are supported!')
