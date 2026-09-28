#!/usr/bin/env python

import json
from operator import methodcaller
from functools import partial
from itertools import repeat, chain

from .alonzo.church import sequential, parallel

from . import common

"""
    @context
    @type
 x  title
 x  description
 x  jobLocationType
 x  url
 x  datePosted
 x  employmentType
 x  industry
 x  inLanguage
 x  hiringOrganization.name
 x  jobLocation[].address
    jobLocation[].address.addressLocality
    jobLocation[].address.addressRegion
    jobLocation[].address.addressCountry
 x  baseSalary.value.minValue
 x  baseSalary.value.maxValue
 x  baseSalary.currency
 x  baseSalary.value.unitText
 x  identifier[].name
 x  identifier[].value
"""


def parse(response_data):
    return json.loads(response_data)


def _is_list(x):
    return isinstance(x, list)


def make_list(ats_json):
    return tuple(ats_json)


def title(posting_record):
    return methodcaller('get', 'text', None)(posting_record)


def company_name(posting_record):
    return common.empty_company_name(posting_record)


def description(posting_record):
    return methodcaller('get', 'description', None)(posting_record)



def job_location_type(posting_record):
    steps = (methodcaller('get', 'workplaceType', None),
             common.title_transform,)
    return sequential(steps)(posting_record)


def url(posting_record):
    return methodcaller('get', 'hostedUrl', None)(posting_record)


def date_posted(posting_record):
    steps = (methodcaller('get', 'createdAt', None),
             partial(common.convert_to_ISO8601_calendar_date, 'lever'),
             )
    return sequential(steps)(posting_record)


def employment_type(posting_record):
    return common.return_none(posting_record)


def language(posting_record):
    return common.return_none(posting_record)


def industry(posting_record):
    return common.return_none(posting_record)


def _a_in_b(a, b):
    return a in b


_unittext_mapping = {'bi-week-salary': 'P2W',
                     'per-day-wage': 'P1D',
                     'per-hour-wage': 'PT1H',
                     'per-month-salary': 'P1M',
                     'per-year-salary': 'P1Y',
                     'semi-month-salary': 'P0.5M'}


def _salary_value_fn(posting_record):
    min_value_steps = (methodcaller('get', 'salaryRange', None),
                       methodcaller('get', 'min', None),)
    min_value = sequential(min_value_steps)
    max_value_steps = (methodcaller('get', 'salaryRange', None),
                       methodcaller('get', 'max', None),)
    max_value = sequential(max_value_steps)

    unittext_value_steps = (methodcaller('get', 'salaryRange', None),
                            methodcaller('get', 'interval', None),
                            _unittext_mapping.get,)
    unittext_value = sequential(unittext_value_steps)
    fns = (lambda x: 'QuantitativeValue',
           min_value,
           max_value,
           unittext_value,)
    keys = ('@type', 'minValue', 'maxValue', 'unitText',)
    steps = (parallel(fns),
             partial(zip, keys),
             dict,)
    return sequential(steps)(posting_record)


def _salary_currency(posting_record):
    steps = (methodcaller('get', 'salaryRange', None),
             methodcaller('get', 'currency', None),)
    return sequential(steps)(posting_record)


def base_salary(posting_record):
    fns = (lambda x: 'MonetaryAmount',
           _salary_currency,
           _salary_value_fn,)
    keys = ('@type', 'currency', 'value',)
    steps = (parallel(fns),
             partial(zip, keys),
             dict,)
    return sequential(steps)(posting_record)


def job_location(posting_record):
    primary = (methodcaller('get', 'categories', None),
               methodcaller('get', 'location', None),
               lambda x: [x],)
    primary = sequential(primary)
    secondary = (methodcaller('get', 'categories', None),
                 methodcaller('get', 'allLocations', None),
                 partial(filter, bool),
                 tuple,)
    secondary = sequential(secondary)
    keys = ('@type',
            'address',)
    steps = (parallel((primary, secondary)),
             partial(filter, bool),
             chain,
             chain.from_iterable,
             partial(map, lambda x: ('Place', x)),
             partial(map, zip, repeat(keys)),
             partial(map, tuple),
             partial(map, dict),
             common.deduplicate_dicts,
             tuple)
    return sequential(steps)(posting_record)


def record_id(posting_record):
    return methodcaller('get', 'id', None)(posting_record)
