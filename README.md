This is repository for os-version-checker in openEuler, based on Debian
OpenStack team's tool os-version-checker
https://salsa.debian.org/openstack-team/debian/os-version-checker

os-version-checker will check and compare self from upstream against openEuler
or other version of OpenStack.

    pip install -r requirements.txt

    python3 VersionsStatus.py

    Usage: VersionStatus.py [OPTIONS]

    Options:
    -r, --releases <release-distro>
                                    Comma separated releases with openstack or
                                    distribution of openEuler to check, for
                                    example: train-20.03-LTS-SP1,train-ussuri
                                    [required]

    -t, --file-type [txt|html]      Output file format  [default: html]
    -n, --file-name-os TEXT         Output file name of openstack version
                                    checker  [default: index.html]

    -a, --arch [aarch64|x86_64]     CPU architecture of distribution  [default:
                                    aarch64]

    -h, --help                      Show this message and exit.
