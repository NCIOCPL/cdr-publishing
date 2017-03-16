#!/usr/bin/python

#----------------------------------------------------------------------
# Tool to support keeping CDR server configuration consistent across
# tiers.
#----------------------------------------------------------------------
import cgi
import cdrutil

if __name__ == "__main__":
    fields = cgi.FieldStorage()
    session = fields.getvalue("Session")
    if not cdrutil.can_do(session, "GET SYS CONFIG"):
        print "Status: 403\n\n<h1>Access to tier settings denied</h1>"
        exit(0)
    indent = fields.getvalue("indent") or None
    if indent:
        indent = int(indent)
    settings = cdrutil.Settings("emailers").serialize(indent)
    print "Content-type: application/json\n\n%s" % settings
