from time import time, sleep


class RatelimitControl:
    def __init__(self, name='', limit=60):
        self._limit = limit
        self._lock = []
        self._name = name

    def _expires(self):
        now = time()
        self._lock = [date for date in self._lock if date > now]

    def lock(self, num_operations):
        # print(f'=> locklen={len(self._lock)}')
        # print(self._lock)
        while num_operations > 0:
            self._expires()
            for i in range(num_operations):
                if len(self._lock) < self._limit:
                    num_operations -= 1
                    self._lock.append(time() + 60)
                else:
                    print(f'=> ratelimit {self._name} sleeping... total locks={len(self._lock)}')
                    sleep(5)
