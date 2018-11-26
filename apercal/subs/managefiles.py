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


def director(self, option, dest, file_=None, verbose=True,
             ignore_nonexistent=False):
    """
    director: Function to move, remove, and copy file_s and directories
    option: 'mk', 'ch', 'mv', 'rm', and 'cp' are supported
    dest: Destination of a file or directory to move to
    file_: Which file to move or copy, otherwise None
    ignore_nonexistent: ignore rm on existing files
    """
    subs_setinit.setinitdirs(self)
    if option == 'mk':
        if os.path.exists(dest):
            pass
        else:
            os.makedirs(dest)
            if verbose:
                logger.debug('Creating directory ' + str(dest) + ' #')
    elif option == 'ch':
        if os.getcwd() == dest:
            pass
        else:
            self.lwd = os.getcwd()  # Save the former working directory in a variable
            try:
                os.chdir(dest)
            except Exception:
                os.makedirs(dest)
                if verbose:
                    logger.debug('Creating directory ' + str(dest) + ' #')
                os.chdir(dest)
            self.cwd = os.getcwd()  # Save the current working directory in a variable
            if verbose:
                logger.debug('Moved to directory ' + str(dest) + ' #')
    elif option == 'mv':  # Move
        if os.path.exists(dest):
            lib.basher("mv " + str(file_) + " " + str(dest))
        else:
            os.mkdir(dest)
            lib.basher("mv " + str(file_) + " " + str(dest))
    elif option == 'rn':  # Rename
        lib.basher("mv " + str(file_) + " " + str(dest))
    elif option == 'cp':  # Copy
        lib.basher("cp -r " + str(file_) + " " + str(dest))
    elif option == 'rm':  # Remove
        if ignore_nonexistent and not os.path.exists(str(dest)):
            return
        lib.basher("rm -r " + str(dest))
    else:
        logger.warning(' Option not supported! Only mk, ch, mv, rm, rn, and cp are supported!')
