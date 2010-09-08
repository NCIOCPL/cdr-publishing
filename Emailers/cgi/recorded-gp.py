#!/usr/bin/python
#----------------------------------------------------------------------
#
# $Id$
#
# Sets the recorded column for a row in the gp_emailer table.
#
#----------------------------------------------------------------------
import util, cgi

fields = cgi.FieldStorage()
mailerId = fields.getvalue('mailerId')
recorded = fields.getvalue('recorded')
try:
    conn = util.getConnection()
    cursor = conn.cursor()
    cursor.execute("UPDATE gp_emailer SET recorded = %s WHERE id = %s",
                   (recorded, mailerId))
    conn.commit()
    print "Content-type: text/plain\n\nOK"
except Exception, e:
    print "Content-type: text/plain\n\n%s" % e
