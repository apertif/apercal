import ConfigParser
import os

class config:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        default = ConfigParser.ConfigParser()
        default.readfp(open(os.path.realpath(__file__).rstrip('config.py') + 'default.cfg'))
        modified = default
        self.cfgfile = default
        self.modfile = modified

    def show(self):
        secs = self.cfgfile.sections()
        for s in secs:
            print(s)
            opts = self.cfgfile.options(s)
            for o in opts:
                print('\t' + o + ' = ' + self.cfgfile.get(s,o))

    def add_step(self, step):
        if step in ['INITIAL','PREFLAG','CONVERT','FLAG','CROSSCAL','SELFCAL','FINAL']:
            try:
                self.modfile.add_section(str(step))
                self.cfgfile = self.modfile
                print('Step ' + str(step) + ' successfully added!')
            except:
                print('Step already exists!')
        else:
            print('Calibration step not allowed! Only INITIAL, PREFLAG, CONVERT, FLAG, CROSSCAL, SELFCAL, and FINAL are allowed!')

    def rm_step(self, step):
        if self.cfgfile.has_section(str(step)):
            self.cfgfile.remove_section(str(step))
            self.cfgfile = self.modfile
            print('Step ' + str(step) + ' successfully removed!')
        else:
            print('Section does not exist!')

    def show_step(self, step):
        secs = self.cfgfile.sections()
        for s in secs:
            if s == step:
                print(s)
                opts = self.cfgfile.options(s)
                for o in opts:
                    print('\t' + o + ' = ' + self.cfgfile.get(s, o))
            else:
                continue

    def add_option(self, step, option, value):
        if self.cfgfile.has_section(str(step)):
            self.cfgfile.set(str(step), str(option), value)
            self.cfgfile = self.modfile
            print('Option ' + str(option) + '=' + str(value) + ' successfully added in step ' + str(step) + '!')
        else:
            print('Section does not exist! Options could not be added!')

    def rm_options(self, step, option):
        if self.cfgfile.has_option(str(step), str(option)):
            self.cfgfile.remove_option(str(step), str(option))
            self.cfgfile = self.modfile
            print('Option ' + str(option) + 'has been successfully removed from step ' + str(step) + '!')
        else:
            print('No option ' + str(option) + 'in step ' + str(step) + '! Option could not be removed!')

    def load(self, file):
        loadfile = ConfigParser.ConfigParser()
        loadfile.readfp(open(file))
        self.cfgfile = loadfile

    def save(self, file):
        with open(str(file), 'wb') as configfile:
            self.modfile.write(configfile)

    def default(self):
        default = ConfigParser.ConfigParser()
        default.readfp(open(os.path.realpath(__file__).rstrip('config.py') + 'default.cfg'))
        modified = default
        self.cfgfile = default
        self.modfile = modified