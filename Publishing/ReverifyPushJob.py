# ========================================================================
# ReverifyPushJob.py
# ------------------
# Script to re-verify a job if documents failed processing on Gatekeeper
# due to a bug at the GK side.  Once the bug has been corrected and the
# documents have been re-processed successfully, the CDR will still have
# the picture of the document(s) not being published properly.  This
# tool will re-ajust the picture between the CDR and GK.
# This program has been adapted from PublishingService.py.
#                                           Volker Englisch, 2011-09-22
#
# BZIssue::5087 - [Internal] Create Re-Verification Tool
# ========================================================================
import cdrdb, cdrbatch, os, time, cdr, sys, string, cdr2gk, optparse

# Script and log file for publishing
LOGNAME = "publish.log"
PUBLOG  = cdr.PUBLOG
uid = pw = sessionID = None

# Publishing query
# ----------------
status = 'Stalled'
query  = """\
SELECT id
  FROM pub_proc
 WHERE status = '%s'
"""

# ------------------------------------------------------------
# Function to parse the command line arguments
# ------------------------------------------------------------
def parseArguments(args):
    """
    Assign all input parameters to variables and perform some error
    checking.
    """

    usage = "usage: %prog [--livemode | --testmode] --user=UID --passwd=PW [options]"
    parser = optparse.OptionParser(usage = usage)
    global transferDate

    parser.set_defaults(testMode = True)
    parser.add_option('-t', '--testmode',
                      action = 'store_true', dest = 'testMode',
                      help = 'running in TEST mode')
    parser.add_option('-l', '--livemode',
                      action = 'store_false', dest = 'testMode',
                      help = 'running in LIVE mode')
    parser.add_option('-u', '--user',
                      action = 'store', dest = 'uid',
                      help = 'userId')
    parser.add_option('-p', '--passwd',
                      action = 'store', dest = 'pw',
                      help = 'password')
    parser.add_option('-s', '--status',
                      action = 'store', dest = 'status',
                      help = 'Status of job to re-verify (must also '
                                                    'provide Job-ID)')
    parser.add_option('-j', '--jobid',
                      action = 'store', dest = 'jobid',
                      help = 'JobID for job to re-verify (must also '
                                                    'provide status)')
    parser.add_option('-i', '--session',
                      action = 'store', dest = 'session',
                      help = 'User SessionID (unless user/pw are specified)')

    # Exit if no command line argument has been specified
    # ---------------------------------------------------
    if len(args[1:]) == 0:
        parser.print_help()
        sys.exit('No arguments given!')

    (options, args) = parser.parse_args()

    # Read and process options, if any
    # --------------------------------
    if parser.values.testMode:
        l.write("Running in TEST mode", stdout = True)
    else:
        l.write("Running in LIVE mode", stdout = True)

    if parser.values.status and not parser.values.jobid:
        parser.print_help()
        sys.exit('Must provide Job-ID and Status')
    elif not parser.values.status and parser.values.jobid:
        parser.print_help()
        sys.exit('Must provide Job-ID and Status')
    return parser


# Open the logfile
# --------------------------------------------------
l = cdr.Log(LOGNAME)
l.write("ReverifyPubJob - Started", stdout = True)
l.write('Arguments: %s' % sys.argv)

options   = parseArguments(sys.argv)
testMode  = options.values.testMode

if options.values.uid:
    uid       = options.values.uid
    pw        = options.values.pw
else:
    sessionID = options.values.session

if options.values.status and options.values.jobid:
    status = options.values.status
    jobid  = options.values.jobid

#----------------------------------------------------------------------
# Find out if loading of documents to Cancer.gov has completed, and
# whether any of the documents failed the load.
#----------------------------------------------------------------------
def updateMessage(message, jobId, docId = 0):
    # Create log message
    # ------------------
    if docId == 0:
        msg = '\n<br><span style="font-weight: bold;">%s: %s</span>' % (
                                                  time.ctime(), message)
    else:
        msg = "%s: %s\n" % (time.ctime(), message)

    # Updating job status
    if docId == 0:
        try:
            # Relies on DBMS for synchronization
            cursor = conn.cursor()
            cursor.execute("""
                SELECT messages
                  FROM pub_proc
                 WHERE id = ?""", jobId)
            row     = cursor.fetchone()
            msg = (row and row[0] or '') + msg

            cursor.execute("""
                UPDATE pub_proc
                   SET messages  = ?
                 WHERE id        = ?""", (msg, jobId))
            conn.commit()
        except cdrdb.Error, info:
            msg = 'Failure updating pub_proc messages: %s' % info[1][0]
            l.write(msg)
            raise Exception(msg)
    # Updating Document status
    else:
        try:
            # Relies on DBMS for synchronization
            cursor = conn.cursor()
            cursor.execute("""
                SELECT messages
                  FROM pub_proc_doc
                 WHERE pub_proc = ?
                   AND doc_id = ?""", (jobId, docId))
            row     = cursor.fetchone()
            msg = (row and row[0] or '') + msg

            cursor.execute("""
                UPDATE pub_proc_doc
                   SET messages = ?
                 WHERE pub_proc = ?
                   AND doc_id   = ?""", (msg, jobId, docId))
            conn.commit()
        except cdrdb.Error, info:
            msg = 'Failure updating pub_proc_doc messages: %s' % info[1][0]
            l.write(msg)
            raise Exception(msg)
    return


#----------------------------------------------------------------------
# Find out if loading of documents to Cancer.gov has completed (i.e.
# all documents "arrived" on live, and whether any of the documents
# failed the load.
#----------------------------------------------------------------------
def verifyLoad(jobId, pushFinished, cursor, conn, testMode = 'True'):

    # l.write("Re-verifying push job %d" % jobId, stdout = True)

    # Local values.
    # -------------
    failures = []
    warnings = []
    target   = "Live"
    verified = True

    # Find out which host the job was sent to, if overridden.
    # -----------------------------------------------------------
    cursor.execute("""\
        SELECT parm_value
          FROM pub_proc_parm
         WHERE pub_proc = ?
           AND parm_name = 'GKServer'""", jobId)
    rows = cursor.fetchall()
    host = rows and rows[0][0] or None


    # Retrieve status information from Cancer.gov for the push job
    # and identify failures and warnings.
    # ------------------------------------------------------------
    l.write("GKServer: %s" % (host or cdr2gk.HOST), stdout=True)

    response = cdr2gk.requestStatus('Summary', jobId, host=host)

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
            l.write("Still processing documents", stdout = True)
            break

    # If the load is done, update the status of the job.
    # --------------------------------------------------
    if verified:
        # Mark failed docs.
        # -----------------
        # a) Need to reset all previously failed docs first
        #    Add a comment listing the last failure status.
        # -------------------------------------------------
        if testMode:
            cursor.execute("""\
                SELECT count(*)
                  FROM pub_proc_doc
                 WHERE pub_proc = ?""", jobId)
            rows = cursor.fetchall()
            l.write('Total records for this publishing job: %d' % rows[0][0],
                                                               stdout = True)
            cursor.execute("""\
                SELECT count(*)
                  FROM pub_proc_doc
                 WHERE pub_proc = ?
                   AND failure = 'Y'""", jobId)
            rows = cursor.fetchall()
            l.write('Failed records for this publishing job: %d' % rows[0][0],
                                                               stdout = True)
        else:
            cursor.execute("""\
                SELECT doc_id, failure
                  FROM pub_proc_doc
                 WHERE pub_proc = ?
                   AND failure = 'Y'""", jobId)
            rows = cursor.fetchall()

            for row in rows:
                try:
                    cursor.execute("""\
                        UPDATE pub_proc_doc
                           SET failure = Null
                         WHERE pub_proc = ?
                           AND doc_id = ?""", (jobId, int(row[0])))
                    conn.commit()
                except:
                    l.write('Error resetting failure column in pub_proc_doc',
                                                               stdout = True)
                    sys.exit(1)

                # Add a comment but preserve existing comments.
                # ---------------------------------------------
                updateMessage(u'Resetting failure=%s to re-verify.' % row[1],
                                                         jobId, row[0])

        # b) Setting all docs to failure that still failed
        # ------------------------------------------------
        if failures:
            if testMode:
                print len(failures)
                cursor.execute("""\
                    SELECT *
                      FROM pub_proc_doc
                     WHERE pub_proc = %d
                       AND doc_id in (%s)""" % (jobId,
                                 ','.join(["%s" % x.cdrId for x in failures])))
                rows = cursor.fetchall()
                l.write('Records failed:', stdout = True)
                for row in rows:
                    l.write(repr(row), stdout = True)
                l.write('', stdout = True)
            else:
                for doc in failures:
                    cursor.execute("""\
                        UPDATE pub_proc_doc
                           SET failure = 'Y'
                         WHERE pub_proc = ?
                           AND doc_id = ?""", (jobId, doc.cdrId))
                    conn.commit()
                    updateMessage(u'Setting failure=Y at re-verify.',
                                                             jobId, doc.cdrId)
        else:
            l.write('Failures: None', stdout = True)

        # Print out the information if we're still listing failures
        if failures or warnings:
            l.write("Job %s" % jobId, stdout = True)
            l.write("Failures: %s" % failures, stdout = True)
            l.write("Warnings: %s" % warnings, stdout = True)
            l.write("", stdout = True)

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
        # -----------------------------------------------------------
        if len(failures) == len(details.docs):
            jobStatus = "Failure"
        else:
            jobStatus = "Success"
        if testMode:
            l.write("Test mode: Job status not updated", stdout = True)
        else:
            cursor.execute("""\
                SELECT status
                  FROM pub_proc
                 WHERE id = ?""", jobId)
            rows = cursor.fetchall()
            updateMessage(u'Re-verify push job. '
                           'Old job status = %s' % rows[0][0], jobId, docId = 0)
            cursor.execute("""\
                UPDATE pub_proc
                   SET status = ?
                 WHERE id = ?""", (jobStatus, jobId))
            conn.commit()
            updateMessage(u'Re-verify push job. '
                           'New job status = %s' % jobStatus, jobId, docId = 0)
        l.write("Status of Job %s set to '%s'" % (jobId, jobStatus),
                                                        stdout = True)
        return


# -------------------------------------------------------------------
# MAIN starts here
# -------------------------------------------------------------------
# Checking CDR user or session ID
# (the session ID is passed when running from the Admin interface)
# ----------------------------------------------------------------
error = None
sessionUsr = None

if sessionID:
     session = sessionID
     sessionUsr = cdr.idSessionUser('', session)
else:
     session = cdr.login(uid, pw)
     error   = cdr.checkErr(session)

# Exit if the session ID is unknown or the user credentials are invalid
# ---------------------------------------------------------------------
if sessionID and not sessionUsr:
    l.write("*** Invalid or expired session ID: %s" % session, stdout = True)
    sys.exit(1)

if error:
    l.write("*** Error logging in: %s" % error, stdout = True)
    sys.exit(1)

try:
    # Connection for all efforts
    # --------------------------
    conn = cdrdb.connect("cdr")
    cursor = conn.cursor()

    # We're re-verifying all stalled jobs but if we're re-verifying
    # non-stalled jobs we're only doing one at a time.
    # -------------------------------------------------------------
    newQuery = query % status
    if status == 'Stalled':
        cursor.execute(newQuery)
        rows = cursor.fetchall()
    else:
        newQuery += '   AND id = %d' % int(jobid)
        cursor.execute(newQuery)
        rows = cursor.fetchall()
        if len(rows) > 1:
            l.write('*** Error: Only one job at a time allowed', stdout = True)
            l.write('Query:\n%s' % newQuery, stdout = True)
            l.write('Result:\n%s' % rows, stdout = True)
            sys.exit(1)

    if rows:
        l.write("", stdout = True)
        l.write("List of jobs to re-verify", stdout = True)
        l.write("-------------------------", stdout = True)
        for row in rows:
            l.write("Job %d, Status: %s" % (row[0], status), stdout = True)
        l.write("", stdout = True)
    else:
        l.write("No job(s) found to re-verify!", stdout = True)
        sys.exit(0)

    # Verify loading of documents pushed to Cancer.gov.
    # -------------------------------------------------
    try:
        newQuery = u"""\
            SELECT id, completed
              FROM pub_proc
             WHERE status = '%s'""" % status

        if status == 'Stalled':
            cursor.execute(newQuery)
        else:
            newQuery += '   AND id = %d' % int(jobid)
            cursor.execute(newQuery)

        rows = cursor.fetchall()

        for row in rows:
            l.write("Job %d, Completed: %s" % (row[0], row[1]),
                                                            stdout = True)
            verifyLoad(row[0], row[1], cursor, conn, testMode)
            l.write("Verification for Job %d done." % row[0], stdout = True)
    except Exception, e:
        l.write("failure re-verifying push jobs: %s" % e, stdout = True)

except cdrdb.Error, info:
    # Log publishing job initiation errors
    conn = None
    l.write ('Database failure: %s' % info[1][0], stdout = True)
except Exception, e:
    l.write('Failure: %s' % str(e), tback = True, stdout = True)
except SystemExit:
    l.write('Exiting...', stdout = True)
except:
    l.write('Unknown failure', tback = True, stdout = True)

l.write("ReverifyPubJob - Finished", stdout = True)
sys.exit(0)
