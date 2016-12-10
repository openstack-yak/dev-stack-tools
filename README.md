# Early release developer stack tools

## osic-venv.py

A customized version of pyvenv, for openstack developers.
Intended for developer station use (e.g. on your development laptop
or workstation).
Requires Python 3.4 or later to run.
You can specify a Python 2.7 interpreter for the openstack client
environment (but there really is no need).

*Warning:* This is a work in progress.

- creates or updates a python virtualenv (it's a custom pyvenv);
- includes openrc in the activation (*note:* given `clouds.yaml` evolution, this is likely to change);
  - you can specificy location and name of `openrc`
  - if `--openrc` option is given without a filename, then "./openrc" is assumed;
  - if you don't specify `--openrc` then "~/.config/openstack/openrc" must exist;
- localy installs `python-openstackclient` (i.e. `openstack` command line interface);
- optionally, installs additional packages specified in a requirements file (similar to the `-r` option of `pip`);

Since openstack clients and cloud-config are currently targeted at cloud operators,
much of this is likely to evolve to address needs of cloud and cloud-application developers.

Use:

    python3 osic-venv.py env/my-cloud-env

will create a virtual environment, just as with `pyvenv`.

You can also simply `chmod +x osic-env.py`, and run it directly.
Try:

    osic-venv.py -h
    

You can activate in the usual virtualenv way.
A copy of your openrc file is copied into the venv bin path, and sourced
with `venv` activation.

You may also find a shell script handy to activate (symmetric with `deactivate`), e.g.:

    activate()
    {
        source "$*"/bin/activate
    }

You could include this in your `~/.bash_login` or `~/.bashrc` file.


## BUGS / Known Issues:

- `setuptools` and `pip` are always downloaded and installed fresh;
   - eventually, this will be updated to do what standard `pip` does;
- `openrc` overrides clouds.yaml settings.  This can / will be problematic.
   - however, currently `os-client-config` is only looking for:
     - clouds.yaml   # general cloud specification
     - clouds-public.yaml  # common items, which can be shared among multiple people
     - secure.yaml   # passwords, etc. which should not be version controlled;
   - this doesn't account for developer uses, such as:
     - cloud creation templates / specs (w/o endpoints);
   - how this gets resolved is unclear (local developer yamls? use of heat (w/ dependencies)?  etc.)
- currently, there is no tool to convert from openrc to clouds.yaml;
   - it's likely that openrc may be deprecated in favor of clouds.yaml format;

