import ConfigParser
import os
import logging

class config:
    '''
    Class to manage configuration files.
    '''
    def __init__(self, file=None, **kwargs):
        logging.basicConfig(level=20)
        self.logger = logging.getLogger('CONFIG')
        self.__dict__.update(kwargs)
        default = ConfigParser.ConfigParser()  # Initialise the config parser
        if file != None:
            default.readfp(open(file))
            self.logger.info('### Configuration file ' + file + ' successfully read! ###')
        else:
            default.readfp(open(os.path.realpath(__file__).rstrip('config.pyc') + 'default.cfg'))
            self.logger.info('### No configuration file given or file not found! Using default values! ###')
        for s in default.sections():
            for o in default.items(s):
                setattr(self, o[0], eval(o[1]))
        modified = default
        self.cfgfile = default
        self.modfile = modified

    def show(self, step=None):
        '''
        Shows the current configuration file.
        step (string): Step name to show. If left blank all steps and parameters are shown.
        '''
        secs = self.cfgfile.sections()
        for s in secs:
            if step==None:
                print(s)
                opts = self.cfgfile.options(s)
                for o in opts:
                    print('\t' + o + ' = ' + self.cfgfile.get(s,o))
            else:
                if step==s:
                    print(s)
                    opts = self.cfgfile.options(s)
                    for o in opts:
                        print('\t' + o + ' = ' + self.cfgfile.get(s, o))
                else:
                    pass

    def add_step(self, step):
        '''
        Add a step to the configuration file
        step (string): Name of the step to add
        '''
        if step in ['INITIAL','PREFLAG','CONVERT','CROSSCAL','SELFCAL','LINE','FINAL']:
            try:
                self.modfile.add_section(str(step))
                self.cfgfile = self.modfile
                print('Step ' + str(step) + ' successfully added!')
            except:
                print('Step already exists!')
        else:
            print('Calibration step not allowed! Only INITIAL, PREFLAG, CONVERT, CROSSCAL, SELFCAL, LINE, and FINAL are allowed!')

    def rm_step(self, step):
        '''
        Remove a step from a configuration file
        step (string): Name of the step to remove
        '''
        if self.cfgfile.has_section(str(step)):
            self.cfgfile.remove_section(str(step))
            self.cfgfile = self.modfile
            print('Step ' + str(step) + ' successfully removed!')
        else:
            print('Section does not exist!')

    def add_option(self, step, option, value):
        '''
        Add an option to a step in the configuration file
        step (string): The name opf the step to add the option to
        option (string): The name of the option to add
        value (): The value of the option to add
        :return:
        '''
        if self.cfgfile.has_section(str(step)):
            self.cfgfile.set(str(step), str(option), value)
            self.cfgfile = self.modfile
            print('Option ' + str(option) + '=' + str(value) + ' successfully added in step ' + str(step) + '!')
        else:
            print('Section does not exist! Options could not be added!')

    def rm_options(self, step, option):
        '''
        Remove an option from a configuration file
        step (string): The name of the step to remove the option from
        option (string): The name of the option to remove
        '''
        if self.cfgfile.has_option(str(step), str(option)):
            self.cfgfile.remove_option(str(step), str(option))
            self.cfgfile = self.modfile
            print('Option ' + str(option) + 'has been successfully removed from step ' + str(step) + '!')
        else:
            print('No option ' + str(option) + 'in step ' + str(step) + '! Option could not be removed!')

    def load(self, file):
        '''
        Load a configuration file
        file (string): The name and absolute path of the configuration file to load
        '''
        loadfile = ConfigParser.ConfigParser()
        loadfile.readfp(open(file))
        self.cfgfile = loadfile

    def save(self, file):
        '''
        Save a configuration file
        file (string): The name and absolute path of the configuration file to save
        '''
        with open(str(file), 'wb') as configfile:
            self.modfile.write(configfile)

    def default(self):
        '''
        Loads the default configuration file. Resets all parameters to the default values.
        '''
        default = ConfigParser.ConfigParser()
        default.readfp(open(os.path.realpath(__file__).rstrip('config.py') + 'default.cfg'))
        modified = default
        self.cfgfile = default
        self.modfile = modified