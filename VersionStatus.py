import datetime
import os
import sys
import time
from collections import OrderedDict
from dataclasses import dataclass

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
STATUS_NONE = ["0", "NONE"]
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
                .render(data=self.data, time=datetime.datetime.utcnow())
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


@dataclass
class Image:
    name: str
    repository: str
    tag: str


class ImagesVersions:
    def __init__(self, manifest, nexus_url, repository, tag):
        if os.path.exists("manifest.yaml"):
            with open('manifest.yaml', 'r') as f:
                self._manifest = "".join(f.readlines())
        else:
            self._manifest = manifest
        self._nexus_url = nexus_url
        self._repository = repository
        self._tag = tag
        self._results_dir = 'images_versions'

    @property
    def images(self):
        return re.findall(r'image: ' + self._nexus_url + '/' +
                          self._repository + '/' + '(.*?)' + ':' +
                          self._tag + '\n', self._manifest)

    @property
    def images_data(self):
        files_counter = 0
        attempts_counter = 0
        images_count = len(self.images)
        while files_counter != images_count:
            if attempts_counter > 6:
                print("Count of attempts is bigger than 6 (25 s), "
                      "can not read all results")
                sys.exit(1)
            files_counter = 0
            for file in os.listdir(self._results_dir + "/" + self._tag):
                if file.endswith(".txt"):
                    files_counter += 1
            if files_counter != images_count:
                time.sleep(5)
                attempts_counter += 1

        images_data = dict()
        for file in os.listdir(self._results_dir + "/" + self._tag):
            image_data = dict()
            with open(os.path.join(self._results_dir + "/" + self._tag,
                                   file)) as f:
                for line in f:
                    (package, version) = line.split()
                    image_data[package] = dict(version=version)
            images_data[file.replace('.txt', '')] = image_data
        return images_data


class VersionsComparator:
    def __init__(self, base_data, to_comparison_data, show_other_versions):
        self._base_data = base_data
        self._comp_data = to_comparison_data
        self._show_other_versions = show_other_versions

    def get_pair(self, base_pkg_name, from_data):
        def sanitize_base_pkg_name(_base_pkg_name, str_to_replace):
            default_replace = _base_pkg_name.replace("_", "-")
            cases = {
                "-": default_replace,
                "python-": "python-{}".format(default_replace),
                "openstack-": default_replace.replace("openstack-", ""),
                "puppet-": default_replace.replace("puppet-", "puppet-module-")
            }
            return cases.get(str_to_replace)

        def is_in_comp_data(_base_pkg_name, _replacement):
            if sanitize_base_pkg_name(_base_pkg_name, replacement) \
                    in from_data:
                return sanitize_base_pkg_name(_base_pkg_name, replacement)
            return False

        # try find modified to comparison package name in to comp. packages
        replacements = ["-", "python-", "puppet-", "openstack-"]
        for replacement in replacements:
            if is_in_comp_data(base_pkg_name, replacement):
                return sanitize_base_pkg_name(base_pkg_name, replacement)

    @property
    def compared_data(self):
        def set_status(base_ver, comp_ver):
            if "+" in comp_ver:
                comp_ver = comp_ver.split('+')[0]
            if "~" in comp_ver:
                comp_ver = comp_ver.split('~')[0]
            if version.parse(base_ver) == version.parse(comp_ver):
                return STATUS_OK
            else:
                return STATUS_OUTDATED

        result_data = dict()
        paired = 0
        overall_status = STATUS_NONE
        for base_pkg_name, base_pkg_info in self._base_data.items():
            comp_pkg_name = self.get_pair(base_pkg_name, self._comp_data)
            base_pkg_ver = base_pkg_info.get('version')
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

        if self._show_other_versions:
            for comp_pkg_name, comp_pkg_info in self._comp_data.items():
                base_pkg_name = self.get_pair(comp_pkg_name, self._base_data)
                comp_pkg_ver = comp_pkg_info.get('version')
                if base_pkg_name is None:
                    pkg_infos = dict(comparison_package_version=comp_pkg_ver,
                                     base_package_version=None,
                                     status=STATUS_NONE[1],
                                     status_id=STATUS_NONE[0])
                result_data[comp_pkg_name] = pkg_infos

        # print("BASE_PACKAGES: {}    TO_COMPARISON_PACKAGES: {} PAIRED: {}"
        #      .format(len(self.base_data), len(self.comp_data) + paired, paired))
        result_data = OrderedDict(sorted(result_data.items(),
                                         key=lambda x:
                                         operator.getitem(x[1], 'status_id')))
        return dict(overall_status=overall_status[1],
                    overall_status_id=overall_status[0],
                    paired=paired,
                    data=result_data)


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
@click.option('-y', '--manifest', type=click.STRING, help='Jenkins kubernetes template',
              metavar='<manifest>')
@click.option('-l', '--filters', type=click.STRING, help='Comma separated filters for images',
              metavar='<release:repository:tag>')


def run(releases, type, file, separated, nexus_config, images_repository, tags,
        mappings, dockerhub_url, manifest, filters):
    releases = [r.strip() for r in releases.split(',')]
    tmp_mappings = [m.strip() for m in mappings.split(',')]
    mappings = dict()
    for m in tmp_mappings:
        mappings[m.split(':')[0]] = m.split(':')[1]
    filters = [f.strip() for f in filters.split(',')]

    # if nexus_config or images_repository or dockerhub_url or mappings or tags:
    #     if nexus_config and images_repository and dockerhub_url and mappings \
    #             and tags:
    #         nexus_config = [r.strip() for r in nexus_config.split(',')]
    #         tmp_mappings = [r.strip() for r in mappings.split(',')]
    #         mappings = dict()
    #         for m in tmp_mappings:
    #             mappings[m.split(':')[0]] = m.split(':')[1]
    #         tags = [r.strip() for r in tags.split(',')]
    #         if len(nexus_config) != 3 or len(tags) < 1 or len(mappings) < 1:
    #             raise Exception(f"Too few values given (--nexus config: 3, "
    #                             f"--tags: 1, --mappings: 1, \n\tgiven: "
    #                             f"{len(nexus_config)}, {len(tags)}, "
    #                             f"{len(mappings)}")
    #     else:
    #         raise Exception(f"All arguments must be filled (--nexus-config, "
    #                         f"--images-repository, --dockerhub-url --mappings,"
    #                         f" --tags),\n\tgiven: "
    #                         f"{nexus_config}, {images_repository}, "
    #                         f"{dockerhub_url}, {mappings}, {tags}")
    #
    # if os.path.exists("tmp_manifest.yaml"):
    #     os.remove("tmp_manifest.yaml")
    images_versions = dict()
    # for tag in tags:
    #     image_versions = DockerImageVersions(nexus_config, images_repository,
    #                                          tag, dockerhub_url,
    #                                          "images_versions")
    #     _ = image_versions.kube_template
    #     images_versions[tag.replace('^', '').replace('$', '')] = image_versions

    for filter in filters:
        dockerhub_url = filter.split(':')[0]
        images_repository = filter.split(':')[1]
        tag = filter.split(':')[2].replace('^', '').replace('$', '')
        images_versions[tag] = ImagesVersions(manifest, dockerhub_url, images_repository, tag)
        _ = images_versions[tag].images

    # if os.path.exists("manifest.yaml"):
    #     os.remove("manifest.yaml")
    # if os.path.exists("tmp_manifest.yaml"):
    #     os.rename('tmp_manifest.yaml',
    #               'manifest.yaml')
    #
    # if os.path.exists("docker-compose.yaml"):
    #     os.remove("docker-compose.yaml")
    # if os.path.exists("tmp_docker-compose.yaml"):
    #     os.rename('tmp_docker-compose.yaml',
    #               'docker-compose.yaml')

    ver_data = dict()
    for release in releases:
        release_data = dict()
        os_data = UpstreamVersions(release).upstream_versions
        deb_data = DebianVersions(release).debian_versions
        os_deb_data = VersionsComparator(os_data, deb_data, False).compared_data
        release_data["upstream-debian"] = os_deb_data
        if mappings.get(release):
            images_data = images_versions\
                .get(mappings.get(release)).images_data
            for image, image_data in images_data.items():
                deb_image_data = VersionsComparator(deb_data, image_data, True)\
                    .compared_data
                release_data["debian-" + image] = deb_image_data
        ver_data[release] = release_data

    # import json
    # with open('result.json', 'w') as fp:
    #     json.dump(ver_data, fp)
    #
    # import json
    # with open('result.json', 'r') as fp:
    #     ver_data = json.load(fp)

    Renderer(ver_data, "html", "index.html").render()


    # ver_data = dict()
    # for release in releases:
    #     os_data = UpstreamVersions(release).upstream_versions
    #     deb_data = DebianVersions(release).debian_versions
    #     os_deb_data = VersionsData(os_data, deb_data)
    #     if separated:
    #         release_data = dict()
    #         release_data[release] = os_deb_data.get_all_versions_data()
    #         if file is None:
    #             renderer = Renderer(release_data, type, file)
    #         else:
    #             renderer = Renderer(release_data, type,
    #                                 "{}_{}".format(release, file))
    #         renderer.render()
    #     else:
    #         ver_data[release] = os_deb_data.get_all_versions_data()
    # if not separated:
    #     renderer = Renderer(ver_data, type, file)
    #     renderer.render()


if __name__ == '__main__':
    if len(sys.argv) == 1:
        run.main(['--help'])
    else:
        run()
