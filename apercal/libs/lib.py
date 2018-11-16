import logging
import os
import subprocess
import sys
from ConfigParser import SafeConfigParser, ConfigParser

import astropy.io.fits as pyfits
import matplotlib.pyplot as plt
import numpy as np
import drivecasa

from apercal.subs import setinit as subs_setinit
from apercal.modules import default_cfg
from apercal.exceptions import ApercalException


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
    plt.figure(figsize=(10, 10))
    fits = miriad('fits')
    if not os.path.exists(image):
        raise ApercalException(image + " not found!")
    fits.in_ = image
    fits.out = image + '.fits'
    fits.op = 'xyout'
    fits.go(rmfiles=True)
    imheader = pyfits.open(image + '.fits')
    imdata = imheader[0].data
    rms = np.sqrt(np.mean(np.abs(imdata[0, 0, :, :]) ** 2))
    logger.info('RMS = ' + "{:2.2}".format(rms))
    logger.info("Plotting from " + str(rmin) + "*RMS to " + str(rmax) + str("*RMS"))
    plt.imshow(np.flipud(imdata[0, 0, :, :]), cmap=cmap, vmin=rmin * rms, vmax=rmax * rms)
    plt.colorbar()
    plt.xticks(())
    plt.yticks(())


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
        if logfile:
            logger.info('To see the log in a bash window use the following command:')
            logger.info("tail -n +1 -f " + logfile)

    elif logfile:
        print("Logging to file. To see the log in a bash window use the following command:")
        print("tail -n +1 -f " + logfile)
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


def exceptioner(O, E):
    """
    exceptioner(O, E) where O and E are the stdout outputs and errors.
    A simple and stupid way to do exception handling.
    """
    for e in E:
        if "FATAL" in e.upper() > 0:
            raise FatalMiriadError(E)


def run_casa(cmd, raise_on_severe=False, log_output=False, timeout=1800):
    """Run a list of casa commands"""
    casa = drivecasa.Casapy()
    try:
        casa_output, casa_error = casa.run_script(cmd, raise_on_severe=True, timeout=timeout)
        if log_output:
            logger.info('\n'.join(casa_output))
        logger.debug('\n'.join(casa_error))
    except RuntimeError:
        logger.error("Casa command failed")
        if raise_on_severe:
            raise


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
        logger.info(path)
        logger.info(os.path.exists(path))
        logger.info('Making Path')
        o, e = basher('mkdir ' + path)
        logger.info(o, e)


def masher(task=None, **kwargs):
    """
    masher - Miriad Task Runner
    Usage: masher(task='sometask', arg1=val1, arg2=val2)
    Example: masher(task='invert', vis='/home/frank/test.uv/', options='mfs,double', ...)
    Each argument is passed to the task through the use of the keywords.
    """
    logger = logging.getLogger('masher')
    if task:
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
        error = "Usage = masher(task='sometask', arg1=val1, arg2=val2...)"
        logger.critical(error)
        raise ApercalException


def strip_prefixes(lines, prefixes):
    """
    Remove lines starting that start with a given string

    Args:
        lines (str): output to be filtered
        prefixes (List[str]): lines to be stripped

    Returns:
        str: Output with filtered lines
    """
    ret = ''
    for line in lines.split('\n'):
        matches = False
        for start in prefixes:
            if line.startswith(start):
                matches = True
                break
        if not matches:
            ret += '\n' + line
    return ret


def basher(cmd, showasinfo=False, prefixes_to_strip=[]):
    """
    basher: shell run - helper function to run commands on the shell.

    Args:
        cmd (str): command to be run
        showasinfo (bool): Log the output to info (default: log to debug)
        remove_ouput (List[str]): do not log lines that start with any of these strings
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
        # logger.info(cmd)
        pass
    else:
        cmd = cmd.replace("(", "\\(")
        cmd = cmd.replace(")", "\\)")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, shell=True)
    out, err = proc.communicate()

    if len(out) > 0:
        if showasinfo:
            logger.debug("Command = " + cmd)
            logger.debug(strip_prefixes(out, prefixes_to_strip))
        else:
            logger.debug("Command = " + cmd)
            logger.debug(strip_prefixes(out, prefixes_to_strip))
    if len(err) > 0:
        logger.debug(err)
    # NOTE: Returns the STD output.
    exceptioner(out, err)
    if proc.returncode != 0:
        raise RuntimeError()
    logger.debug("Returning output.")
    # Standard output error are returned in a more convenient way
    return out.split('\n')[0:-1]


def get_source_names(vis=None):
    """
    get_source_names (vis=None)
    Helper function that uses the MIRIAD task UVINDEX to grab the name of the
    sources from a MIRIAD visibility file.
    """
    if vis:
        u = masher(task='uvindex', vis=vis)
        i = [i for i in range(0, len(u)) if "pointing" in u[i]]
        N = len(u)
        s_raw = u[int(i[0] + 2):N - 2]
        sources = []
        for s in s_raw:
            sources.append(s.replace('  ', ' ').split(' ')[0])
        return sources[0:-1]
    else:
        raise ApercalException("get_source_names needs a vis!")


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
        paths = os.path.split(self.exp)
        if paths[0] != '':
            os.chdir(paths[0])
            self.exp = paths[1]
            self.mask = self.mask.replace(paths[0] + '/', '')
        output = masher(**self.__dict__)
        return output


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
            if section:
                logger.info("[" + section + "]")
                for p in parser.items(section):
                    logger.info(p[0], " = ", p[1])
                logger.info("\n")
            else:
                for s in parser.sections():
                    logger.info("[" + s + "]")
                    for p in parser.items(s):
                        logger.info(p[0], " = ", p[1])
                    logger.info("\n")
        except Exception:
            logger.error("Settings - Section doesn't exist.")

    def get(self, section=None, keyword=None):
        logger = logging.getLogger('settings.get')
        parser = self.parser
        try:
            if section and keyword:
                if len(parser.get(section, keyword).split(';')) > 1:
                    return parser.get(section, keyword).split(';')
                else:
                    return parser.get(section, keyword)
            else:
                return get_params(parser, section)
        except Exception:
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
        raise ApercalException("MS not specified. Please check parameters")
    if path2ms != '':
        try:
            os.chdir(path2ms)
            logger.info("Moved to path " + path2ms)
        except Exception:
            raise ApercalException("Directory or MS does not exist!")

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
        raise ApercalException("UVFITS not specified. Please check parameters")

    if path2uvfits != '':
        try:
            os.chdir(path2uvfits)
            logger.info("Moved to path " + path2uvfits)
        except Exception:
            raise ApercalException("Error: Directory does not exist!")

    # cmd = 'wsrtfits in='+uvf+' op=uvin velocity=optbary out='+uv
    if uvfits.split('.')[1] == 'MS':
        uvfits = uvfits.split('.')[0] + '.UVF'
    if not os.path.exists(uvfits):
        raise ApercalException(uvfits + " does not exist!")
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
        basher('mv temp ' + uv)
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
        raise ApercalException("Vis or Flags not specified. Check parameters.")
    try:
        os.chdir(path2vis)
        logger.info("Moved to path " + path2vis)
    except Exception:
        raise ApercalException("Path to vis does not exist!")
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
        raise ApercalException("No inputs - please provide either vis and flagpar or settings.")
    path2vis = os.path.split(vis)[0]
    vis = os.path.split(vis)[1]
    try:
        os.chdir(path2vis)
        logger.info("Moved to path " + path2vis)
    except Exception:
        raise ApercalException("Error: path to vis does not exist!")

    o = None

    # Do pgflag with the settings parameters if provided.
    if settings and vis:
        params = settings.get('pgflag')
        logger.info("Doing PGFLAG on " + vis + " using stokes=" + params.stokes + " with flagpar=" + params.flagpar)
        logger.info("Output written to " + vis + '.pgflag.txt')
        o = masher(task='pgflag', vis=vis, stokes=params.stokes, flagpar=params.flagpar,
                   options='nodisp', command="'<'")
    # Do PGFLAG with input settings, i.e. no settings file provided.
    if vis and settings is None:
        logger.info("Doing PGFLAG on " + vis + " using stokes " + stokes + " with flagpar=" + flagpar)
        o = masher(task='pgflag', vis=vis, stokes=stokes, flagpar=flagpar, options='nodisp', command="'<'")

    if o:
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
        if default and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")


def director(self, option, dest, file_=None, verbose=True):
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
            if verbose:
                self.logger.info('Creating directory ' + str(dest))
    elif option == 'ch':
        if os.getcwd() == dest:
            pass
        else:
            self.lwd = os.getcwd()  # Save the former working directory in a variable
            try:
                os.chdir(dest)
            except Exception:
                os.mkdir(dest)
                if verbose:
                    self.logger.info('Creating directory ' + str(dest))
                os.chdir(dest)
            self.cwd = os.getcwd()  # Save the current working directory in a variable
            if verbose:
                self.logger.info('Moved to directory ' + str(dest))
    elif option == 'mv':  # Move
        if os.path.exists(dest):
            basher("mv " + str(file_) + " " + str(dest))
        else:
            os.mkdir(dest)
            basher("mv " + str(file_) + " " + str(dest))
    elif option == 'rn':  # Rename
        basher("mv " + str(file_) + " " + str(dest))
    elif option == 'cp':  # Copy
        basher("cp -r " + str(file_) + " " + str(dest))
    elif option == 'rm':  # Remove
        basher("rm -r " + str(dest))
    else:
        logger.info(' Option not supported! Only mk, ch, mv, rm, rn, and cp are supported!')


def show(config_object, section, showall=False):
    """
    show: Prints the current settings of the pipeline. Only shows keywords, which are in the default config file
            default.cfg
    showall: Set to true if you want to see all current settings instead of only the ones from the current step
    """
    subs_setinit.setinitdirs(config_object)
    config = ConfigParser()
    config.readfp(open(default_cfg))
    for s in config.sections():
        if showall:
            logger.info(s)
            o = config.options(s)
            for o in config.items(s):
                try:
                    logger.info('\t' + str(o[0]) + ' = ' + str(config_object.__dict__.__getitem__(o[0])))
                except KeyError:
                    pass
        else:
            if s == section:
                logger.info(s)
                o = config.options(s)
                for o in config.items(s):
                    try:
                        logger.info('\t' + str(o[0]) + ' = ' + str(config_object.__dict__.__getitem__(o[0])))
                    except KeyError:
                        pass
            else:
                pass


def load_config(config_object, file_=None):
    logger = logging.getLogger('config')
    config = ConfigParser()  # Initialise the config parser
    if file_:
        config.readfp(open(file_))
        logger.info(' Configuration file ' + file_ + ' successfully read!')
    else:
        config.readfp(open(default_cfg))
        logger.info(' No configuration file given or file not found, using default values.')

    for s in config.sections():

        for o in config.items(s):
            setattr(config_object, o[0], eval(o[1]))
    return config  # Save the loaded config file as defaults for later usage
