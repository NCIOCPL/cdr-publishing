#!/usr/bin/env python

"""Prepare the DB and file system pub control document for comparison.
"""

from datetime import datetime
from re import sub
import lxml.etree as etree
from cdrapi import db

OPTS = dict(pretty_print=True, encoding="unicode")

def normalize(xml):
    """Take encoded XML and convert it to normalized Unicode."""
    root = etree.XML(xml)
    xml = sub(r"\r+", "", etree.tostring(root, **OPTS))
    return xml.strip() + "\n"

cursor = db.connect(user="CdrGuest").cursor()
now = datetime.now()
stamp = now.strftime("%Y%m%d%H%M%S")
query = db.Query("doc_version v", "v.id", "MAX(v.num)")
query.join("doc_type t", "t.id = v.doc_type")
query.join("active_doc a", "a.id = v.id")
query.where("t.name = 'PublishingSystem'")
query.group("v.id")
for doc_id, doc_ver in query.execute(cursor).fetchall():
    query = db.Query("doc_version", "title", "xml")
    query.where(query.Condition("id", doc_id))
    query.where(query.Condition("num", doc_ver))
    title, xml = query.execute(cursor).fetchone()
    name = "%s.xml" % title
    from_fs = normalize(open(name, "rb").read())
    from_db = normalize(xml.encode("utf-8"))
    if from_fs != from_db:
        db_name = "%s-from-db-%s.xml" % (title, stamp)
        fs_name = "%s-from-fs-%s.xml" % (title, stamp)
        with open(db_name, "w", encoding="utf-8") as fp:
            fp.write(from_db)
        with open(fs_name, "w", encoding="utf-8") as fp:
            fp.write(from_fs)
        print("diff %s %s" % (db_name, fs_name))
