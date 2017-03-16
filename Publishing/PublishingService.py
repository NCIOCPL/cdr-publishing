# ========================================================================
# This script starts the publishing service.
#
# BZIssue::3678 - better control over email recipients on lower tiers
# BZIssue::5009 Fix PublishingService.py
# OCECDR-3727: Bug in Publishing Verification on Lower Tiers
# OCECDR-4096: fix bug which closed cursor prematurely
# ========================================================================
import cdrdb, cdrbatch, os, time, cdr, sys, string, cdr2gk

# Sleep time between checks for things to do
sleepSecs = len(sys.argv) > 1 and string.atoi(sys.argv[1]) or 10

# Script and log file for publishing
PUBSCRIPT = cdr.BASEDIR + "/publishing/publish.py"
LOGNAME   = "publish.log"
BANNER    = "*************** Starting Publishing Service ***************"
SENDER    = "NCIPDQoperator@mail.nih.gov"
emailDL   = cdr.getEmailList('Developers Notification')
SUBJECT   = "%s: *** Error Starting Publishing Service ***" % \
                                          cdr.PUB_NAME.capitalize()
BODY      = """
<html>
 <head>
  <title>Publishing Error Notification</title>
 </head>
 <body>
  <h3>Publishing Error Notification</h3>
   The CDR publishing software is unable to open the log file. <br/>
   Please check permissions for d:\cdr\log\%s
""" % LOGNAME
FOOTER    = """
 </body>
</html>"""

PUBLOG      = cdr.PUBLOG
LOGFLAG     = cdr.DEFAULT_LOGDIR + "/LogLoop.on"
VERIFYFLAG  = cdr.DEFAULT_LOGDIR + "/VerifyPushJobsLoop.on"
LogDelay    = 0
VerifyDelay = 0


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

# If we can't open the log file it's most likely due to permission problems
# (This typically only happens when the server has been rebuild).
# Submit an email because we're unable to log any problems.
# -------------------------------------------------------------------------
try:
    l = cdr.Log(LOGNAME, banner = BANNER)
except IOError, info:
    body = BODY + "<br/><br/>Error Message:<br/>%s" % info + FOOTER
    cdr.sendMail(SENDER, emailDL, SUBJECT, body, html=1)

#----------------------------------------------------------------------
# Check to see whether we should check the disposition of documents
# pushed to Cancer.gov.  The presense of the file VERIFYFLAG tells
# us whether we should ever check.  A countdown integer is used to
# throttle the checks so we're not performing it every time we go
# through the top-level loop.
#----------------------------------------------------------------------
def timeToVerifyPushJobs():

    global VerifyDelay

    if os.path.isfile(VERIFYFLAG):
        if VerifyDelay:
            VerifyDelay -= 1
            return False
        try:
            f = open(VERIFYFLAG)
            VerifyDelay = int(f.readline().strip())
            f.close()
        except:
            VerifyDelay = 360
        return True
    return False

def logLoop():

    global LogDelay
    # If the flag file exists, add a line to the publication log.
    try:
        if os.path.isfile(LOGFLAG):
            if not LogDelay:
                l.write('CDR Publishing Service: Top of processing loop')
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

    l.write("verifying push job %d" % jobId)

    # Local values.
    failures = []
    warnings = []
    target   = "Live"
    verified = True

    # Find out which host the job was sent to, if overridden.
    cursor.execute("""\
        SELECT parm_value
          FROM pub_proc_parm
         WHERE pub_proc = ?
           AND parm_name = 'GKServer'""", jobId)
    rows = cursor.fetchall()
    host = rows and rows[0][0] or None

    # Retrieve status information from Cancer.gov for the push job.
    # Note: If no host has been specified we're using the default host.
    #       However, without the "else"-statement the default host would
    #       be redefined to the new host, so we're redefining the default
    #       again.
    # -------------------------------------------------------------------
    if host:
        cdr2gk.host = host
    else:
        host = "%s.%s" % (cdr.h.host['GK'][0], cdr.h.host['GK'][1])
        cdr2gk.host = host

    response = cdr2gk.requestStatus('Summary', jobId)
    details = response.details

    # Check each of the documents in the job.
    for doc in details.docs:

        # Remember if any warnings have been reported.
        if doc.status == "Warning":
            warnings.append(doc)

        # Find out if the document failed the load.
        if "Error" in (doc.status, doc.dependentStatus):
            failures.append(doc)

        # If it hasn't failed, and it finished loading, the loading
        # process is still under way, so we can't verify the status
        # of the job yet.
        elif doc.location != target:
            verified = False
            break

    # If the load is done, update the status of the job.
    if verified:

        # Mark failed docs.
        for doc in failures:
            cursor.execute("""\
                UPDATE pub_proc_doc
                   SET failure = 'Y'
                 WHERE pub_proc = ?
                   AND doc_id = ?""", (jobId, doc.cdrId))
        if failures:
            conn.commit()

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
        then[3] -= 15
        then = time.localtime(time.mktime(then))
        then = time.strftime("%Y-%m-%d %H:%M:%S", then)

        # If it's been longer than 15 hours, the job is probably stuck.
        # Note: This should only happen if very many summaries have to
        #       be processed.
        l.write("verifying push job: then=%s pushFinished=%s" %
                     (then, str(pushFinished)))
        if then > str(pushFinished):
            reportLoadProblems(jobId, stalled = True)
            cursor.execute("""\
                UPDATE pub_proc
                   SET status = 'Stalled'
                 WHERE id = ?""", jobId)
            conn.commit()

#----------------------------------------------------------------------
# Send out an alert for problems with loading of a push job.
#----------------------------------------------------------------------
def reportLoadProblems(jobId, failures = None, warnings = None,
                       stalled = False):

    # Gather some values needed for the call to cdr.sendMail().
    import cdrcgi
    # sender = "cdr@%s" % cdrcgi.WEBSERVER
    sender = "cdr@%s" % cdr.CBIIT_NAMES[1]
    url = ("%s/cgi-bin/cdr/GateKeeperStatus.py?jobId=%d&targetHost=%s&flavor=all" %
           (cdr.CBIIT_NAMES[2], jobId, cdr2gk.host))

    # Don't send the notification to everyone if we're on the test server
    # if cdr2gk.host == 'bach.nci.nih.gov':
    if cdr.h.tier == 'PROD':
        recips = cdr.getEmailList('PushVerificationAlerts')
    else:
        recips = cdr.getEmailList('Test PushVerificationAlerts')

    # Different message and subject for jobs that are stuck.
    if stalled:
        if cdr.h.org == 'OCE':
            subject = "%s: Push job %d stalled" % (cdr.PUB_NAME.capitalize(),
                                                   jobId)
        else:
            subject = "%s-%s: Push job %d stalled" % (cdr.h.org, cdr.h.tier,
                                                      jobId)
        body = """\
More than 15 hours have elapsed since completion of the push of CDR
documents for publishing job %d, and loading of the documents
has still not completed.
""" % jobId

    # The job finished, but there were problems reported.
    else:
        # subject = "Problems with loading of job %d to Cancer.gov" % jobId
        if cdr.h.org == 'OCE':
            subject = "%s: Problems with loading of job %d to Cancer.gov" % (
                                             cdr.PUB_NAME.capitalize(), jobId)
        else:
            subject = "%s-%s: Problems with loading of job %d to Cancer.gov" % (
                                             cdr.h.org, cdr.h.tier, jobId)
        body = """\
%d failures and %d warnings were encountered in the loading of documents
for job %d to Cancer.gov.
""" % (len(failures), len(warnings), jobId)

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
            l.write("PublishingService starting job %d" % row[0])
            print "publishing job %d" % row[0]
            os.spawnv(os.P_NOWAIT, cdr.PYTHON, ("CdrPublish", PUBSCRIPT,
                                                str(row[0])))

        # Batch jobs
        try:
            cursor = conn.cursor()
            cursor.execute(batchQry)
            rows = cursor.fetchall()
            cursor.close()
            cursor = None

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
                    l.write ("Daemon: about to show initiation of %s" %\
                                  script, cdrbatch.LF)
                    cdrbatch.sendSignal (conn, jobId, cdrbatch.ST_INITIATING,
                                         cdrbatch.PROC_DAEMON)
                    l.write ("Daemon: back from initiation", cdrbatch.LF)

                    # Close any open transactions.
                    conn.commit()

                    # Spawn the job
                    # Haven't found a good way to find out if it worked
                    # Return code doesn't help much
                    # Called job should update status to cdrbatch.ST_INPROCESS
                    l.write ("Daemon: about to spawn: %s %s" % \
                                  (cmd, script), cdrbatch.LF)
                    os.spawnv (os.P_NOWAIT, cmd, (cmd, script))

                    # Record it
                    l.write ("Daemon: spawned: %s %s" % (cmd, script),
                                  cdrbatch.LF)
        # Log any errors
        except cdrbatch.BatchException, be:
            l.write ("Daemon - batch execution error: %s", str(be),
                          cdrbatch.LF)
        except cdrdb.Error, info:
            l.write ("Daemon - batch database error: %s" % info[1][0],
                          cdrbatch.LF)
            conn = None

        # Verify loading of documents pushed to Cancer.gov.
        if conn and timeToVerifyPushJobs():
            try:
                cursor = conn.cursor()
                cursor.execute("""\
                    SELECT id, completed
                      FROM pub_proc
                     WHERE status = 'Verifying'
                  ORDER BY id""")
                for jobId, completed in cursor.fetchall():
                    verifyLoad(jobId, completed, cursor, conn)
                cursor.close()
                cursor = None
            except Exception, e:
                try:
                    l.write("failure verifying push jobs: %s" % e)
                except:
                    pass

    except cdrdb.Error, info:
        # Log publishing job initiation errors
        try:
            conn = None
            l.write ('Database failure: %s' % info[1][0])
        except:
            pass
    except Exception, e:
        try:
            l.write('Failure: %s' % str(e), tback = True)
        except:
            pass
    except:
        try:
            l.write('Unknown failure', tback = True)
        except:
            pass

    # Do it all again after a decent interval
    try:
        time.sleep(sleepSecs)
    except:
        pass
