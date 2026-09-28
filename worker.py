#!/usr/bin/env python

import os
import time
import logging
import traceback
from logging.handlers import SysLogHandler
from concurrent.futures import ThreadPoolExecutor
from itertools import repeat
from collections import deque

import urllib3
import ssl
from urllib3.util import Retry

from . import cafs
from . import datumizer
from . import transform
from .callbus import CallBusClient


RETRY = Retry(total=5,
 backoff_factor=4.0,
 status_forcelist=[429, 500, 502, 503, 504],
 allowed_methods=["HEAD", "GET", "OPTIONS"]
)


def create_logger(worker_id):
    prov_logger = logging.getLogger(f'cagg.{worker_id}')
    prov_logger.setLevel(logging.INFO)
    
    # 2. Use LOG_LOCAL1 to keep it separate from system logs
    # Address is usually '/dev/log' on Linux
    handler = SysLogHandler(address='/dev/log', facility=SysLogHandler.LOG_LOCAL0)
    
    # 3. Clean format: [Time] [Level] [Message]
    formatter = logging.Formatter('%(asctime)s | %(message)s')
    handler.setFormatter(formatter)
    prov_logger.addHandler(handler)
    return prov_logger


class Worker:
    def __init__(self, socket_path):
        self.http = urllib3.PoolManager(maxsize=10,
                                        num_pools=20,
                                        block=True,
                                        retries=RETRY)
        self.etag_client = CallBusClient(socket_path)
        self.prov_logger = create_logger(id(self))
        self.bg_pool = ThreadPoolExecutor(max_workers=5)
        self.user_agent = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/147.0.0.0 Safari/537.36")
        self.cafs_root = os.getenv('CAFS_ROOT')


    def process(self, adapter_name, url, stored_etag):
        module = transform.get_adapter(adapter_name)
        headers = {'User-Agent': self.user_agent,
                   'X-Service-Name': 'TRACE Bot',
                   'X-Service-Contact': 'support@kaleh.net'}
        #stored_etag = self.etag_client.call('get', adapter_name, url)
        if stored_etag is not None:
            headers['If-None-Match'] = stored_etag
        try:
            resp = self.http.request('GET', url, headers=headers)
        except urllib3.exceptions.MaxRetryError:
            # with open("exceptions.log", "a") as f:
            #     f.write(traceback.format_exc())
            return None
        except urllib3.exceptions.SSLError:
            # with open("exceptions.log", "a") as f:
            #     f.write(traceback.format_exc())
            return None
        except ssl.SSLCertVerificationError:
            # with open("exceptions.log", "a") as f:
            #     f.write(traceback.format_exc())
            return None

        if resp.status == 304:
            #print(304, url)
            return None
        if resp.status == 200:
            new_etag = resp.headers.get('ETag', None)
            if new_etag is not None:
                self.etag_client.call('set', adapter_name, url, new_etag)
            board_data = resp.data.decode('utf-8')
            try:
                board_obj = module.parse(board_data)
            except:
                return None    
            records = module.make_list(board_obj)
            objs = zip(records, repeat(adapter_name), repeat(url))
            deque(self.bg_pool.map(self.process_record, objs), maxlen=0)
        return None


    def process_record(self, obj):
        try:
            record, adapter_name, url = obj
            canon = datumizer.canonize(adapter_name, record)
            content_hash = cafs.put(canon, cafs_root=self.cafs_root)
            provenance = datumizer.formalize(content_hash, adapter_name, record, url)
            self.prov_logger.info(provenance)
        except Exception:
            with open("exceptions.log", "a") as f:
                print(adapter_name, file=f)
                print(url, file=f)
                print(record, file=f)
                print(traceback.format_exc(), file=f)
                print('====================================', file=f)
            return None

    def shutdown(self):
        self.etag_client.close()
        self.http.clear()
        for handler in self.prov_logger.handlers[:]:
            handler.close()
            self.prov_logger.removeHandler(handler)
        self.bg_pool.shutdown(wait=True)


def create_worker(socket_path):
    return Worker(socket_path)
