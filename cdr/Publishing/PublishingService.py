import cdrdb, os, time, cdr, sys, string

sleepSecs = len(sys.argv) > 1 and string.atoi(sys.argv[1]) or 10
SCRIPT = cdr.SCRIPTS + "/publish.py"
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
