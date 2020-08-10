import logging
import sys


class DATA_TYPES:
    BINARY = "application/octet-stream"
    IMAGE = "application/vnd.docker.container.image.v1+json"
    MANIFEST = "application/vnd.docker.distribution.manifest.v2+json"


class Logging:
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    @staticmethod
    def get_logger(name):
        log = logging.getLogger(name)
        log.addHandler(Logging.handler)
        return log

    @staticmethod
    def set_level(level_name):
        level = logging.getLevelName(level_name.upper())
        LOG = Logging.get_logger(__name__)
        LOG.info(f"Setting logging level to '{level_name}' ({level})")
        for name in logging.root.manager.loggerDict.keys():
            log = logging.getLogger(name)
            log.setLevel(level)