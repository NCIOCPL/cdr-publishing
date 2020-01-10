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
import cdrbatch, os, time, cdr, sys, string, cdr2gk, optparse
from cdrapi import db
from cdrapi.users import Session

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
        LOGGER.info("Running in TEST mode")
    else:
        LOGGER.info("Running in LIVE mode")

    if parser.values.status and not parser.values.jobid:
        parser.print_help()
        sys.exit('Must provide Job-ID and Status')
    elif not parser.values.status and parser.values.jobid:
        parser.print_help()
        sys.exit('Must provide Job-ID and Status')
    return parser


# Open the logfile
# --------------------------------------------------
LOGGER = cdr.Logging.get_logger("publish", console=True)
LOGGER.info("ReverifyPubJob - Started")
LOGGER.info('Arguments: %s', sys.argv)

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
def updateMessage(message, jobId, docId=0):
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
            row = cursor.fetchone()
            msg = (row and row[0] or '') + msg

            cursor.execute("""
                UPDATE pub_proc
                   SET messages  = ?
                 WHERE id        = ?""", (msg, jobId))
            conn.commit()
        except Exception as e:
            msg = 'Failure updating pub_proc messages: %s' % e
            LOGGER.exception(msg)
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
            row = cursor.fetchone()
            if row and row[0]:
                try:
                    messages = eval(row[0])
                except:
                    messages = [row[0]]
            else:
                messages = []
            messages.append(msg)
            msg = repr(messages)
            cursor.execute("""
                UPDATE pub_proc_doc
                   SET messages = ?
                 WHERE pub_proc = ?
                   AND doc_id   = ?""", (msg, jobId, docId))
            conn.commit()
        except Exception as e:
            msg = 'Failure updating pub_proc_doc messages: %s' % e
            LOGGER.exception(msg)
            raise Exception(msg)
    return


#----------------------------------------------------------------------
# Find out if loading of documents to Cancer.gov has completed (i.e.
# all documents "arrived" on live, and whether any of the documents
# failed the load.
#----------------------------------------------------------------------
def verifyLoad(jobId, pushFinished, cursor, conn, testMode = 'True'):

    # LOGGER.info("Re-verifying push job %d", jobId)

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
    LOGGER.info("GKServer: %s", host or cdr2gk.HOST)

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
            LOGGER.info("Still processing documents")
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
            rows = cursor.fetchone()
            LOGGER.info('Total records for this publishing job: %d', rows[0])
            cursor.execute("""\
                SELECT count(*)
                  FROM pub_proc_doc
                 WHERE pub_proc = ?
                   AND failure = 'Y'""", jobId)
            rows = cursor.fetchone()
            LOGGER.info('Failed records for this publishing job: %d', rows[0])
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
                    message = "Error resetting failure column in pub_proc_doc"
                    LOGGER.exception(message)
                    sys.exit(1)

                # Add a comment but preserve existing comments.
                # ---------------------------------------------
                updateMessage('Resetting failure=%s to re-verify.' % row[1],
                                                         jobId, row[0])

        # b) Setting all docs to failure that still failed
        # ------------------------------------------------
        if failures:
            if testMode:
                print(len(failures))
                cursor.execute("""\
                    SELECT *
                      FROM pub_proc_doc
                     WHERE pub_proc = %d
                       AND doc_id in (%s)""" % (jobId,
                                 ','.join(["%s" % x.cdrId for x in failures])))
                rows = cursor.fetchall()
                LOGGER.info('Records failed:')
                for row in rows:
                    LOGGER.info(repr(row))
                LOGGER.info('')
            else:
                for doc in failures:
                    cursor.execute("""\
                        UPDATE pub_proc_doc
                           SET failure = 'Y'
                         WHERE pub_proc = ?
                           AND doc_id = ?""", (jobId, doc.cdrId))
                    conn.commit()
                    updateMessage('Setting failure=Y at re-verify.',
                                                             jobId, doc.cdrId)
        else:
            LOGGER.info('Failures: None')

        # Print out the information if we're still listing failures
        if failures or warnings:
            LOGGER.info("Job %s", jobId)
            LOGGER.info("Failures: %s", failures)
            LOGGER.info("Warnings: %s", warnings)
            LOGGER.info("")

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
            LOGGER.info("Test mode: Job status not updated")
        else:
            cursor.execute("""\
                SELECT status
                  FROM pub_proc
                 WHERE id = ?""", jobId)
            rows = cursor.fetchall()
            updateMessage('Re-verify push job. '
                           'Old job status = %s' % rows[0][0], jobId, docId = 0)
            cursor.execute("""\
                UPDATE pub_proc
                   SET status = ?
                 WHERE id = ?""", (jobStatus, jobId))
            conn.commit()
            updateMessage('Re-verify push job. '
                           'New job status = %s' % jobStatus, jobId, docId = 0)
        LOGGER.info("Status of Job %s set to '%s'", jobId, jobStatus)
        return


# -------------------------------------------------------------------
# MAIN starts here
# -------------------------------------------------------------------
# Checking CDR user or session ID
# (the session ID is passed when running from the Admin interface)
# ----------------------------------------------------------------
if sessionID:
    try:
        Session(sessionID)
        session = sessionID
    except:
        LOGGER.error("*** Invalid or expired session ID: %s", session)
        sys.exit(1)
else:
    session = cdr.login(uid, pw)
    error   = cdr.checkErr(session)
    if error:
        LOGGER.error("*** Error logging in: %s", error)
        sys.exit(1)

try:
    # Connection for all efforts
    # --------------------------
    conn = db.connect()
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
            LOGGER.error('*** Error: Only one job at a time allowed')
            LOGGER.error('Query:\n%s', newQuery)
            LOGGER.error('Result:\n%s', rows)
            sys.exit(1)

    if rows:
        LOGGER.info("")
        LOGGER.info("List of jobs to re-verify")
        LOGGER.info("-------------------------")
        for row in rows:
            LOGGER.info("Job %d, Status: %s", row[0], status)
        LOGGER.info("")
    else:
        LOGGER.info("No job(s) found to re-verify!")
        sys.exit(0)

    # Verify loading of documents pushed to Cancer.gov.
    # -------------------------------------------------
    try:
        newQuery = """\
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
            LOGGER.info("Job %d, Completed: %s", row[0], row[1])
            verifyLoad(row[0], row[1], cursor, conn, testMode)
            LOGGER.info("Verification for Job %d done.", row[0])
    except Exception as e:
        LOGGER.exception("Failure re-verifying push jobs")

except Exception as e:
    LOGGER.exception('Processing failure')
except SystemExit:
    LOGGER.info('Exiting...')
except:
    LOGGER.exception('Unknown failure')

LOGGER.info("ReverifyPubJob - Finished")
sys.exit(0)
