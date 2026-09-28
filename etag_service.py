#!/usr/bin/env python

import os
import sys
import dbm.gnu as gdbm
from operator import itemgetter
from itertools import repeat

from . import transform
from . import callbus

ATS_ROOT = os.getenv('ATS_ROOT')

def get_stores():
    modules = transform.get_adapters()
    names = map(itemgetter(0), modules)
    names = tuple(names)
    paths = map(lambda x: f'{ATS_ROOT}/{x}/etag_cache.gdbm', names)
    handles = map(gdbm.open, paths, repeat('cf'))
    store = zip(names, handles)
    return dict(store)


STORES = None

def exists(store, key):
    db = STORES[store]
    return key.encode() in db

def get(store, key):
    db = STORES[store]
    return db.get(key.encode(), None)

def set(store, key, value):
    db = STORES[store]
    db[key.encode()] = value
    return True

def delete(store, key):
    db = STORES[store]
    try:
        del db[key.encode()]
        return True
    except KeyError:
        return False

handlers = {
    "exists": exists,
    "get": get,
    "set": set,
    "delete": delete,
}

def main():
    try:
        global STORES
        STORES = get_stores()
        if len(sys.argv) > 1:
            socket_path = sys.argv[1]
        else:
            socket_path = os.getenv('CALLBUS_SOCK')
        callbus.run(socket_path, handlers)
    except Exception:
        with open("exceptions.log", "a") as handle:
            handle.write(traceback.format_exc())
            handle.write("\n\n")
        sys.exit(1)

if __name__ == "__main__":
    print('etag service running...')
    main()
