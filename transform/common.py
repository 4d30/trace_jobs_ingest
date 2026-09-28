#!/usr/bin/env python

import json
from operator import methodcaller
from datetime import datetime, timezone

import pycountry


def deduplicate_dicts(dict_gen):
    seen = set()
    for d in dict_gen:
        marker = json.dumps(d, sort_keys=True)
        if marker not in seen:
            seen.add(marker)
            yield d


def flatten(iterable):
    """Flatten one level of nesting, handling non-iterables."""
    for el in iterable:
        if isinstance(el, (list, tuple)):
            yield from el
        else:
            yield el


def return_none(posting_record):
    return None


def safe_next(maybe_iterable):
    # next() we a None sentinel
    return next(maybe_iterable, None)


def empty_salary_value(dummy):
    return {'@type': 'QuantitativeValue',
            'minValue': None,
            'maxValue': None,
            'unitText': None}


def empty_salary(posting_record):
    return {'@type': 'MonetaryAmount',
            'currency': None,
            'value': empty_salary_value(posting_record)}


def empty_location(posting_record):
    return ({'@type': 'Place',
             'address': {'@type': 'PostalAddress',
                         'addressLocality': None,
                         'addressRegion': None,
                         'addressCountry': None}
             },
            )


def convert_to_ISO8601_calendar_date(format, raw_date_string):
    if format == 'iso8601':
        dt = datetime.fromisoformat(raw_date_string)
    elif format == 'crelate':
        dt = datetime.strptime(raw_date_string, "%a, %d %b %Y %H:%M:%S Z")
    elif format == 'jazz':
        dt = datetime.strptime(raw_date_string, "%Y%m%d%H%M%S")
    elif format == 'recr':
        dt = datetime.strptime(raw_date_string, '%Y-%m-%d %H:%M:%S UTC')
    elif format == 'tt':
        dt = datetime.strptime(raw_date_string, '%a, %d %b %Y %H:%M:%S %z')
    elif format == 'lever':
        dt = datetime.fromtimestamp(raw_date_string / 1000.0, tz=timezone.utc)
    else:
        raise Exception('Unknown date format')
    return dt.strftime('%Y-%m-%d')


def convert_to_ISO3166(country_name):
    # We default back to whatever was input if a code cannot be found.
    # While this breaks stricht
    """
    Maybe
     - opensanctions/countrynames (MIT)
     - dr5hn/countries+states+cities dataset (ODBL)
    for eliminating pycountry
    """
    try:
        country = pycountry.countries.lookup(country_name)
        return country.alpha_2
    except LookupError:
        return country_name


def convert_to_ISO6093(string):
    if isinstance(string, str):
        string = string.strip()
        if not string:
            return False
        test_string = string
        if test_string[0] in ('-', '+') and len(test_string) > 1:
            test_string = test_string[1:]
        all_char_is_digit = test_string.replace('.', '', 1).isdigit()
        any_char_is_digit = any(char.isdigit() for char in test_string)
        if all_char_is_digit and any_char_is_digit:
            return float(string)
        else:
            return string
    return float(string)


def convert_to_iso8601_interval(interval):
    ii = interval.lower()
    if 'year' in ii:
        unit = 'Y'
    elif 'month' in ii:
        unit = 'M'
    elif 'week' in ii:
        unit = 'W'
    elif 'hour' in ii:
        unit = 'H'
    else:
        unit = None
    if unit is None:
        return None
    elif unit != 'H':
        return f'P1{unit}'
    else:
        return f'PT1{unit}'


def is_substantial(d):
    """True if dict has more than just '@type'."""
    return bool(d) and len(d) > 1


def empty_company_name(posting_record):
    return {'@type': 'Organization',
            'name': None}

def title_transform(chars):
    chars = filter(methodcaller('isalpha'), chars)
    chars = ''.join(chars)
    chars = chars.title()
    return chars
