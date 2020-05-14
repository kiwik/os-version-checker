import re
import urllib.request
import itertools
import requests
from packaging import version
import yaml


class ParserHTML:
    def __init__(self, url_releases_upstream, url_releases_debian):
        self.url_releases_upstream = url_releases_upstream
        self.url_releases_debian = url_releases_debian

    def get_html_content(self, release):
        url = self.url_releases_upstream + release + "/"
        return urllib.request.urlretrieve(url, "{}.html".format(release))

    def get_upstream_versions_from_HTML(self, release):
        url = self.url_releases_upstream + release + "/"
        html = requests.get(url)
        content = html.content.decode()
        hrefs = re.findall('https://.*\.tar\.gz', content)
        results = {}

        for href in hrefs:
            tmp = href.split("/")
            name = tmp[3]
            package = tmp[4]
            version = package[package.rfind('-') + 1:package.rfind('.tar')]
            if not name in results:
                packages = {}
                tmp = {}
                tmp["version"] = version
                tmp["href"] = href
                packages[package] = tmp
                results[name] = packages
            else:
                if not package in results[name]:
                    tmp = {}
                    tmp["version"] = version
                    tmp["href"] = href
                    results[name][package] = tmp
        return results

    def get_debian_versions_from_HTML(self, release):
        url = self.url_releases_debian.format(release, release)
        print(url)
        html = requests.get(url)
        packages_yamls = html.content.decode().split('\n\n')
        packages_yamls = [x.replace(": @", ": ") for x in packages_yamls if x != '']
        results = {}
        for package_yaml in packages_yamls:
            tmp = yaml.safe_load(package_yaml)
            name = tmp.get("Package")
            package = tmp.get("Package") + str(tmp.get("Version"))
            version = re.search('([\d]+:)?([^-]+)([-~+].+)?', str(tmp.get("Version"))).group(2)
            # print(version)

            # version = re.search('([\d]+:)?([^-]*)(~rc[\d]+)?([-~+]?.*)?',str(tmp.get("Version"))).group(2)
            # if "+dfsg" in version:
            #     version = version.split('+dfsg')[0]
            # if "~bpo" in version:
            #     version = version.split('~bpo')[0]
            # tmp_version = re.match('(.*)(~)(rc[\d]+)([+]*.*)', version)
            # if tmp_version:
            #     version = tmp_version.group(1) + ".0" + tmp_version.group(3)
            packages = {}
            tmp_result = {}
            tmp_result["version"] = version
            tmp_result["href"] = tmp.get("Vcs-Browser")
            packages[package] = tmp_result

            results[name] = packages

            # print("     {}    {}".format(name, results[name]))
        return results


    def get_higher_versions(self, versions):
        results = {}
        for name, packages in versions.items():
            higher_version = list(packages.keys())[0]
            for package in packages:
                if version.parse(packages[higher_version]["version"]) < version.parse(packages[package]["version"]):
                    higher_version = packages[package]
            tmp_result = {}
            tmp_result[higher_version] = packages[higher_version]
            results[name] = tmp_result
            # print("NAME: {}     PACKAGE: {}".format(name, results[name]))
        return results


