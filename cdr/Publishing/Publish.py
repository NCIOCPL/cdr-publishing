#----------------------------------------------------------------------
#
# Bridge PublishingService.py to cdrpub.py
#
# $Id: Publish.py,v 1.1 2002-02-20 22:25:10 Pzhang Exp $
# $Log: not supported by cvs2svn $
#
#----------------------------------------------------------------------

import sys, string, cdrpub, time

log = "d:/cdr/log/publish.log" 
jobId = string.atoi(sys.argv[1])
open(log, "a").write("Job %d: Started at: %s\n" % \
    (jobId, time.ctime(time.time())))
cdrpub.Publish("", "", "", [], [], jobId = jobId).publish()
open(log, "a").write("Job %d: Ended at: %s\n" % \
    (jobId, time.ctime(time.time())))
       
