This repository is os-version-checker for [openEuler](https://openeuler.org/),
based on Debian OpenStack team's tool os-version-checker
https://salsa.debian.org/openstack-team/debian/os-version-checker

Github action will generate latest page everyday, check here
https://kiwik.github.io/os-version-checker/

os-version-checker will check and compare self from upstream against openEuler
or other version of OpenStack.

Command execute:

    pip install -r requirements.txt

    python3 VersionsStatus.py

Command usage:

    Usage: python -m VersionStatus [OPTIONS]

    Options:
      -r, --releases TEXT      Comma separated releases with openstack/openEuler
                               to check, for example: rocky/20.03-LTS-
                               SP3,train/20.03-LTS-SP3  [default: train/22.03-LTS-
                               SP1]
      -n, --file-name TEXT     Output file name of openstack version checker
                               [default: index.html]
      -p, --proxy TEXT         HTTP proxy url
      -b, --bypass-ssl-verify  Bypass SSL verify  [default: False]
      -h, --help               Show this message and exit.
