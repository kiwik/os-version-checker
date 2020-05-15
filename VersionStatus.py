from collections import OrderedDict
from packaging import version
import yaml
import requests
import jinja2
import re
import operator

OS_VER_URI = "https://releases.openstack.org/{}"
DEB_VER_URI = "http://buster-{}.debian.net/debian/dists/buster-{}-backports/main/source/Sources"
RELEASES = ["stein", "train", "ussuri"]

DEFAULT = "None"

VERSION = "Version"
STATUS = "Status"
PACKAGE = "Package"
VCS_BROWSER = "Vcs-Browser"

STATUS_OUT_OF_DATE = "1"
STATUS2_UP_TO_DATE = "2"
STATUS_MISSING = "3"


class GeneratorHTMLVersionStatus:

    @staticmethod
    def render_page(page_file_name, data):
        output = jinja2.Environment(loader=jinja2.FileSystemLoader('./templates/')) \
            .get_template("index-template.j2") \
            .render(packages_versions_data=data)
        print
        output
        with open(page_file_name, 'w') as f:
            f.write(output)


class HTMLVersionsParser:

    @staticmethod
    def get_upstream_versions(url):
        # get all links, which ends .tar.gz from HTML
        links = re.findall('https://.*\.tar\.gz', requests.get(url).content.decode())
        results = dict()
        for pkg_link in links:
            # get name and package informations from link
            tmp = pkg_link.split("/")
            pkg_name = tmp[3]
            pkg_full_name = tmp[4]
            pkg_ver = pkg_full_name[pkg_full_name.rfind('-') + 1:pkg_full_name.rfind('.tar')]
            # check if package with version are in results, and check for higher version
            if pkg_name not in results:
                pkg_info = dict(Version=pkg_ver, Href=pkg_link)
                results.update([(pkg_name, pkg_info)])
            else:
                # if current versions < new version, than update it
                if version.parse(results.get(pkg_name).get(VERSION)) < version.parse(pkg_ver):
                    results.get(pkg_name).update(Version=pkg_ver)
        return results

    @staticmethod
    def get_debian_versions(url):
        # get all yaml package info from debian HTML
        pkg_info_yamls = [x.replace(": @", ": ") for x in requests.get(url).content.decode().split('\n\n') if x != '']
        results = dict()
        for pkg_info_yaml in pkg_info_yamls:
            pkg_info = yaml.safe_load(pkg_info_yaml)
            pkg_name = pkg_info.get(PACKAGE)
            pkg_ver = re.search('([\d]+:)?([^-]+)([-~+].+)?', str(pkg_info.get(VERSION))).group(2)
            pkg_link = pkg_info.get(VCS_BROWSER)
            pkg_info = dict(Version=pkg_ver, Href=pkg_link)
            results.update([(pkg_name, pkg_info)])
        return results


class VersionStatus:

    @staticmethod
    def deb_pair(deb_data, os_pkg_name):
        # new_upstream_package_name = os_pkg_name.replace("_", "-")
        if os_pkg_name.replace("_", "-") in deb_data:
            return os_pkg_name.replace("_", "-")
        elif ("python-" + os_pkg_name.replace("_", "-")) in deb_data:
            return "python-" + os_pkg_name.replace("_", "-")
        elif re.match('^puppet-', os_pkg_name.replace("_", "-")):
            if os_pkg_name.replace("_", "-").replace("puppet-", "puppet-module-") in deb_data:
                return os_pkg_name.replace("_", "-").replace("puppet-", "puppet-module-")

    @staticmethod
    def compare_versions(os_data, deb_data):
        result = dict()
        paired = 0
        for os_pkg_name, os_pkg_info in os_data.items():
            deb_pkg_name = VersionStatus.deb_pair(deb_data, os_pkg_name)
            # if debian package a openstack package have pair, then check version
            if deb_pkg_name is not None:
                pkg_infos = dict(debian_package_version=deb_data.get(deb_pkg_name).get(VERSION),
                                 upstream_package_version=os_pkg_info.get(VERSION),
                                 Status=DEFAULT)
                if version.parse(os_pkg_info.get(VERSION)) == version.parse(deb_data.get(deb_pkg_name).get(VERSION)):
                    pkg_infos.update(Status=STATUS2_UP_TO_DATE)
                else:
                    pkg_infos.update(Status=STATUS_OUT_OF_DATE)
                paired += 1
                del deb_data[deb_pkg_name]
            else:
                pkg_infos = dict(debian_package_version=DEFAULT,
                                 upstream_package_version=os_pkg_info.get(VERSION),
                                 Status=STATUS_MISSING)
            result.update([(os_pkg_name, pkg_infos)])

        print("UPSTREAM_PACKAGES: {}    DEBIAN_PACKAGES: {} PAIRED: {}"
              .format(len(os_data), len(deb_data) + paired, paired))
        return OrderedDict(sorted(result.items(), key=lambda x: operator.getitem(x[1], STATUS)))


if __name__ == '__main__':

    pkg_ver_data = dict()
    for release in RELEASES:
        os_ver_data = HTMLVersionsParser.get_upstream_versions(OS_VER_URI.format(release))
        deb_ver_data = HTMLVersionsParser.get_debian_versions(DEB_VER_URI.format(release, release))
        pkg_ver_data.update([(release, VersionStatus.compare_versions(os_ver_data, deb_ver_data))])

    GeneratorHTMLVersionStatus.render_page("index.html", pkg_ver_data)
