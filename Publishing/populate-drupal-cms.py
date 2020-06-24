#!/usr/bin/env python

"""Install a clean set of PDQ content on the Drupal CMS

Clears out existing PDQ content first, unless told not to.

Ignores problems caused by broken links from non-PDQ content to PDQ summaries.

See JIRA ticket https://tracker.nci.nih.gov/browse/OCECDR-4584.

Logs to session-yyyy-mm-dd.log in CDR log directory (usually d:/cdr/log).

Part of https://github.com/NCIOCPL/cgov-digital-platform/issues/825 epic.

This script has been enhanced to add options for processing only a
portion of the summaries. This is because on the production tier the
server gets overwhelmed when all of the summaries are loaded at once,
and the job fails part of the way through. For example, on April 13,
2020, Volker run the script to load all the summaries to
www-cms.cancer.gov and the script got through the first pass for
almost 500 of the documents and then crashed. So he started it again
and it made it through only 208 documents before failing (again, first
pass only). So I hacked this script to load the documents in smaller
batches and to skip over the drug information summaries, and was able
to get all of the cancer information summaries successfully
loaded. The first 600 succeeded in batches of 100. Then the next batch
(601-700) failed partway through, so I tried just 601-625 and that
failed, too. So I waited a few minutes and tried a batch of 50, and
that succeeded.  So I ran two more batches of 50, and they completed
successfully. The remaining 92 summaries were loaded successfully in a
single batch.

Example of loading only CIS documents in batches.
./populate-drupal-cms.py [other options] --keep --cis --max 100
./populate-drupal-cms.py [other options] --keep --cis --max 100 --skip 100
./populate-drupal-cms.py [other options] --keep --cis --max 100 --skip 200
./populate-drupal-cms.py [other options] --keep --cis --max 100 --skip 300
./populate-drupal-cms.py [other options] --keep --cis --max 100 --skip 400
....

If you're testing this on a non-production tier, be sure to do any subset
batch processing in order from the beginning of the sequence so the English
summaries get pushed before the Spanish summaries. In other words, don't
start with --skip 500.
"""

from argparse import ArgumentParser
from cdrapi.users import Session
from cdrapi.docs import Doc
from cdrapi.publishing import DrupalClient
from cdrpub import Control
from cdrapi import db
from cdr import Logging

PATH = "/Summary/SummaryMetaData/SummaryLanguage"
DROP = "drop existing PDQ content (UNAVAILABLE ON PRODUCTION)"
MAX = "limit the number of summaries to push"
SKIP = "start part-way through the set of summaries"
VERBOSE = "show what's happening"
LEVEL = "logging level (info, debug, warning, error)"

# Collect the options for this run.
parser = ArgumentParser()
parser.add_argument("--session", required=True, help="CDR login key")
parser.add_argument("--tier", help="publish from another tier")
parser.add_argument("--base", help="override base URL for Drupal site")
parser.add_argument("--password", help="override password for PDQ account")
parser.add_argument("--dumpfile", help="where to store serialized docs")
parser.add_argument("--drop", action="store_true", help=DROP)
parser.add_argument("--verbose", action="store_true", help=VERBOSE)
parser.add_argument("--level", default="info", help=LEVEL)
parser.add_argument("--max", type=int, default=1000000, help=MAX)
parser.add_argument("--skip", type=int, default=0, help=SKIP)
group = parser.add_mutually_exclusive_group()
group.add_argument("--cis", action="store_true", help="only CIS docs")
group.add_argument("--dis", action="store_true", help="only DIS docs")
opts = parser.parse_args()
auth = ("PDQ", opts.password) if opts.password else None

# Make sure we are allowed to publish to the CMS.
session = Session(opts.session, tier=opts.tier)
if not session.can_do("USE PUBLISHING SYSTEM"):
    raise Exception("Not authorized")

# Clean out existing documents if so instructed.
if opts.drop and not opts.cis and not opts.dis:
    if session.tier.name == "PROD":
        raise Exception("** CANNOT DROP EXISTING PDQ CONTENT ON PROD! **")
    client = DrupalClient(session, tier=opts.tier, base=opts.base, auth=auth)
    catalog = client.list()
    for langcode in ("es", "en"):
        for doc in catalog:
            if doc.langcode == langcode:
                client.remove(doc.cdr_id)

# Send PDQ content to the CMS.
cols = "d.id", "t.name", "ISNULL(l.value, 'English') AS language"
query = db.Query("document d", *cols)
query.join("doc_type t", "t.id = d.doc_type")
query.join("pub_proc_cg c", "c.id = d.id")
query.outer("query_term l", "l.doc_id = d.id", f"path = '{PATH}'")
if opts.cis:
    query.where("t.name = 'Summary'")
elif opts.dis:
    query.where("t.name = 'DrugInformationSummary'")
else:
    query.where("t.name in ('Summary', 'DrugInformationSummary')")
query.order(3, "d.id")
if opts.verbose:
    print(query)
rows = query.execute(session.cursor).fetchall()
if opts.verbose:
    print(f"{len(rows)} found by query")
end = min(opts.skip + opts.max, len(rows))
rows = rows[opts.skip:end]
if opts.verbose:
    print(f"sending {len(rows)} docs ({opts.skip+1} - {end})")
docs = dict([(row.id, row.name) for row in rows])
opts = dict(
    send=docs,
    base=opts.base,
    dumpfile=opts.dumpfile,
    auth=auth,
    logger=Logging.get_logger("populate-drupal-cms", level=opts.level),
)
Control.update_cms(session, **opts)
