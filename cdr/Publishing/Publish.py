#----------------------------------------------------------------------
#
# Bridge PublishingService.py to cdrpub.py
#
# $Id: Publish.py,v 1.3 2002-04-18 01:18:05 bkline Exp $
# $Log: not supported by cvs2svn $
# Revision 1.2  2002/04/04 22:44:55  bkline
# Modified to match new cdrpub.py.
#
# Revision 1.1  2002/02/20 22:25:10  Pzhang
# First version of GOOD publish.py.
#
#----------------------------------------------------------------------

import sys, string, cdrpub, time

log = "d:/cdr/log/publish.log" 
jobId = string.atoi(sys.argv[1])
divider = "=" * 60
open(log, "a").write("Job %d: %s\nJob %d: Started at: %s\n" % \
    (jobId, divider, jobId, time.ctime(time.time())))
try:
    cdrpub.Publish(jobId).publish()
    open(log, "a").write("Job %d: Ended at: %s\nJob %d: %s\n" % \
        (jobId, time.ctime(time.time()), jobId, divider))
except cdrdb.Error, info:
    open(log, "a").write("Job %d: Database failure: %s\n" % (jobId, info[1][0]))
except StandardError, arg:
    open(log, "a").write("Job %d: Failure: %s\n" % (jobId, arg[0]))
except:
    open(log, "a").write("Job %d: Unexpected failure\n" % jobId)
