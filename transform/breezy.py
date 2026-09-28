#!/usr/bin/env python

from operator import methodcaller, itemgetter, lt, eq, not_
from functools import partial
from itertools import chain, repeat
import json

from . import common
from .alonzo.church import sequential, parallel, safe_call, branch

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


def make_list(ats_json):
    return tuple(ats_json)


def title(posting_record):
    return methodcaller('get', 'name', None)(posting_record)


def company_name(posting_record):
    keys = ('@type', 'name',)
    branches = (lambda x: 'Organization',
                sequential((methodcaller('get', 'company', None),
                            methodcaller('get', 'name', None),)),)
    steps = (parallel(branches),
             partial(zip, keys),
             dict)
    return sequential(steps)(posting_record)


def description(posting_record):
    return methodcaller('get', 'description', None)(posting_record)


def job_location_type(posting_record):
    # Hybrid Onsite Remote Null

    def has_valid_remote_details(x):
        rd = x.get('remote_details')
        return rd is not None and rd.get('value') is not None

    def affrimative(x):
        steps = (branch(has_valid_remote_details,
                        sequential((methodcaller('get', 'remote_details',
                                                 None),
                                    methodcaller('get', 'value', None),
                                    methodcaller('replace', '-location', ''),
                                    common.title_transform,)),
                        lambda x: 'Remote'),)
        return sequential(steps)(x)

    def negative(x):
        return "Onsite"

    steps = (methodcaller('get', 'location', None),
             branch(methodcaller('get', 'is_remote'),
                    affrimative,
                    negative),)
    return sequential(steps)(posting_record)


def url(posting_record):
    return methodcaller('get', 'url', None)(posting_record)


def date_posted(posting_record):
    dp = methodcaller('get', 'published_date', None)(posting_record)
    return common.convert_to_ISO8601_calendar_date('iso8601', dp)


def employment_type(posting_record):
    # Contract Fulltime Intern Parttime Other Temporary
    steps = (methodcaller('get', 'type', None),
             methodcaller('get', 'id', None),
             common.title_transform,)
    return sequential(steps)(posting_record)


def language(posting_record):
    return common.return_none(posting_record)


def industry(posting_record):
    return common.return_none(posting_record)


def _a_in_b(a, b):
    return a in b


def _extract_interval(salary_field):
    # 20000 < value
    looks_like_salary = branch(partial(lt, 20000),
                               lambda x: 'P1Y',
                               lambda x: None)

    # Interval indicated
    is_annual = branch(partial(_a_in_b, '/ year'),
                       lambda x: 'P1Y',
                       sequential((_extract_values_salary,
                                   itemgetter(0),
                                   looks_like_salary),))

    is_monthly = branch(partial(_a_in_b, '/ monthly'),
                     lambda x: 'P1M',
                     sequential((lambda x: x,
                                 is_annual),))
    is_weekly = branch(partial(_a_in_b, '/ week'),
                     lambda x: 'P1W',
                     sequential((lambda x: x,
                                 is_monthly),))
    is_hrly = branch(partial(_a_in_b, '/ hr'),
                     lambda x: 'PT1H',
                     sequential((lambda x: x,
                                 is_weekly),))
    is_hourly = branch(partial(_a_in_b, '/ hour'),
                       lambda x: 'PT1H',
                       sequential((lambda x: x,
                                   is_hrly),))

    is_daily = branch(partial(_a_in_b, '/ day'),
                      lambda x: 'P1D',
                      sequential((lambda x: x,
                                  is_hourly),))

    # What is interval?
    interval_steps = (
                      methodcaller('replace', ',', ''),
                      is_daily,
                     )
    try:
        return sequential(interval_steps)(salary_field)
    except Exception:
        print("breezy salary: ", salary_field)
        return common.return_none(salary_field)


def _has_no_currency(posting_record):
    steps = (methodcaller('get', 'salary', None),
             _extract_currency_symbol,
             bool,
             not_)
    return sequential(steps)(posting_record)


def _symbol_is_dollar(posting_record):
    steps = (methodcaller('get', 'salary', None),
             _extract_currency_symbol,
             partial(eq, '$'),)
    return sequential(steps)(posting_record)


def _resolve_currency(posting_record):
    SYMBOL_MAP = {"£": "GBP",
                  "€": "EUR",
                  "₱": "PHP",
                  "₹": "INR"}

    DOLLAR_MAP = {"CA": "CAD",
                  "AU": "AUD",
                  "US": "USD",
                  "PR": "USD", }

    dollar_steps = (methodcaller('get', 'location', None),
                    methodcaller('get', 'country', None),
                    methodcaller('get', 'name', None),
                    common.convert_to_ISO3166,
                    DOLLAR_MAP.get,)

    not_dollar_steps = (methodcaller('get', 'salary', None),
                        _extract_currency_symbol,
                        SYMBOL_MAP.get,)

    proc = branch(_has_no_currency,
                  None,
                  branch(_symbol_is_dollar,
                         sequential(dollar_steps),
                         sequential(not_dollar_steps)))
    return proc(posting_record)


def _extract_currency_symbol(salary_field):
    # return itemgetter(0)(salary_field)
    symbol = ""
    for char in salary_field:
        if char.isdigit():
            break
        symbol += char
    return symbol


def _scale(value):
    if 'k' in value:
        return float(value.replace('k', '')) * 1000
    elif 'm' in value:
        return float(value.replace('m', '')) * 1000000
    else:
        return value


def _extract_values_salary(salary_field):
    remove_symbol = methodcaller('replace',
                                 _extract_currency_symbol(salary_field),
                                 '')
    steps = (remove_symbol,
             methodcaller('replace', '/ day', ''),
             methodcaller('replace', '/ hr', ''),
             methodcaller('replace', '/ hour', ''),
             methodcaller('replace', '/ year', ''),
             methodcaller('replace', '/ month', ''),
             methodcaller('replace', '/ week', ''),
             methodcaller('replace', ',', ''),
             methodcaller('replace', '\u2013', '-'),
             methodcaller('split', '-'),
             partial(map, methodcaller('strip')),
             partial(map, methodcaller('lower')),
             partial(map, methodcaller('replace', '+', '')),
             partial(map, _scale),
             partial(map, common.convert_to_ISO6093),
             tuple,
             branch(lambda x: len(x) == 1,
                    lambda x: (x[0], x[0],),
                    lambda x: (min(x), max(x)), )
             )
    return sequential(steps)(salary_field)


def _make_value_record(posting_record):
    get_salary = methodcaller('get', 'salary', None)
    get_values = sequential((get_salary,
                            _extract_values_salary,))
    get_interval = sequential((get_salary,
                               _extract_interval,))
    fns = (lambda x: "QuantitativeValue",
           get_values,
           get_interval,)

    keys = ('@type', 'minValue', 'maxValue', 'unitText',)

    steps = (parallel(fns),
             common.flatten,
             partial(zip, keys),
             dict,)
    make_dict = sequential(steps)

    def zero_salary(posting_record):
        return get_values(posting_record)[0] == 0

    is_min = sequential((methodcaller('get', 'salary', None),
                        partial(_a_in_b, '+'),))

    is_max = sequential((methodcaller('get', 'salary', None),
                        partial(_a_in_b, 'Up to'),))

    def delete_and_return(obj, key):
        del obj[key]
        return obj

    do_the_thing = (parallel((is_min, is_max, make_dict),),
                    branch(lambda x: x[0],
                           lambda x: delete_and_return(x[2], 'maxValue'),
                           branch(lambda x: x[1],
                                  lambda x: delete_and_return(x[2],
                                                              'minValue'),
                                  lambda x: x[2]),
                           ),
                    )

    proc = branch(zero_salary,
                  common.return_none,
                  sequential(do_the_thing),)
    return proc(posting_record)


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
    fns = (lambda x: "MonetaryAmount",
           _resolve_currency,
           _make_value_record)
    keys = ('@type', 'currency', 'value',)
    steps = (parallel(fns),
             partial(zip, keys),
             dict)
    proc = branch(lambda x: bool(x['salary']),
                  sequential(steps),
                  lambda x: None)
    return proc(posting_record)


def _postal_address(postalAddress):
    # Pluck components from node

    locality_seq = (methodcaller('get', 'city', None),
                    methodcaller('title'),)
    region_seq = (methodcaller('get', 'state', None),
                  methodcaller('get', 'name', None),)
    country_seq = (methodcaller('get', 'country', None),
                   methodcaller('get', 'name', None),
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
               lambda x: [x],)
    primary = sequential(primary)
    secondary = (methodcaller('get', 'locations', None),
                 partial(filter, bool),)
    secondary = sequential(secondary)

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
