import cdrdb, os
PYTHON = "d:\\python\\python.exe"
SCRIPT = "d:\\cdr\\src\\script\\publish.py"
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
