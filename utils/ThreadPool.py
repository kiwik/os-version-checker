import queue
import threading
import time

from utils.utils import Logging

LOG = Logging.get_logger("ThreadPool")


class Worker:
    def __init__(self, name, task_queue):
        self.name = name
        self.task_queue = task_queue
        self.count = 0

    def _work(self):
        while True:
            task = self.task_queue.get()
            try:
                if task is None:
                    # Thread terminating
                    break

                td = task.do(self.name)
                self.count += 1
                for t in td:
                    self.task_queue.put(t)
            except Exception as e:
                # todo: Catch thread exceptions here and cleanup/skip task
                #       etc...
                LOG.error("Exception")
                LOG.exception(e)
            finally:
                self.task_queue.task_done()

    def work(self):
        self._work()


class ThreadPool:
    def __init__(self, count):
        self.count = count
        self.queue = queue.Queue()
        self.threads = []

    def add_task(self, task):
        self.queue.put(task)

    def _cleanup_workers(self):
        # Kill all worker threads and block until they do
        for i in range(0, self.count):
            self.queue.put(None)
        for t in self.threads:
            t.join()

    # Emulates queue.Queue.join() without KeyboardInterrupt immunity, which
    # the original join has
    def _join_queue(self):
        while not hasattr(self.queue, 'unfinished_tasks') \
               or self.queue.unfinished_tasks > 0:
            time.sleep(10)
        self._cleanup_workers()

    def run(self):
        for i in range(0, self.count):
            w = Worker(i, self.queue)
            t = threading.Thread(target=w.work)
            t.start()
            self.threads.append(t)

        # Block until queue is empty
        try:
            self._join_queue()
        except KeyboardInterrupt:
            LOG.info("Keyboard interrupt received, terminating.")
            # Terminate worker threads before emptying the task queue to prevent
            # them from filling it up again.
            self._cleanup_workers()
            # Empty the queue of tasks without running their logic
            while not self.queue.empty():
                LOG.debug("Emptying task queue")
                self.queue.get()
                self.queue.task_done()

        # Formally empty the queue; this shouldn't actually do anything at this
        # point
        self.queue.join()

