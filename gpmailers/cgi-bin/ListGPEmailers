#!/usr/bin/python

#----------------------------------------------------------------------
#
# $Id$
#
# Tool used by CIAT to review Genetics Professional electronic mailers,
# and to mark mailers which have been returned to sender ("bounced").
#
#----------------------------------------------------------------------
import cdrutil, cgi

fields = cgi.FieldStorage()
bounce = fields.getvalue('bounce')
debug = fields.getvalue('debug')
conn = cdrutil.getConnection('emailers')
cursor = conn.cursor()
if bounce:
    cursor.execute("""\
        UPDATE gp_emailer
           SET bounced = NOW()
         WHERE id = %s""", bounce)
    conn.commit()
cursor.execute("""\
    SELECT id, cdr_id, job, email, name, mailed, completed, bounced
      FROM emailers.gp_emailer
  ORDER BY id""")
output = [u"""\
<html>
 <body>
  <table border='1' cellpadding='2' cellspacing='0'>
   <tr>
    <th>Mailer ID</th>
    <th>CDR Person ID</th>
    <th>Job ID</th>
    <th>Email Address</th>
    <th>Person Name</th>
    <th>Mailed</th>
    <th>Completed</th>
    <th>Bounced</th>
   </tr>
"""]
for (mailerId, cdrId, jobId, email, name, mailed,
     completed, bounced) in cursor.fetchall():
    if completed:
        url = 'ShowGPChanges.py?id=%d' % mailerId
        completed = u"<a href='%s'>%s</a>" % (url, completed)
    else:
        completed = u"&nbsp;"
    if not bounced:
        bounced = ("<a href='ListGPEmailers?bounce=%d'>Mark as Bounced</a>" %
                   mailerId)
    output.append(u"""\
   <tr>
    <td><a href='cgsd.py?id=%s%s'>%d</a></td>
    <td>%d</td>
    <td>%d</td>
    <td>%s</td>
    <td>%s</td>
    <td>%s</td>
    <td>%s</td>
    <td>%s</td>
   </tr>
""" % (cdrutil.base36((mailerId << 32) + cdrId), debug and u"&debug=1" or u"",
       mailerId, cdrId, jobId, email, cgi.escape(name), mailed, completed,
       bounced))
output.append(u"""\
  </table>
 </body>
</html>
""")
cdrutil.sendPage(u"".join(output))
