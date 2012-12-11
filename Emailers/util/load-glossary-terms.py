#!/usr/bin/python

import urllib2, MySQLdb, sys, util

if len(sys.argv) < 2:
    sys.stderr.write("usage: %s host-name\n" % sys.argv[0])
    sys.exit(1)

host = sys.argv[1]
conn = MySQLdb.connect(user = 'glossifier', passwd = '***REMOVED***',
                       db = 'glossifier')
cursor = conn.cursor()
app = len(sys.argv) < 3 and 'cgi-bin/cdr/GetGlossifierTerms.py' or sys.argv[2]
reader = urllib2.urlopen("http://%s/%s" % (host, app))
doc = reader.read()
cursor.execute("""\
    UPDATE terms
       SET loaded = NOW(),
           terms_dict = %s
     WHERE terms_id = 1""", doc)
cursor.execute("DELETE FROM term_regex")
conn.commit()
util.log("loaded glossifier terms (length %d bytes)" % len(doc))
