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

# Collect the options for this run.
parser = ArgumentParser()
parser.add_argument("--session", required=True, help="CDR login key")
parser.add_argument("--tier", help="publish from another tier")
parser.add_argument("--base", help="override base URL for Drupal site")
parser.add_argument("--password", help="override password for PDQ account")
parser.add_argument("--dumpfile", help="where to store serialized docs")
opts = dict(action="store_true", help="don't drop existing PDQ content")
parser.add_argument("--keep", **opts)
parser.add_argument("--level", default="info", help="how much to log")
opts = parser.parse_args()
auth = ("PDQ", opts.password) if opts.password else None

# Make sure we are allowed to publish to the CMS.
session = Session(opts.session, tier=opts.tier)
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
query.where("t.name in ('Summary', 'DrugInformationSummary')")
query.order("d.id")
docs = dict([list(row) for row in query.execute(session.cursor).fetchall()])
opts = dict(
    send=docs,
    base=opts.base,
    dumpfile=opts.dumpfile,
    auth=auth,
    logger=Logging.get_logger("populate-drupal-cms", level=opts.level),
)
Control.update_cms(session, **opts)
