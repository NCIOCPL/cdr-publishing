#!/usr/bin/env python

"""
Send a PDQ Summary to a Drupal CMS server

Logs to session-yyyy-mm-dd.log in CDR log directory (usually d:/cdr/log).

Part of https://github.com/NCIOCPL/cgov-digital-platform/issues/825 epic.
"""

from argparse import ArgumentParser
from cdrapi.users import Session
from cdrapi.docs import Doc
from cdrapi.publishing import DrupalClient
from cdrpub import Control

FILTERS = dict(
    Summary="Cancer Information Summary for Drupal CMS",
    DrugInformationSummary="Drug Information Summary for Drupal CMS",
)
ASSEMBLE = dict(
    Summary=Control.assemble_values_for_cis,
    DrugInformationSummary=Control.assemble_values_for_dis,
)

# Collect the options for this run.
parser = ArgumentParser()
parser.add_argument("--session", required=True, help="CDR login key")
parser.add_argument("--tier", help="publish from another tier")
parser.add_argument("--base", help="override base URL for Drupal site")
parser.add_argument("--password", help="override password for PDQ account")
parser.add_argument("--dumpfile", help="where to store the serialized doc")
parser.add_argument("--id", type=int, help="CDR ID for Summary", required=True)
opts = parser.parse_args()
auth = "PDQ", opts.password if opts.password else None

# Make sure we are allowed to publish to the CMS.
session = Session(opts.session, tier=opts.tier)
if not session.can_do("USE PUBLISHING SYSTEM"):
    raise Exception("Not authorized")

# Prepare the document.
doc = Doc(session, id=opts.id)
print("Pushing {} document {}".format(doc.doctype.name, doc.cdr_id))
root = Control.fetch_exported_doc(session, doc.id, "pub_proc_cg")
xsl = Doc.load_single_filter(session, FILTERS[doc.doctype.name])
values = ASSEMBLE[doc.doctype.name](session, doc.id, xsl, root)

# Store the document and mark it publishable.
client = DrupalClient(session)
nid = client.push(values)
documents = [(doc.id, nid, values.get("language", "en"))]
errors = client.publish(documents)
print("pushed {} as Drupal node {:d}".format(doc.cdr_id, nid))
if errors:
    print(errors)
