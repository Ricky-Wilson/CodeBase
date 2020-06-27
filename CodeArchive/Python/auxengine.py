from os.path import abspath
from argparse import SUPPRESS
from log import LOG
from re import sub
import deployer
import undeployer
import pkgutil
import utility


def auxengine(fingerengine):
    """ Our core auxiliary engine runs as such:

            1. While building the command parser, we load all modules and append their
               CLI flags to a hidden argument parser.

            2. After fingerprinting the remote service, we load all of the platform's
               modules and run check(); this will return True/False as to whether or
               not it applies to the fingerprint.

            3. If the fingerprint applies, we check for --fingerprint, which will
               simply list that it is acceptable.  We also check for the auxiliarys
               hidden flag and, if it exists, we run the auxiliary.
    """

    fpath = [abspath("./src/platform/%s/auxiliary" % fingerengine.service)]
    modules = list(pkgutil.iter_modules(fpath))
    found = []

    for fingerprint in fingerengine.fingerprints:
        for auxiliary in modules:

            mod = auxiliary[0].find_module(auxiliary[1]).load_module(auxiliary[1])

            try:
                mod = mod.Auxiliary()
            except:
                # logged in build_platform_flags
                continue

            if mod.name not in found and mod.check(fingerprint):
                if fingerengine.options.fp:
                    utility.Msg("  %s (--%s)" % (mod.name, mod.flag), LOG.UPDATE)

                # work around argparse internally converting - to _ for var names
                elif (mod.flag in vars(fingerengine.options) and \
                     vars(fingerengine.options)[mod.flag])   or \
                     (sub('-','_',mod.flag) in vars(fingerengine.options) and\
                     vars(fingerengine.options)[sub('-','_',mod.flag)]):
                    try:
                        mod.run(fingerengine, fingerprint)
                    except Exception, e:
                        utility.Msg("Error with module: %s" % e, LOG.ERROR)

                found.append(mod.name)

    execMod(fingerengine)


def execMod(fingerengine):
    """
    """

    if fingerengine.options.deploy:
        deployer.run(fingerengine)

    if fingerengine.options.undeploy:
        undeployer.run(fingerengine)


def build_platform_flags(platform, egroup):
    """ This builds the auxiliary argument group
    """
    
    fpath = [abspath("./src/platform/%s/auxiliary" % platform)]
    modules = list(pkgutil.iter_modules(fpath))

    for auxiliary in modules:
        mod = auxiliary[0].find_module(auxiliary[1]).load_module(auxiliary[1])

        try:
            mod = mod.Auxiliary()
        except Exception, e:
            utility.Msg("Auxiliary %s failed to load: %s" % (auxiliary[1], e),
                                                          LOG.DEBUG)
            continue

        if not 'flag' in dir(mod):
            continue

        if 'enable_args' in dir(mod) and mod.enable_args:
            egroup.add_argument("--%s" % mod.flag, action='store', help=SUPPRESS)
        else:
            egroup.add_argument("--%s" % mod.flag, action='store_true', dest=mod.flag,
                            help=SUPPRESS)

    return egroup
