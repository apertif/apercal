import logging
import os
import subprocess
import sys
from ConfigParser import SafeConfigParser

import astropy.io.fits as pyfits
import pylab as pl

deg2rad = pl.pi / 180.


logger = logging.getLogger(__name__)


def qimplot(image=None, rmin=-2, rmax=2, cmap='gray'):
    """
    qimplot: Quick Image Plot
    Plots image in grayscale. Colorscale is from rmin*RMS to rmax*RMS.
    Defaults:
        rmin = -2
        rmax = +2
        cmap = 'gray'
            Can be any of the usual cmap values, e.g. 'YlOrRd' or 'jet'
    """
    logger = logging.getLogger('QIMPLOT')
    logger.info("Quick Image Plot")
    if image is None:
        logger.critical("Please provide input image!")
    pl.figure(figsize=(10, 10))
    fits = miriad('fits')
    if not os.path.exists(image):
        logger.critical(image + " not found!")
        sys.exit(0)
    fits.in_ = image
    fits.out = image + '.fits'
    fits.op = 'xyout'
    fits.go(rmfiles=True)
    imheader = pyfits.open(image + '.fits')
    imdata = imheader[0].data
    rms = pl.rms_flat(imdata[0, 0, :, :])
    logger.info('RMS = ' + "{:2.2}".format(rms))
    logger.info("Plotting from " + str(rmin) + "*RMS to " + str(rmax) + str("*RMS"))
    pl.imshow(pl.flipud(imdata[0, 0, :, :]), cmap=cmap, vmin=rmin * rms, vmax=rmax * rms)
    pl.colorbar()
    pl.xticks(())
    pl.yticks(())


class source:
    def __init__(self, pathtodata=None, ms=None, uvf=None, uv=None, path=None):
        self.pathtodata = pathtodata
        self.ms = ms
        if uvf is None:
            self.uvf = self.ms.upper.replace('.MS', 'UVF')
        else:
            self.uvf = uvf
        self.uv = uv
        if self.path is None:
            self.path = pathtodata
        else:
            self.path = path

    def make_source(self):
        self.ms = (self.pathtodata + '/' + self.ms).replace('//', '/')
        self.uvf = (self.pathtodata + '/' + self.uvf).replace('//', '/')
        self.uv = (self.path + '/' + self.uv).replace('//', '/')


def write2file(header, text2write, file2write):
    """
    write2file writes the output of some task to a textfile.
    """
    f = open(file2write, 'a')
    f.writelines(header)
    f.writelines('\n')
    for t in text2write.split('\n'):
        f.writelines(t + '\n')
    f.writelines('\n---- \n')
    f.close()


def implotter(fname, i=0, ni=3, j=0, nj=3):
    """
    """
    # put some code here


def setup_logger(level='info', logfile=None, quiet=False):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    fh_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s : %(message)s',
                                     datefmt='%m/%d/%Y %I:%M:%S %p')
    if logfile is None:
        fh = logging.FileHandler('log_filename.txt')
    else:
        fh = logging.FileHandler(logfile)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fh_formatter)
    logger.addHandler(fh)

    if not quiet:
        ch_formatter = logging.Formatter('%(name)s - %(levelname)s : %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
        ch = logging.StreamHandler()
        if level == 'info':
            ch.setLevel(logging.INFO)
        if level == 'debug':
            ch.setLevel(logging.DEBUG)
        ch.setFormatter(ch_formatter)
        logger.addHandler(ch)
        logger.info('Logging started!')
        if logfile is not None:
            logger.info('To see the log in a bash window use the following command:')
            logger.info("tail -n +1 -f " + logfile)
    elif logfile is not None:
        print "Logging to file. To see the log in a bash window use the following command:"
        print "tail -n +1 -f " + logfile
    return logger


class FatalMiriadError(Exception):
    """
    Custom  Exception for Fatal MIRIAD Errors
    """

    def __init__(self, error=None):
        if error is None:
            self.message = "Fatal MIRIAD Task Error"
        else:
            self.message = "Fatal MIRIAD Task Error: \n" + error
        super(FatalMiriadError, self).__init__(self.message)
        sys.exit(self.message)


def exceptioner(O, E):
    """
    exceptioner(O, E) where O and E are the stdout outputs and errors.
    A simple and stupid way to do exception handling.
    """
    for e in E:
        if "FATAL" in e.upper() > 0:
            raise FatalMiriadError(E)


def str2bool(s):
    if s.upper() == 'TRUE' or s.upper() == "T" or s.upper() == "Y":
        return True
    elif s.upper() == 'FALSE' or s.upper() == 'F' or s.upper() == 'N':
        return False
    else:
        raise ValueError  # evil ValueError that doesn't tell you what the wrong value was


def mkdir(path):
    """
    mkdir(path)
    Checks if path exists, and creates if it doesn't exist.
    """
    if not os.path.exists(path):
        print path
        print os.path.exists(path)
        print 'Making Path'
        o, e = basher('mkdir ' + path)
        print o, e


def masher(task=None, **kwargs):
    """
    masher - Miriad Task Runner
    Usage: masher(task='sometask', arg1=val1, arg2=val2)
    Example: masher(task='invert', vis='/home/frank/test.uv/', options='mfs,double', ...)
    Each argument is passed to the task through the use of the keywords.
    """
    logger = logging.getLogger('masher')
    if task != None:
        argstr = " "
        for k in kwargs.keys():
            if str(kwargs[k]).upper() != 'NONE':
                if k == 'in_':
                    argstr += 'in=' + str(kwargs[k]) + ' '
                else:
                    k = k
                    argstr += k + '=' + str(kwargs[k]) + ' '
        cmd = task + argstr
        logger.debug(cmd)
        if ("-k" in cmd) is True:
            out = basher(cmd, showasinfo=True)
        else:
            out = basher(cmd, showasinfo=False)
        return out
    else:
        logger.critical("Usage = masher(task='sometask', arg1=val1, arg2=val2...)")
        sys.exit(0)


def basher(cmd, showasinfo=False):
    """
    basher: shell run - helper function to run commands on the shell.
    """
    logger = logging.getLogger('basher')
    logger.debug(cmd)
    # Replacing brackets so that bash won't complain.
    # cmd = cmd.replace('""','"')
    if 'window' or 'uvrange' or 'percentage' in cmd:
        # pos = cmd.find('window')
        # cmdlist = list(cmd)
        # cmdlist.insert(pos, '')
        # cmd = ''.join(cmdlist)
        # br = cmd.find(')')
        # cmdlist = list(cmd)
        # cmdlist.insert(br+1, '')
        # cmd = ''.join(cmdlist)
        # print(cmd)
        pass
    else:
        cmd = cmd.replace("(", "\(")
        cmd = cmd.replace(")", "\)")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, shell=True)
    out, err = proc.communicate()

    if len(out) > 0:
        if showasinfo:
            logger.debug("Command = " + cmd)
            logger.debug("\n" + out)
        else:
            logger.debug("Command = " + cmd)
            logger.debug("\n" + out)
    if len(err) > 0:
        logger.debug(err)
    # NOTE: Returns the STD output.
    exceptioner(out, err)
    logger.debug("Returning output.")
    # Standard output error are returned in a more convenient way
    return out.split('\n')[0:-1]


def get_source_names(vis=None):
    """
    get_source_names (vis=None)
    Helper function that uses the MIRIAD task UVINDEX to grab the name of the
    sources from a MIRIAD visibility file.
    """
    if vis != None:
        u = masher(task='uvindex', vis=vis)
        i = [i for i in range(0, len(u)) if "pointing" in u[i]]
        N = len(u)
        s_raw = u[int(i[0] + 2):N - 2]
        sources = []
        for s in s_raw:
            sources.append(s.replace('  ', ' ').split(' ')[0])
        return sources[0:-1]
    else:
        logger.critical("get_source_names needs a vis!")
        sys.exit(0)


class maths:
    """
    Special MIRIAD type class for the stupid task MATHS, which does not know how to refer to
    directories.
    """

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.task = 'maths'
        self.exp = ''
        self.mask = 'mask'
        self.out = ''

    def __getitem__(self, key):
        return getattr(self, key)

    def keywords(self):
        masher(task=self.task + " -kw")

    def help(self):
        masher(task=self.task + " -k")

    def go(self):
        logger = logging.getLogger(self.task)
        paths = os.path.split(self.exp)
        path0 = os.getcwd()
        if paths[0] != '':
            os.chdir(paths[0])
            self.exp = paths[1]
            self.mask = self.mask.replace(paths[0] + '/', '')
        output = masher(**self.__dict__)
        return output
        # Return to old path
        if paths[0] != '':
            os.chdir(path0)
            # Return the exp and image parameters
            self.exp = paths[0] + '/' + self.exp
            self.mask = paths[0] + '/' + self.image
        logger.debug('Completed.')


class miriad:
    def __init__(self, task, **kwargs):
        """
        DO NOT DEFINE ANY OTHER VARIABLES HERE
        """
        self.__dict__.update(kwargs)
        self.task = task

    def __getitem__(self, key):
        return getattr(self, key)

    def keywords(self):
        masher(task=self.task + " -kw")
        masher(task=self.task + " -w")

    def help(self):
        masher(task=self.task + " -k")

    def rmfiles(self):
        logger = logging.getLogger('miriad ' + self.task)
        logger.debug("Cleanup - files will be DELETED.")
        if self.task == 'invert':
            if os.path.exists(self.map):
                basher("rm -r " + self.map)
            if os.path.exists(self.beam):
                basher("rm -r " + self.beam)
        elif self.task == 'clean':
            if os.path.exists(self.out):
                basher('rm -r ' + self.out)
        elif self.task == 'restor':
            if os.path.exists(self.out):
                basher('rm -r ' + self.out)
        elif self.task == 'maths':
            if os.path.exists(self.out):
                basher('rm -r ' + self.out)
        elif self.task == 'uvlin':
            if os.path.exists(self.out):
                basher('rm -r ' + self.out)
        elif self.task == 'uvcat':
            if os.path.exists(self.out):
                basher('rm -r ' + self.out)
        else:
            if os.path.exists(self.out):
                basher('rm -r ' + self.out)

    def inp(self):
        logger = logging.getLogger('miriad ' + self.task)
        attrs = vars(self)
        logger.info(', '.join("%s=%s" % item for item in attrs.items() if item[0] is not 'logger'))

    def go(self, rmfiles=False):
        logger = logging.getLogger('miriad ' + self.task)
        if rmfiles:
            self.rmfiles()
        output = masher(**self.__dict__)
        #        logger.info('Completed.')
        return output


class Bunch:
    def __init__(self, **kwds):
        self.__dict__.update(kwds)

    def __getitem__(self, key):
        return getattr(self, key)


class settings:
    def __init__(self, filename):
        self.filename = filename
        self.parser = SafeConfigParser()
        self.parser.read(self.filename)

    def set(self, section, *args, **kwds):
        """
        settings.set(section, keyword1=value1, keyword2=value2)
        Change settings using this method.
        """
        parser = self.parser
        if section not in parser.sections():
            parser.add_section(section)
        if not kwds:
            parser.set(section, args[0], args[1])
        else:
            for k in kwds:
                parser.set(section, k, kwds[k])
        self.save()

    def show(self, section=None):
        """
        settings.show(section=None)
        Output the settings, by section if necessary.
        """
        logger = logging.getLogger('settings.show')
        parser = self.parser
        try:
            if section != None:
                print "[" + section + "]"
                for p in parser.items(section):
                    print p[0], " = ", p[1]
                print "\n"
            else:
                for s in parser.sections():
                    print "[" + s + "]"
                    for p in parser.items(s):
                        print p[0], " = ", p[1]
                    print "\n"
        except:
            logger.error("Settings - Section doesn't exist.")

    def get(self, section=None, keyword=None):
        logger = logging.getLogger('settings.get')
        parser = self.parser
        try:
            if section is not None and keyword is not None:
                if len(parser.get(section, keyword).split(';')) > 1:
                    return parser.get(section, keyword).split(';')
                else:
                    return parser.get(section, keyword)
            else:
                return get_params(parser, section)
        except:
            logger.error("Settings - Either section or keyword does not exist.")

    def update(self):
        """
        Read the file again.
        """
        logger = logging.getLogger('settings.update')
        logger.info("Settings - Updated.")
        self.parser.read(self.filename)

    def save(self):
        """
        settings.save()
        Saves the new settings.
        """
        parser = self.parser
        parser.write(open(self.filename, 'w'))

    def full_path(self, dirx):
        """
        Uses rawdata and base to make the full working path, when necessary.
        """
        # full_path = self.get('data', 'working')+self.get('data', 'base')
        full_path = self.get('data', 'working') + dirx
        return full_path


def get_params(config_parser, section):
    params = Bunch()
    for p in config_parser.items(section):
        if len(p[1].split(';')) > 1:
            setattr(params, p[0], p[1].split(';'))
        else:
            setattr(params, p[0], p[1])
    return params


def ms2uvfits(ms=None, uvf=None):
    """
    ms2uvfits(ms=None)
    Utility to convert ms to a uvfits file
    """
    logger = logging.getLogger('ms2uvfits')
    # Setup the path and input file name.
    path2ms = os.path.split(ms)[0]
    ms = os.path.split(ms)[1]
    logger.info("ms2uvfits: Converting MS to UVFITS Format")
    if ms is None:
        logger.error("MS not specified. Please check parameters")
        sys.exit(0)
    if path2ms != '':
        try:
            os.chdir(path2ms)
            logger.info("Moved to path " + path2ms)
        except:
            logger.error("Error: Directory or MS does not exist!")
            sys.exit(0)

    # Start the processing by setting up an output name and reporting the status.
    if uvf is None:
        uvfits = ms.replace(".MS", ".UVF")
    else:
        uvfits = uvf
    if os.path.exists(uvfits):
        logger.error(uvfits + " exists! Skipping this part....")
        logger.info("Exiting gracefully.")
        return
        # TODO: Decided whether to replace logger.info with logger.debug, since this module is
    # wrapped up.
    logger.info("MS: " + ms)
    logger.info("UVFITS: " + uvfits)
    logger.info("Directory: " + path2ms)
    # NOTE: Here I'm using masher to call ms2uvfits.
    o = masher(task='ms2uvfits', ms=ms, fitsfile=uvfits, writesyscal='T',
               multisource='T', combinespw='T')
    logger.info("Appears to have ended successfully.")


def importuvfitsys(uvfits=None, uv=None, tsys=True):
    """
    Imports UVFITS file and does Tsys correction on the output MIRIAD UV file.
    Uses the MIRIAD task WSRTFITS to import the UVFITS file and convert it to MIRIAD UV format.
    Uses the MIRIAD task ATTSYS to do the Tsys correction.
    """
    logger = logging.getLogger('importuvfitsys')
    # NOTE: Import the fits file
    path2uvfits = os.path.split(uvfits)[0]
    uvfits = os.path.split(uvfits)[1]
    if uv is None:
        # Default output name if a custom name isn't provided.
        uv = uvfits.split('.')[0] + '.UV'
    if uvfits is None:
        logger.error("UVFITS not specified. Please check parameters")
        sys.exit(0)
    if path2uvfits != '':
        try:
            os.chdir(path2uvfits)
            logger.info("Moved to path " + path2uvfits)
        except:
            logger.error("Error: Directory does not exist!")
            sys.exit(0)
    # cmd = 'wsrtfits in='+uvf+' op=uvin velocity=optbary out='+uv
    if uvfits.split('.')[1] == 'MS':
        uvfits = uvfits.split('.')[0] + '.UVF'
    if not os.path.exists(uvfits):
        logger.critical(uvfits + " does not exist!")
        sys.exit(0)
    if os.path.exists(uv):
        logger.warn(uv + ' exists! I won\'t clobber. Skipping this part...')
        logger.info("Exiting gracefully.")
        return
    masher(task='wsrtfits', in_=uvfits, out=uv, op='uvin', velocity='optbary')

    # NOTE: Tsys Calibration
    # basher("attsys vis="+uv+" out=temp")
    if tsys is True:
        if os.path.exists('temp'):
            basher("rm -r temp")
        masher(task='attsys', vis=uv, out='temp')
        basher('rm -r ' + uv)
        basher('mv temp ' + uv);
    logger.info('Appears to have ended successfully...')


def uvflag(vis=None, select=None):
    """
    vis: visibility file to be flagged
    select: semi-colon separated list of data selections to be flagged
    """
    # Setup the path and move to it.
    logger = logging.getLogger('uvflag')
    path2vis = os.path.split(vis)[0]
    vis = os.path.split(vis)[1]
    logger.info("uvflag: Flagging Tool")
    if vis is None or select is None:
        logger.error("Vis or Flags not specified. Check parameters.")
        sys.exit(0)
    try:
        os.chdir(path2vis)
        logger.info("Moved to path " + path2vis)
    except:
        logger.error("Error: path to vis does not exist!")
        sys.exit(0)
    # Flag each selection in a for-loop
    for s in select.split(';'):
        o = masher(task='uvflag', vis=vis, select='"' + s + '"', flagval='flag')
        logger.info(o)
    logger.info("Appears to have ended successfully.")


def pgflag(vis=None, flagpar='6,2,2,2,5,3', settings=None, stokes='qq'):
    """
    Wrapper around the MIRIAD task PGFLAG, which in turn is a wrapper for the AOFlagger
    SumThreshold algorithm.
    Defaults:  flagpar='6,2,2,2,5,3',  stokes='qq'
    Uses parameters from a settings object if this is provided.
    Outputs are written to a log file, which is in the same directory as vis, and has name
    <vis>.pgflag.txt.
    Note: The considerably long output of PGFLAG is written out with the logger at debug level.
    This may not be ideal if you're having a quick look, so switch the level to info if you want
    to avoid the output of the task appearing in your console.
    Beware: You could lose a LOT of data if you're not careful!!!
    """
    # Exception handling and checking
    logger = logging.getLogger('pgflag')
    logger.info("PGFLAG: Automated Flagging using SumThresholding")
    if vis is None and settings is None:
        logger.error("No inputs - please provide either vis and flagpar or settings.")
        sys.exit(0)
    path2vis = os.path.split(vis)[0]
    vis = os.path.split(vis)[1]
    try:
        os.chdir(path2vis)
        logger.info("Moved to path " + path2vis)
    except:
        logger.error("Error: path to vis does not exist!")
        sys.exit(0)

    # Do pgflag with the settings parameters if provided.
    if settings is not None and vis is not None:
        params = settings.get('pgflag')
        logger.info("Doing PGFLAG on " + vis + " using stokes=" + params.stokes + " with flagpar=" + params.flagpar)
        logger.info("Output written to " + vis + '.pgflag.txt')
        o = masher(task='pgflag', vis=vis, stokes=params.stokes, flagpar=params.flagpar,
                   options='nodisp', command="'<'")
    # Do PGFLAG with input settings, i.e. no settings file provided.
    if vis is not None and settings is None:
        logger.info("Doing PGFLAG on " + vis + " using stokes " + stokes + " with flagpar=" + flagpar)
        o = masher(task='pgflag', vis=vis, stokes=stokes, flagpar=flagpar, options='nodisp', command="'<'")
    logger.info("Writing output " + path2vis + '/' + vis + '.pgflag.txt')
    write2file('pgflag', o, vis + '.pgflag.txt')
    logger.info("PGFLAG: DONE.")


def query_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = raw_input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")


def director(self, option, dest, file=None, verbose=True):
    """
    director: Function to move, remove, and copy files and directories
    option: 'mk', 'ch', 'mv', 'rm', and 'cp' are supported
    dest: Destination of a file or directory to move to
    file: Which file to move or copy, otherwise None
    """
    if option == 'mk':
        if os.path.exists(dest):
            pass
        else:
            os.mkdir(dest)
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
                os.mkdir(dest)
                if verbose == True:
                    self.logger.info('# Creating directory ' + str(dest) + ' #')
                os.chdir(dest)
            self.cwd = os.getcwd()  # Save the current working directory in a variable
            if verbose == True:
                self.logger.info('# Moved to directory ' + str(dest) + ' #')
    elif option == 'mv':  # Move
        if os.path.exists(dest):
            basher("mv " + str(file) + " " + str(dest))
        else:
            os.mkdir(dest)
            basher("mv " + str(file) + " " + str(dest))
    elif option == 'rn':  # Rename
        basher("mv " + str(file) + " " + str(dest))
    elif option == 'cp':  # Copy
        basher("cp -r " + str(file) + " " + str(dest))
    elif option == 'rm':  # Remove
        basher("rm -r " + str(dest))
    else:
        print('### Option not supported! Only mk, ch, mv, rm, rn, and cp are supported! ###')
