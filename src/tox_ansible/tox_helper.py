from os.path import join
import py
from tox.config import \
    (
        testenvprefix,
        SectionReader,
        DepOption
    )
try:
    from tox.config import ParseIni  # tox 3.4.0+
except ImportError:
    from tox.config import parseini as ParseIni


class Tox(object):
    instance = None
    """A class that handles interacting with the specific internals of the tox
    world for the plugin."""
    def __new__(cls, *args):
        if cls.instance is None:
            cls.instance = super(Tox, cls).__new__(cls)
        return cls.instance

    def __init__(self, config=None):
        """Initialize this object

        :param config: the tox config object"""
        if config is not None:
            self.config = config

    def get_reader(self, section, prefix=None):
        """Creates a SectionReader and configures it with known and reasonable
        substitution values based on the config.

        :param section: Config section name to read from
        :param prefix: Any applicable prefix to the ini section name. Default
        None"""
        reader = SectionReader(section, self.config._cfg, prefix=prefix)
        distshare_default = join(self.config.homedir, ".tox", "distshare")
        reader.addsubstitutions(toxinidir=self.config.toxinidir,
                                homedir=self.config.homedir,
                                toxworkdir=self.config.toxworkdir)
        self.config.distdir = reader.getpath("distdir",
                                             join(self.config.toxworkdir,
                                                  "dist"))
        reader.addsubstitutions(distdir=self.config.distdir)
        self.config.distshare = reader.getpath("distshare", distshare_default)
        reader.addsubstitutions(distshare=self.config.distshare)
        return reader

    @property
    def posargs(self):
        """Returns any configured posargs from the tox world"""
        return self.config.option.args

    def get_opts(self):
        """Return the options as a dictionary-style object.

        :return: A dictionary of the command line options"""
        return vars(self.config.option)

    def add_envconfigs(self, tox_cases, options):
        """Modifies the list of envconfigs in tox to add any that were
        generated by this plugin.

        :param tox_cases: An iterable of test cases to create environments
        from"""
        # Stripped down version of parseini.__init__ for making a generated
        # envconfig
        prefix = 'tox' if self.config.toxinipath.basename == 'setup.cfg' \
            else None
        reader = self.get_reader("tox", prefix=prefix)
        make_envconfig = ParseIni.make_envconfig
        # Python 2 fix
        make_envconfig = getattr(make_envconfig, '__func__', make_envconfig)

        # Store the generated ansible envlist
        self.config.ansible_envlist = []
        for tox_case in tox_cases:
            section = testenvprefix + tox_case.get_name()
            config = make_envconfig(self.config,
                                    tox_case.get_name(),
                                    section,
                                    reader._subs,
                                    self.config)
            config.tox_case = tox_case
            self.customize_envconfig(config, options)
            self.config.envconfigs[tox_case.get_name()] = config
            self.config.ansible_envlist.append(tox_case.get_name())

    def customize_envconfig(self, config, options):
        """Writes the fields of the envconfig that need to be given default
        molecule related values.

        :param config: the constructed envconfig for this to customize"""
        tox_case = config.tox_case
        # Default commands to run molecule
        if not config.commands:
            config.commands = tox_case.get_commands(options)
        # Default deps to install molecule, etc
        if not config.deps:
            do = DepOption()
            config.deps = do.postprocess(config, tox_case.get_dependencies())
        # Cannot run in {toxinidir}, which is default
        if not config.envdir or config.envdir == self.config.toxinidir:
            config.envdir = self.config.toxworkdir.join("ansible")
        # Need to run molecule from the role directory
        if not config.changedir or \
                config.changedir == self.config.toxinidir:
            config.changedir = py.path.local(tox_case.get_working_dir())
        if not config.basepython and tox_case.python is not None:
            config.basepython = tox_case.get_basepython()
        if not config.whitelist_externals:
            config.whitelist_externals = ["bash"]
