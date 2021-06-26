import datetime
import operator
import os
import re
import sys
from collections import OrderedDict

import click
import jinja2
import requests
from packaging import version

OS_URI = "https://releases.openstack.org/{}"
RPM_OS_URI = "https://repo.openeuler.org/openEuler-{0}/{1}/{2}/Packages/"
RPM_DIRECTORY = ["EPOL", "everything", "update"]
STATUS_NONE = ["0", "NONE"]
STATUS_OUTDATED = ["1", "OUTDATED"]
STATUS_MISMATCH = ["2", "MISMATCH"]
STATUS_OK = ["3", "OK"]
STATUS_MISSING = ["4", "MISSING"]
UPSTREAM_FILTER_LIST = [
    re.compile(r"^puppet[-_][-_\w]+$"),  # puppet-*
    re.compile(r"^[-_\w]+[-_]dashboard$"),  # *-dashboard
    re.compile(r"^[-_\w]+[-_]tempest[-_]plugin$"),  # *-tempest-plugin
]
OPENEULER_VERSION_PATTERN = re.compile(r"^\d.*$")
OPENEULER_DEFAULT_REPLACE = re.compile(r"[._]")


class ReleasesConfig:
    def __init__(self, content, arch):
        if isinstance(content, str):
            self.releases_config = dict()
            self.releases = [r.strip() for r in content.split(',')]
            for release in self.releases:
                self.releases_config[release] = dict()
        for release in self.releases:
            from_os_version, to_os_version = release.split('/', 1)

            # openstack version check openeuler
            check_openeuler = OPENEULER_VERSION_PATTERN.match(to_os_version)

            self.releases_config[release] = dict()
            if 'rpm_os_ver_uri' not in self.releases_config[release]:
                self.releases_config[release]['rpm_os_ver_uri'] = list()
                if check_openeuler:
                    for _dir in RPM_DIRECTORY:
                        self.releases_config[release]['rpm_os_ver_uri'].append(
                            RPM_OS_URI.format(to_os_version, _dir, arch))
            if 'os_ver_uri' not in self.releases_config[release]:
                self.releases_config[release]['os_ver_uri'] = list()
                self.releases_config[release]['os_ver_uri'].append(
                    OS_URI.format(from_os_version))
                if not check_openeuler:
                    self.releases_config[release]['os_ver_uri'].append(
                        OS_URI.format(to_os_version))


class Renderer:
    def __init__(self, data, template, file_format, file_name):
        self.data = data
        self.file_format = file_format
        self.file_name = file_name
        self.template = template
        self.path = os.path.abspath(os.path.dirname(sys.argv[0]))
        self.template_path = "{}/templates/".format(self.path)

    def render(self):
        output = ""
        if "txt" == self.file_format:
            for release, pkg_vers_data in self.data.items():
                output += "Release: {}\n\n".format(release)
                output += "{:<30} {:<15} {:<15} {:<15}\n\n" \
                    .format('Package name',
                            'OpenStack version',
                            'openEuler version',
                            'Status')
                for _value in pkg_vers_data.values():
                    for pkg_name, pkg_info in _value['data'].items():
                        output += "{:<30} {:<15} {:<15} {:<15}\n".format(
                            pkg_name,
                            pkg_info.get('base_package_version'),
                            str(pkg_info.get('comparison_package_version')),
                            pkg_info.get('status'))
                output += "\n"
        if "html" == self.file_format:
            output = jinja2.Environment(
                loader=jinja2.FileSystemLoader(
                    self.template_path)).get_template(self.template).render(
                data=self.data,
                time=datetime.datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S"))
        # if file name is not set,
        # then file format is None and output print to stdout
        if self.file_name is None:
            print(output)
        else:
            if os.path.exists(self.file_name):
                os.remove(self.file_name)
            with open(self.file_name, 'w') as f:
                f.write(output)


class RPMVersions:
    def __init__(self, release, config):
        self.rpm_os_ver_uri_list = config.releases_config.get(release).get(
            'rpm_os_ver_uri')

    @property
    def rpm_versions(self):
        results = dict()
        for _rpm_os_ver_uri in self.rpm_os_ver_uri_list:
            r = requests.get(_rpm_os_ver_uri)
            if r.status_code != requests.codes.ok:
                print("%s can't get", _rpm_os_ver_uri)
                continue
            uri_content = r.content.decode()
            # get all links, which ends .rpm from HTML
            links = re.findall(r'\shref="(.*\.rpm)"\s', uri_content)
            for _link in links:
                pkg_link = _rpm_os_ver_uri + _link
                # get name and package information from link
                pkg_full_name, _ = _link.rsplit('-', 1)
                pkg_name, pkg_ver = pkg_full_name.rsplit('-', 1)
                # check if package with version are in results,
                # and check for higher version
                if pkg_name not in results:
                    pkg_info = dict(version=pkg_ver, href=pkg_link)
                    results[pkg_name] = pkg_info
                else:
                    # if current version < new version, then update it
                    if version.parse(results.get(pkg_name).get('version')) \
                            < version.parse(pkg_ver):
                        results.get(pkg_name).update(version=pkg_ver)
        return results


class UpstreamVersions:
    def __init__(self, _os_ver_uri):
        self.url_os_content = requests.get(_os_ver_uri).content.decode()

    @property
    def upstream_versions(self):
        # get all links, which ends .tar.gz from HTML
        links = re.findall(r'https://.*\.tar\.gz', self.url_os_content)
        results = dict()
        for pkg_link in links:
            # get name and package informations from link
            tmp = pkg_link.split("/")
            pkg_full_name = tmp[4]
            pkg_name = pkg_full_name[0:pkg_full_name.rfind('-')]
            pkg_ver = pkg_full_name[
                      pkg_full_name.rfind('-') + 1:pkg_full_name.rfind('.tar')]
            # check if package with version are in results,
            # and check for higher version
            if pkg_name not in results:
                pkg_info = dict(version=pkg_ver, href=pkg_link)
                results[pkg_name] = pkg_info
            else:
                # if current versions < new version, then update it
                if version.parse(results.get(pkg_name).get('version')) \
                        < version.parse(pkg_ver):
                    results.get(pkg_name).update(version=pkg_ver)
        return results


class VersionsComparator:
    def __init__(self, base_data, to_comparison_data):
        self._base_data = base_data
        self._comp_data = to_comparison_data

    @staticmethod
    def get_pair(base_pkg_name, from_data):
        def sanitize_base_pkg_name(_base_pkg_name, str_to_replace):
            default_replace = OPENEULER_DEFAULT_REPLACE.sub("-",
                                                            _base_pkg_name)
            cases = {
                # Check between openstack versions
                "*": _base_pkg_name,
                # Check between openstack and openEuler packages, package name
                # should to be transformed
                "-": default_replace,
                "python2to3-": default_replace.replace("python-", "python3-"),
                "+python3-": "python3-{}".format(default_replace),
                "+openstack-": "openstack-{}".format(default_replace)
            }
            return cases.get(str_to_replace)

        def is_in_comp_data(_base_pkg_name, _replacement):
            if sanitize_base_pkg_name(_base_pkg_name, replacement) \
                    in from_data:
                return sanitize_base_pkg_name(_base_pkg_name, replacement)
            return False

        # try find modified to comparison package name in to comp. packages
        replacements = ["*",
                        "-",
                        "python2to3-",
                        "+python3-",
                        "+openstack-"]
        for replacement in replacements:
            if is_in_comp_data(base_pkg_name, replacement):
                return sanitize_base_pkg_name(base_pkg_name, replacement)

    @property
    def compared_data(self):
        def set_status(base_ver, comp_ver):
            if "+" in comp_ver:
                comp_ver = comp_ver.split('+')[0]
            if "~" in comp_ver:
                if "~rc" or "~b" in comp_ver:
                    comp_ver_arr = comp_ver.split('~')
                    comp_ver = "{}.0{}".format(comp_ver_arr[0],
                                               comp_ver_arr[1])
                else:
                    comp_ver = comp_ver.split('~')[0]
            if version.parse(base_ver) == version.parse(comp_ver):
                return STATUS_OK
            elif version.parse(base_ver) > version.parse(comp_ver):
                return STATUS_OUTDATED
            else:
                return STATUS_MISMATCH

        def filter_upstream(_base_pkg_name):
            for pattern in UPSTREAM_FILTER_LIST:
                if pattern.match(_base_pkg_name):
                    return False
            return True

        result_data = dict()
        paired = 0
        overall_status = STATUS_NONE
        for base_pkg_name in filter(filter_upstream, self._base_data.keys()):
            comp_pkg_name = self.get_pair(base_pkg_name, self._comp_data)
            base_pkg_ver = self._base_data.get(base_pkg_name).get('version')
            # if to comparison package and base package have pair
            if comp_pkg_name is not None:
                comp_pkg_info = self._comp_data.get(comp_pkg_name)
                comp_pkg_ver = comp_pkg_info.get('version')
                status = set_status(base_pkg_ver, comp_pkg_ver)
                pkg_infos = dict(comparison_package_version=comp_pkg_ver,
                                 base_package_version=base_pkg_ver,
                                 status=status[1], status_id=status[0])
                if status == STATUS_OUTDATED:
                    overall_status = STATUS_OUTDATED
                paired += 1
                del self._comp_data[comp_pkg_name]
            else:
                pkg_infos = dict(comparison_package_version=None,
                                 base_package_version=base_pkg_ver,
                                 status=STATUS_MISSING[1],
                                 status_id=STATUS_MISSING[0])
            result_data[base_pkg_name] = pkg_infos

        result_data = OrderedDict(sorted(result_data.items(),
                                         key=lambda x:
                                         operator.getitem(x[1], 'status_id')))
        return dict(overall_status=overall_status[1],
                    overall_status_id=overall_status[0],
                    paired=paired,
                    data=result_data)


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.option('-r', '--releases', is_flag=False, metavar='<release-distro>',
              type=click.STRING, required=True,
              help='Comma separated releases with openstack or '
                   'distribution of openEuler to check, for example: '
                   'rocky/20.03-LTS-SP2,rocky/train')
@click.option('-t', '--file-type', default='html',
              show_default=True, help='Output file format',
              type=click.Choice(['txt', 'html']))
@click.option('-n', '--file-name-os', default='index.html',
              required=False, show_default=True,
              help='Output file name of openstack version checker')
@click.option('-a', '--arch', default='aarch64',
              required=False, show_default=True,
              type=click.Choice(['aarch64', 'x86_64']),
              help='CPU architecture of distribution')
def run(releases, file_type, file_name_os, arch):
    if not file_name_os:
        file_name_os = "index.html"
    if not arch:
        arch = "aarch64"

    releases_config = None
    if releases:
        releases_config = ReleasesConfig(releases, arch)

    if releases_config:
        ver_data = dict()
        for release in releases_config.releases:
            from_os_uri = releases_config.releases_config.get(
                release).get('os_ver_uri')[0]
            from_os_data = UpstreamVersions(from_os_uri).upstream_versions
            # openstack version check openEuler
            if releases_config.releases_config.get(
                    release).get('rpm_os_ver_uri'):
                to_os_data = RPMVersions(release, releases_config).rpm_versions
            # openstack version check openstack
            else:
                to_os_uri = releases_config.releases_config.get(
                    release).get('os_ver_uri')[-1]
                to_os_data = UpstreamVersions(to_os_uri).upstream_versions

            os_rpm_data = VersionsComparator(from_os_data,
                                             to_os_data).compared_data
            os_rpm_data['apt'] = releases_config.releases_config.get(
                release).get('os_ver_uri')
            os_rpm_data['apt'].extend(releases_config.releases_config.get(
                release).get('rpm_os_ver_uri'))
            ver_data[release] = os_rpm_data
        Renderer(ver_data, "template_os_checker.j2", file_type,
                 file_name_os).render()


if __name__ == '__main__':
    if len(sys.argv) == 1:
        run.main(['--help'])
    else:
        run()
