import os, sys
import logging
import lib
import ConfigParser
import casat

class preflag:
    def __init__(self, file=None, **kwargs):
        self.logger = logging.getLogger('preflag')
        config = ConfigParser.ConfigParser()  # Initialise the config parser
        if file != None:
            config.readfp(open(file))
            self.logger.info('### Configuration file ' + file + ' successfully read! ###')
        else:
            config.readfp(open(os.path.realpath(__file__).rstrip('calibrate.pyc') + 'default.cfg'))
            self.logger.info('### No configuration file given or file not found! Using default values for selfcal! ###')
        for s in config.sections():
            for o in config.items(s):
                setattr(self, o[0], eval(o[1]))

        # Create the directory names
        self.rawdir = self.basedir + self.rawsubdir

    def aoflagger(self):
        '''
        Runs aoflagger on the datasets with the strategies given in the config-file. Strategies for calibrators and target fields normally differ.
        '''
        if self.aoflagger:
            self.logger.info('### Doing pre-flagging with AOFlagger ###')
            if self.aoflagger_fluxcal:
                os.system('aoflagger -strategy ' + self.apercaldir + '/ao_strategies/' + self.aoflagger_fluxcalstrat + ' ' + self.fluxcal)
                self.logger.info('### Flagging of ' + self.fluxcal + ' using ' + self.aoflagger_fluxcalstrat + ' done ###')
            if self.aoflagger_polcal:
                os.system('aoflagger -strategy ' + self.apercaldir + '/ao_strategies/' + self.aoflagger_polcalstrat + ' ' + self.polcal)
                self.logger.info('### Flagging of ' + self.polcal + ' using ' + self.aoflagger_polcalstrat + ' done ###')
            if self.aoflagger_target:
                os.system('aoflagger -strategy ' + self.apercaldir + '/ao_strategies/' + self.aoflagger_targetstrat + ' ' + self.target)
                self.logger.info('### Flagging of ' + self.target + ' using ' + self.aoflagger_targetstrat + ' done ###')
        else:
            self.logger.warning('### No flagging with AOflagger done! Your data might be contaminated by RFI! ###')

    def manual_flag(self):
        '''
        Runs the CASA flagdata task to flag entire antennas, baselines, correlations etc. before doing any other calibration. Mostly used for commissioning where we know that telescopes are not working or correlations are absent.
        '''
        self.logger.info('### Starting pre-flagging of known flags ###')
        self.logger.info('### Pre-flagging of known flags done ###')

    def go(self):
        '''
        Executes the complete preflag step with the parameters indicated in the config-file
        '''
        self.logger.info('########## PRE-FLAGGING started ##########')
        self.director('ch', self.rawdir)
        self.aoflagger()
        self.manual_flag()
        self.logger.info('########## PRE-FLAGGING done ##########')

    ############################################################
    ##### Subfunctions for the different manual_flag steps #####
    ############################################################



    #######################################################################
    ##### Manage the creation and moving of new directories and files #####
    #######################################################################

    def show(self):
        '''
        Prints the current settings of the pipeline. Only shows keywords, which are in the default config file default.cfg
        '''
        config = ConfigParser.ConfigParser()
        config.readfp(open(self.apercaldir + '/default.cfg'))
        for s in config.sections():
            print(s)
            o = config.options(s)
            for o in config.items(s):
                print('\t' + str(o[0]) + ' = ' + str(self.__dict__.__getitem__(o[0])))


    def director(self, option, dest, file=None, verbose=True):
        '''
        director: Function to move, remove, and copy files and directories
        option: 'mk', 'ch', 'mv', 'rm', and 'cp' are supported
        dest: Destination of a file or directory to move to
        file: Which file to move or copy, otherwise None
        '''
        if option == 'mk':
            if os.path.exists(dest):
                pass
            else:
                os.mkdir(dest)
                if verbose == True:
                    self.logger.info('# Creating directory ' + str(dest) + ' #')
        elif option == 'ch':
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
            print('### Option not supported! Only mk, ch, mv, rm, and cp are supported! ###')