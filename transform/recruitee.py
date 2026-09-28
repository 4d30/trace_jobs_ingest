#!/usr/bin/env python

import json
from operator import methodcaller, lshift
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
    return tuple(methodcaller('get', 'offers', None)(ats_json))


def title(posting_record):
    return methodcaller('get', 'title', None)(posting_record)


def company_name(posting_record):
    keys = ('@type', 'name',)
    branches = (lambda x: 'Organization',
                methodcaller('get', 'company_name', None),)
    steps = (parallel(branches),
             partial(zip, keys),
             dict,)
    return sequential(steps)(posting_record)


def description(posting_record):
    steps = (methodcaller('get', 'translations', None),
             methodcaller('values'),
             iter,
             next,
             methodcaller('get', 'description', None),)
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
    fns = (methodcaller('get', 'on_site', None),
           methodcaller('get', 'hybrid', None),
           methodcaller('get', 'remote', None),)
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
    return methodcaller('get', 'careers_url', None)(posting_record)


def date_posted(posting_record):
    steps = (methodcaller('get', 'updated_at', None),
             partial(common.convert_to_ISO8601_calendar_date, 'recr'),)
    return sequential(steps)(posting_record)


def employment_type(posting_record):
    # Contract Fulltime Intern Parttime Other Temporary
    steps = (methodcaller('get', 'employment_type_code', None),
             methodcaller('replace', 'full_time', 'fulltime'),
             methodcaller('replace', 'part_time', 'parttime'),
             methodcaller('replace', 'fixed_term', 'fixedterm'),
             methodcaller('split', '_'),
             partial(map, common.title_transform),
             ','.join,)
    return sequential(steps)(posting_record)


def language(posting_record):
    steps = (methodcaller('get', 'translations', None),
             methodcaller('keys'),
             ','.join,)
    return sequential(steps)(posting_record)


def industry(posting_record):
    return common.return_none(posting_record)


_salary_freq_mapping = {'day': 'P1D',
                        'hour': 'PT1H',
                        'month': 'P1M',
                        'two_weeks': 'P2W',
                        'week': 'P1W',
                        'year': 'P1Y'}


def _salary_value(posting_record):
    min_value = (methodcaller('get', 'salary', None),
                 methodcaller('get', 'min', None),
                 common.convert_to_ISO6093,)
    min_value = sequential(min_value)

    max_value = (methodcaller('get', 'salary', None),
                 methodcaller('get', 'max', None),
                 common.convert_to_ISO6093,)
    max_value = sequential(max_value)

    unit_text = (methodcaller('get', 'salary', None),
                 methodcaller('get', 'period', None),
                 _salary_freq_mapping.get,)
    unit_text = sequential(unit_text)
    fns = (lambda x: 'QuantitativeValue',
           min_value,
           max_value,
           unit_text,)
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
    currency = (methodcaller('get', 'salary', None),
                methodcaller('get', 'currency', None),)
    currency = sequential(currency)
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


def _get_locations(posting_record):
    return methodcaller('get', 'locations', None)(posting_record)


def _postal_address(location_element):
    # Pluck components from node

    locality_seq = (methodcaller('get', 'city', None),)

    region_seq = (methodcaller('get', 'province', None),)
    country_seq = (methodcaller('get', 'country', None),
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
    return sequential(proc)(location_element)


def job_location(posting_record):
    keys = ('@type',
            'address',)
    steps = (_get_locations,
             partial(map, _postal_address),
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
