This is repository for os-version-checker in openEuler, based on Debian
OpenStack team's tool os-version-checker
https://salsa.debian.org/openstack-team/debian/os-version-checker

os-version-checker will check and compare self from upstream against openEuler.

    pip install -r requirements.txt

    python3 VersionsStatus.py

    Usage: VersionStatus.py [OPTIONS]

    Options:
      -r, --releases <distro-release>
                                      Comma separated releases with distribution
                                      of debian to check

      -t, --file-type [txt|html]      Output file format  [default: html]
      -n, --file-name-os TEXT         Output file name of openstack version
                                      checker
      -h, --help                      Show this message and exit.
