from collections import OrderedDict

from ParserHTML import ParserHTML
from GeneratorHTMLVersionStatus import GeneratorHTMLVersionStatus
import requests
import yaml
import re
from packaging import version
import operator

class VersionStatus:
    def __init__(self, url_releases):
        self.url_releases = url_releases

    def pair_in_debian(self, upstream_packages, debian_packages, upstream_package_name):
        prefixes = ["", "python-"]
        for prefix in prefixes:
            tmp_upstream_package_name = prefix + upstream_package_name
            if tmp_upstream_package_name in debian_packages:
                return tmp_upstream_package_name
        return 0

    def compare_versions(self, upstream_packages, debian_packages):
        print("UPSTREAM_PACKAGES: {}    DEBIAN_PACKAGES: {}".format(len(upstream_packages), len(debian_packages)))
        result = {}
        paired = 0
        for upstream_package_name, upstream_package in upstream_packages.items():
            tmp_result = {}
            upstream_package_version = upstream_package[list(upstream_package.keys())[0]]['version']
            upstream_package_href = upstream_package[list(upstream_package.keys())[0]]['href']

            debian_package_name = self.pair_in_debian(upstream_packages, debian_packages, upstream_package_name)
            if debian_package_name != 0:
                debian_package = debian_packages[debian_package_name]
                debian_package_version = debian_package[list(debian_package.keys())[0]]['version']
                debian_package_href = debian_package[list(debian_package.keys())[0]]['href']

                tmp_result['upstream_package_source'] = list(upstream_package.keys())[0]
                tmp_result['upstream_package_version'] = upstream_package_version
                tmp_result['upstream_package_href'] = upstream_package_href
                tmp_result['debian_package_source'] = list(debian_package.keys())[0]
                tmp_result['debian_package_version'] = debian_package_version
                tmp_result['debian_package_href'] = debian_package_href
                if version.parse(upstream_package_version) == version.parse(debian_package_version):
                    tmp_result['status'] = '2'
                else:
                    tmp_result['status'] = '1'
                paired += 1
                del debian_packages[debian_package_name]
            else:
                tmp_result['debian_package_source'] = "X"
                tmp_result['debian_package_version'] = "X"
                tmp_result['upstream_package_source'] = list(upstream_package.keys())[0]
                tmp_result['upstream_package_version'] = upstream_package_version
                tmp_result['status'] = '3'

            result[upstream_package_name] = tmp_result

        for debian_package_name, debian_package in debian_packages.items():
            if debian_package_name not in upstream_packages:
                tmp_result = {}
                debian_package_version = debian_package[list(debian_package.keys())[0]]['version']
                debian_package_href = debian_package[list(debian_package.keys())[0]]['href']
                tmp_result['debian_package_source'] = list(debian_package.keys())[0]
                tmp_result['debian_package_version'] = debian_package_version
                tmp_result['debian_package_href'] = debian_package_href
                tmp_result['upstream_package_source'] = "X"
                tmp_result['upstream_package_version'] = "X"
                tmp_result['status'] = '4'
                result[debian_package_name] = tmp_result

        print("PAIRED: {}".format(paired))
        sorted_result = OrderedDict(sorted(result.items(), key=lambda x: operator.getitem(x[1], 'status')))
        return sorted_result

if __name__ == '__main__':

    version_status = VersionStatus("ahoj")
    parser_html = ParserHTML("https://releases.openstack.org/", "http://buster-{}.debian.net/debian/dists/buster-{}-backports/main/source/Sources")
    generator_html = GeneratorHTMLVersionStatus()

    higher_versions_stein = parser_html.get_higher_versions(parser_html.get_upstream_versions_from_HTML("stein"))
    higher_versions_train = parser_html.get_higher_versions(parser_html.get_upstream_versions_from_HTML("train"))
    higher_versions_ussuri = parser_html.get_higher_versions(parser_html.get_upstream_versions_from_HTML("ussuri"))

    debian_versions_stein = parser_html.get_debian_versions_from_HTML("stein")
    debian_versions_train = parser_html.get_debian_versions_from_HTML("train")
    debian_versions_ussuri = parser_html.get_debian_versions_from_HTML("ussuri")

    packages_versions_data_stein = version_status.compare_versions(higher_versions_stein, debian_versions_stein)
    packages_versions_data_train = version_status.compare_versions(higher_versions_train, debian_versions_train)
    packages_versions_data_ussuri = version_status.compare_versions(higher_versions_ussuri, debian_versions_ussuri)

    packages_versions_data = {}
    packages_versions_data["stein"] = packages_versions_data_stein
    packages_versions_data["train"] = packages_versions_data_train
    packages_versions_data["ussuri"] = packages_versions_data_ussuri

    generator_html.html_file_name = "index.html"
    generator_html.generate_mainpage(packages_versions_data)



