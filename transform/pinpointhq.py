#!/usr/bin/env python

import json
from operator import methodcaller
from functools import partial
from itertools import repeat
from collections import ChainMap

from .alonzo.church import sequential, parallel, safe_call
from . import common

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


def parse(response_data):
    return json.loads(response_data)


def _make_mapping(x):
    return ChainMap(*x)


def make_list(ats_json):
    return tuple(methodcaller('get', 'data', None)(ats_json))


def title(posting_record):
    return methodcaller('get', 'title', None)(posting_record)


def company_name(posting_record):
    return common.empty_company_name(posting_record)


def description(posting_record):
    return methodcaller('get', 'description', None)(posting_record)



def job_location_type(posting_record):
    # Hybrid Onsite Remote Null
    steps = (methodcaller('get', 'workplace_type', None),
             common.title_transform)
    return sequential(steps)(posting_record)


def url(posting_record):
    return methodcaller('get', 'url', None)(posting_record)


def date_posted(posting_record):
    return common.return_none(posting_record)


def employment_type(posting_record):
    # Contract Fulltime Intern Parttime Other Temporary
    steps = (methodcaller('get', 'employment_type', None),
             methodcaller('replace', 'full_time', 'fulltime'),
             methodcaller('replace', '_temp', '_temporary'),
             methodcaller('replace', 'part_time', 'parttime'),
             methodcaller('replace', 'fixed_term', 'fixedterm'),
             methodcaller('split', '_'),
             partial(map, common.title_transform),
             ','.join,)
    try:
        return sequential(steps)(posting_record)
    except Exception:
        print("pinpoint, employment type: ",
              posting_record['employment_type'])
        return common.return_none(posting_record)


def language(posting_record):
    return common.return_none(posting_record)


def industry(posting_record):
    return common.return_none(posting_record)


_salary_freq_mapping = {'day': 'P1D',
                        'hour': 'PT1H',
                        'month': 'P1M',
                        'two_weeks': 'P2W',
                        'week': 'P1W',
                        'year': 'P1Y'}


def _salary_value(posting_record):
    minValue = methodcaller('get', 'compensation_minimum', None)
    maxValue = methodcaller('get', 'compensation_maximum', None)
    unitText = sequential((methodcaller('get', 'compensation_frequency',
                                        None),
                          _salary_freq_mapping.get,))
    fns = (lambda x: 'QuantitativeValue',
           minValue,
           maxValue,
           unitText,)
    keys = ('@type', 'minValue', 'maxValue', 'unitText',)
    steps = (parallel(fns),
             partial(zip, keys),
             tuple,
             dict,)
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
    currency = methodcaller('get', 'compensation_currency', None)
    fns = (lambda x: 'MonetaryAmount',
           currency,
           _salary_value,)
    keys = ('@type',
            'currency',
            'value',)
    steps = (parallel(fns),
             partial(zip, keys),
             tuple,
             dict,)
    return sequential(steps)(posting_record)


def _postal_address(posting_record):
    # Pluck components from node

    locality_seq = (methodcaller('get', 'location', None),
                    methodcaller('get', 'city', None),)

    region_seq = (methodcaller('get', 'location', None),
                  methodcaller('get', 'province', None),)
    components = (lambda x: 'postalAddress',
                  sequential(locality_seq),
                  sequential(region_seq),
                  common.return_none,)

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
             lambda x: [x],
             partial(map, lambda x: ('Place', x,)),
             partial(map, zip, repeat(keys)),
             partial(map, tuple),
             partial(map, dict),
             common.deduplicate_dicts,
             tuple)
    job_locations = sequential(steps)(posting_record)
    return job_locations


def record_id(posting_record):
    return methodcaller('get', 'id', None)(posting_record)
