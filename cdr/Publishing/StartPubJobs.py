#
# This script starts the publishing service.
#
# $Id: StartPubJobs.py,v 1.4 2002-02-19 23:14:18 ameyer Exp $
# $Log: not supported by cvs2svn $
# Revision 1.3  2002/02/06 17:09:43  pzhang
# This is an obsolete version. Use PublishingService.py instead.
#
# Revision 1.2  2002/02/06 16:14:34  pzhang
# Updated SCRIPT definition.
#

import cdr, cdrdb, os
PYTHON = "d:\\python\\python.exe"
SCRIPT = cdr.BASEDIR + "/publishing/publish.py"
query  = """\
SELECT id
  FROM pub_proc
 WHERE status = 'Ready'
"""
update = """\
UPDATE pub_proc
   SET status = 'Started'
 WHERE status = 'Ready'
"""

try:
    conn = cdrdb.connect("CdrPublishing")
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.execute(update)
    conn.commit()
except cdrdb.Error, info:
    print 'Database failure: %s' % info[1][0]
for row in rows:
    print "publishing document %d" % row[0]
    os.spawnv(os.P_NOWAIT, PYTHON, ("CdrPublish", SCRIPT, str(row[0])))
