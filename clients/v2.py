import re
import requests
import abc
from utils import url
from utils.utils import Logging
from requests.auth import HTTPBasicAuth
from clients.UrlRepositories import RegistryUrls

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


class RegistryService(Service):
    def test_connection(self):
        url = self.urls.status()
        if not self._get(url):
            # todo: break execution
            LOG.error(f"Failed to connect to nexus: {url}")
        else:
            LOG.info(f"Connection to nexus established successfully: {url}")


class ImageService(RegistryService):
    def _page(self, repository, page_limit=None):
        continuation_token = None
        page_count = 0
        while True:
            url = self.urls.image_list(continuation_token, repository)
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
        url = self.urls.image_list(continuation_token, repository)
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


class NexusClient:
    def __init__(self, registry_url, username, password):
        registry_host, registry_endpoint = url.parse(registry_url)

        auth = HTTPBasicAuth(username, password)

        registry_urls = RegistryUrls(registry_host, registry_endpoint)

        self._images = ImageService(registry_urls, auth)

    def tags(self):
        tags = set()
        for image in self.images.list():
            tags.add(image.get('version'))
        return list(tags)

    @property
    def images(self):
        return self._images

    def test_connections(self, repository):
        # Tests nexus connection
        self._images.test_connection()