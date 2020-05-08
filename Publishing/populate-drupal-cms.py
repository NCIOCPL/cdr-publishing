#!/usr/bin/env python

"""
Install a clean set of PDQ content on the Drupal CMS

Clears out existing PDQ content first, unless told not to.

Ignores problems caused by broken links from non-PDQ content to PDQ summaries.

See JIRA ticket https://tracker.nci.nih.gov/browse/OCECDR-4584.

Logs to session-yyyy-mm-dd.log in CDR log directory (usually d:/cdr/log).

Part of https://github.com/NCIOCPL/cgov-digital-platform/issues/825 epic.
"""

from argparse import ArgumentParser
from cdrapi.users import Session
from cdrapi.docs import Doc
from cdrapi.publishing import DrupalClient
from cdrpub import Control
from cdrapi import db
from cdr import Logging

KEEP = "don't drop existing PDQ content (REQUIRED ON PRODUCTION)"

# Collect the options for this run.
parser = ArgumentParser()
parser.add_argument("--session", required=True, help="CDR login key")
parser.add_argument("--tier", help="publish from another tier")
parser.add_argument("--base", help="override base URL for Drupal site")
parser.add_argument("--password", help="override password for PDQ account")
parser.add_argument("--dumpfile", help="where to store serialized docs")
parser.add_argument("--keep", action="store_true", help=KEEP)
parser.add_argument("--verbose", action="store_true", help="show more")
parser.add_argument("--level", default="info", help="how much to log")
parser.add_argument("--max", type=int, default=1000000)
parser.add_argument("--skip", type=int, default=0)
group = parser.add_mutually_exclusive_group()
group.add_argument("--cis", action="store_true", help="only CIS docs")
group.add_argument("--dis", action="store_true", help="only DIS docs")
opts = parser.parse_args()
auth = ("PDQ", opts.password) if opts.password else None

# Make sure we are allowed to publish to the CMS.
session = Session(opts.session, tier=opts.tier)
if session.tier.name == "PROD" and not opts.keep:
    raise Exception("** CANNOT DROP EXISTING PDQ CONTENT ON PROD! **")
if not session.can_do("USE PUBLISHING SYSTEM"):
    raise Exception("Not authorized")

# Clean out existing documents unless told not to.
if not opts.keep:
    client = DrupalClient(session, tier=opts.tier, base=opts.base, auth=auth)
    catalog = client.list()
    for langcode in ("es", "en"):
        for doc in catalog:
            if doc.langcode == langcode:
                client.remove(doc.cdr_id)

# Send all the PDQ content to the CMS.
query = db.Query("document d", "d.id", "t.name")
query.join("doc_type t", "t.id = d.doc_type")
query.join("pub_proc_cg c", "c.id = d.id")
if opts.cis:
    query.where("t.name = 'Summary'")
elif opts.dis:
    query.where("t.name = 'DrugInformationSummary'")
else:
    query.where("t.name in ('Summary', 'DrugInformationSummary')")
query.order("d.id")
if opts.verbose:
    print(query)
rows = query.execute(session.cursor).fetchall()
if opts.verbose:
    print(f"{len(rows)} found by query")
end = min(opts.skip + opts.max, len(rows))
rows = rows[opts.skip:end]
if opts.verbose:
    print(f"sending {len(rows)} docs ({opts.skip+1} - {end}")
docs = dict([list(row) for row in rows])
opts = dict(
    send=docs,
    base=opts.base,
    dumpfile=opts.dumpfile,
    auth=auth,
    logger=Logging.get_logger("populate-drupal-cms", level=opts.level),
)
Control.update_cms(session, **opts)
