import os
import re
import threading
import queue
import time

from clients.v2 import NexusClient
from nexusconfig import NexusConfig
from threads.structs import LockedCounter, LockedDict
from utils.ThreadPool import ThreadPool
from utils.utils import Logging

LOG = Logging.get_logger("NexusClient")
Logging.set_level('info')
image_counter = LockedCounter()
images = LockedDict()


class Component:
    def __init__(self):
        self._lock = threading.Lock()
        self._name = None
        self._version = None
        self._repository = None

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        with self._lock:
            self._name = value

    @property
    def version(self):
        return self._version

    @version.setter
    def version(self, value):
        with self._lock:
            self._version = value

    @property
    def repository(self):
        return self._repository

    @repository.setter
    def repository(self, value):
        with self._lock:
            self._repository = value


class ClientRepository:
    instance = None

    def __init__(self, src_nexus):
        self.src_nexus = src_nexus

    @staticmethod
    def get():
        # todo: if not initialized, fail
        return ClientRepository.instance

    @staticmethod
    def setup(src_nexus):
        ClientRepository.instance = ClientRepository(src_nexus)


class ImagesListContext:
    instance = None

    def __init__(self, src_repo, src_tag):
        self.src_repo = src_repo
        self.src_tag = src_tag

    @staticmethod
    def get():
        # todo: if not initialized, fail
        return ImagesListContext.instance

    @staticmethod
    def setup(src_repo, src_tag):
        ImagesListContext.instance = ImagesListContext(
            src_repo, src_tag
        )


class ThreadTask:
    def __init__(self):
        self.clients = ClientRepository.get()
        self.context = ImagesListContext.get()

    # todo: prototype debug outputs
    def debug(self, message):
        LOG.debug(f"{message}")


class ComponentListTask(ThreadTask):
    def __init__(self, repository, continuation_token=None, filters={}):
        super().__init__()
        self.repository = repository
        self.continuation_token = continuation_token
        self.filters = filters

    # todo: filtering should really be done on the service
    def _check_filters(self, item):
        for name, value in self.filters.items():
            item_value = item.get(name)
            m = re.search(value, item_value)
            if not m:
                return False
        return True

    def do(self, thread_name):
        res = self.clients.src_nexus.components.page(
            self.repository, self.continuation_token
        )
        data = res.json()

        # Threaded paging: Add another list if another page exists
        # (continuation token is present)
        ct = data.get("continuationToken", None)
        if ct:
            new_task = ComponentListTask(self.repository, ct, self.filters)
            yield new_task

        # For each item, return a new task to download the assets for that task
        items = data.get('items', [])
        image_counter.increase(len(items))
        for item in items:
            if self._check_filters(item):
                LOG.info('Item name: {}, version: {}'.format(item.get('name'), item.get('version')))
                component = Component()
                component.name = item.get('name').replace(
                    f"{item.get('repository')}/", "")
                component.version = item.get('version')
                component.repository = item.get('repository')
                images.add(item.get('name'), component)


class ThreadedImageList:
    def __init__(self, source):
        self.queue = queue.Queue()

        self.source_nexus = NexusClient(
            source.registry,
            source.nexus,
            source.username,
            source.password
        )
        self.thread_count = 12
        ClientRepository.setup(self.source_nexus)

    def _test_connections(self, src_repo):
        LOG.info("Testing source connections")
        self.source_nexus.test_connections(src_repo)

    def get_images(self, repository, tag, image_regex=None):
        self._test_connections(repository)
        count = self.thread_count

        filters = {
            "version": re.compile(tag)
        }
        if image_regex:
            filters['name'] = re.compile(image_regex)

        ImagesListContext.setup(repository, tag)

        task = ComponentListTask(repository, None, filters)

        thread_pool = ThreadPool(count)
        thread_pool.add_task(task)
        thread_pool.run()


class DockerImageVersions:
    def __init__(self, nexus_config, repository, tag, dockerhub_url,
                 results_dir):
        self._nexus_config = NexusConfig(nexus_config[0]+"service/rest/",
                                         nexus_config[0], nexus_config[1],
                                         nexus_config[2])
        self._repository = repository
        self._tag = tag
        self._dockerhub_url = dockerhub_url
        self._results_dir = results_dir
        ThreadedImageList(self._nexus_config).get_images(
            self._repository, self._tag, None)
        self._images_list = images.values

    @property
    def kube_template(self):
        kube_template = ["", """apiVersion: v1
    kind: Pod
    metadata:
      name: os-version-checker
      namespace: os-version-checker
      labels:
        name: os-version-checker
    spec:
      volumes:
      - name: os-version-checker-storage
        emptyDir: {}
      restartPolicy: Never
      containers:
      - name: os-version-checker
        image: dockerhub.ultimum.io/ultimum-internal/os-version-checker:latest
        volumeMounts:
        - name: os-version-checker-storage
          mountPath: /opt
        imagePullPolicy: Always
        command: ["/bin/sh", "-c"] 
        args: ["sleep infinity"]
        tty: true"""]
        container_template = """      - name: {}
        image: {}/{}/{}:{}
        volumeMounts:
        - name: os-version-checker-storage
          mountPath: /opt
        imagePullPolicy: Always
        command: ["/bin/sh", "-c"] 
        args:
        - dpkg-query -W --showformat '${{Status}} ${{Package}} ${{Version}}\\n' $(dpkg -l | tail -n +6 | tr -s ' ' | cut -d ' ' -f2) | grep ^install | cut -d ' ' -f4,5 > /opt/{}.txt
        tty: true"""

        LOG.info(f"Components: {image_counter.get()}, "
                 f"filtered: {len(images.values)}")
        for name in self._images_list:
            component = self._images_list.get(name)
            kube_template.append(container_template.format(component.name,
                                                           self._dockerhub_url,
                                                           component.repository,
                                                           component.name,
                                                           component.version,
                                                           component.name))
        return "\n".join(kube_template)

    @property
    def images_data(self):
        files_counter = 0
        # images_count = len(self._images_list)
        images_count = 2
        while files_counter != images_count:
            files_counter = 0
            for file in os.listdir(self._results_dir):
                files_counter += 1 if file.endswith(".txt") else files_counter
            time.sleep(5) if files_counter != images_count else time.sleep(0)

        images_data = dict()
        for file in os.listdir(self._results_dir):
            image_data = dict()
            with open(os.path.join(self._results_dir, file)) as f:
                for line in f:
                    (package, version) = line.split()
                    image_data[package] = dict(version=version)
            images_data[file.replace('.txt', '')] = image_data
        return images_data

