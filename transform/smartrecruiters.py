#!/usr/bin/env python

import json
from operator import methodcaller, attrgetter, lshift, not_
from functools import partial
from collections import ChainMap

from . import common
from .alonzo.church import sequential, parallel, safe_call

"""
    @context
    @type
    title
    description
    jobLocationType
    url
    datePosted
    employmentType
    industry
    inLanguage
    hiringOrganization.name
    jobLocation[].address.addressLocality
    jobLocation[].address.addressRegion
    jobLocation[].address.addressCountry
    baseSalary.value.minValue
    baseSalary.value.maxValue
    baseSalary.currency
    baseSalary.value.unitText
    identifier[].name
    identifier[].value
"""


import urllib3
from urllib3.util import Retry

retry_strategy = Retry(
    total=5,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"]
)

http = urllib3.PoolManager(
    maxsize=20,
    num_pools=50,
    block=True,
    retries=retry_strategy
)

http_get = partial(http.request, 'GET')


def parse(response_data):
    return json.loads(response_data)


def _make_mapping(x):
    return ChainMap(*x)


def make_list(ats_json):
    detail_steps = (methodcaller('get', 'content', None),
                    partial(map, methodcaller('get', 'ref', None)),
                    partial(map, http_get),
                    partial(filter, lambda x: x.status == 200),
                    partial(map, attrgetter('data')),
                    partial(map, methodcaller('decode', 'utf-8')),
                    partial(map, json.loads),
                    tuple,)
    return sequential(detail_steps)(ats_json)


def title(posting_record):
    return methodcaller('get', 'name', None)(posting_record)


def company_name(posting_record):
    keys = ('@type', 'name',)
    steps = (methodcaller('get', 'company', None),
             methodcaller('get', 'name', None),)
    steps = sequential(steps)
    values = (lambda x: 'Organization',
              steps)
    steps = (parallel(values),
             partial(zip, keys),
             dict,)
    return sequential(steps)(posting_record)


def description(posting_record):
    steps = (methodcaller('get', 'jobAd', None),
             methodcaller('get', 'sections', None),
             methodcaller('get', 'jobDescription', None),
             methodcaller('get', 'text', None),)
    return sequential(steps)(posting_record)


_job_location_mapping = {0: 'Null',
                         4: 'Onsite',
                         2: 'Hybrid',
                         1: 'Remote',
                         6: 'Onsite,Hybrid',
                         5: 'Onsite,Remote',
                         3: 'Hybrid,Remote',
                         7: 'Onsite,Hybrid,Remote'
                         }


def job_location_type(posting_record):
    # Hybrid Onsite Remote Null

    is_hybrid = sequential((methodcaller('get', 'location', None),
                            methodcaller('get', 'hybrid', None),))

    is_remote = sequential((methodcaller('get', 'location', None),
                            methodcaller('get', 'remote', None),))

    is_onsite = (is_hybrid,
                 is_remote,)

    is_onsite = sequential((parallel(is_onsite),
                            any,
                            not_,))

    fns = (is_onsite,
           is_hybrid,
           is_remote,)
    shifts = (2, 1, 0)
    steps = (parallel(fns),
             partial(map, int),
             partial(zip, shifts),
             partial(map, lambda x: lshift(x[1], x[0])),
             sum,
             _job_location_mapping.get,
             )
    return sequential(steps)(posting_record)


def url(posting_record):
    return methodcaller('get', 'postingUrl', None)(posting_record)


def date_posted(posting_record):
    steps = (methodcaller('get', 'releasedDate', None),
             partial(common.convert_to_ISO8601_calendar_date, 'iso8601'),)
    return sequential(steps)(posting_record)


def employment_type(posting_record):
    # Contract Fulltime Intern Parttime Other Temporary
    steps = (methodcaller('get', 'typeOfEmployment', None),
             methodcaller('get', 'label', None),
             methodcaller('replace', 'Intern', 'internship'),
             methodcaller('split', '_'),
             partial(map, common.title_transform),
             partial(safe_call, ','.join),
             )
    return sequential(steps)(posting_record)


def language(posting_record):
    steps = (methodcaller('get', 'language', None),
             methodcaller('get', 'code', None),
             )
    return sequential(steps)(posting_record)


def industry(posting_record):
    steps = (methodcaller('get', 'industry', None),
             methodcaller('get', 'label', None),
             )
    return sequential(steps)(posting_record)


def base_salary(posting_record):
    """
    `salary` field is taken to mean it's a salary and
    therefore has an annual interval. This can be overridden if an
    interval is specfied (eg: $20 -$25 / hr) and then the interval
    is what is specified.

    If no interval is specified and the min value is less than 20000,
    then I don't believe it's an annual salary and I don't know what
    the interval is, so we drop it.

    Accept salary if:

    1. Explicit time unit is present (/hr, etc.)
    OR
    2. Parsed numeric value is ≥ 20,000

    Otherwise reject.

    """
    return common.empty_salary(posting_record)


def _postal_address(posting_record):
    # Pluck components from node

    locality_seq = (methodcaller('get', 'location', None),
                    methodcaller('get', 'city', None),)
    region_seq = (methodcaller('get', 'location', None),
                  methodcaller('get', 'region', None),)
    country_seq = (methodcaller('get', 'location', None),
                   methodcaller('get', 'country', None),
                   common.convert_to_ISO3166,)
    components = (lambda x: 'postalAddress',
                  sequential(locality_seq),
                  sequential(region_seq),
                  sequential(country_seq),)

    # Keys corresponding to the values above
    keys = ('@type',
            'addressLocality',
            'addressRegion',
            'addressCountry',)

    safe_strip = partial(safe_call, methodcaller('strip'))
    # the entire process
    proc = (parallel(components),
            partial(map, safe_strip),
            partial(zip, keys),
            dict)
    return sequential(proc)(posting_record)


def job_location(posting_record):
    keys = ('@type',
            'address',)
    steps = (_postal_address,
             lambda x: ('Place', x,),
             partial(zip, keys),
             tuple,
             dict,
             lambda x: (x,))
    job_locations = sequential(steps)(posting_record)
    return job_locations


def record_id(posting_record):
    return methodcaller('get', 'id', None)(posting_record)
