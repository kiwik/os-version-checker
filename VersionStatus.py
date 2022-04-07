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
RPM_OS_URI_MAPPING = {
    ('20.03-LTS', '20.03-LTS-SP1', '20.09', '21.03'):
        "https://repo.openeuler.org/openEuler-{0}/EPOL/{1}/Packages/",
    ('20.03-LTS-SP2',):
        "https://repo.oepkgs.net/openEuler/rpm/openEuler-{0}/budding-openeuler"
        "/openstack/{2}/{1}/Packages/",
    ('20.03-LTS-SP3', '21.09'):
        "https://repo.openeuler.org/openEuler-{0}/EPOL/main/{1}/Packages/",
    ('22.03-LTS',):
        "https://repo.openeuler.org/openEuler-{0}/EPOL/multi_version"
        "/OpenStack/{2}/{1}/Packages/",
    ('dev-20.03-LTS', 'dev-20.03-LTS-SP1', 'dev-20.03-LTS-SP2',
     'dev-20.03-LTS-SP3', 'dev-20.03-LTS-Next',
     'dev-20.09', 'dev-21.03', 'dev-21.09',
     'dev-Mainline'):
        "http://119.3.219.20:82/openEuler:/{0}/{1}/{2}"
        "/Epol/standard_{3}/{4}/",
    ('dev-22.03-LTS',
     'dev-22.03-LTS-Next'):
        "http://119.3.219.20:82/openEuler:/{0}/{1}/{2}"
        "/Epol:/Multi-Version:/OpenStack:/{5}/standard_{3}/{4}",
}
OPENEULER_REPO_DOMAIN = "repo.openeuler.org"
RPM_119_SUB_DIR = 'noarch'
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
OPENEULER_DEFAULT_REPLACE = re.compile(r"[._]")


class ReleasesConfig:
    def __init__(self, content, arch):
        if not isinstance(content, str):
            raise RuntimeError('Input Error')
        self.releases = [r.strip() for r in content.split(',') if r]
        self.releases_config = dict()
        for release in self.releases:
            from_os_version, to_os_version = release.split('/', 1)
            self.releases_config[release] = dict()
            self.releases_config[release]['rpm_os_ver_uri'] = list()
            self.releases_config[release]['os_ver_uri'] = [
                OS_URI.format(from_os_version), ]
            # Get URL template
            for _to_version_tuple in RPM_OS_URI_MAPPING.keys():
                if to_os_version in _to_version_tuple:
                    _url = RPM_OS_URI_MAPPING.get(_to_version_tuple)
                    break
            # openstack vs openstack
            else:
                self.release_config[release]['os_ver_url'].append(
                    OS_URI.format(to_os_version))
                return

            # openstack vs 119 openEuler
            if to_os_version.startswith('dev-'):
                to_os_version = to_os_version[4:]
                _parts = to_os_version.split('-')
                # pad placeholder in URI
                _version_parts = [_parts[i] + ':'
                                  if (i < len(_parts) and
                                      to_os_version != 'Mainline')
                                  else ''
                                  for i in range(3)]
                # aarch64
                _version_parts.extend([arch, arch,
                                       from_os_version.capitalize()])
                self.releases_config[release]['rpm_os_ver_uri'].append(
                    _url.format(*_version_parts))
                # noarch
                _version_parts[-2] = RPM_119_SUB_DIR
                self.releases_config[release]['rpm_os_ver_uri'].append(
                    _url.format(*_version_parts))
            # openstack vs openEuler
            else:
                _from_os_version = from_os_version.capitalize() \
                    if OPENEULER_REPO_DOMAIN in _url else from_os_version
                self.releases_config[release]['rpm_os_ver_uri'].append(
                    _url.format(to_os_version, arch, _from_os_version))


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
            SHA_TZ = datetime.timezone(
                datetime.timedelta(hours=8),
                name='Asia/Shanghai',
            )
            utc_now = datetime.datetime.utcnow().replace(
                tzinfo=datetime.timezone.utc)
            xian_now = utc_now.astimezone(SHA_TZ)
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
    def __init__(self, _rpm_os_ver_uri_list):
        self.rpm_os_ver_uri_list = _rpm_os_ver_uri_list

    @property
    def rpm_versions(self):
        results = dict()
        for _rpm_os_ver_uri in self.rpm_os_ver_uri_list:
            r = requests.get(_rpm_os_ver_uri)
            if r.status_code != requests.codes.ok:
                raise RuntimeError('CAN NOT GET {}'.format(_rpm_os_ver_uri))
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
                "python-to2-": default_replace.replace("python-", "python2-"),
                "python-to3-": default_replace.replace("python-", "python3-"),
                "+python2-": "python2-{}".format(default_replace),
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
    if releases:
        releases_config = ReleasesConfig(releases, arch)
    ver_data = dict()
    for release in releases_config.releases:
        _release_config = releases_config.releases_config.get(release)
        from_os_uri = _release_config.get('os_ver_uri')[0]
        from_os_data = UpstreamVersions(from_os_uri).upstream_versions
        # openstack version check openEuler
        _rpm_os_ver_uri = _release_config.get('rpm_os_ver_uri')
        if _rpm_os_ver_uri:
            to_os_data = RPMVersions(_rpm_os_ver_uri).rpm_versions
        # openstack version check openstack
        else:
            to_os_uri = _release_config.get('os_ver_uri')[-1]
            to_os_data = UpstreamVersions(to_os_uri).upstream_versions

        ver_data[release] = VersionsComparator(from_os_data,
                                               to_os_data).compared_data
        ver_data[release]['apt'] = _release_config.get(
            'os_ver_uri') + _release_config.get('rpm_os_ver_uri')

    Renderer(ver_data, "template_os_checker.j2", file_type,
             file_name_os).render()


if __name__ == '__main__':
    if len(sys.argv) == 1:
        run.main(['--help'])
    else:
        run()
