import abc
from utils import url


class UrlRepository(abc.ABC):
    def __init__(self, host, root, schema="http"):
        self.schema = schema
        self.host = host
        self._root = root.strip("/")

    def _build_query(self, **kwargs):
        return "&".join(
            f"{key}={value}" for key, value in kwargs.items() if value)

    def _build(self, hierarchy, query=""):
        h = hierarchy

        params = (
            self.schema,
            self.host,
            h,
            "",
            query,
            ""
        )
        return url.unparse(params)

    def _build_path(self, *args, cap=False):
        stripped = [arg.strip("/") for arg in args]
        elements = [self._root, *stripped]

        if cap:
            # This is a little trick to append a trailing forward slash
            # using a single join - it technically adds an empty string after a
            # delimiting forward slash
            elements.append("")

        path = "/".join(elements)
        return path


class RegistryUrls(UrlRepository):
    def component_list(self, continuation_token, repository):
        endpoint = self._build_path("v1/components")
        query = self._build_query(
            repository=repository,
            continuationToken=continuation_token
        )
        return self._build(endpoint, query=query)

    def status(self):
        endpoint = self._build_path("v1", "status")
        return self._build(endpoint)


class NexusUrls(UrlRepository):
    def manifest_get(self, repository, path):
        endpoint = self._build_path("repository", repository, path)
        return self._build(endpoint)

    def manifest_get_pathless(self, repository, name, tag):
        endpoint = self._build_path("repository", repository, "v2", name, "manifests", tag)
        return self._build(endpoint)

    def manifest_create(self, repository, name, tag):
        endpoint = self._build_path(
            "repository", repository, "v2", name, "manifests", tag
        )
        return self._build(endpoint)

    def blob_exists(self, repository, digest):
        endpoint = self._build_path(
            "repository", repository, "v2", repository, "blobs", digest
        )
        return self._build(endpoint)

    def blob_uploads(self, repository):
        endpoint = self._build_path(
            "repository", repository, "v2", repository, "blobs", "uploads",
            cap=True
        )
        return self._build(endpoint)

    def blob_upload(self, repository, location, digest):
        endpoint = self._build_path("repository", repository, location)
        query = self._build_query(digest=digest)
        return self._build(endpoint, query)

    def blob_get(self, repository, name, digest):
        endpoint = self._build_path(
            "repository", repository, "v2", name, "blobs", digest
        )
        return self._build(endpoint)

    def repository(self, repository):
        endpoint = self._build_path(
            "repository", repository, cap=True
        )
        return self._build(endpoint)
