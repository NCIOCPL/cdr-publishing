#!/usr/bin/python
#----------------------------------------------------------------------
# Show a piece of a log file.
#----------------------------------------------------------------------
import os, cgi, sys, time, re

DEFAULT_COUNT = 2000000

LOGDIR = "/weblogs/gpmailers"
LOGS = ("access_log", "error_log", "gpmailers.log")

def makeAscii(s):
    return re.sub(u"[\x80-\xff%]", lambda m: "%%%02X" % ord(m.group(0)[0]), s)

def showForm(info=""):
    print """\
Content-type: text/html

<html>
 <head>
  <title>GP Mailers Log Viewer</title>
  <style type="text/css">
   * { font-family: sans-serif }
   label { width: 50px; padding-bottom: 5px; display: inline-block; }
   #log, #start, #count { width: 100px; }
  </style>
 </head>
 <body>
  <h1>GP Mailers Log Viewer</h1>
  <p>%s</p>
  <form action="log-tail.py" method="POST">
   <label for="path">Log: </label>
   <select id="log" name="l">%s
   </select><br>
   <label for="start">Start: </label>
   <input name="s" id="start"><br>
   <label for="count">Count: </label>
   <input name="c" id="count"><br><br>
   <input type="submit">
  </form>
 </body>
</html>
""" % (info, 
       "".join(['<option value="%s">%s</option>' % (l, l) for l in LOGS]))

fields = cgi.FieldStorage()
l = fields.getvalue("l") or ""
s = fields.getvalue("s") or ""
c = fields.getvalue("c") or ""

if l in LOGS:
    try:
        p = "%s/%s" % (LOGDIR, l)
        stat = os.stat(p)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(stat.st_mtime))
        info = "%s %s bytes (%s GMT)" % (p, stat.st_size, stamp)
        count = long(c or DEFAULT_COUNT)
        start = long(s or "0")
        if count < 0:
            count = 0
        if not start and s != "0":
            if not count:
                count = DEFAULT_COUNT
            if count > stat.st_size:
                count = stat.st_size
            else:
                start = stat.st_size - count
        else:
            if start < 0:
                if abs(start) > stat.st_size:
                    start = 0
                else:
                    start = stat.st_size + start
            elif start > stat.st_size:
                start = stat.st_size
            available = stat.st_size - start
            if count > available:
                count = available
        if count:
            fp = open(p)
            if start:
                fp.seek(start)
            bytes = fp.read(count)
            print "Content-type: text/plain\n"
            print "%s bytes %d-%d\n" % (info, start + 1, start + count)
            print makeAscii(bytes)
        else:
            showForm(info)
    except Exception, e:
        print "Content-type: text/plain\n\n%s" % repr(e)
else:
    showForm()
