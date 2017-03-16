#----------------------------------------------------------------------
# Bridge PublishingService.py to cdrpub.py
#----------------------------------------------------------------------

import sys, string, cdrdb, cdrpub, time

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
except Exception, arg:
    open(log, "a").write("Job %d: Failure: %s\n" % (jobId, arg[0]))
except SystemExit:
    # The mailers invoke sys.exit(0) when they're done, raising this exception.
    pass
except:
    open(log, "a").write("Job %d: Unexpected failure\n" % jobId)
