import datetime
import operator
import os
import re
import sys
from collections import defaultdict, OrderedDict
from typing import Any

import click
import jinja2
import requests
import validators
from packaging import version

OS_URI = "https://releases.openstack.org/{}"
RPM_OS_URI_MAPPING = {
    # Archived version
    ('20.09', '21.03'):
        "https://archives.openeuler.openatom.cn/openEuler-{oe_version}/EPOL/"
        "{aarch}/Packages/",
    ('21.09', '22.09'):
        "https://archives.openeuler.openatom.cn/openEuler-{oe_version}/EPOL/"
        "main/{aarch}/Packages/",
    # Active version
    ('20.03-LTS', '20.03-LTS-SP1'):
        "https://repo.openeuler.org/openEuler-{oe_version}/EPOL/{aarch}/"
        "Packages/",
    ('20.03-LTS-SP2',):
        "https://repo.oepkgs.net/openEuler/rpm/openEuler-{oe_version}/"
        "budding-openeuler/openstack/{os_version}/{aarch}/Packages/",
    ('20.03-LTS-SP3',):
        defaultdict(
            lambda: "https://repo.openeuler.org/openEuler-{oe_version}/EPOL/"
                    "main/{aarch}/Packages/",
            dict(rocky="https://repo.oepkgs.net/openEuler/rpm/"
                       "openEuler-{oe_version}/budding-openeuler/openstack/"
                       "{os_version}/{aarch}/Packages/",
                 queens="https://repo.oepkgs.net/openEuler/rpm/"
                        "openEuler-{oe_version}/budding-openeuler/openstack/"
                        "{os_version}/{aarch}/Packages/")
        ),
    # OpenStack SIG decide to end supporting for openEuler innovation release
    # from openEuler 23.03 because of lacking users that use OpenStack with
    # openEuler innovation release, most users use openEuler LTS release to
    # deploy OpenStack. openEuler LTS supporting will continue forever :)
    ('22.03-LTS', '22.03-LTS-SP1', '22.03-LTS-SP2', '22.03-LTS-SP3'):
        "https://repo.openeuler.org/openEuler-{oe_version}/EPOL/multi_version"
        "/OpenStack/{os_version}/{aarch}/Packages/",
    # dev version
    ('dev-20.03-LTS', 'dev-20.03-LTS-SP1', 'dev-20.03-LTS-SP2',
     'dev-20.03-LTS-SP3', 'dev-20.03-LTS-Next',
     'dev-20.09', 'dev-21.03', 'dev-21.09', 'dev-22.09',
     'dev-Mainline'):
        "http://119.3.219.20:82/openEuler:/{oe_version_v}/{oe_version_lts}/"
        "{oe_version_sp}/Epol/standard_{aarch}/{aarch_option}/",
    ('dev-22.03-LTS', 'dev-22.03-LTS-SP1', 'dev-22.03-LTS-SP2',
     'dev-22.03-LTS-Next'):
        "http://119.3.219.20:82/openEuler:/{oe_version_v}/{oe_version_lts}/"
        "{oe_version_sp}/Epol:/Multi-Version:/OpenStack:/{os_version}/"
        "standard_{aarch}/{aarch_option}",
}
OPENEULER_REPO_DOMAIN = "repo.openeuler.org"
DEFAULT_FILE_TYPE = 'html'
STATUS_NONE = ["0", "NONE"]
STATUS_OK = ["1", "OK"]
STATUS_EOL = ["2", "EOL"]
STATUS_OUTDATED = ["3", "OUTDATED"]
STATUS_MISMATCH = ["4", "MISMATCH"]
STATUS_MISSING = ["5", "MISSING"]
UPSTREAM_FILTER_LIST = [
    re.compile(r"^puppet[-_][-_\w]+$"),  # puppet-*
    re.compile(r"^[-_\w]+[-_]dashboard$"),  # *-dashboard
    re.compile(r"^[-_\w]+[-_]ui$"),  # *-ui
    re.compile(r"^[-_\w]+[-_]tempest[-_]plugin$"),  # *-tempest-plugin
]
OPENEULER_DEFAULT_REPLACE = re.compile(r"[._]")
REQUESTS_ARGS = {}
AARCH64 = 'aarch64'
NOARCH = 'noarch'
EOL_PKG_SUFFIX = ('last', 'eom')


class FormatInput(dict):
    def __init__(self) -> None:
        self.oe_version = None
        self.oe_version_v = None
        self.oe_version_lts = None
        self.oe_version_sp = None
        self.os_version = None
        self.aarch = AARCH64
        self.aarch_option = AARCH64

    def __getattribute__(self, name: str) -> Any:
        return dict.__getitem__(self, name)

    def __setattr__(self, name: str, value: Any) -> None:
        return dict.__setitem__(self, name, value)


class ReleasesConfig:
    def __init__(self, content):
        if not isinstance(content, str):
            raise RuntimeError('Input format error')
        self.releases = [r.strip() for r in content.split(',') if r]
        self.releases_config = {}
        for release in self.releases:
            openeuler_version, openstack_version = release.split('/', 1)
            self.releases_config[release] = {}
            self.releases_config[release]['openeuler_ver'] = openeuler_version
            self.releases_config[release]['rpm_os_ver_uri'] = []
            self.releases_config[release]['openstack_ver'] = openstack_version
            self.releases_config[release]['os_ver_uri'] = [
                OS_URI.format(openstack_version), ]
            # Get URL template
            for _to_version_tuple in RPM_OS_URI_MAPPING.keys():
                if openeuler_version in _to_version_tuple:
                    _url = RPM_OS_URI_MAPPING[_to_version_tuple]
                    if isinstance(_url, dict):
                        _url = _url[openstack_version]
                    break
            # openeuler_version not in RPM_OS_URI_MAPPING
            else:
                # openstack vs openstack
                # self.releases_config[release]['os_ver_uri'].append(
                #     OS_URI.format(openeuler_version))
                # return
                raise RuntimeError(
                    'openEuler {} not found in list'.format(openeuler_version))

            format_input = FormatInput()
            format_input.oe_version = openeuler_version
            # 119 openEuler vs openstack
            if openeuler_version.startswith('dev-'):
                openeuler_version = openeuler_version[4:]
                _parts = openeuler_version.split('-')
                # pad placeholder in URI
                (format_input.oe_version_v, format_input.oe_version_lts,
                 format_input.oe_version_sp) = (
                    _parts[i] + ':'
                    if i < len(_parts) and openeuler_version != 'Mainline'
                    else ''
                    for i in range(3))
                # aarch64
                format_input.os_version = openstack_version.capitalize()
                self.releases_config[release]['rpm_os_ver_uri'].append(
                    _url.format(**format_input))
                # noarch
                format_input.aarch_option = NOARCH
                self.releases_config[release]['rpm_os_ver_uri'].append(
                    _url.format(**format_input))
            # openEuler vs openstack
            else:
                _openstack_version = openstack_version.capitalize() \
                    if OPENEULER_REPO_DOMAIN in _url else openstack_version
                format_input.os_version = _openstack_version
                self.releases_config[release]['rpm_os_ver_uri'].append(
                    _url.format(**format_input))


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
                            pkg_info['base_package_version'],
                            str(pkg_info['comparison_package_version']),
                            pkg_info['status'])
                output += "\n"
        if "html" == self.file_format:
            sha_tz = datetime.timezone(
                datetime.timedelta(hours=8),
                name='Asia/Shanghai',
            )
            utc_now = datetime.datetime.utcnow().replace(
                tzinfo=datetime.timezone.utc)
            xian_now = utc_now.astimezone(sha_tz)
            output = jinja2.Environment(
                loader=jinja2.FileSystemLoader(
                    self.template_path)).get_template(self.template).render(
                data=self.data,
                time=xian_now.strftime("%Y.%m.%d %H:%M:%S %Z"))
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
    def __init__(self, _rpm_os_ver_uri_list, openeuler_ver):
        self.rpm_os_ver_uri_list = _rpm_os_ver_uri_list
        self.openeuler_ver = openeuler_ver

    @property
    def rpm_versions(self):
        results = dict()
        for _rpm_os_ver_uri in self.rpm_os_ver_uri_list:
            r = requests.get(_rpm_os_ver_uri, **REQUESTS_ARGS)
            if r.status_code != requests.codes.ok:
                raise RuntimeError('CAN NOT GET openEuler {} from {}'.format(
                        self.openeuler_ver, _rpm_os_ver_uri))
            uri_content = r.content.decode()
            # get all links, which ends .rpm from HTML, work for oepkg and
            # openEuler EPOL page format
            links = re.findall(r'<a\shref="(.*?\.rpm)"[\s>]', uri_content)
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
                    if version.parse(results[pkg_name]['version']) \
                            < version.parse(pkg_ver):
                        results[pkg_name].update(version=pkg_ver)
        return results


class UpstreamVersions:
    def __init__(self, _os_ver_uri, openstack_ver):
        self.url_os_content = requests.get(_os_ver_uri,
                                           **REQUESTS_ARGS).content.decode()
        self.openstack_ver = openstack_ver

    @property
    def upstream_versions(self):
        # get all links, which ends .tar.gz from HTML
        # regular package format: https://releases.openstack.org/
        # {pkg_name}/{pkg_name}-{pkg-version}.tar.gz
        # for regular package
        # a new format is added at 2022-12: https://releases.openstack.org/
        # {pkg_name}/{pkg_name}-{release-version}-last.tar.gz
        # for last compatible version
        # a new format is added at 2024-02: https://releases.openstack.org/
        # {pkg_name}/{pkg_name}-{release-version}-eom.tar.gz
        # for unmaintained version
        links = re.findall(r'https://.*\.tar\.gz', self.url_os_content)
        results = dict()
        for pkg_link in links:
            # get name and package information from link
            tmp = pkg_link.split("/")
            pkg_name = tmp[3]
            pkg_full_name = tmp[4]
            pkg_ver = pkg_full_name[pkg_full_name.rfind('-')+1:
                                    pkg_full_name.rfind('.tar')]
            # check if package with version are in results,
            # and check for higher version
            if pkg_name not in results:
                pkg_info = dict(version=pkg_ver, href=pkg_link)
                results[pkg_name] = pkg_info
            elif results[pkg_name]['version'] in EOL_PKG_SUFFIX:
                continue
            else:
                # if current versions < new version, then update it
                if (pkg_ver in EOL_PKG_SUFFIX or
                        version.parse(results[pkg_name]['version']) <
                        version.parse(pkg_ver)):
                    results[pkg_name].update(version=pkg_ver, href=pkg_link)
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
                "python-to2-": default_replace.replace("python-", "python2-"),
                "python-to3-": default_replace.replace("python-", "python3-"),
                "+python2-": "python2-{}".format(default_replace),
                "+python3-": "python3-{}".format(default_replace),
                "+openstack-": "openstack-{}".format(default_replace)
            }
            return cases[str_to_replace]

        def is_in_comp_data(_base_pkg_name, _replacement):
            if sanitize_base_pkg_name(_base_pkg_name,
                                      replacement) in from_data:
                return sanitize_base_pkg_name(_base_pkg_name, replacement)
            return False

        # try find modified to comparison package name in to comp. packages
        replacements = ["*",
                        "-",
                        "python-to2-",
                        "python-to3-",
                        "+python2-",
                        "+python3-",
                        "+openstack-"]
        for replacement in replacements:
            if is_in_comp_data(base_pkg_name, replacement):
                return sanitize_base_pkg_name(base_pkg_name, replacement)

    @property
    def compared_data(self):
        # base_ver is OpenStack upstream
        # comp_ver is openEuler
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
            if base_ver in EOL_PKG_SUFFIX:
                return STATUS_EOL
            elif version.parse(base_ver) == version.parse(comp_ver):
                return STATUS_OK
            elif version.parse(base_ver) > version.parse(comp_ver):
                return STATUS_OUTDATED
            elif version.parse(base_ver) < version.parse(comp_ver):
                return STATUS_MISMATCH
            else:
                return STATUS_NONE

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
            base_pkg_ver = self._base_data[base_pkg_name]['version']
            # if to comparison package and base package have pair
            if comp_pkg_name is not None:
                comp_pkg_info = self._comp_data[comp_pkg_name]
                comp_pkg_ver = comp_pkg_info['version']
                status = set_status(base_pkg_ver, comp_pkg_ver)
                pkg_info = dict(comparison_package_version=comp_pkg_ver,
                                base_package_version=base_pkg_ver,
                                status=status[1], status_id=status[0])
                if status == STATUS_OUTDATED:
                    overall_status = STATUS_OUTDATED
                paired += 1
                del self._comp_data[comp_pkg_name]
            else:
                pkg_info = dict(comparison_package_version=None,
                                base_package_version=base_pkg_ver,
                                status=STATUS_MISSING[1],
                                status_id=STATUS_MISSING[0])
            result_data[base_pkg_name] = pkg_info

        result_data = OrderedDict(sorted(result_data.items(),
                                         key=lambda x:
                                         operator.getitem(x[1], 'status_id')))
        return dict(overall_status=overall_status[1],
                    overall_status_id=overall_status[0],
                    paired=paired,
                    data=result_data)


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.option('-r', '--releases', default='22.03-LTS-SP3/train',
              type=click.STRING, required=False, show_default=True,
              help='Comma separated releases with openEuler/OpenStack '
                   'to check, for example: '
                   '22.03-LTS-SP3/wallaby,22.03-LTS-SP3/train')
@click.option('-n', '--file-name', default='index.html',
              required=False, show_default=True,
              help='Output file name of openstack version checker')
@click.option('-p', '--proxy', required=False, help='HTTP proxy url')
@click.option('-b', '--bypass-ssl-verify', default=False,
              required=False, show_default=True, is_flag=True,
              help='Bypass SSL verify')
def run(releases, file_name, proxy, bypass_ssl_verify):

    if isinstance(proxy, str) and validators.url(proxy):
        REQUESTS_ARGS.update({'proxies': {'http': proxy, 'https': proxy}})
    REQUESTS_ARGS.update({'verify': not bypass_ssl_verify})

    ver_data = {}
    openstack_ver_uri = openeuler_ver_uri = None
    try:
        releases_config = ReleasesConfig(releases)
        for release in releases_config.releases:
            _release_config = releases_config.releases_config[release]
            openstack_ver = _release_config['openstack_ver']
            openstack_ver_uri = _release_config['os_ver_uri'][0]
            openeuler_ver = _release_config['openeuler_ver']
            openeuler_ver_uri = _release_config['rpm_os_ver_uri']
            openstack_data = UpstreamVersions(
                openstack_ver_uri, openstack_ver).upstream_versions
            # openEuler vs OpenStack
            openeuler_data = None
            if openeuler_ver_uri:
                openeuler_data = RPMVersions(openeuler_ver_uri,
                                             openeuler_ver).rpm_versions
            # else:
            #     # OpenStack vs OpenStack
            #     com_openstack_uri = _release_config['os_ver_uri'][-1]
            #     openeuler_data = UpstreamVersions(
            #         com_openstack_uri).upstream_versions
            ver_data[release] = VersionsComparator(
                openstack_data, openeuler_data).compared_data
            ver_data[release]['apt'] = _release_config['os_ver_uri'] + \
                _release_config['rpm_os_ver_uri']
    except Exception as e:
        print('openstack_ver_uri: {}\nopeneuler_ver_uri: {}\n'.format(
            openstack_ver_uri, openeuler_ver_uri))
        raise e

    Renderer(ver_data, "template_os_checker.j2", DEFAULT_FILE_TYPE, file_name
             ).render()


if __name__ == '__main__':
    run()
