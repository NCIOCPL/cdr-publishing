#!/usr/bin/env python

"""Bridge PublishingService.py to cdrpub.py.
"""

from argparse import ArgumentParser
from cdr import Logging
from cdrpub import Control

parser = ArgumentParser()
parser.add_argument("job", type=int)
opts = parser.parse_args()
logger = Logging.get_logger("publish")
logger.info("Job %d started", opts.job)
try:
    Control(opts.job).publish()
    logger.info("Job %d ended", opts.job)
except Exception:
    logger.exception("Job %d failed", opts.job)
