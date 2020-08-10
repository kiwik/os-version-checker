import re

from utils import url
from utils.utils import Logging, DATA_TYPES
from requests.auth import HTTPBasicAuth
from clients.UrlRepositories import NexusUrls, RegistryUrls
import requests
import abc

LOG = Logging.get_logger("NexusClient")


class Service(abc.ABC):
    def __init__(self, url, auth):
        self.auth = auth
        self.urls = url

    def _do_request(self, func, url, headers=None, json=None, data=None):
        try:
            res = func(url, auth=self.auth, headers=headers, json=json,
                       data=data, timeout=3600)
            # todo: proper handling (exception throwing probably?)
            """
            error body for failed put requests:
            {
               "errors":[
                  {
                     "code":"MANIFEST_INVALID",
                     "message":"manifest invalid",
                     "detail":"Corrupt manifest jv-test/debian-binary-cron: No content to map due to end-of-input at [Source: (org.sonatype.nexus.blobstore.PerformanceLoggingInputStream); line: 1, column: 0]"
                  }
               ]
            }

            requests.exceptions.ConnectionError
            """
            if res.status_code == 200:
                # LOG.debug(f"HTTP response: {res.status_code}, {url}")
                return res
            if res.status_code == 201:
                # LOG.debug(f"HTTP response: {res.status_code}, {url}")
                return res
            elif res.status_code == 202:
                # LOG.debug(f"HTTP response: {res.status_code}, {url}")
                return res
            else:
                # LOG.error(f"HTTP response: {res.status_code}, {url}")
                return None
        except requests.exceptions.ConnectionError as e:
            print("Connection error")
            print(e)
            return None

    def _get(self, url, headers=None):
        return self._do_request(requests.get, url, headers)

    def _post(self, url, headers=None):
        return self._do_request(requests.post, url, headers)

    def _head(self, url, headers=None):
        return self._do_request(requests.head, url, headers)

    def _put(self, url, headers=None, json=None, data=None):
        return self._do_request(requests.put, url, headers, json=json,
                                data=data)


class RegistryService(Service):
    def test_connection(self):
        url = self.urls.status()
        if not self._get(url):
            # todo: break execution
            LOG.error(f"Failed to connect to nexus: {url}")
        else:
            LOG.info(f"Connection to nexus established successfully: {url}")


class NexusService(Service):
    def test_connection(self, repository):
        url = self.urls.repository(repository)
        if not self._get(url):
            # todo: break execution
            LOG.info("Failed to connect to repository: {}".format(url))
        else:
            LOG.info("Connection to repository established successfully: {}".format(url))


class ComponentService(RegistryService):
    def _page(self, repository, page_limit=None):
        continuation_token = None
        page_count = 0
        while True:
            url = self.urls.component_list(continuation_token, repository)

            res = self._get(url)
            page_count += 1

            data = res.json()
            continuation_token = data.get("continuationToken", None)

            for item in data.get("items", []):
                yield item

            if page_limit and page_count >= page_limit:
                print("Page limit reached: {}/{}").format(page_count, page_limit)
                break

            if not continuation_token:
                break

    def _check_filter(self, item, filters):
        for name, value in filters.items():
            component_value = item.get(name)
            m = re.search(value, component_value)
            if not m:
                return False
        return True

    def page(self, repository, continuation_token, filters={}):
        url = self.urls.component_list(continuation_token, repository)
        #LOG.debug(f"url: {url}")
        res = self._get(url)
        return res

    def list(self, repository, filters={}, page_limit=None):
        if filters:
            # todo: allowed filters validation?
            for component in self._page(repository, page_limit=page_limit):
                if self._check_filter(component, filters):
                    yield component
        else:
            for component in self._page(repository, page_limit=page_limit):
                yield component


class ManifestService(NexusService):
    def get(self, repository, path):
        headers = {
            'Accept': DATA_TYPES.MANIFEST
        }
        url = self.urls.manifest_get(repository, path)
        return self._get(url, headers=headers).json()

    def get_pathless(self, repository, name, tag):
        headers = {
            'Accept': DATA_TYPES.MANIFEST
        }
        url = self.urls.manifest_get_pathless(repository, name, tag)
        return self._get(url, headers=headers)

    def exists(self, repository, name, tag):
        headers = {
            'Accept': DATA_TYPES.MANIFEST
        }
        url = self.urls.manifest_get_pathless(repository, name, tag)
        return self._head(url, headers=headers)

    # todo: model data structure (dict for now, can be expanded to full model
    #       if needed)
    def create(self, repository, manifest, name, tag):
        manifest_header = {
            'Content-Type': DATA_TYPES.MANIFEST
        }
        url = self.urls.manifest_create(repository, name, tag)
        return self._put(url, headers=manifest_header, json=manifest)


class BlobService(NexusService):
    def exists(self, repository, digest):
        url = self.urls.blob_exists(repository, digest)
        return self._head(url)

    def _setup_blob_location(self, repository):
        url = self.urls.blob_uploads(repository)
        return self._post(url)

    def _create(self, repository, digest, data, headers):
        location_res = self._setup_blob_location(repository)
        location = location_res.headers.get('location')
        url = self.urls.blob_upload(repository, location, digest)
        return self._put(url, headers=headers, data=data)

    def create(self, repository, digest, data, content_type=None):
        headers = None if not content_type else {
            'Content-Type': content_type
        }
        return self._create(repository, digest, data, headers)

    def get(self, repository, name, digest, accepts=None):
        headers = None if not accepts else {
            'Content-Type': accepts
        }
        url = self.urls.blob_get(repository, name, digest)
        return self._get(url, headers)


class NexusClient:
    def __init__(self, registry_url, nexus_url, username, password):
        nexus_host, nexus_endpoint = url.parse(nexus_url)
        registry_host, registry_endpoint = url.parse(registry_url)

        auth = HTTPBasicAuth(username, password)

        nexus_urls = NexusUrls(nexus_host, nexus_endpoint)
        registry_urls = RegistryUrls(registry_host, registry_endpoint)

        self._components = ComponentService(registry_urls, auth)

        self._manifest = ManifestService(nexus_urls, auth)
        self._blobs = BlobService(nexus_urls, auth)

    def tags(self):
        tags = set()
        for component in self.components.list():
            tags.add(component.get('version'))
        return list(tags)

    @property
    def blobs(self):
        return self._blobs

    @property
    def components(self):
        return self._components

    @property
    def manifests(self):
        return self._manifest

    def test_connections(self, repository):
        # Tests nexus connection
        self._components.test_connection()
        # Tests repository connection
        self._manifest.test_connection(repository)

        # No need to test blobs connection, because it's the same as manifests
        # ne repo and one nexus service need be tested at this time, leaving
        # this as a reminder:
        #           self._blobs.test_connection(repository)
