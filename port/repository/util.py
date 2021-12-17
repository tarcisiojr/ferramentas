import datetime
import inspect
from time import sleep


DATETIME_FORMAT = '%Y-%m-%d %H:%M'


def _get_key():
    return datetime.datetime.now().strftime(DATETIME_FORMAT)


def _to_datetime(key):
    return datetime.datetime.strptime(key, DATETIME_FORMAT)


class RatelimitControl:
    def __init__(self, name='', limit=60):
        self._limit = limit
        self._lock = _to_datetime(_get_key())
        self._count = limit
        self._name = name

    def _expires(self):
        key_datetime = _to_datetime(_get_key())
        if key_datetime > self._lock:
            self._count = self._limit
            self._lock = _to_datetime(_get_key())

    def lock(self, num_operations):
        while num_operations > 0:
            self._expires()

            dec = min(num_operations, self._count)
            num_operations -= dec
            self._count -= dec

            if num_operations > 0:
                print(f'=> ratelimit -> restante={num_operations} / key={self._lock} / call={inspect.stack()[2].function}')
                sleep(5)

