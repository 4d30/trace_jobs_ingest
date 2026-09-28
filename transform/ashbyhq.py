#!/usr/bin/env python

from operator import methodcaller
from functools import partial
from itertools import chain, repeat
import json

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


def make_list(ats_json):
    return tuple(methodcaller('get', 'jobs', None)(ats_json))


def title(posting_record):
    return methodcaller('get', 'title', None)(posting_record)


def company_name(posting_record):
    return common.empty_company_name(posting_record)


def description(posting_record):
    return methodcaller('get', 'descriptionHtml', None)(posting_record)


def job_location_type(posting_record):
    # Hybrid Onsite Remote Null
    steps = (methodcaller('get', 'workplaceType', None),
             common.title_transform)
    return sequential(steps)(posting_record)


def url(posting_record):
    return methodcaller('get', 'jobUrl', None)(posting_record)


def date_posted(posting_record):
    dp = methodcaller('get', 'publishedAt', None)(posting_record)
    return common.convert_to_ISO8601_calendar_date('iso8601', dp)


def employment_type(posting_record):
    # Contract Fulltime Intern Parttime
    steps = (methodcaller('get', 'employmentType', None),
             methodcaller('replace', 'Intern', 'Internship'),
             common.title_transform)
    return sequential(steps)(posting_record)


def language(posting_record):
    return common.return_none(posting_record)


def industry(posting_record):
    return common.return_none(posting_record)


def _is_salary(x):
    return x['compensationType'] == 'Salary'


def _salary_value(compensation_component):
    minval = (methodcaller('get', 'minValue', None),
              common.convert_to_ISO6093,)
    minval = sequential(minval)

    maxval = (methodcaller('get', 'maxValue', None),
              common.convert_to_ISO6093,)
    maxval = sequential(maxval)

    interval = (methodcaller('get', 'interval', None),
                common.convert_to_iso8601_interval,)
    interval = sequential(interval)
    fns = (lambda x: 'QuantitativeValue',
           minval,
           maxval,
           interval,)

    keys = ('@type', 'minValue', 'maxValue', 'unitText',)
    steps = (parallel(fns),
             partial(zip, keys),
             dict)
    return sequential(steps)(compensation_component)


def _get_salary_component(posting_record):
    steps = (methodcaller('get', 'compensation', None),
             methodcaller('get', 'summaryComponents', None),
             partial(filter, _is_salary),
             common.safe_next)
    return sequential(steps)(posting_record)


def base_salary(posting_record):
    fns = (lambda x: 'MonetaryAmount',
           methodcaller('get', 'currencyCode', None),
           _salary_value,)
    keys = ('@type', 'currency', 'value',)
    steps = (_get_salary_component,
             parallel(fns),
             partial(zip, keys),
             dict)
    return sequential(steps)(posting_record)


def _postal_address(postalAddress):
    # Country field requires normalization
    country_seq = (methodcaller('get', 'addressCountry', None),
                   common.convert_to_ISO3166,)

    # Pluck components from node
    components = (lambda x: 'postalAddress',
                  methodcaller('get', 'addressLocality', None),
                  methodcaller('get', 'addressRegion', None),
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
    p_steps = (methodcaller('get', 'address', None),
               methodcaller('get', 'postalAddress', None),
               lambda x: [x],)
    primary = sequential(p_steps)
    s_steps = (methodcaller('get', 'secondaryLocations', None),
               partial(filter, bool),
               partial(map, methodcaller('get', 'address', None)),
               partial(filter, bool),
               partial(map, methodcaller('get', 'postalAddress', None)),
               partial(filter, bool),)
    secondary = sequential(s_steps)

    keys = ('@type',
            'address',)

    steps = (parallel((primary, secondary)),
             partial(filter, bool),
             chain.from_iterable,
             partial(map, _postal_address),
             partial(filter, common.is_substantial),  # rm MT records
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
