#
# This script starts the publishing service.
#
# $Id: PublishingService.py,v 1.4 2002-02-20 15:10:14 pzhang Exp $
# $Log: not supported by cvs2svn $
# Revision 1.3  2002/02/19 23:13:33  ameyer
# Removed SCRIPT and replaced it with BASEDIR in keeping with new decisions
# about where things are.
#
# Revision 1.2  2002/02/06 16:22:39  pzhang
# Added Log. Don't want to change SCRIPT here; change cdr.py.
#
#

import cdrdb, os, time, cdr, sys, string

sleepSecs = len(sys.argv) > 1 and string.atoi(sys.argv[1]) or 10
SCRIPT = cdr.BASEDIR + "/lib/python/publish.py"
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
conn = None
while 1:
    try:
        if not conn:
            conn = cdrdb.connect("CdrPublishing")
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        if len(rows):
            cursor.execute(update)
        conn.commit()
        cursor.close()
        cursor = None
        for row in rows:
            #print "publishing job %d" % row[0]
            os.spawnv(os.P_NOWAIT, cdr.PYTHON, ("CdrPublish", SCRIPT,
                                                str(row[0])))
    except cdrdb.Error, info:
        # XXX Change this to log errors (add logging to cdr.py)
        print 'Database failure: %s' % info[1][0]
        conn = None
    time.sleep(sleepSecs)
