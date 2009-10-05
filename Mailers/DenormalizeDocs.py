#----------------------------------------------------------------------
#
# $Id: DenormalizeDocs.py,v 1.1 2003-10-08 12:36:19 bkline Exp $
#
# $Log: not supported by cvs2svn $
# Revision 1.1  2002/09/15 19:08:04  bkline
# New tools.
#
#----------------------------------------------------------------------
import sys, cdr, cdrdb

filters = {
    "InScopeProtocol"  : ["set:Mailer InScopeProtocol Set"],
    "Organization"     : ["set:Mailer Organization Set"],
    "Person"           : ["set:Mailer Person Set"],
    "Term"             : ["name:Denormalization Filter (1/1): Terminology"],
    "Summary"          : ["set:Mailer Summary Set"],
    "PoliticalSubUnit" : [
        "name:Denormalization Filter (1/1): Political SubUnit",
        "name:Vendor Filter: PoliticalSubUnit"
    ],
    "StatMailer"       : [
        "name:InScopeProtocol Status and Participant Mailer"
    ],
}

maxDocs = -1
rows    = []
leadOrg = None
if len(sys.argv) < 2:
    sys.stderr.write("usage: DenormalizeDocs cdrType [max-docs]\n")
    sys.stderr.write("   or: DenormalizeDocs cdrType [--leadorg id] "
                     "--list id [id ...]\n")
    sys.stderr.write("   or: DenormalizeDocs --filelist filename\n")
    sys.exit(1)
if sys.argv[1] == "--filelist":
    listFile = open(sys.argv[2])
    for line in listFile.readlines():
        line = line.strip()
        (id, docType) = line.split("\t")
        rows.append([int(id), docType])
else:
    cdrType = sys.argv[1]
    if not filters.has_key(cdrType):
        sys.stderr.write("don't know how to filter %s documents\n" % cdrType)
        sys.exit(1)
if len(sys.argv) > 2:
    print "sys.argv[2] = %s" % sys.argv[2]
    if sys.argv[2] == '--leadorg':
        leadOrg = sys.argv[3]
        sys.argv[2:4] = []
    print "sys.argv[2] = %s" % sys.argv[2]
    if sys.argv[2] == '--list':
        for i in range(3, len(sys.argv)):
            rows.append([int(sys.argv[i]), cdrType])
    else:
        maxDocs = int(sys.argv[2])
if not rows:
    conn = cdrdb.connect()
    curs = conn.cursor()
    curs.execute("""\
    SELECT document.id, doc_type.name
      FROM document
      JOIN doc_type
        ON doc_type.id = document.doc_type
     WHERE doc_type.name = '%s'
       AND document.active_status = 'A'
  ORDER BY document.id""" % cdrType)
    rows = curs.fetchall()
sess = cdr.login('rmk', '***REDACTED***')
if maxDocs == -1: maxDocs = len(rows)
sys.stderr.write("found %d documents; processing %d\n" % (len(rows), maxDocs))
if leadOrg:
    parms = [['leadOrgId','CDR%010d' % int(leadOrg)]]                 
numDocs = 0
for row in rows:
    if numDocs >= maxDocs:
        break
    numDocs += 1
    id = row[0]
    cdrType = row[1]
    if not filters.has_key(cdrType):
        sys.stderr.write("don't know how to filter %s documents\n" % cdrType)
        continue
    for f in filters[cdrType]:
        print f
    resp = cdr.filterDoc('guest', filters[cdrType], id, 
                         parm = leadOrg and parms or [])
    if type(resp) in (type(""), type(u"")):
        sys.stderr.write("Error for document %d: %s\n" % (id, resp))
    else:
        sys.stderr.write("Processing document CDR%010d\n" % id)
        open("%d.xml" % id, "w").write(resp[0])
