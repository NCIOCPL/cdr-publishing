#!/usr/bin/python

#----------------------------------------------------------------------
#
# $Id: show-table-defs.py,v 1.1 2008-04-17 21:08:50 bkline Exp $
#
# $Log: not supported by cvs2svn $
#----------------------------------------------------------------------
import MySQLdb, sys, cgi

databases = (
    ('emailers', 'emailers',   '***REMOVED***'),
    ('dropbox',  'emailers',   '***REMOVED***'),
    ('cts',      'cts',        '***REMOVED***'),
    ('bugs',     'bugsbackup', '')
    )

print """\
Content-type: text/html

<html>
 <head>
  <meta http-equiv='content-type' content='text/html;charset=utf-8' />
  <style type='text/css'>
   body { font-family: Arial, sans-serif; font-size: 10pt; }
   h1 { font-size: 14pt; text-align: center; color: maroon; }
   .tname { background: green; color: white; font-size: 11pt;
            font-weight: bold; text-align: center; }
   pre { color: blue; margin-left: 50px; }
  </style>
  <title>Table Definitions</title>
 </head>
 <body>
  <h1>Table Definitions</h1>"""
for db, uid, pwd in databases:
    conn = MySQLdb.connect(db = db, user = uid, passwd = pwd)
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    names = [row[0] for row in cursor.fetchall()]
    for name in names:
        cursor.execute("SHOW CREATE TABLE %s" % name)
        tname, sql = cursor.fetchone()
        print """\
  <p class='tname'>%s.%s</p>
  <pre>%s</pre>""" % (db, tname, sql.replace('`', ''))
print """\
 </body>
</html>"""
