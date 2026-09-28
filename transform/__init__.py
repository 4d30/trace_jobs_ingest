#!/usr/bin/env python

from . import ashbyhq
from . import breezy
from . import crelate
from . import greenhouse
from . import jazz
from . import jobscore
from . import lever
from . import pinpointhq
from . import recruitee
from . import smartrecruiters
from . import teamtailor
from . import workable

_ADAPTERS = {
    "ashbyhq": ashbyhq,
    "breezy": breezy,
    "crelate": crelate,
    "greenhouse": greenhouse,
    "jazz": jazz,
    "jobscore": jobscore,
    "lever": lever,
    "pinpointhq": pinpointhq,
    "recruitee": recruitee,
    "smartrecruiters": smartrecruiters,
    "teamtailor": teamtailor,
    "workable": workable,
}

def get_adapters():
    return _ADAPTERS.items()

def get_adapter(name):
    return _ADAPTERS[name]
