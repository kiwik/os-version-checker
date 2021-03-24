This is repository for os-version-checker.

Os-Version-Checker will check and compare self
from upstream against debian.

Using templates/datatables

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

      -i, --file-name-img TEXT        Output file name of images version checker
      -f, --filters <release:repository:tag>
                                      Comma separated filters for images
      -y, --manifest <manifest>       Jenkins kubernetes template file path
      -c, --config-file <configfile_path>
                                      Config file for openstack releases
      -h, --help                      Show this message and exit.
