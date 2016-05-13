import cdrdb
import glob
import re
import datetime
import lxml.etree as etree

def normalize(xml):
    root = etree.XML(xml)
    xml = re.sub(r"\r+", "", etree.tostring(root, pretty_print=True))
    return xml.strip() + "\n"
now = datetime.datetime.now()
stamp = now.strftime("%Y%m%d%H%M%S")
query = cdrdb.Query("document d", "title", "xml")
query.join("doc_type t", "t.id = d.doc_type")
query.where("t.name = 'PublishingSystem'")
for title, xml in query.execute().fetchall():
    name = "%s.xml" % title
    from_fs = normalize(open(name).read())
    from_db = normalize(xml.encode("utf-8"))
    if from_fs != from_db:
        db_name = "%s-from-db-%s.xml" % (title, stamp)
        fs_name = "%s-from-fs-%s.xml" % (title, stamp)
        fp = open(db_name, "wb")
        fp.write(from_db)
        fp.close()
        fp = open(fs_name, "wb")
        fp.write(from_fs)
        fp.close()
        print "diff %s %s" % (db_name, fs_name)
