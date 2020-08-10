import urllib.parse


def unparse(params):
    return urllib.parse.urlunparse(params)


def parse(url):
    scheme = "http"
    if not url.startswith(scheme):
        url = f"{scheme}://{url.lstrip('/')}"

    unparsed = urllib.parse.urlparse(url)
    return unparsed.netloc, unparsed.path