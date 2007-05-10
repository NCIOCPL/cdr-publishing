#
# This script starts the publishing service.
#
# $Id: PublishingService.py,v 1.11 2007-05-10 02:33:51 bkline Exp $
# $Log: not supported by cvs2svn $
# Revision 1.10  2006/10/20 04:22:20  ameyer
# Added logging to publishing job start.
#
# Revision 1.9  2004/07/08 19:16:58  bkline
# Made the script as bulletproof as possible by catching every possible
# exception.
#
# Revision 1.8  2004/07/08 18:58:48  bkline
# Cleaned up loop logging.
#
# Revision 1.7  2004/06/01 20:34:14  bkline
# Added code to optionally add a line to the publication log at the top
# of the processing loop.
#
# Revision 1.6  2002/08/02 03:45:29  ameyer
# Added batch job initiation and logging.
#
# Revision 1.5  2002/02/20 22:25:10  Pzhang
# First version of GOOD publish.py.
#
# Revision 1.4  2002/02/20 15:10:14  pzhang
# Modified SCRIPT to point to /cdr/lib/python/publish.py. Avoided duplicate
# files in /cdr/publishing/publish.py this way.
#
# Revision 1.3  2002/02/19 23:13:33  ameyer
# Removed SCRIPT and replaced it with BASEDIR in keeping with new decisions
# about where things are.
#
# Revision 1.2  2002/02/06 16:22:39  pzhang
# Added Log. Don't want to change SCRIPT here; change cdr.py.
#
#

import cdrdb, cdrbatch, os, time, cdr, sys, string

# Sleep time between checks for things to do
sleepSecs = len(sys.argv) > 1 and string.atoi(sys.argv[1]) or 10

# Script and log file for publishing
PUBSCRIPT = cdr.BASEDIR + "/publishing/publish.py"
PUBLOG    = cdr.PUBLOG
LOGFLAG   = cdr.DEFAULT_LOGDIR + "/LogLoop.on"
LogDelay  = 0

# Publishing queries
query  = """\
SELECT id
  FROM pub_proc
 WHERE status = 'Ready'
"""
update = """\
UPDATE pub_proc
   SET status = 'Started'
 WHERE status = 'Ready'
"""

# Query for batch job initiation
batchQry = "SELECT id, command FROM batch_job WHERE status='%s'" %\
           cdrbatch.ST_QUEUED

def logLoop():

    global LogDelay
    # If the flag file exists, add a line to the publication log.
    try:
        if os.path.isfile(LOGFLAG):
            if not LogDelay:
                cdr.logwrite('CDR Publishing Service: Top of processing loop',
                             PUBLOG)
                file = open(LOGFLAG)
                try:
                    LogDelay = int(file.readline().strip())
                except:
                    LogDelay = 0
                file.close()
            else:
                LogDelay -= 1
        else:
            LogDelay = 0
    except:
        LogDelay = 0

#----------------------------------------------------------------------
# Find out if loading of documents to Cancer.gov has completed, and
# whether any of the documents failed the load.
#----------------------------------------------------------------------
def verifyLoad(jobId, pushFinished, cursor, conn):
    
    cdr.logwrite("verifying push job %d" % jobId, PUBLOG)
    import cdr2gk
    
    # Local values.
    failures = 0
    warnings = 0
    target   = "Live"
    verified = True

    # Retrieve status information from Cancer.gov for the push job.
    import cdr2gk
    response = cdr2gk.requestStatus('Summary', jobId)
    details = response.details

    # Check each of the documents in the job.
    for doc in details.docs:

        # Remember if any warnings have been reported.
        if doc.status == "Warning":
            warnings += 1

        # Find out if the document failed the load.
        if "Error" in (doc.status, doc.dependentStatus):
            failures += 1

        # If it hasn't failed, and it finished loading, the loading
        # process is still under way, so we can't verify the status
        # of the job yet.
        elif doc.location != target:
            verified = False
            break

    # If the load is done, update the status of the job.
    if verified:

        # Notify the appropriate people of any problems found.
        if failures or warnings:
            reportLoadProblems(jobId, failures, warnings)

        # If every document failed the load, mark the status for the
        # entire job as Failure; however, if even 1 document was
        # successfully loaded to the live site, we must set the
        # status to Success; otherwise, software to find out whether
        # that document is on Cancer.gov may return the wrong answer.
        #
        # Note that if the attempt to report any problems fails,
        # we won't reach this code, because an exception will have
        # been thrown.  That's appropriate, because we don't want
        # to close out a job with problems going undetected.
        if len(failures) == len(details.docs):
            jobStatus = "Failure"
        else:
            jobStatus = "Success"
        cursor.execute("""\
            UPDATE pub_proc
               SET status = ?
             WHERE id = ?""", (jobStatus, jobId))
        conn.commit()

    # The load hasn't yet finished; find out how long we've been waiting.
    else:
        now = time.localtime()
        then = list(now)
        then[2] -= 1
        then = time.localtime(time.mktime(then))
        yesterday = time.strftime("%Y-%m-%d %H:%M:%S", then)

        # If it's been longer than a day, the job is probably stuck.
        if yesterday < str(pushFinished):
            reportLoadProblems(jobId, stalled = True)
            cursor.execute("""\
                UPDATE pub_proc
                   SET status = 'Stalled'
                 WHERE id = ?""", jobId)
            conn.commit()

#----------------------------------------------------------------------
# Send out an alert for problems with loading of a push job.
#----------------------------------------------------------------------
def reportLoadProblems(jobId, failures = 0, warnings = 0, stalled = False):

    # Gather some values needed for the call to cdr.sendMail().
    import cdrcgi
    sender = "cdr@%s" % cdrcgi.WEBSERVER
    url = ("http://%s%s/GateKeeperStatus.py?jobId=%d&targetHost=%s" %
           (cdrcgi.WEBSERVER, cdrcgi.BASE, jobId, cdr2gk.host))
    recips = cdr.getEmailList('xPushVerificationAlerts')

    # Different message and subject for jobs that are stuck.
    if stalled:
        subject = "Push job %d stalled" % jobId
        body = """\
More than 24 hours have elapsed since completion of the push of CDR
documents for publishing job %d, and loading of the documents
has still not completed.
""" % jodId

    # The job finished, but there were problems reported.
    else:
        subject = "Problems with loading of job %d to Cancer.gov" % jobId
        body = """\
%s were encountered in the loading of documents for job %d
to Cancer.gov.
""" % (failures and "Errors" or "Warnings", jobId)

    # Provide a link to a web page where the status of each document
    # in the job can be checked.
    body += """
Please visit the following link for further details:

%s
""" % url

    # Make sure the alert gets sent to someone.
    if not recips:
        recips = ['***REMOVED***']
        body += """
*** NO RECIPIENTS FOUND FOR ALERT NOTIFICATION GROUP ***
"""

    # Make sure the mail gets out.
    errors = cdr.sendMail(sender, recips, subject, body)
    if errors:
        raise cdr.Exception("reportLoadProblems(): %s" % errors)
    
conn = None
while True:
    try:

        # Let the world know we're still alive.
        logLoop()

        # Connection for all efforts
        if not conn:
            conn = cdrdb.connect("CdrPublishing")
        cursor = conn.cursor()

        # Publishing
        cursor.execute(query)
        rows = cursor.fetchall()
        if len(rows):
            cursor.execute(update)
        conn.commit()
        cursor.close()
        cursor = None
        for row in rows:
            cdr.logwrite("PublishingService starting job %d" % row[0], PUBLOG)
            print "publishing job %d" % row[0]
            os.spawnv(os.P_NOWAIT, cdr.PYTHON, ("CdrPublish", PUBSCRIPT,
                                                str(row[0])))

        # Batch jobs
        try:
            cursor = conn.cursor()
            cursor.execute(batchQry)
            rows = cursor.fetchall()

            if len (rows):
                # Process each queued job
                for jobId, cmd in rows:
                    # Is the command cdr relative or absolute?
                    if not os.path.isabs (cmd):
                        cmd = cdr.BASEDIR + '/' + cmd

                    # By convention, all jobs take a job id as last parameter
                    script = "%s %d" % (cmd, jobId)

                    # Distinguish scripts requiring an interpreter from others
                    # Python script
                    if cmd.endswith ('.py'):
                        cmd = cdr.PYTHON

                    # Perl script (may never be used)
                    elif cmd.endswith ('.pl'):
                        cmd = cdr.PERL

                    # Executable or .bat/.cmd file
                    else:
                        cmd = script
                        script = ""

                    # Indicate that we are initiating job
                    cdr.logwrite ("Daemon: about to show initiation of %s" %\
                                  script, cdrbatch.LF)
                    cdrbatch.sendSignal (conn, jobId, cdrbatch.ST_INITIATING,
                                         cdrbatch.PROC_DAEMON)
                    cdr.logwrite ("Daemon: back from initiation", cdrbatch.LF)

                    # Done with cursor
                    conn.commit()
                    cursor.close()

                    # Spawn the job
                    # Haven't found a good way to find out if it worked
                    # Return code doesn't help much
                    # Called job should update status to cdrbatch.ST_INPROCESS
                    cdr.logwrite ("Daemon: about to spawn: %s %s" % \
                                  (cmd, script), cdrbatch.LF)
                    os.spawnv (os.P_NOWAIT, cmd, (cmd, script))

                    # Record it
                    cdr.logwrite ("Daemon: spawned: %s %s" % (cmd, script),
                                  cdrbatch.LF)
        # Log any errors
        except cdrbatch.BatchException, be:
            cdr.logwrite ("Daemon - batch execution error: %s", str(be),
                          cdrbatch.LF)
        except cdrdb.Error, info:
            cdr.logwrite ("Daemon - batch database error: %s" % info[1][0],
                          cdrbatch.LF)
            conn = None

        # Verify loading of documents pushed to Cancer.gov.
        try:
            cursor.execute("""\
                SELECT id, completed
                  FROM pub_proc
                 WHERE status = 'Verifying'
              ORDER BY id""")
            for row in cursor.fetchall():
                verifyLoad(row[0], row[1], cursor, conn)
        except Exception, e:
            try:
                cdr.logwrite("failure verifying push jobs: %s" % e)
            except:
                pass
                
    except cdrdb.Error, info:
        # Log publishing job initiation errors
        try:
            conn = None
            cdr.logwrite ('Database failure: %s' % info[1][0], PUBLOG)
        except:
            pass
    except Exception, e:
        try:
            cdr.logwrite('Failure: %s' % str(e), logfile = PUBLOG,
                         tback = True)
        except:
            pass
    except:
        try:
            cdr.logwrite('Unknown failure', logfile = PUBLOG, tback = True)
        except:
            pass

    # Do it all again after a decent interval
    try:
        time.sleep(sleepSecs)
    except:
        pass
