#!/usr/bin/env python


from operator import methodcaller
from functools import partial
from itertools import repeat

from xmltodict import parse as xml_parse

from .alonzo.church import sequential, parallel, branch
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
    jobLocation[].address
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
    return xml_parse(response_data)


def _is_list(x):
    return isinstance(x, list)


def make_list(ats_json):
    steps = (methodcaller('get', 'rss', None),
             methodcaller('get', 'channel', None),
             methodcaller('get', 'item', None),
             branch(_is_list,
                    lambda x: tuple(x),
                    lambda x: (x,)),)
    data = sequential(steps)(ats_json)
    if data is None:
        return tuple()
    else:
        return data


def title(posting_record):
    return methodcaller('get', 'title', None)(posting_record)


def company_name(posting_record):
    keys = ('@type', 'name',)
    branches = (lambda x: 'Organization',
                sequential((methodcaller('get', 'company', None),
                            methodcaller('get', 'name', None),)),)
    steps = (parallel(branches),
             partial(zip, keys),
             partial(filter, common.is_substantial),
             dict)
    return sequential(steps)(posting_record)


def description(posting_record):
    return methodcaller('get', 'description', None)(posting_record)


def job_location_type(posting_record):
    return common.return_none(posting_record)


def url(posting_record):
    return methodcaller('get', 'link', None)(posting_record)


def date_posted(posting_record):
    steps = (methodcaller('get', 'pubDate', None),
             partial(common.convert_to_ISO8601_calendar_date, 'crelate'),
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


def base_salary(posting_record):
    return common.empty_salary(posting_record)


def _conform_country(location_machine_record):
    return {
        k: common.convert_to_ISO3166(v) if 'Country' in k else v
        for k, v in location_machine_record.items()
    }


def job_location(posting_record):
    value_steps = (methodcaller('get', 'crelate:location', None),
                   lambda x: [x],
                   tuple,)
    value_fn = sequential(value_steps)
    keys = ('@type',
            'address',)
    steps = (value_fn,
             partial(map, lambda x: ('Place', x)),
             partial(map, zip, repeat(keys)),
             partial(map, tuple),
             partial(map, dict),
             common.deduplicate_dicts,
             tuple)
    return sequential(steps)(posting_record)


def record_id(posting_record):
    return methodcaller('get', 'crelate:jobnumber', None)(posting_record)
