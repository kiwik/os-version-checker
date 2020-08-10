import sys
from collections import OrderedDict
from packaging import version
import yaml
import requests
import jinja2
import re
import operator
import click

from DockerImageVersions import DockerImageVersions
from nexusconfig import NexusConfig

OS_VER_URI = "https://releases.openstack.org/{}"
DEB_VER_URI = "http://buster-{}.debian.net/debian/dists/" \
              "buster-{}-backports/main/source/Sources"
RELEASES = ["stein", "train", "ussuri"]
STATUS_OUTDATED = ["1", "OUTDATED"]
STATUS_OK = ["2", "OK"]
STATUS_MISSING = ["3", "MISSING"]


class Renderer:
    def __init__(self, data, file_format, file_name):
        self.data = data
        self.file_format = file_format
        self.file_name = file_name

    def render(self):
        output = ""
        if "txt" == self.file_format:
            for release, pkg_vers_data in self.data.items():
                output += "Release: {}\n\n".format(release)
                output += "{:<30} {:<15} {:<15} {:<15}\n\n" \
                    .format('Package name', 'OS version', 'DEB version',
                            'Status')
                for pkg_name, pkg_info in pkg_vers_data.items():
                    output += "{:<30} {:<15} {:<15} {:<15}\n".format(
                        pkg_name,
                        pkg_info.get('upstream_package_version'),
                        str(pkg_info.get('debian_package_version')),
                        pkg_info.get('status'))
                output += "\n"
        if "html" == self.file_format:
            output = jinja2.Environment(
                loader=jinja2.FileSystemLoader('./templates/')) \
                .get_template("template.j2") \
                .render(packages_versions_data=self.data)
        # if file name is not set,
        # then file format is None and output print to stdout
        if self.file_name is None:
            print(output)
        else:
            with open(self.file_name, 'w') as f:
                f.write(output)


class DebianVersions:
    def __init__(self, release):
        self.url_deb_content = requests \
            .get(DEB_VER_URI.format(release, release)).content.decode()

    @property
    def debian_versions(self):
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


class UpstreamVersions:
    def __init__(self, release):
        self.url_os_content = requests \
            .get(OS_VER_URI.format(release)).content.decode()

    @property
    def upstream_versions(self):
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


class VersionsData:
    def __init__(self, os_data, deb_data):
        self._os_data = os_data
        self._deb_data = deb_data
        self._versions_data = self.compare_versions()

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
                return STATUS_OK
            else:
                return STATUS_OUTDATED

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
                                 status=set_status(os_pkg_ver, deb_pkg_ver)[1],
                                 status_id=
                                 set_status(os_pkg_ver, deb_pkg_ver)[0])
                paired += 1
                del self.deb_data[deb_pkg_name]
            else:
                pkg_infos = dict(debian_package_version=None,
                                 upstream_package_version=
                                 os_pkg_ver,
                                 status=STATUS_MISSING[1],
                                 status_id=STATUS_MISSING[0])
            result[os_pkg_name] = pkg_infos

        # print("UPSTREAM_PACKAGES: {}    DEBIAN_PACKAGES: {} PAIRED: {}"
        #      .format(len(self.os_data), len(self.deb_data) + paired, paired))
        return OrderedDict(sorted(
            result.items(), key=lambda x: operator.getitem(x[1], 'status_id')))

    def get_all_versions_data(self):
        return self.versions_data


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.option('-r', '--releases', is_flag=False, default=','.join(RELEASES),
              show_default=True, metavar='<releases>', type=click.STRING,
              help='Releases to check.')
@click.option('-t', '--type', default='html',
              show_default=True, help='Output file format.',
              type=click.Choice(['txt', 'html']))
@click.option('-f', '--file', required=False,
              show_default=True, help='Output file name')
@click.option('-s', '--separated', required=False, default=False, is_flag=True,
              help='If chosen, then output is in separated files.')
@click.option('-n', '--nexus-config', is_flag=False,
              metavar='<nexus-url,nexus-user,nexus-pass>', type=click.STRING,
              help='Configuration of nexus')
@click.option('-i', '--images-repository', is_flag=False,
              metavar='<repository>', type=click.STRING,
              help='Images repository')
@click.option('-t', '--tags', is_flag=False,
              metavar='<tags>', type=click.STRING,
              help='Comma separated images tags')
@click.option('-m', '--mappings', is_flag=False,
              metavar='<release:tag>', type=click.STRING,
              help='Comma separated mappings for release and tag')
@click.option('-d', '--dockerhub-url', type=click.STRING, help='Dockerhub url',
              metavar='<dockerhub-url>')
def run(releases, type, file, separated, nexus_config, images_repository, tags,
        mappings, dockerhub_url):
    releases = [r.strip() for r in releases.split(',')]
    if nexus_config or images_repository or dockerhub_url or mappings or tags:
        if nexus_config and images_repository and dockerhub_url and mappings \
                and tags:
            nexus_config = [r.strip() for r in nexus_config.split(',')]
            mappings = [r.strip() for r in mappings.split(',')]
            tags = [r.strip() for r in tags.split(',')]
            if len(nexus_config) != 3 or len(tags) < 1 or len(mappings) < 1:
                raise Exception(f"Too few values given (--nexus config: 3, "
                                f"--tags: 1, --mappings: 1, \n\tgiven: "
                                f"{len(nexus_config)}, {len(tags)}, "
                                f"{len(mappings)}")
            print(nexus_config, images_repository, dockerhub_url, mappings)
        else:
            raise Exception(f"All arguments must be filled (--nexus-config, "
                            f"--images-repository, --dockerhub-url --mappings,"
                            f" --tags),\n\tgiven: "
                            f"{nexus_config}, {images_repository}, "
                            f"{dockerhub_url}, {mappings}, {tags}")

    image_versions = DockerImageVersions(nexus_config, images_repository,
                                         tags[0], dockerhub_url,
                                         "images_versions")
    template = image_versions.kube_template
    with open('manifest.yaml', 'w') as f:
        f.write(template)
    aaaa = image_versions.images_data

    ver_data = dict()
    for release in releases:
        os_data = UpstreamVersions(release).upstream_versions
        deb_data = DebianVersions(release).debian_versions
        release_ver_data = VersionsData(os_data, deb_data)
        if separated:
            release_data = dict()
            release_data[release] = release_ver_data.get_all_versions_data()
            if file is None:
                renderer = Renderer(release_data, type, file)
            else:
                renderer = Renderer(release_data, type,
                                    "{}_{}".format(release, file))
            renderer.render()
        else:
            ver_data[release] = release_ver_data.get_all_versions_data()
    if not separated:
        renderer = Renderer(ver_data, type, file)
        renderer.render()


if __name__ == '__main__':
    if len(sys.argv) == 1:
        run.main(['--help'])
    else:
        run()
