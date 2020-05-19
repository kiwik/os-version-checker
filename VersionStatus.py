from collections import OrderedDict
from packaging import version
import yaml
import requests
import jinja2
import re
import operator
import click

OS_VER_URI = "https://releases.openstack.org/{}"
DEB_VER_URI = "http://buster-{}.debian.net/debian/dists/" \
              "buster-{}-backports/main/source/Sources"
RELEASES = ["stein", "train", "ussuri"]
STATUS_OUT_OF_DATE = "1"
STATUS_UP_TO_DATE = "2"
STATUS_MISSING = "3"


class Renderer:
    def __init__(self, data, file_format, file_name):
        self.data = data
        self.file_name = "{}.{}".format(file_name, file_format)
        self.file_format = file_format

    def render(self):
        if "txt" in self.file_format:
            output=""
            for release, pkg_vers_data in self.data.items():
                output += "Release: {}\n\n".format(release)
                output += "PACKAGE_NAME|OS_VERSION|DEB_VERSION|STATUS\n\n"
                for pkg_name, pkg_info in pkg_vers_data.items():
                    output += \
                        "{}|{}|{}|{}\n".format(
                            pkg_name,
                            pkg_info.get('upstream_package_version'),
                            pkg_info.get('debian_package_version'),
                            pkg_info.get('status'))
                output += "\n"
        if "html" in self.file_format:
            output = jinja2.Environment(
                loader=jinja2.FileSystemLoader('./templates/')) \
                .get_template("index-template.j2") \
                .render(packages_versions_data=self.data)
        with open(self.file_name, 'w') as f:
            f.write(output)


class VersionsData:
    def __init__(self, _release):
        self.url_deb_content = requests \
            .get(DEB_VER_URI.format(_release, _release)).content.decode()
        self.url_os_content = requests \
            .get(OS_VER_URI.format(_release)).content.decode()
        self.deb_data = self.get_debian_versions()
        self.os_data = self.get_upstream_versions()
        self.versions_data = self.compare_versions()

    def get_upstream_versions(self):
        # get all links, which ends .tar.gz from HTML
        links = re.findall("https://.*.tar.gz", self.url_os_content)
        results = dict()
        for pkg_link in links:
            # get name and package informations from link
            tmp = pkg_link.split("/")
            pkg_name = tmp[3]
            pkg_full_name = tmp[4]
            pkg_name2 = pkg_full_name[0:pkg_full_name.rfind('-')]
            pkg_ver = pkg_full_name[pkg_full_name.rfind('-') + 1
                                    :pkg_full_name.rfind('.tar')]
            # check if package with version are in results,
            # and check for higher version
            if pkg_name2 not in results:
                pkg_info = dict(version=pkg_ver, href=pkg_link)
                results[pkg_name2] = pkg_info
            else:
                # if current versions < new version, than update it
                if version.parse(results.get(pkg_name2).get('version')) \
                        < version.parse(pkg_ver):
                    results.get(pkg_name2).update(version=pkg_ver)
        return results

    def get_debian_versions(self):
        # get all yaml package info from debian HTML
        pkg_info_yamls = [x.replace(": @", ": ")
                          for x in
                          self.url_deb_content.split('\n\n')
                          if x != '']
        results = dict()
        for pkg_info_yaml in pkg_info_yamls:
            pkg_info = yaml.safe_load(pkg_info_yaml)
            pkg_name = pkg_info.get('Package')
            pkg_ver = re.search('([0-9]+:)?([^-]+)([-~+].+)?',
                                str(pkg_info.get('Version'))).group(2)
            pkg_link = pkg_info.get('Vcs-Browser')
            pkg_info = dict(version=pkg_ver, href=pkg_link)
            results[pkg_name] = pkg_info
        return results

    def get_deb_pair(self, os_pkg_name):
        def sanitize_os_pkg_name(_os_pkg_name, str_to_replace):
            default_replace = os_pkg_name.replace("_", "-")
            cases = {
                "-": default_replace,
                "python-": "python-{}".format(default_replace),
                "openstack-": default_replace.replace("openstack-", ""),
                "puppet-": default_replace.replace("puppet-", "puppet-module-")
            }
            return cases.get(str_to_replace)

        def is_in_deb_data(_os_pkg_name, _replacement):
            if sanitize_os_pkg_name(os_pkg_name, replacement) in self.deb_data:
                return sanitize_os_pkg_name(os_pkg_name, replacement)
            return False

        # try find modified debian package name in debian packages
        replacements = ["-", "python-", "puppet-", "openstack-"]
        for replacement in replacements:
            if is_in_deb_data(os_pkg_name, replacement):
                return sanitize_os_pkg_name(os_pkg_name, replacement)

    def compare_versions(self):
        def set_status(os_ver, deb_ver):
            if "+" in deb_ver:
                deb_ver = deb_ver.split('+')[0]
            if "~" in deb_ver:
                deb_ver = deb_ver.split('~')[0]
            if version.parse(os_ver) == version.parse(deb_ver):
                return STATUS_UP_TO_DATE
            else:
                return STATUS_OUT_OF_DATE

        result = dict()
        paired = 0
        for os_pkg_name, os_pkg_info in self.os_data.items():
            deb_pkg_name = self.get_deb_pair(os_pkg_name)
            os_pkg_ver = os_pkg_info.get('version')
            # if debian and openstack package have pair
            if deb_pkg_name is not None:
                deb_pkg_info = self.deb_data.get(deb_pkg_name)
                deb_pkg_ver = deb_pkg_info.get('version')
                pkg_infos = dict(debian_package_version
                                 =deb_pkg_ver,
                                 upstream_package_version
                                 =os_pkg_ver,
                                 status=set_status(os_pkg_ver, deb_pkg_ver))
                paired += 1
                del self.deb_data[deb_pkg_name]
            else:
                pkg_infos = dict(debian_package_version=None,
                                 upstream_package_version=
                                 os_pkg_ver,
                                 status=STATUS_MISSING)
            result[os_pkg_name] = pkg_infos

        print("UPSTREAM_PACKAGES: {}    DEBIAN_PACKAGES: {} PAIRED: {}"
              .format(len(self.os_data), len(self.deb_data) + paired, paired))
        return OrderedDict(sorted(
            result.items(), key=lambda x: operator.getitem(x[1], 'status')))

    def get_versions_data(self):
        return self.versions_data


@click.command()
@click.option('--s', default=False, is_flag=True,
              help='Separate status page per one release')
@click.option('--file-format', default='html',
              help='Output file format [html|txt]')
@click.option('--file-name', required=False, default='index',
              help='Output file name')
def run(s, file_format, file_name):
    print(s)
    print(file_format)
    print(file_name)

    ver_data = dict()
    for release in RELEASES:
        release_ver_data = VersionsData(release)
        ver_data[release] = release_ver_data.get_versions_data()

    if s:
        for release in ver_data:
            release_data = dict()
            release_data[release] = ver_data.get(release)
            renderer = Renderer(release_data, file_format,
                                "{}-{}".format(file_name, release))
            renderer.render()
    else:
        renderer = Renderer(ver_data, file_format, file_name)
        renderer.render()


if __name__ == '__main__':
    run()
