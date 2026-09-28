#!/usr/bin/env python

import os
import time
import dbm.gnu as gdbm
from operator import itemgetter, methodcaller
from itertools import chain, repeat, compress, islice # noqa
from concurrent.futures import ProcessPoolExecutor
from collections import deque
import subprocess
import atexit
import random
import traceback

from tqdm import tqdm

from . import transform
from .worker import create_worker

_worker = None

SOCK_PATH = os.getenv('CALLBUS_SOCK')
ATS_ROOT = os.getenv('ATS_ROOT')


def load_urls(adapter_name):
    file_name = 'board_urls.csv'
    file_path = os.path.join(ATS_ROOT, adapter_name, file_name)
    with open(file_path, 'r') as handle:
        urls = map(methodcaller('strip'), handle)
        name__url = zip(repeat(adapter_name), urls)
        yield from name__url


def get_stores():
    modules = transform.get_adapters()
    names = map(itemgetter(0), modules)
    names = tuple(names)
    paths = map(lambda x: f'{ATS_ROOT}/{x}/etag_cache.gdbm', names)
    handles = map(gdbm.open, paths, repeat('cf'))
    store = zip(names, handles)
    return dict(store)


def add_etag(stores, name__url):
    name, url = name__url
    return (name, url, stores[name].get(url, None))


def url_generator():
    stores = get_stores()
    adapters = transform.get_adapters()
    adapter_names = map(itemgetter(0), adapters)
    name__url_tuples = map(load_urls, adapter_names)
    name__url = chain.from_iterable(name__url_tuples)
    name__url__etag = tuple(map(add_etag, repeat(stores), name__url))
    name__url__etag = list(name__url__etag)
    random.shuffle(name__url__etag)        
    for store in stores.values():
        store.close()
    return name__url__etag


def init_worker():
    global _worker
    try:
        _worker = create_worker(SOCK_PATH)
        atexit.register(_worker.shutdown)
    except Exception as e:
        print(f"Worker init failed: {e}")
        raise e


def run_task(task_data):
    try:
        adapter_name, url, etag = task_data
        _worker.process(adapter_name, url, etag)
        return 0
    except Exception:
        with open("exceptions.log", "a") as handle:
            handle.write(traceback.format_exc())
            handle.write("\n\n")
        return 1
        

def main():
    import sys
    errors = False
    data = url_generator()
    etag_proc = subprocess.Popen([sys.executable, '-m', 'trace_jobs_ingest.etag_service', SOCK_PATH])
    while not os.path.exists(SOCK_PATH):
        time.sleep(0.1)
    time.sleep(2)
    if etag_proc.poll() is not None:
        with open("exceptions.log", "a") as f:
            f.write("etag_service exited early\n")
        sys.exit(1)
    try:
        with ProcessPoolExecutor(max_workers=6,
                                 initializer=init_worker) as executor:
            results = executor.map(run_task, data, chunksize=36)
            errors = sum(results) > 0
    except Exception:
        with open("exceptions.log", "a") as f:
            f.write(traceback.format_exc())
        errors = True
    finally:
        etag_proc.terminate()
        if errors:
            sys.exit(1)


if __name__ == '__main__':
    main()
