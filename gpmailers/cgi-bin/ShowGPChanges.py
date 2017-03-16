#!/usr/bin/python

#----------------------------------------------------------------------
#
# Display a diff report between the original information for a
# genetics professional and the information as modified in the
# mailer interface by the GP.
#
# JIRA::OCECDR-4107
# JIRA::OCECDR-4118 - normalize root-level attribute order
#
#----------------------------------------------------------------------
import cgi, cdrutil, difflib, lxml.etree as etree
import re

def show(me):
    print """\
Content-type: text/html; charset: utf-8

<pre>%s</pre>
""" % me

def callback(match):
    return "<GP %s %s>" % (match.group(2), match.group(1))

def fix(me):
    xml = etree.tostring(etree.XML(me), pretty_print=True)
    xml = re.sub("<GP (tracker=[^>]+) (id=[^>]+)>", callback, xml)
    return xml.replace("\r", "").splitlines(1)

def addColor(line, color):
    return "<span style='background-color: %s'>%s</span>" % (color, line)

def main():
    fields = cgi.FieldStorage()
    session = fields.getvalue("Session")
    if not cdrutil.can_do(session, "GP MAILERS"):
        print "Status: 403\n\n<h1>Access to GP mailers denied</h1>"
        exit(0)
    mailerId = fields.getvalue('id')
    cursor = cdrutil.getConnection('emailers').cursor()
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
