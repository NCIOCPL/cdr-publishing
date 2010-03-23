#!/usr/bin/python

#----------------------------------------------------------------------
#
# $Id$
#
# Display a diff report between the original information for a
# genetics professional and the information as modified in the
# mailer interface by the GP.
#
#----------------------------------------------------------------------
import cgi, util, difflib, lxml.etree as etree

def show(me):
    print """\
Content-type: text/html; charset: utf-8

<pre>%s</pre>
""" % me

def fix(me):
    xml = etree.tostring(etree.XML(me), pretty_print=True)
    return xml.replace("\r", "").splitlines(1)

def addColor(line, color):
    return "<span style='background-color: %s'>%s</span>" % (color, line)

def main():
    fields = cgi.FieldStorage()
    mailerId = fields.getvalue('id')
    cursor = util.getConnection('emailers').cursor()
    cursor.execute("SELECT original, xml FROM gp_emailer WHERE id = %s",
                   mailerId)
    original, new = cursor.fetchone()
    diffObj = difflib.Differ()
    before = fix(original)
    after = fix(new)
    diffSeq = diffObj.compare(before, after)
    lines = []
    changes = False
    for line in diffSeq:
        line = cgi.escape(line)
        if not line.startswith(' '):
            changes = True
        if line.startswith('-'):
            lines.append(addColor(line, '#FAFAD2')) # Light goldenrod yellow
        elif line.startswith('+'):
            lines.append(addColor(line, '#F0E68C')) # Khaki
        elif line.startswith('?'):
            lines.append(addColor(line, '#87CEFA')) # Light sky blue
        else:
            lines.append(line)
    if not changes:
        show("No changes")
    else:
        show("".join(lines))
        #show("".join(diffSeq))

if __name__ == '__main__':
    main()
