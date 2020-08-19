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
# image_counter = LockedCounter()
# images = LockedDict()


class Component:
    def __init__(self):
        self._lock = threading.Lock()
        self._name = None
        self._tag = None
        self._repository = None

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        with self._lock:
            self._name = value

    @property
    def tag(self):
        return self._tag

    @tag.setter
    def tag(self, value):
        with self._lock:
            self._tag = value

    @property
    def repository(self):
        return self._repository

    @repository.setter
    def repository(self, value):
        with self._lock:
            self._repository = value


class ClientRepository:
    instance = None
    image_counter = None
    images = None

    def __init__(self, src_nexus):
        self.src_nexus = src_nexus

    @staticmethod
    def get():
        return ClientRepository.instance

    @staticmethod
    def images():
        return ClientRepository.images

    @staticmethod
    def images_counter():
        return ClientRepository.image_counter

    @staticmethod
    def setup(src_nexus):
        ClientRepository.instance = ClientRepository(src_nexus)
        ClientRepository.images = LockedDict()
        ClientRepository.image_counter = LockedCounter()


class ImageListContext:
    instance = None

    def __init__(self, src_repo, src_tag):
        self.src_repo = src_repo
        self.src_tag = src_tag

    @staticmethod
    def get():
        # todo: if not initialized, fail
        return ImageListContext.instance

    @staticmethod
    def setup(src_repo, src_tag):
        ImageListContext.instance = ImageListContext(
            src_repo, src_tag
        )


class ThreadTask:
    def __init__(self):
        self.client = ClientRepository.get()
        self.context = ImageListContext.get()

    # todo: prototype debug outputs
    def debug(self, message):
        LOG.debug(f"{message}")


class ImageListTask(ThreadTask):
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
        res = self.client.src_nexus.images.page(
            self.repository, self.continuation_token
        )
        data = res.json()

        # Threaded paging: Add another list if another page exists
        # (continuation token is present)
        ct = data.get("continuationToken", None)
        if ct:
            new_task = ImageListTask(self.repository, ct, self.filters)
            yield new_task

        # For each item, return a new task to download the assets for that task
        items = data.get('items', [])
        self.client.image_counter.increase(len(items))
        for item in items:
            if self._check_filters(item):
                LOG.info('Item name: {}, version: {}'.format(item.get('name'), item.get('version')))
                image = Component()
                image.name = item.get('name').replace(
                    f"{item.get('repository')}/", "")
                image.tag = item.get('version')
                image.repository = item.get('repository')
                self.client.images.add(item.get('name'), image)


class ThreadedImageList:
    def __init__(self, source):
        self.queue = queue.Queue()

        self.source_nexus = NexusClient(
            source.registry,
            source.username,
            source.password
        )
        self.thread_count = 12
        ClientRepository.setup(self.source_nexus)
        self.images = ClientRepository.images
        self.image_count = ClientRepository.image_counter

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

        ImageListContext.setup(repository, tag)

        task = ImageListTask(repository, None, filters)

        thread_pool = ThreadPool(count)
        thread_pool.add_task(task)
        thread_pool.run()

        return self.images, self.image_count


class DockerImageVersions:
    def __init__(self, nexus_config, repository, tag_regex, dockerhub_url,
                 results_dir):
        self._nexus_config = NexusConfig(nexus_config[0],
                                         nexus_config[1],
                                         nexus_config[2])
        self._repository = repository
        self._tag_regex = tag_regex
        self._dockerhub_url = dockerhub_url
        self._results_dir = results_dir
        self._images, self._image_counter = ThreadedImageList(
            self._nexus_config).get_images(self._repository, self._tag_regex,
                                           None)
        self._images = self._images.values

    @property
    def tag(self):
        return self._tag_regex.replace('^', '').replace('$', '')

    @property
    def kube_template(self):
        docker_compose = ["""version: '3'
volumes:
  os-version-checker-storage:
services:
  os-version-checker-build:
    build: .
    image: os-version-checker
    user: root
    volumes:
      - "os-version-checker-storage:/opt"
  os-version-checker:
    image: os-version-checker
    user: root
    volumes:
      - "os-version-checker-storage:/opt"
    entrypoint: /bin/sh -c
    command: ["sleep 1h"]
    depends_on:
      - os-version-checker-build"""]
        docker_compose_cont = """  {}:
    image: {}/{}/{}:{}
    user: root
    working_dir: /opt/app
    entrypoint: /bin/bash -c
    command: ["./get_image_versions.sh {} {}"]
    volumes:
      - "os-version-checker-storage:/opt"
    depends_on:
      - os-version-checker"""
        kube_template = ["""apiVersion: v1
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
      privileged: true
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
        securityContext:
          privileged: true
        command: ["/bin/sh", "-c"] 
        args:
        - ./get_image_versions.sh {} {}
        tty: true"""
        LOG.info(f"Images: {self._image_counter.get()}, "
                 f"filtered: {len(self._images)}")
        template = []
        dtemplate = []
        for name in self._images:
            component = self._images.get(name)
            template.append(container_template.format(component.name,
                                                      self._dockerhub_url,
                                                      component.repository,
                                                      component.name,
                                                      component.tag,
                                                      component.name,
                                                      component.tag))
            dtemplate.append(docker_compose_cont.format(component.name,
                                                       self._dockerhub_url,
                                                       component.repository,
                                                       component.name,
                                                       component.tag,
                                                       component.name,
                                                       component.tag))

        if os.path.isfile("tmp_manifest.yaml"):
            with open("tmp_manifest.yaml", "a+") as f:
                f.write("\n".join(template))
                result = f.readlines()
        else:
            kube_template.append("\n".join(template))
            with open("tmp_manifest.yaml", "w+") as f:
                f.write("\n".join(kube_template))
                result = f.readlines()

        if os.path.isfile("tmp_docker-compose.yaml"):
            with open("tmp_docker-compose.yaml", "a+") as f:
                f.write("\n".join(dtemplate))
                result = f.readlines()
        else:
            docker_compose.append("\n".join(dtemplate))
            with open("tmp_docker-compose.yaml", "w+") as f:
                f.write("\n".join(docker_compose))
                result = f.readlines()

        return result

    @property
    def images_data(self):
        files_counter = 0
        images_count = len(self._images_list)
        # images_count = 2
        while files_counter != images_count:
            files_counter = 0
            for file in os.listdir(self._results_dir + "/" + self.tag):
                files_counter += 1 if file.endswith(".txt") else files_counter
            time.sleep(5) if files_counter != images_count else time.sleep(0)

        images_data = dict()
        for file in os.listdir(self._results_dir + "/" + self.tag):
            image_data = dict()
            with open(os.path.join(self._results_dir + "/" + self.tag, file)) as f:
                for line in f:
                    (package, version) = line.split()
                    image_data[package] = dict(version=version)
            images_data[file.replace('.txt', '')] = image_data
        return images_data

