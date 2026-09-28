#!/usr/bin/env python

from . import transform


def conform(adapter_name, posting_record):
    module = transform.get_adapter(adapter_name)
    return {'@context': 'https://schema.org/',
            '@type': 'JobPosting',
            'title': module.title(posting_record),
            'description': module.description(posting_record),
            'employmentType': module.employment_type(posting_record),
            'jobLocationType': module.job_location_type(posting_record),
            'url': module.url(posting_record),
            'datePosted': module.date_posted(posting_record),
            'inLanguage': module.language(posting_record),
            'industry': module.industry(posting_record),
            'hiringOrganization': module.company_name(posting_record),
            'jobLocation': module.job_location(posting_record),
            'baseSalary': module.base_salary(posting_record)}


def prune(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            v = prune(v)
            if v is None:
                continue
            if not v:
                continue
            out[k] = v
        if not out:
            return None
        # remove pure @type shells
        if set(out.keys()) == {"@type"}:
            return None
        return out

    if isinstance(obj, tuple):
        out = []
        for x in obj:
            x = prune(x)
            if x is not None:
                out.append(x)
        return out if out else None

    if isinstance(obj, list):
        out = []
        for x in obj:
            x = prune(x)
            if x is not None:
                out.append(x)
        return out if out else None
    return obj


def canonize(adapter_name, record):
    # create sparse dict for entry into cafs hot path
    return prune(conform(adapter_name, record))


def formalize(content_hash, adapter_name, posting_record, url):
    # create metadata record for internal bookkeeping
    module = transform.get_adapter(adapter_name)
    ats_id = module.record_id(posting_record)
    record = map(str, (content_hash, adapter_name, ats_id, url,))
    return ' | '.join(record)


if __name__ == '__main__':
    import os
    import json
    sample_dir = ('/home/joey/projects/cagg'
                  '/canonical_model/workable/samples/')
    module = transform.get_adapter('workable')
    for board_sample in os.listdir(sample_dir):
        with open(os.path.join(sample_dir, board_sample), 'r') as handle:
            board = json.load(handle)
            board = module.make_list(board)
        for record in board:
            rr = conform('workable', record)
            pr = prune(rr)
            print(json.dumps(pr, indent=2))
            breakpoint()
