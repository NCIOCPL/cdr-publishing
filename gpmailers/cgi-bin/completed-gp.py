#!/usr/bin/python
#----------------------------------------------------------------------
#
# $Id$
#
# Returns XML document for GP mailers that need to be recorded.
#
#----------------------------------------------------------------------
import cdrutil, lxml.etree as etree

conn = cdrutil.getConnection()
cursor = conn.cursor()
cursor.execute("""\
    SELECT id, bounced, completed, xml <> original
      FROM gp_emailer
     WHERE recorded IS NULL
       AND (bounced IS NOT NULL
        OR completed IS NOT NULL)""")
tree = etree.Element('mailers')
for id, bounced, completed, modified in cursor.fetchall():
    b = bounced and unicode(bounced) or ''
    c = completed and unicode(completed) or ''
    m = modified and 'Y' or 'N'
    child = etree.Element('mailer', id=str(id), bounced=b, completed=c,
                          modified=m)
    tree.append(child)
cursor.execute("""\
    SELECT id, DATE_ADD(mailed, INTERVAL 120 DAY)
      FROM gp_emailer
     WHERE bounced IS NULL
       AND completed IS NULL
       AND recorded IS NULL
       AND DATEDIFF(NOW(), mailed) >= 120""")
for id, expired in cursor.fetchall():
    child = etree.Element('mailer', id=str(id), expired=str(expired))
    tree.append(child)
print "Content-type: text/xml\n"
print etree.tostring(tree)
