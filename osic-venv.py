#!/usr/bin/env python
import os
import os.path
from subprocess import Popen, PIPE
import sys
from threading import Thread
from urllib.parse import urlparse
from urllib.request import urlretrieve
import venv

# for openrc setup:
import shutil
from glob import glob
# run pip from the module
from pip.commands import commands_dict
from pip import parseopts
from pip import check_isolated, deprecation, locale

OPENRC = "openrc"  # default filename

class ExtendedEnvBuilder(venv.EnvBuilder):
    """
    This builder installs setuptools and pip so that you can pip or
    easy_install other packages into the created virtual environment.

    :param nodist: If True, setuptools and pip are not installed into the
                   created virtual environment.
    :param nopip: If True, pip is not installed into the created
                  virtual environment.
    :param progress: If setuptools or pip are installed, the progress of the
                     installation can be monitored by passing a progress
                     callable. If specified, it is called with two
                     arguments: a string indicating some progress, and a
                     context indicating where the string is coming from.
                     The context argument can have one of three values:
                     'main', indicating that it is called from virtualize()
                     itself, and 'stdout' and 'stderr', which are obtained
                     by reading lines from the output streams of a subprocess
                     which is used to install the app.

                     If a callable is not specified, default progress
                     information is output to sys.stderr.
    """

    def __init__(self, *args, **kwargs):
        self.nodist = kwargs.pop('nodist', False)
        self.nopip = kwargs.pop('nopip', False)
        self.progress = kwargs.pop('progress', None)
        self.verbose = kwargs.pop('verbose', False)
        # osic specific:
        self.requirements = kwargs.pop('requirements', None)
        self.openrc = kwargs.pop('openrc', None)
        if self.openrc:
            # check (early) that it is accessible:
            if not os.access(self.openrc, os.R_OK):
                raise Warning('Couldn\'t find "{}" '.format(self.openrc) +
                        'Either have a default "openrc.sh" file '
                        'in "~/.config/openstack" or specify a path '
                        'for one with the --openrc option')
        super().__init__(*args, **kwargs)


    def post_setup(self, context):
        """
        Set up any packages which need to be pre-installed into the
        virtual environment being created.

        :param context: The information for the virtual environment
                        creation request being processed.
        """
        os.environ['VIRTUAL_ENV'] = context.env_dir
        if not self.nodist:
            self.install_setuptools(context)
        # Can't install pip without setuptools
        if not self.nopip and not self.nodist:
            self.install_pip(context)

        ## add openrc to activation;
        if self.openrc:    # options set to guarentee this is set
            # copy self.openrc to bin directory
            openrc_dest = os.path.join(context.env_dir, 'bin', OPENRC)
            shutil.copyfile(self.openrc, openrc_dest)
            # append  "source openrc" to activate scripts
            for fn in glob(os.path.join(context.env_dir, 'bin', 'activate*')):
                cmd = '.' if fn[-4:] == 'fish' else 'source'
                print("updating {}: {} {} ...".format(fn, cmd, OPENRC), file=sys.stderr) 
                with open(fn, 'a') as f:
                    f.write('{} {}\n'.format(cmd, OPENRC))

        ## add pip-installation of openstack (or update, in case it's there)
        # setup pip for use, as pip.main() (mostly) does:
        deprecation.install_warning_logger()
        locale.setlocale(locale.LC_ALL, '')

        # --prefix has to be told to ignore existing libraries in path;
        self.pip("install -I --prefix {} python-openstackclient"
                .format(context.env_dir))
        '''
        # -t option doesn't work on 2.7 or 3.5 - but does on 3.6;
        self.pip("install -t {} -U python-openstackclient"
                 .format(os.path.join(context.env_dir, "lib",
                                      context.python_exe, "site_packages")))
         '''
        ## add any requirements options installations too;
        if self.requirements:
            self.pip( "install -I --prefix {} -r {}"
                    .format( context.env_dir, self.requirements))


    def pip(self, args):
        cmd_name, cmd_args = parseopts(args.split())
        command = commands_dict[cmd_name](isolated=check_isolated(cmd_args))
        rtn = command.main(cmd_args)


    def reader(self, stream, context):
        """
        Read lines from a subprocess' output stream and either pass to a progress
        callable (if specified) or write progress information to sys.stderr.
        """
        progress = self.progress
        while True:
            s = stream.readline()
            if not s:
                break
            if progress is not None:
                progress(s, context)
            else:
                if not self.verbose:
                    sys.stderr.write('.')
                else:
                    sys.stderr.write(s.decode('utf-8'))
                sys.stderr.flush()
        stream.close()

    def install_script(self, context, name, url):
        _, _, path, _, _, _ = urlparse(url)
        fn = os.path.split(path)[-1]
        binpath = context.bin_path
        distpath = os.path.join(binpath, fn)
        # Download script into the virtual environment's binaries folder
        urlretrieve(url, distpath)
        progress = self.progress
        if self.verbose:
            term = '\n'
        else:
            term = ''
        if progress is not None:
            progress('Installing %s ...%s' % (name, term), 'main')
        else:
            sys.stderr.write('Installing %s ...%s' % (name, term))
            sys.stderr.flush()
        # Install in the virtual environment
        args = [context.env_exe, fn]
        p = Popen(args, stdout=PIPE, stderr=PIPE, cwd=binpath)
        t1 = Thread(target=self.reader, args=(p.stdout, 'stdout'))
        t1.start()
        t2 = Thread(target=self.reader, args=(p.stderr, 'stderr'))
        t2.start()
        p.wait()
        t1.join()
        t2.join()
        if progress is not None:
            progress('done.', 'main')
        else:
            sys.stderr.write('done.\n')
        # Clean up - no longer needed
        os.unlink(distpath)

    def install_setuptools(self, context):
        """
        Install setuptools in the virtual environment.

        :param context: The information for the virtual environment
                        creation request being processed.
        """
        url = 'https://bootstrap.pypa.io/ez_setup.py'
        self.install_script(context, 'setuptools', url)
        # clear up the setuptools archive which gets downloaded
        pred = lambda o: o.startswith('setuptools-') and o.endswith('.tar.gz')
        files = filter(pred, os.listdir(context.bin_path))
        for f in files:
            f = os.path.join(context.bin_path, f)
            os.unlink(f)

    def install_pip(self, context):
        """
        Install pip in the virtual environment.

        :param context: The information for the virtual environment
                        creation request being processed.
        """
        url = "https://bootstrap.pypa.io/get-pip.py"
        self.install_script(context, 'pip', url)

def main(args=None):
    compatible = True
    if sys.version_info < (3, 3):
        compatible = False
    elif not hasattr(sys, 'base_prefix'):
        compatible = False
    if not compatible:
        raise ValueError('This script is only for use with '
                         'Python 3.3 or later')
    else:
        import argparse

        parser = argparse.ArgumentParser(prog=__name__,
                                         description='Creates virtual Python '
                                                     'environments in one or '
                                                     'more target '
                                                     'directories.')
        parser.add_argument('dirs', metavar='ENV_DIR', nargs='+',
                            help='A directory in which to create the '
                                 'virtual environment.')
        parser.add_argument('--no-setuptools', default=False,
                            action='store_true', dest='nodist',
                            help="Don't install setuptools or pip in the "
                                 "virtual environment.")
        parser.add_argument('--no-pip', default=False,
                            action='store_true', dest='nopip',
                            help="Don't install pip in the virtual "
                                 "environment.")
        parser.add_argument('--system-site-packages', default=False,
                            action='store_true', dest='system_site',
                            help='Give the virtual environment access to the '
                                 'system site-packages dir.')
        ## osic-venv:
        # if option not specified,
        #   try ~/.config/openstack/openrc.sh
        # if option specified w/o filename,
        #   try ./openrc
        parser.add_argument('-O', '--openrc', nargs='?',
                            const=os.path.join('.', OPENRC),
                            default=os.path.expanduser('~/.config/openstack/openrc.sh'),
                            help='path to OpenStack openrc file, ("./'+OPENRC+'" by default); '
                                 '"~/.config/openstack/openrc.sh" '
                                 'if option not specified')
        parser.add_argument('-r', '--requirements', nargs='?', # type=argparse.FileType('r'),
                            const='requirements.txt',
                            help='pip requirements file for installation '
                                 '(default: "requirements.txt")')
        if os.name == 'nt':
            use_symlinks = False
        else:
            use_symlinks = True
        parser.add_argument('--symlinks', default=use_symlinks,
                            action='store_true', dest='symlinks',
                            help='Try to use symlinks rather than copies, '
                                 'when symlinks are not the default for '
                                 'the platform.')
        parser.add_argument('--clear', default=False, action='store_true',
                            dest='clear', help='Delete the contents of the '
                                               'virtual environment '
                                               'directory if it already '
                                               'exists, before virtual '
                                               'environment creation.')
        parser.add_argument('--upgrade', default=False, action='store_true',
                            dest='upgrade', help='Upgrade the virtual '
                                                 'environment directory to '
                                                 'use this version of '
                                                 'Python, assuming Python '
                                                 'has been upgraded '
                                                 'in-place.')
        parser.add_argument('--verbose', default=False, action='store_true',
                            dest='verbose', help='Display the output '
                                               'from the scripts which '
                                               'install setuptools and pip.')
        options = parser.parse_args(args)
        if options.upgrade and options.clear:
            raise ValueError('you cannot supply --upgrade and --clear together.')
        builder = ExtendedEnvBuilder(
                                    openrc=options.openrc,
                                    requirements=options.requirements,
                                    system_site_packages=options.system_site,
                                    clear=options.clear,
                                    symlinks=options.symlinks,
                                    upgrade=options.upgrade,
                                    nodist=options.nodist,
                                    nopip=options.nopip,
                                    verbose=options.verbose)
        for d in options.dirs:
            builder.create(d)

if __name__ == '__main__':
    rc = 1
    try:
        main()
        rc = 0
    except Exception as e:
        print('Error: %s' % e, file=sys.stderr)
    sys.exit(rc)

