import ConfigParser
import glob
import logging

import casac
import os

import subs.setinit
from libs import lib

casalog = casac.casac.logsink()
casalog.setglobal(False)

class preflag:
    '''
    Preflagging class. Used to automatically flag data and apply preknown flags.
    '''
    def __init__(self, file=None, **kwargs):
        logging.basicConfig(level=20)
        self.logger = logging.getLogger('PREFLAG')
        config = ConfigParser.ConfigParser()  # Initialise the config parser
        if file != None:
            config.readfp(open(file))
            # self.logger.info('### Configuration file ' + file + ' successfully read! ###')
        else:
            config.readfp(open(os.path.realpath(__file__).rstrip('preflag.pyc') + 'default.cfg'))
            # self.logger.info('### No configuration file given or file not found! Using default values! ###')
        for s in config.sections():
            for o in config.items(s):
                setattr(self, o[0], eval(o[1]))
        subs.setinit.setinitdirs(self)

    def manualflag(self):
        '''
        Uses the CASA toolbox to flag entire antennas, baselines, correlations etc. before doing any other calibration. Mostly used for commissioning where we know that telescopes are not working or correlations are absent.
        '''
        # self.logger.info('### Starting pre-flagging of known flags ###')
        if self.preflag_manualflag:
            self.manualflag_auto()
            self.manualflag_antenna()
            self.manualflag_corr()
            self.manualflag_shadow()
            self.manualflag_baseline()
            self.manualflag_channel()
            self.manualflag_time()
        # self.logger.info('### Pre-flagging of known flags done ###')

    def aoflagger(self):
        '''
        Runs aoflagger on the datasets with the strategies given in the config-file. Creates and applies a preliminary bandpass before executing the strategy for better performance of the flagging routines. Strategies for calibrators and target fields normally differ.
        '''
        if self.preflag_aoflagger:
            subs.setinit.setinitdirs(self)
            # self.logger.info('### Doing pre-flagging with AOFlagger ###')
            self.aoflagger_bandpass()
            self.aoflagger_flag()
            # self.logger.info('### Pre-flagging with AOFlagger done! ###')
        else:
            pass
            # self.logger.warning('### No flagging with AOflagger done! Your data might be contaminated by RFI! ###')

    def go(self):
        '''
        Executes the complete preflag step with the parameters indicated in the config-file in the following order:
        manualflag
        aoflagger
        '''
        # self.logger.info('########## PRE-FLAGGING started ##########')
        self.manualflag()
        self.aoflagger()
        # self.logger.info('########## PRE-FLAGGING done ##########')

    ############################################################
    ##### Subfunctions for the different manual_flag steps #####
    ############################################################

    def manualflag_auto(self):
        '''
        Function to flag the auto-correlations
        '''
        if self.preflag_manualflag_auto:
            subs.setinit.setinitdirs(self)
            self.director('ch', self.rawdir, verbose=False)
            af = casac.casac.agentflagger()
            if self.preflag_manualflag_fluxcal:
                # self.logger.info('# Flagging auto-correlations for flux calibrator data #')
                af.open(self.fluxcal)
                af.selectdata()
                af.parsemanualparameters(autocorr=True)
                af.init()
                af.run(writeflags=True)
                af.done()
                # self.logger.info('# Auto-correlation flagging for flux calibrator data done #')
            if self.preflag_manualflag_polcal:
                # self.logger.info('# Flagging auto-correlations for polarisation calibrator data #')
                af.open(self.polcal)
                af.selectdata()
                af.parsemanualparameters(autocorr=True)
                af.init()
                af.run(writeflags=True)
                af.done()
                # self.logger.info('# Auto-correlation flagging for polarisation calibrator data done #')
            if self.preflag_manualflag_target:
                # self.logger.info('# Flagging auto-correlations for target data set(s) #')
                mslist = glob.glob(self.basedir + '*/' + self.rawsubdir + '/' + self.target)
                for ms in mslist:
                    af.open(ms)
                    af.selectdata()
                    af.parsemanualparameters(autocorr=True)
                    af.init()
                    af.run(writeflags=True)
                    af.done()
                # self.logger.info('# Auto-correlation flagging for target data set(s) done #')

    def manualflag_antenna(self):
        '''
        Function to flag complete antennas
        '''
        if self.preflag_manualflag_antenna != '':
            subs.setinit.setinitdirs(self)
            self.director('ch', self.rawdir)
            af = casac.casac.agentflagger()
            if self.preflag_manualflag_fluxcal:
                # self.logger.info('# Flagging antenna(s) ' + self.preflag_manualflag_antenna + ' for flux calibrator data #')
                af.open(self.fluxcal)
                af.selectdata()
                for ant in self.preflag_manualflag_antenna.split(','):
                    af.parsemanualparameters(antenna=str(ant) + '&&' + str(ant))
                af.parsemanualparameters(antenna=self.preflag_manualflag_antenna)
                af.init()
                af.run(writeflags=True)
                af.done()
                # self.logger.info('# Flagging of antenna(s) ' + self.preflag_manualflag_antenna + ' for flux calibrator data done #')
            if self.preflag_manualflag_polcal:
                # self.logger.info('# Flagging antenna(s) ' + self.preflag_manualflag_antenna + ' for polarised calibrator data #')
                af.open(self.polcal)
                af.selectdata()
                for ant in self.preflag_manualflag_antenna.split(','):
                    af.parsemanualparameters(antenna=str(ant) + '&&' + str(ant))
                af.parsemanualparameters(antenna=str(self.preflag_manualflag_antenna))
                af.init()
                af.run(writeflags=True)
                af.done()
                # self.logger.info('# Flagging of antenna(s) ' + self.preflag_manualflag_antenna + ' for polariased calibrator data done #')
            if self.preflag_manualflag_target:
                # self.logger.info('# Flagging antenna(s) ' + self.preflag_manualflag_antenna + ' for target data set(s) #')
                mslist = glob.glob(self.basedir + '*/' + self.rawsubdir + '/' + self.target)
                for ms in mslist:
                    af.open(ms)
                    af.selectdata()
                    for ant in self.preflag_manualflag_antenna.split(','):
                        af.parsemanualparameters(antenna=str(ant) + '&&' + str(ant))
                    af.parsemanualparameters(antenna=str(self.preflag_manualflag_antenna))
                    af.init()
                    af.run(writeflags=True)
                    af.done()
                # self.logger.info('# Flagging of antenna(s) ' + self.preflag_manualflag_antenna + ' for target data set(s) done #')

    def manualflag_corr(self):
        '''
        Function to flag whole correlations
        '''
        if self.preflag_manualflag_corr != '':
            subs.setinit.setinitdirs(self)
            self.director('ch', self.rawdir)
            af = casac.casac.agentflagger()
            if self.preflag_manualflag_fluxcal:
                # self.logger.info('# Flagging correlation(s) ' + self.preflag_manualflag_corr + ' for flux calibrator data #')
                af.open(self.fluxcal)
                af.selectdata()
                af.parsemanualparameters(correlation=self.preflag_manualflag_corr)
                af.init()
                af.run(writeflags=True)
                af.done()
                # self.logger.info('# Flagging of correlation(s) ' + self.preflag_manualflag_corr + ' for flux calibrator data done #')
            if self.preflag_manualflag_polcal:
                # self.logger.info('# Flagging correlation(s) ' + self.preflag_manualflag_corr + ' for polarised calibrator data #')
                af.open(self.polcal)
                af.selectdata()
                af.parsemanualparameters(correlation=self.preflag_manualflag_corr)
                af.init()
                af.run(writeflags=True)
                af.done()
                # self.logger.info('# Flagging of correlation(s) ' + self.preflag_manualflag_corr + ' for polarised calibrator data done #')
            if self.preflag_manualflag_target:
                # self.logger.info('# Flagging correlation(s) ' + self.preflag_manualflag_corr + ' for target data set(s) #')
                mslist = glob.glob(self.basedir + '*/' + self.rawsubdir + '/' + self.target)
                for ms in mslist:
                    af.open(ms)
                    af.selectdata()
                    af.parsemanualparameters(correlation=self.preflag_manualflag_corr)
                    af.init()
                    af.run(writeflags=True)
                    af.done()
                # self.logger.info('# Flagging of correlation(s) ' + self.preflag_manualflag_corr + ' for target data set(s) done #')

    def manualflag_shadow(self):
        '''
        Function to flag shadowing of antennas
        '''
        if self.preflag_manualflag_shadow:
            subs.setinit.setinitdirs(self)
            self.director('ch', self.rawdir)
            af = casac.casac.agentflagger()
            if self.preflag_manualflag_fluxcal:
                # self.logger.info('# Flagging shadowed antennas for flux calibrator data #')
                af.open(self.fluxcal)
                af.selectdata()
                shadowagent = {}
                shadowagent['mode'] = 'shadow'
                af.parseagentparameters(shadowagent)
                af.init()
                af.run(writeflags=True)
                af.done()
                # self.logger.info('# Flagging of shadowed antennas for flux calibrator data done #')
            if self.preflag_manualflag_polcal:
                # self.logger.info('# Flagging shadowed antennas for polarised calibrator data #')
                af.open(self.polcal)
                af.selectdata()
                shadowagent = {}
                shadowagent['mode'] = 'shadow'
                af.parseagentparameters(shadowagent)
                af.init()
                af.run(writeflags=True)
                af.done()
                # self.logger.info('# Flagging of shadowed antennas for polarised calibrator data done #')
            if self.preflag_manualflag_target:
                # self.logger.info('# Flagging of shadowed antennas for target data set(s) #')
                mslist = glob.glob(self.basedir + '*/' + self.rawsubdir + '/' + self.target)
                for ms in mslist:
                    af.open(ms)
                    af.selectdata()
                    shadowagent = {}
                    shadowagent['mode'] = 'shadow'
                    af.parseagentparameters(shadowagent)
                    af.init()
                    af.run(writeflags=True)
                    af.done()
                # self.logger.info('# Flagging of shadowed antennas for target data set(s) done #')

    def manualflag_baseline(self):
        '''
        Function to flag individual baselines
        '''
        if self.preflag_manualflag_baseline != '':
            subs.setinit.setinitdirs(self)
            self.director('ch', self.rawdir)
            af = casac.casac.agentflagger()
            if self.preflag_manualflag_fluxcal:
                # self.logger.info('# Flagging baseline(s) ' + self.preflag_manualflag_baseline + ' for flux calibrator data #')
                af.open(self.fluxcal)
                af.selectdata()
                for baseline in self.preflag_manualflag_baseline.split(','):
                    af.parsemanualparameters(antenna=baseline)
                af.init()
                af.run(writeflags=True)
                af.done()
                # self.logger.info('# Flagging of baseline(s) ' + self.preflag_manualflag_baseline + ' for flux calibrator data done #')
            if self.preflag_manualflag_polcal:
                # self.logger.info('# Flagging baseline(s) ' + self.preflag_manualflag_baseline + ' for polarised calibrator data #')
                af.open(self.polcal)
                af.selectdata()
                for baseline in self.preflag_manualflag_baseline.split(','):
                    af.parsemanualparameters(antenna=baseline)
                af.init()
                af.run(writeflags=True)
                af.done()
                # self.logger.info('# Flagging of baseline(s) ' + self.preflag_manualflag_baseline + ' for polariased calibrator data done #')
            if self.preflag_manualflag_target:
                # self.logger.info('# Flagging baseline(s) ' + self.preflag_manualflag_baseline + ' for target data set(s) #')
                mslist = glob.glob(self.basedir + '*/' + self.rawsubdir + '/' + self.target)
                for dataset in mslist:
                    af.open(dataset)
                    af.selectdata()
                    for baseline in self.preflag_manualflag_baseline.split(','):
                        af.parsemanualparameters(antenna=baseline)
                    af.init()
                    af.run(writeflags=True)
                    af.done()
                # self.logger.info('# Flagging of baseline(s) ' + self.preflag_manualflag_baseline + ' for target data set(s) done #')

    def manualflag_channel(self):
        '''
        Function to flag individual channels
        '''
        if self.preflag_manualflag_channel != '':
            subs.setinit.setinitdirs(self)
            self.director('ch', self.rawdir)
            af = casac.casac.agentflagger()
            if self.preflag_manualflag_fluxcal:
                # self.logger.info('# Flagging channel(s) ' + self.preflag_manualflag_channel + ' for flux calibrator data #')
                af.open(self.fluxcal)
                af.selectdata()
                af.parsemanualparameters(spw='0:' + self.preflag_manualflag_channel)
                af.init()
                af.run(writeflags=True)
                af.done()
                # self.logger.info('# Flagging of channel(s) ' + self.preflag_manualflag_channel + ' for flux calibrator data done #')
            if self.preflag_manualflag_polcal:
                # self.logger.info('# Flagging channel(s) ' + self.preflag_manualflag_channel + ' for polarised calibrator data #')
                af.open(self.polcal)
                af.selectdata()
                af.parsemanualparameters(spw='0:' + self.preflag_manualflag_channel)
                af.init()
                af.run(writeflags=True)
                af.done()
                # self.logger.info('# Flagging of channel(s) ' + self.preflag_manualflag_channel + ' for polariased calibrator data done #')
            if self.preflag_manualflag_target:
                # self.logger.info('# Flagging channel(s) ' + self.preflag_manualflag_channel + ' for target data set(s) #')
                mslist = glob.glob(self.basedir + '*/' + self.rawsubdir + '/' + self.target)
                for dataset in mslist:
                    af.open(dataset)
                    af.selectdata()
                    af.parsemanualparameters(spw='0:' + self.preflag_manualflag_channel)
                    af.init()
                    af.run(writeflags=True)
                    af.done()
                # self.logger.info('# Flagging of channel(s) ' + self.preflag_manualflag_channel + ' for target data set(s) done #')

    def manualflag_time(self):
        '''
        Function to flag individual channels
        '''
        if self.preflag_manualflag_time != '':
            subs.setinit.setinitdirs(self)
            self.director('ch', self.rawdir)
            af = casac.casac.agentflagger()
            if self.preflag_manualflag_fluxcal:
                # self.logger.info('# Flagging timerange ' + self.preflag_manualflag_time + ' for flux calibrator data #')
                af.open(self.fluxcal)
                af.selectdata()
                af.parsemanualparameters(time=self.preflag_manualflag_time)
                af.init()
                af.run(writeflags=True)
                af.done()
                # self.logger.info('# Flagging of timerange ' + self.preflag_manualflag_time + ' for flux calibrator data done #')
            if self.preflag_manualflag_polcal:
                # self.logger.info('# Flagging timerange ' + self.preflag_manualflag_time + ' for polarised calibrator data #')
                af.open(self.polcal)
                af.selectdata()
                af.parsemanualparameters(time=self.preflag_manualflag_time)
                af.init()
                af.run(writeflags=True)
                af.done()
                # self.logger.info('# Flagging of timerange ' + self.preflag_manualflag_time + ' for polariased calibrator data done #')
            if self.preflag_manualflag_target:
                # self.logger.info('# Flagging timerange ' + self.preflag_manualflag_time + ' for target data set(s) #')
                mslist = glob.glob(self.basedir + '*/' + self.rawsubdir + '/' + self.target)
                for dataset in mslist:
                    af.open(dataset)
                    af.selectdata()
                    af.parsemanualparameters(time=self.preflag_manualflag_time)
                    af.init()
                    af.run(writeflags=True)
                    af.done()
                # self.logger.info('# Flagging of timerange ' + self.preflag_manualflag_time + ' for target data set(s) done #')

    def aoflagger_bandpass(self):
        '''
        Creates a bandpass from the flux calibrator and applies it to all calibrators and target fields
        '''
        if self.preflag_aoflagger_bandpass:
            self.director('ch', self.basedir + '00' + '/' + self.rawsubdir, verbose=False)
            cb = casac.casac.calibrater()
            cb.open(self.fluxcal)
            cb.setsolve('B', 'inf', self.fluxcal + '_Bcal')
            cb.solve()
            if os.path.isdir(self.fluxcal + '_Bcal'):
                pass
                # self.logger.info('# Bandpass for flagging successfully derived! #')
            else:
                pass
                # self.logger.warning('# Bandpass for flagging could not be derived! Performance of the automatic flagger might be bad! #')
            cb.setapply('B', 'inf', self.fluxcal + '_Bcal')
            cb.correct()
            # self.logger.info('# Applied bandpass for flagging to flux calibrator! #')
            cb.close()
            if self.preflag_aoflagger_polcal:
                if os.path.isdir(self.polcal):
                    cb = casac.casac.calibrater()
                    cb.open(self.polcal)
                    cb.setapply('B', 'inf', self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal + '_Bcal')
                    cb.correct()
                    cb.close()
                    # self.logger.info('# Successfully applied bandpass for flagging to polarised calibrator! #')
                else:
                    pass
                    # self.logger.warning('# Cannot find polarisation calibrator data set! Bandpass for flagging will not be applied! #')
            else:
                pass
                # self.logger.warning('# Flagging for polarised calibrator disabled! Bandpass for flagging will not be applied! #')
            if self.preflag_aoflagger_target:
                mslist = glob.glob(self.basedir + '*/' + self.rawsubdir + '/' + self.target)
                for dataset in mslist:
                    # if os.path.isdir(ms):
                    cb = casac.casac.calibrater()
                    cb.open(dataset)
                    cb.setapply('B', 'inf', self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal + '_Bcal')
                    cb.correct()
                    cb.close()
                        # self.logger.info('# Successfully applied bandpass for flagging to target dataset in ' + ms + ' ! #')
                    # else:
                    #     pass
                        # self.logger.warning('# Cannot locate target data set in ' + ms + ' ! No bandpass for flagging applied! #')
            else:
                pass
                # self.logger.warning('# Flagging for target dataset(s) disabled! Bandpass for flagging will not be applied! #')

    def aoflagger_flag(self):
        '''
        Uses the aoflagger to flag the calibrators and the target data set(s).
        '''
        if self.preflag_aoflagger_fluxcal:
            # if os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal):
            try:
                os.system('aoflagger -strategy ' + self.apercaldir + '/ao_strategies/' + self.preflag_aoflagger_fluxcalstrat + ' -column CORRECTED_DATA ' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal)
            except:
                os.system('aoflagger -strategy ' + self.apercaldir + '/ao_strategies/' + self.preflag_aoflagger_fluxcalstrat + ' ' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal)
        if self.preflag_aoflagger_polcal:
            # if os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal):
            try:
                os.system('aoflagger -strategy ' + self.apercaldir + '/ao_strategies/' + self.preflag_aoflagger_fluxcalstrat + ' -column CORRECTED_DATA ' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal)
            except:
                os.system('aoflagger -strategy ' + self.apercaldir + '/ao_strategies/' + self.preflag_aoflagger_fluxcalstrat + ' ' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal)
        if self.preflag_aoflagger_target:
            mslist = glob.glob(self.basedir + '*/' + self.rawsubdir + '/' + self.target)
            for dataset in mslist:
                # if os.path.isdir(ms):
                try:
                    os.system('aoflagger -strategy ' + self.apercaldir + '/ao_strategies/' + self.preflag_aoflagger_fluxcalstrat + ' -column CORRECTED_DATA ' + dataset)
                except:
                    os.system('aoflagger -strategy ' + self.apercaldir + '/ao_strategies/' + self.preflag_aoflagger_fluxcalstrat + ' ' + dataset)

    #######################################################################
    ##### Manage the creation and moving of new directories and files #####
    #######################################################################

    def show(self, showall=False):
        '''
        show: Prints the current settings of the pipeline. Only shows keywords, which are in the default config file default.cfg
        showall: Set to true if you want to see all current settings instead of only the ones from the current step
        '''
        subs.setinit.setinitdirs(self)
        config = ConfigParser.ConfigParser()
        config.readfp(open(self.apercaldir + '/modules/default.cfg'))
        for s in config.sections():
            if showall:
                print(s)
                o = config.options(s)
                for o in config.items(s):
                    try:
                        print('\t' + str(o[0]) + ' = ' + str(self.__dict__.__getitem__(o[0])))
                    except KeyError:
                        pass
            else:
                if s == 'PREFLAG':
                    print(s)
                    o = config.options(s)
                    for o in config.items(s):
                        try:
                            print('\t' + str(o[0]) + ' = ' + str(self.__dict__.__getitem__(o[0])))
                        except KeyError:
                            pass
                else:
                    pass

    def reset(self):
        '''
        Function to reset the current step and remove all generated data. Be careful! Deletes all data generated in this step!
        '''
        subs.setinit.setinitdirs(self)
        # self.logger.warning('### Deleting all preflagged data. You might need to run the PREPARE step again. ###')
        self.director('ch', self.rawdir)
        self.director('rm', self.rawdir + '/*')

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
                os.mkdir(dest)
                if verbose == True:
                    pass
                    # self.logger.info('# Creating directory ' + str(dest) + ' #')
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
                        pass
                        # self.logger.info('# Creating directory ' + str(dest) + ' #')
                    os.chdir(dest)
                self.cwd = os.getcwd()  # Save the current working directory in a variable
                if verbose == True:
                    pass
                    # self.logger.info('# Moved to directory ' + str(dest) + ' #')
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