#!/usr/bin/env python

import json
from operator import methodcaller
from functools import partial
from itertools import repeat
from collections import ChainMap

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
 x  jobLocation[].address.addressLocality
 x  jobLocation[].address.addressRegion
 x  jobLocation[].address.addressCountry
 x  baseSalary.value.minValue
 x  baseSalary.value.maxValue
 x  baseSalary.currency
 x  baseSalary.value.unitText
    identifier[].name
    identifier[].value
"""

def parse(response_data):
    return json.loads(response_data)


def _make_mapping(x):
    return ChainMap(*x)


def make_list(ats_json):
    cmp_steps = (methodcaller('get', 'name', None),
                 lambda x: [x],
                 partial(zip, ['company']),
                 dict,
                 repeat,
                 )
    cmp_fn = sequential(cmp_steps)
    jobs_fn = methodcaller('get', 'jobs', None)
    proc_steps = (parallel((cmp_fn, jobs_fn,)),
                  lambda x: zip(x[0], x[1]),
                  partial(map, _make_mapping),
                  tuple,
                  )
    proc = sequential(proc_steps)
    return proc(ats_json)


def title(posting_record):
    return methodcaller('get', 'title', None)(posting_record)


def company_name(posting_record):
    keys = ('@type', 'name',)
    values = (lambda x: 'Organization',
              methodcaller('get', 'company', None),)
    steps = (parallel(values),
             partial(zip, keys),
             dict)
    return sequential(steps)(posting_record)


def description(posting_record):
    return methodcaller('get', 'description', None)(posting_record)


def job_location_type(posting_record):
    # Hybrid Onsite Remote Null Temporary
    # telecommute bool doesn't provide enough information to map
    # to Remote or Hybrid, so we provide both interpretations.
    steps = (methodcaller('get', 'remoteStatus', None),
             branch(bool,
                    lambda x: "Remote,Hybrid",
                    lambda x: "Onsite"),)
    return sequential(steps)(posting_record)


def url(posting_record):
    return methodcaller('get', 'url', None)(posting_record)


def date_posted(posting_record):
    return methodcaller('get', 'published_on', None)(posting_record)


def employment_type(posting_record):
    # Contract FullTime Intern PartTime Other Temporary
    steps = (methodcaller('get', 'employment_type', None),
             branch(bool,
                    lambda x: x,
                    lambda x: None),
             common.title_transform)
    return sequential(steps)(posting_record)


def language(posting_record):
    return common.return_none(posting_record)


def industry(posting_record):
    return common.return_none(posting_record)


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


def _postal_address(location_value):
    # Pluck components from node
    locality_seq = (methodcaller('get', 'city', None),
                    branch(bool,
                           lambda x: x,
                           lambda x: None,),)
    region_seq = (methodcaller('get', 'region', None),
                  branch(bool,
                         lambda x: x,
                         lambda x: None,),)
    country_seq = (methodcaller('get', 'countryCode', None),)
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
    return sequential(proc)(location_value)


def _location_is_list(location_record):
    return isinstance(location_record, list)


def job_location(posting_record):
    keys = ('@type',
            'address',)

    steps = (methodcaller('get', 'locations', None),
             branch(_location_is_list,
                    lambda x: x,
                    lambda x: [x]),
             partial(map, _postal_address),
             partial(map, lambda x: ('Place', x,)),
             partial(map, zip, repeat(keys)),
             partial(map, tuple),
             partial(map, dict),
             common.deduplicate_dicts,
             list)
    job_locations = sequential(steps)(posting_record)
    return job_locations


def record_id(posting_record):
    return methodcaller('get', 'shortcode', None)(posting_record)
