import json
from contextvars import ContextVar

_config = ContextVar("config", default={})


def _load_config(name):
    if not _config.get().get(name):
        with open('./config.json') as file:
            data = json.load(file)
            _config.set(data)


def get_config(name) -> str:
    _load_config(name)

    return _config.get().get(name)


def write_config(key, value):
    _load_config(key)

    config = _config.get()
    config[key] = value
    _config.set(config)

    with open('./config.json', 'w') as file:
        json.dump(config, file)


