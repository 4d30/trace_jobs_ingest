#!/usr/bin/env python

import json
from operator import methodcaller, gt, mul
from functools import partial
from itertools import chain, repeat

from .alonzo.church import sequential, parallel, safe_call, branch
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
    identifier[].name
    identifier[].value
"""


def parse(response_data):
    return json.loads(response_data)


def make_list(ats_json):
    return tuple(methodcaller('get', 'jobs')(ats_json))


def title(posting_record):
    return methodcaller('get', 'title', None)(posting_record)


def company_name(posting_record):
    keys = ('@type', 'name',)
    values = (lambda x: 'Organization',
              methodcaller('get', 'company_name', None),)
    steps = (parallel(values),
             partial(zip, keys),
             dict)
    return sequential(steps)(posting_record)


def description(posting_record):
    return methodcaller('get', 'content', None)(posting_record)


def job_location_type(posting_record):
    # Hybrid Onsite Remote Null
    return common.return_none(posting_record)


def url(posting_record):
    return methodcaller('get', 'absolute_url', None)(posting_record)


def date_posted(posting_record):
    dp = methodcaller('get', 'updated_at', None)(posting_record)
    return common.convert_to_ISO8601_calendar_date('iso8601', dp)


def employment_type(posting_record):
    # Contract Fulltime Intern Parttime Other Temporary
    return common.return_none(posting_record)


def language(posting_record):
    return methodcaller('get', 'language')(posting_record)


def industry(posting_record):
    return common.return_none(posting_record)


def _a_in_b(a, b):
    return a in b


def _is_hourly(x):
    steps = (methodcaller('get', 'pay_input_ranges', None),
             partial(map, methodcaller('get', 'title', None)),
             lambda x: any(('hour' in y.lower() for y in x)),)
    return sequential(steps)(x)


def _20k_gt_minValue(x):
    min_steps = (methodcaller('get', 'pay_input_ranges', None),
                 partial(map, methodcaller('get', 'min_cents', None)),
                 partial(map, mul, repeat(0.01)),
                 min,
                 common.convert_to_ISO6093,
                 partial(gt, 20000),)
    return sequential(min_steps)(x)


def pay_input_range_is_filled(posting_record):
    steps = (methodcaller('get', 'pay_input_ranges', None),
             bool,)
    return sequential(steps)(posting_record)


def _quantitative_value(posting_record):
    min_steps = (methodcaller('get', 'pay_input_ranges', None),
                 partial(map, methodcaller('get', 'min_cents', None)),
                 partial(map, mul, repeat(0.01)),
                 min,
                 common.convert_to_ISO6093,)
    min_fn = sequential(min_steps)

    max_steps = (methodcaller('get', 'pay_input_ranges', None),
                 partial(map, methodcaller('get', 'max_cents', None)),
                 partial(map, mul, repeat(0.01)),
                 max,
                 common.convert_to_ISO6093,)
    max_fn = sequential(max_steps)

    unit_text = branch(_is_hourly,
                       partial(safe_call, lambda x: 'PT1H'),
                       branch(_20k_gt_minValue,
                              partial(safe_call, lambda x: None),
                              partial(safe_call, lambda x: 'P1Y')))
    value_fns = (lambda x: 'QuantitativeValue',
                 min_fn,
                 max_fn,
                 unit_text,)
    keys = ('@type',
            'minValue',
            'maxValue',
            'unitText',)
    steps = (parallel(value_fns),
             partial(zip, keys),
             dict)
    return branch(pay_input_range_is_filled,
                  sequential(steps),
                  common.empty_salary_value)(posting_record)


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

    currency_steps = (methodcaller('get', 'pay_input_ranges', None),
                      iter,
                      next,
                      methodcaller('get', 'currency_type', None),)
    fns = (lambda x: "MonetaryAmount",
           branch(pay_input_range_is_filled,
                  sequential(currency_steps),
                  common.return_none,),
           _quantitative_value,)
    keys = ('@type', 'currency', 'value',)
    steps = (parallel(fns),
             partial(zip, keys),
             dict)
    return sequential(steps)(posting_record)


def _postal_address(postalAddress):
    # Pluck components from node

    locality_seq = (methodcaller('get', 'addressLocality', None),
                    methodcaller('title'),)
    region_seq = (methodcaller('get', 'addressRegion', None),)
    country_seq = (methodcaller('get', 'addressCountry', None),
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
    return sequential(proc)(postalAddress)


def job_location(posting_record):
    primary = (methodcaller('get', 'location', None),
               methodcaller('get', 'name', None),
               lambda x: [x],)
    primary = sequential(primary)
    secondary = (methodcaller('get', 'offices', None),
                 partial(map, methodcaller('get', 'location', None)),
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
