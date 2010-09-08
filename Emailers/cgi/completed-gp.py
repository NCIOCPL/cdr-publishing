#!/usr/bin/python
#----------------------------------------------------------------------
#
# $Id$
#
# Returns XML document for GP mailers that need to be recorded.
#
#----------------------------------------------------------------------
import util, lxml.etree as etree

conn = util.getConnection()
cursor = conn.cursor()
cursor.execute("""\
    SELECT id, bounced, completed
      FROM gp_emailer
     WHERE bounced IS NOT NULL
        OR completed IS NOT NULL""")
tree = etree.Element('mailers')
for id, bounced, completed in cursor.fetchall():
    child = etree.Element('mailer', id=id, bounced=bounced or '',
                          completed=completed or '')
    tree.append(child)
print "Content-type: text/xml\n"
print etree.tostring(tree)
