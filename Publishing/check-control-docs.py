import cdrdb
import re
import datetime
import lxml.etree as etree

def normalize(xml):
    root = etree.XML(xml)
    xml = re.sub(r"\r+", "", etree.tostring(root, pretty_print=True))
    return xml.strip() + "\n"
cursor = cdrdb.connect("CdrGuest").cursor()
now = datetime.datetime.now()
stamp = now.strftime("%Y%m%d%H%M%S")
query = cdrdb.Query("doc_version v", "v.id", "MAX(v.num)")
query.join("doc_type t", "t.id = v.doc_type")
query.join("active_doc a", "a.id = v.id")
query.where("t.name = 'PublishingSystem'")
query.group("v.id")
for doc_id, doc_ver in query.execute(cursor).fetchall():
    query = cdrdb.Query("doc_version", "title", "xml")
    query.where(query.Condition("id", doc_id))
    query.where(query.Condition("num", doc_ver))
    title, xml = query.execute(cursor).fetchone()
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
