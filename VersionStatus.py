import datetime
import gzip
import os
import sys
import time
import yaml
import requests
import jinja2
import re
import operator
import click
from collections import OrderedDict
from os import path
from packaging import version
import htmlmin

OS_VER_URI = "https://releases.openstack.org/{}"
DEB_OS_VER_URI = "http://buster-{}.debian.net/debian/dists/buster-{}-backports/main/source/Sources"
DEB_ALL_VER_URI = "https://packages.debian.org/stable/allpackages?format=txt.gz"
STATUS_NONE = ["0", "NONE"]
STATUS_OUTDATED = ["1", "OUTDATED"]
STATUS_OK = ["2", "OK"]
STATUS_MISSING = ["3", "MISSING"]


class Renderer:
    def __init__(self, data, template, file_format, file_name):
        self.data = data
        self.file_format = file_format
        self.file_name = file_name
        self.template = template

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
                .get_template(self.template) \
                .render(data=self.data, time=datetime.datetime.utcnow())
        # if file name is not set,
        # then file format is None and output print to stdout
        if self.file_name is None:
            print(output)
        else:
            with open(self.file_name, 'w') as f:
                # minified = htmlmin.minify(output, remove_empty_space=True)
                # f.write(minified)
                f.write(output)


class DebianVersions:
    def __init__(self, release):
        self.url_deb_content = requests \
            .get(DEB_OS_VER_URI.format(release, release)).content.decode()
        # self.url_deb_all_content = gzip.decompress(
        #     requests.get(DEB_ALL_VER_URI).content).decode()

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
        # for line in self.url_deb_all_content.splitlines():
        #     if re.match('^.*\([^\(\)]*\)',line):
        #         pkg_name = line.split(' ')[0]
        #         pkg_ver = line.split(' ')[1].replace('(', '').replace(')', '')
        #         pkg_info = dict(version=pkg_ver)
        #         results[pkg_name] = pkg_info
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
            pkg_ver = pkg_full_name[
                      pkg_full_name.rfind('-') + 1:pkg_full_name.rfind('.tar')]
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


class ImagesVersions:
    def __init__(self, manifest, nexus_url, repository, tag):
        with open(manifest, 'r') as f:
            self._manifest = "".join(f.readlines())
        self._nexus_url = nexus_url
        self._repository = repository
        self._tag = tag
        self._results_dir = 'images_versions'

    @property
    def images(self):
        return re.findall(r'image: ' + self._nexus_url + '/' +
                          self._repository + '/' + '(.*?)' + ':' +
                          self._tag + '\n', self._manifest)

    # get all images data with tag and with compared versions
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
            overall_status = STATUS_OK
            with open(os.path.join(self._results_dir + "/" + self._tag,
                                   file)) as f:
                for line in f:
                    package, *versions = line.split()
                    if len(versions) == 2:
                        image_data[package] = dict(
                            comparison_package_version=versions[0],
                            base_package_version=versions[1],
                            status=STATUS_OUTDATED[1],
                            status_id=STATUS_OUTDATED[0])
                        overall_status = STATUS_OUTDATED
                    elif len(versions) == 1:
                        if not image_data.get(package):
                            image_data[package] = dict(
                                comparison_package_version=versions[0],
                                base_package_version=versions[0],
                                status=STATUS_OK[1], status_id=STATUS_OK[0])
                    else:
                        print("Too few values to unpack.")
                        sys.exit(1)
            images_data[file.replace('.txt', '')] = dict(
                overall_status=overall_status[1],
                overall_status_id=overall_status[0], paired=len(image_data),
                data=image_data)
        return images_data


class VersionsComparator:
    def __init__(self, base_data, to_comparison_data):
        self._base_data = base_data
        self._comp_data = to_comparison_data

    @staticmethod
    def get_pair(base_pkg_name, from_data):
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

        # print("BASE_PACKAGES: {}    TO_COMPARISON_PACKAGES: {} PAIRED: {}"
        #      .format(len(self.base_data), len(self.comp_data)+paired,paired))
        result_data = OrderedDict(sorted(result_data.items(),
                                         key=lambda x:
                                         operator.getitem(x[1], 'status_id')))
        return dict(overall_status=overall_status[1],
                    overall_status_id=overall_status[0],
                    paired=paired,
                    data=result_data)


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.option('-r', '--releases', is_flag=False, metavar='<releases>',
              type=click.STRING, help='Comma separated releases to check')
@click.option('-t', '--file-type', default='html',
              show_default=True, help='Output file format',
              type=click.Choice(['txt', 'html']))
@click.option('-n', '--file-name-os', required=False, show_default=True,
              help='Output file name of openstack version checker')
@click.option('-i', '--file-name-img', required=False, show_default=True,
              help='Output file name of images version checker')
@click.option('-f', '--filters', type=click.STRING,
              help='Comma separated filters for images',
              metavar='<release:repository:tag>')
@click.option('-y', '--manifest', type=click.STRING,
              help='Jenkins kubernetes template file path',
              metavar='<manifest>')
def run(releases, file_type, file_name_os, file_name_img, filters, manifest):
    if not file_name_os:
        file_name_os = "os_index.html"
    if not file_name_img:
        file_name_img = "img_index.html"
    if filters or manifest:
        if filters and manifest:
            if not path.exists(manifest):
                print("Path to manifest does not exist")
                sys.exit(1)
            filters = [f.strip() for f in filters.split(',')]

            images_versions = dict()
            ver_data = dict()
            for f in filters:
                dockerhub_url = f.split(':')[0]
                images_repository = f.split(':')[1]
                tag = f.split(':')[2].replace('^', '').replace('$', '')
                images_versions[tag] = ImagesVersions(manifest, dockerhub_url,
                                                      images_repository, tag)
                _ = images_versions[tag].images
                images_data = images_versions.get(tag).images_data
                release_data = dict()
                for image, deb_image_data in images_data.items():
                    release_data[image] = deb_image_data
                ver_data[tag] = release_data

            Renderer(ver_data, "template_image_checker.j2", file_type,
                     file_name_img).render()
        else:
            print("If one of values (filters, mappings, manifest-path) "
                  "is specified, than all must be entered.")
            sys.exit(1)

    if releases:
        releases = [r.strip() for r in releases.split(',')]
        ver_data = dict()
        for release in releases:
            release_data = dict()
            os_data = UpstreamVersions(release).upstream_versions
            deb_data = DebianVersions(release).debian_versions
            os_deb_data = VersionsComparator(os_data, deb_data).compared_data
            release_data["git:" + release + " - apt:debian"] = os_deb_data
            ver_data[release] = release_data
        Renderer(ver_data, "template_os_checker.j2", file_type,
                 file_name_os).render()


if __name__ == '__main__':
    if len(sys.argv) == 1:
        run.main(['--help'])
    else:
        run()
