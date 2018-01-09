import os

import subs.setinit
from libs import lib


def director(self, option, dest, file=None, verbose=True):
    '''
    director: Function to move, remove, and copy files and directories
    option: 'mk', 'ch', 'mv', 'rm', and 'cp' are supported
    dest: Destination of a file or directory to move to
    file: Which file to move or copy, otherwise None
    '''
    subs.setinit.setinitdirs(self)
    if option == 'mk':
        if os.path.exists(dest):
            pass
        else:
            os.makedirs(dest)
            if verbose == True:
                self.logger.info('# Creating directory ' + str(dest) + ' #')
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
                    self.logger.info('# Creating directory ' + str(dest) + ' #')
                os.chdir(dest)
            self.cwd = os.getcwd()  # Save the current working directory in a variable
            if verbose == True:
                self.logger.info('# Moved to directory ' + str(dest) + ' #')
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
        print('### Option not supported! Only mk, ch, mv, rm, rn, and cp are supported! ###')
