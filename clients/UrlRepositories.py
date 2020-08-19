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
    def image_list(self, continuation_token, repository):
        endpoint = self._build_path("v1/components")
        query = self._build_query(
            repository=repository,
            continuationToken=continuation_token
        )
        return self._build(endpoint, query=query)

    def status(self):
        endpoint = self._build_path("v1", "status")
        return self._build(endpoint)

