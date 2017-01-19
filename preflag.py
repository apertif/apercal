import os
import logging
import lib
import ConfigParser
import casac

class preflag:
    def __init__(self, file=None, **kwargs):
        self.logger = logging.getLogger('PREFLAG')
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
        if self.preflag_aoflagger:
            self.director('ch', self.rawdir)
            self.logger.info('### Doing pre-flagging with AOFlagger ###')
            if self.preflag_aoflagger_fluxcal:
                os.system('aoflagger -strategy ' + self.apercaldir + '/ao_strategies/' + self.preflag_aoflagger_fluxcalstrat + ' ' + self.fluxcal)
                self.logger.info('### Flagging of ' + self.fluxcal + ' using ' + self.preflag_aoflagger_fluxcalstrat + ' done ###')
            if self.preflag_aoflagger_polcal:
                os.system('aoflagger -strategy ' + self.apercaldir + '/ao_strategies/' + self.preflag_aoflagger_polcalstrat + ' ' + self.polcal)
                self.logger.info('### Flagging of ' + self.polcal + ' using ' + self.preflag_aoflagger_polcalstrat + ' done ###')
            if self.preflag_aoflagger_target:
                os.system('aoflagger -strategy ' + self.apercaldir + '/ao_strategies/' + self.preflag_aoflagger_targetstrat + ' ' + self.target)
                self.logger.info('### Flagging of ' + self.target + ' using ' + self.preflag_aoflagger_targetstrat + ' done ###')
        else:
            self.logger.warning('### No flagging with AOflagger done! Your data might be contaminated by RFI! ###')

    def manualflag(self):
        '''
        Uses the CASA toolbox to flag entire antennas, baselines, correlations etc. before doing any other calibration. Mostly used for commissioning where we know that telescopes are not working or correlations are absent.
        '''
        self.logger.info('### Starting pre-flagging of known flags ###')
        if self.preflag_manualflag:
            self.manualflag_auto()
            self.manualflag_antenna()
            self.manualflag_corr()
            self.manualflag_shadow()
            self.manualflag_baseline()
        self.logger.info('### Pre-flagging of known flags done ###')

    def go(self):
        '''
        Executes the complete preflag step with the parameters indicated in the config-file.
        '''
        self.logger.info('########## PRE-FLAGGING started ##########')
        self.aoflagger()
        self.manualflag()
        self.logger.info('########## PRE-FLAGGING done ##########')

    ############################################################
    ##### Subfunctions for the different manual_flag steps #####
    ############################################################

    def manualflag_auto(self):
        '''
        Function to flag the auto-correlations
        '''
        if self.preflag_manualflag_auto:
            self.director('ch', self.rawdir)
            af = casac.casac.agentflagger()
            if self.preflag_manualflag_fluxcal:
                self.logger.info('# Flagging auto-correlations for flux calibrator data #')
                af.open(self.fluxcal)
                af.selectdata()
                af.parsemanualparameters(autocorr=True)
                af.init()
                af.run(writeflags=True)
                af.done()
                self.logger.info('# Auto-correlation flagging for flux calibrator data done #')
            if self.preflag_manualflag_polcal:
                self.logger.info('# Flagging auto-correlations for polarisation calibrator data #')
                af.open(self.polcal)
                af.selectdata()
                af.parsemanualparameters(autocorr=True)
                af.init()
                af.run(writeflags=True)
                af.done()
                self.logger.info('# Auto-correlation flagging for polarisation calibrator data done #')
            if self.preflag_manualflag_target:
                self.logger.info('# Flagging auto-correlations for target data #')
                af.open(self.target)
                af.selectdata()
                af.parsemanualparameters(autocorr=True)
                af.init()
                af.run(writeflags=True)
                af.done()
                self.logger.info('# Auto-correlation flagging for target data done #')

    def manualflag_antenna(self):
        '''
        Function to flag complete antennas
        '''
        if self.preflag_manualflag_antenna != '':
            self.director('ch', self.rawdir)
            af = casac.casac.agentflagger()
            if self.preflag_manualflag_fluxcal:
                self.logger.info('# Flagging antenna(s) ' + self.preflag_manualflag_antenna + ' for flux calibrator data #')
                af.open(self.fluxcal)
                af.selectdata()
                for ant in self.preflag_manualflag_antenna.split(','):
                    af.parsemanualparameters(antenna=str(ant) + '&&' + str(ant))
                af.parsemanualparameters(antenna=self.preflag_manualflag_antenna)
                af.init()
                af.run(writeflags=True)
                af.done()
                self.logger.info('# Flagging of antenna(s) ' + self.preflag_manualflag_antenna + ' for flux calibrator data done #')
            if self.preflag_manualflag_polcal:
                self.logger.info('# Flagging antenna(s) ' + self.preflag_manualflag_antenna + ' for polarised calibrator data #')
                af.open(self.polcal)
                af.selectdata()
                for ant in self.preflag_manualflag_antennas.split(','):
                    af.parsemanualparameters(antenna=str(ant) + '&&' + str(ant))
                af.parsemanualparameters(antenna=str(self.preflag_manualflag_antenna))
                af.init()
                af.run(writeflags=True)
                af.done()
                self.logger.info('# Flagging of antenna(s) ' + self.preflag_manualflag_antenna + ' for polariased calibrator data done #')
            if self.preflag_manualflag_target:
                self.logger.info('# Flagging antenna(s) ' + self.preflag_manualflag_antenna + ' for target data #')
                af.open(self.target)
                af.selectdata()
                for ant in self.preflag_manualflag_antenna.split(','):
                    af.parsemanualparameters(antenna=str(ant) + '&&' + str(ant))
                af.parsemanualparameters(antenna=str(self.preflag_manualflag_antenna))
                af.init()
                af.run(writeflags=True)
                af.done()
                self.logger.info('# Flagging of antenna(s) ' + self.preflag_manualflag_antenna + ' for target data done #')

    def manualflag_corr(self):
        '''
        Function to flag whole correlations
        '''
        if self.preflag_manualflag_corr != '':
            self.director('ch', self.rawdir)
            af = casac.casac.agentflagger()
            if self.preflag_manualflag_fluxcal:
                self.logger.info('# Flagging correlation(s) ' + self.preflag_manualflag_corr + ' for flux calibrator data #')
                af.open(self.fluxcal)
                af.selectdata()
                af.parsemanualparameters(antenna=self.preflag_manualflag_corr)
                af.init()
                af.run(writeflags=True)
                af.done()
                self.logger.info('# Flagging of correlation(s) ' + self.preflag_manualflag_corr + ' for flux calibrator data done #')
            if self.preflag_manualflag_polcal:
                self.logger.info('# Flagging correlation(s) ' + self.preflag_manualflag_corr + ' for polarised calibrator data #')
                af.open(self.polcal)
                af.selectdata()
                af.parsemanualparameters(antenna=self.preflag_manualflag_corr)
                af.init()
                af.run(writeflags=True)
                af.done()
                self.logger.info('# Flagging of correlation(s) ' + self.preflag_manualflag_corr + ' for polarised calibrator data done #')
            if self.preflag_manualflag_target:
                self.logger.info('# Flagging correlation(s) ' + self.preflag_manualflag_corr + ' for target data #')
                af.open(self.target)
                af.selectdata()
                af.parsemanualparameters(antenna=self.preflag_manualflag_corr)
                af.init()
                af.run(writeflags=True)
                af.done()
                self.logger.info('# Flagging of correlation(s) ' + self.preflag_manualflag_corr + ' for target data done #')

    def manualflag_shadow(self):
        '''
        Function to flag shadowing of antennas
        '''
        if self.preflag_manualflag_shadow:
            self.director('ch', self.rawdir)
            af = casac.casac.agentflagger()
            if self.preflag_manualflag_fluxcal:
                self.logger.info('# Flagging shadowed antennas for flux calibrator data #')
                af.open(self.fluxcal)
                af.selectdata()
                shadowagent = {}
                shadowagent['mode'] = 'shadow'
                af.parseagentparameters(shadowagent)
                af.init()
                af.run(writeflags=True)
                af.done()
                self.logger.info('# Flagging of shadowed antennas for flux calibrator data done #')
            if self.preflag_manualflag_polcal:
                self.logger.info('# Flagging shadowed antennas for polarised calibrator data #')
                af.open(self.polcal)
                af.selectdata()
                shadowagent = {}
                shadowagent['mode'] = 'shadow'
                af.parseagentparameters(shadowagent)
                af.init()
                af.run(writeflags=True)
                af.done()
                self.logger.info('# Flagging of shadowed antennas for polarised calibrator data done #')
            if self.preflag_manualflag_target:
                self.logger.info('# Flagging of shadowed antennas for target data #')
                af.open(self.target)
                af.selectdata()
                shadowagent = {}
                shadowagent['mode'] = 'shadow'
                af.parseagentparameters(shadowagent)
                af.init()
                af.run(writeflags=True)
                af.done()
                self.logger.info('# Flagging of shadowed antennas for target data done #')

    def manualflag_baseline(self):
        '''
        Function to flag individual baselines
        '''
        if self.preflag_manualflag_baseline != '':
            self.director('ch', self.rawdir)
            af = casac.casac.agentflagger()
            if self.preflag_manualflag_fluxcal:
                self.logger.info('# Flagging baseline(s) ' + self.preflag_manualflag_baseline + ' for flux calibrator data #')
                af.open(self.fluxcal)
                af.selectdata()
                for baseline in self.preflag_manualflag_baseline.split(','):
                    af.parsemanualparameters(antenna=baseline)
                af.init()
                af.run(writeflags=True)
                af.done()
                self.logger.info('# Flagging of baseline(s) ' + self.preflag_manualflag_baseline + ' for flux calibrator data done #')
            if self.preflag_manualflag_polcal:
                self.logger.info('# Flagging baseline(s) ' + self.preflag_manualflag_baseline + ' for polarised calibrator data #')
                af.open(self.polcal)
                af.selectdata()
                for baseline in self.preflag_manualflag_baseline.split(','):
                    af.parsemanualparameters(antenna=baseline)
                af.init()
                af.run(writeflags=True)
                af.done()
                self.logger.info('# Flagging of baseline(s) ' + self.preflag_manualflag_baseline + ' for polariased calibrator data done #')
            if self.preflag_manualflag_target:
                self.logger.info('# Flagging baseline(s) ' + self.preflag_manualflag_baseline + ' for target data #')
                af.open(self.target)
                af.selectdata()
                for baseline in self.preflag_manualflag_baseline.split(','):
                    af.parsemanualparameters(antenna=baseline)
                af.init()
                af.run(writeflags=True)
                af.done()
                self.logger.info('# Flagging of baseline(s) ' + self.preflag_manualflag_baseline + ' for target data done #')


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