import threading


class LockedDict:
    def __init__(self):
        self.values = {}
        self.lock = threading.Lock()

    def add(self, key, val):
        with self.lock:
            # todo: name conflict
            self.values[key] = val

    def get(self, key):
        if not key in self.values:
            return None
        return self.values[key]


class LockedCounter:
    def __init__(self):
        self.value = 0
        self.lock = threading.Lock()

    def increase(self, value=1):
        with self.lock:
            self.value += value

    def set(self, value):
        with self.lock:
            self.value = value

    def get(self):
        return self.value

    def __repr__(self):
        return str(self.value)