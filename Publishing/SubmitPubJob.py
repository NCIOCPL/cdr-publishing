#!d:/python/python.exe
# *********************************************************************
# Program to submit the interim and full export publishing job.
# ---------------------------------------------------------------------
# Created:          2007-04-03        Volker Englisch
# *********************************************************************
import sys
import cdr
import os
import time
from argparse import ArgumentParser
from cdrapi import db


# Setting the host variable to submit the link for the error report
# -----------------------------------------------------------------
host = cdr.APPC
url = 'https://%s' % host

# Setting directory and file names
# --------------------------------
PUBPATH = os.path.join('d:\\cdr', 'publishing')
# PUBPATH = os.path.join('d:\\home', 'venglisch', 'cdr', 'publishing')

TIER = cdr.Tier().name
MAX_RETRIES = 10
RETRY_MULTIPLIER = 5.0
wait = 60    # number of seconds to wait between status checks

# The performance of the publishing job has greatly improved allowing
# us to cancel a running job much sooner if it fails to finish.
# Optionally overriden below once we know the publishing subset.
# --------------------------------------------------------------------
if cdr.isProdHost():
    waitTotal = 10800  # 3.0 hours
elif cdr.isDevHost():
    waitTotal = 10800  # 3.0 hours
else:
    waitTotal = 14400  # 4.0 hours

testMode = None
fullMode = None

session = cdr.login("cdroperator", cdr.getpw("cdroperator"))
pubSystem = 'Primary'

pubEmail = cdr.getEmailList('Operator Publishing Notification')


# ------------------------------------------------------------
# Custom argument parser (so we can log errors).
# ------------------------------------------------------------
class Parser(ArgumentParser):
    JOBMODES = (
        ("interim", "run in interim (nightly) production mode"),
        ("export", "run in export (weekly) production mode"),
    )
    RUNMODES = (
        ("testmode", "run in TEST mode"),
        ("livemode", "run in LIVE mode"),
    )
    MODES = JOBMODES, RUNMODES

    def __init__(self):
        ArgumentParser.__init__(self)
        for modes in self.MODES:
            group = self.add_mutually_exclusive_group(required=True)
            for option, help in modes:
                args = f"--{option}", f"--{option[0]}"
                opts = dict(action="store_true", help=help)
                group.add_argument(*args, **opts)

    def error(self, message):
        LOGGER.error(message)
        self.print_help(sys.stderr)
        sys.stderr.write(f"\n{message}\n")
        sys.exit(1)


# ---------------------------------------------------------------
# Function to check the job status of the submitted publishing
# job.
# ---------------------------------------------------------------
def checkJobStatus(jobId):
    # Defensive programming.
    tries = MAX_RETRIES

    while tries:
        try:
            conn = db.connect(timeout=300)
            cursor = conn.cursor()
            cursor.execute("""\
                SELECT id, status, started, completed, messages
                  FROM pub_proc
                 WHERE id = %d""" % int(jobId))
            row = cursor.fetchone()

            # We can stop trying now, we got it.
            tries = 0

        except Exception:
            LOGGER.exception("*** Failure connecting to DB ***")
            LOGGER.info("*** Unable to check status for PubJob%s", jobId)
            waitSecs = (MAX_RETRIES + 1 - tries) * RETRY_MULTIPLIER
            LOGGER.info("    RETRY: %d retries left; waiting %f seconds",
                        tries, waitSecs)
            time.sleep(waitSecs)
            tries -= 1

    if not row:
        raise Exception("*** (3) Tried to connect %d times. No Pub Job-ID." %
                        MAX_RETRIES)

    return row


# ---------------------------------------------------------------
# Function to set the job status to failure
# On occasion, the publishing job fails to finish (network
# connectivity issues?) and will get cancelled once the max time
# allowed is reached.
# This function sets the job status to 'Failure' so that the job
# status isn't preventing new jobs from being processed because
# only one single job (per job type) is allowed to run at a time.
#
# If testing this function for a job that *not* actually failed be
# prepared that the status gets set to 'Failure' but will be
# updated again - possibly to 'Success' - at the end of the
# "not-really-failed" publishing job.
# ---------------------------------------------------------------
def statusPubJobFailure(jobId):
    # Defensive programming.
    tries = MAX_RETRIES
    row = cursor = None

    while tries:
        try:
            conn = db.connect(timeout=300)
            cursor = conn.cursor()
            cursor.execute("""\
                SELECT id, status, started, completed, messages
                  FROM pub_proc
                 WHERE id = %d""" % int(jobId))
            row = cursor.fetchone()
            LOGGER.info("Job%d status: %s", row[0], row[1])

            # We can stop trying now, we got it.
            tries = 0

        except Exception:
            LOGGER.exception("*** Failure connecting to DB ***")
            LOGGER.warning("*** Unable to set job status to 'Failure'.")
            LOGGER.info("*** PubJob%d", jobId)
            waitSecs = (MAX_RETRIES + 1 - tries) * RETRY_MULTIPLIER
            LOGGER.info("    RETRY: %d retries left; waiting %f seconds",
                        tries, waitSecs)
            time.sleep(waitSecs)
            tries -= 1

    if cursor is None:
        raise Exception("Unable to connect to the database")

    # Setting the job status to 'Failure' rather than leaving it as
    # 'In process'.  That way a new job won't fail until the job
    # status has been manually updated.
    # -------------------------------------------------------------
    try:
        cursor.execute("""\
            UPDATE pub_proc
               SET status = 'Failure'
            WHERE id = %d
               AND status = 'In process'""" % int(jobId))

        conn.commit()
    except Exception:
        LOGGER.exception("*** Failure updating job status ***")
        LOGGER.info("*** Manually set the job status to 'Failure'.")
        LOGGER.info("*** PubJob%s", jobId)

    if not row:
        raise Exception("*** (3) Tried to connect %d times. No Pub Job-ID." %
                        MAX_RETRIES)

    return row


# --------------------------------------------------------------
# Function to find the job ID of the push job.
# --------------------------------------------------------------
def getPushJobId(jobId):
    # Defensive programming.
    tries = MAX_RETRIES
    time.sleep(15)

    while tries:
        try:
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("""\
                SELECT id, status, started, completed
                  FROM pub_proc
                 WHERE id > %d
                   AND pub_system = 178
                   AND (pub_subset LIKE '%%_Interim-Export'
                        OR
                        pub_subset LIKE '%%_Export')
                   """ % int(jobId))
            row = cursor.fetchone()

            # If the SELECT returns nothing a push job was not submitted
            # because another job is still pending.
            # Otherwise the push job may already have completed.
            # -----------------------------------------------------------
            if row is None:
                LOGGER.error("*** Error - No push job waiting. "
                             "Check for pending job")
                cursor.execute("""\
                   SELECT id, messages
                     FROM pub_proc
                    WHERE id = %d""" % int(jobId))
                row = cursor.fetchone()
                LOGGER.info("%s", row[1])
                raise Exception("No push job waiting")

            # We can stop trying now, we got it.
            tries = 0

        except Exception:
            LOGGER.exception("*** Failure connecting to DB ***")
            LOGGER.info("*** Unable to find status for PushJob%s", jobId)
            waitSecs = (MAX_RETRIES + 1 - tries) * RETRY_MULTIPLIER
            LOGGER.info("    RETRY: %d retries left; waiting %f seconds",
                        tries, waitSecs)
            time.sleep(waitSecs)
            tries -= 1

    if not row:
        raise Exception("*** (1) Tried to connect %d times. No Push Job-ID." %
                        MAX_RETRIES)

    return row[0]


# ---------------------------------------------------------------------
# Function to send an email when the job fails instead of silently
# exiting.
# ---------------------------------------------------------------------
def sendFailureMessage(header="*** Error ***", body=""):
    emailDL = cdr.getEmailList('Test Publishing Notification')
    subject = header
    if not body:
        body = """
The publishing job failed.  Please check the log files.
"""
    opts = dict(subject=subject, body=body)
    cdr.EmailMessage(cdr.OPERATOR, emailDL, **opts).send()

    return


# ---------------------------------------------------------------------
# Function to check if an Interim job is already underway (maybe it runs
# longer then 24 hours or it has been started manually).
# Note:
# We may want to change the SQL query to make sure a weekly export can
# not be started if a nightly job hasn't finished yet.
# ---------------------------------------------------------------------
def checkPubJob():
    # Defensive programming.
    tries = MAX_RETRIES

    while tries:
        try:
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("""\
                SELECT id, pub_subset, status, started, completed
                  FROM pub_proc
                 WHERE status not in ('Failure', 'Success')
                   AND pub_system = 178
                   AND pub_subset LIKE '%%Export' """)
            row = cursor.fetchone()
            return row or 0

        except Exception:
            LOGGER.exception("*** Failure checking for running jobs ***")
            waitSecs = (MAX_RETRIES + 1 - tries) * RETRY_MULTIPLIER
            LOGGER.info("    RETRY: %d retries left; waiting %f seconds",
                        tries, waitSecs)
            time.sleep(waitSecs)
            tries -= 1

    raise Exception(f"*** (2) Giving up after {MAX_RETRIES:d} times.")


# ---------------------------------------------------------------------
# Instantiate the Log class
# ---------------------------------------------------------------------
LOGGER = cdr.Logging.get_logger("PubJob", console=True)
LOGGER.info("SubmitPubJob - Started")
LOGGER.info('Arguments: %s', sys.argv)

opts = Parser().parse_args()
testMode = opts.testmode
fullMode = opts.export


# Based on the command line parameter passed we are submitting a
# interim publishing job or a full export
# ---------------------------------------------------------------
if fullMode:
    pubSubset = 'Export'
else:
    pubSubset = 'Interim-Export'
override = cdr.getControlValue("Publishing", f"{pubSubset}-wait-seconds")
try:
    override = int(override)
    waitTotal = override
except Exception:
    pass

try:
    # Before we start we need to check if a publishing job is already
    # underway.  It could be in the process of publishing or pushing.
    # We do not allow two jobs of the same job type to run simultanously.
    # Also, if a publishing job ran but the push job failed the
    # initiated push job would fail with a message 'Push job pending'.
    # ---------------------------------------------------------------
    LOGGER.info("Checking job queue ...")

    # checkPubJob will exit if another job is already running
    # -------------------------------------------------------
    currentJobs = checkPubJob()
    if currentJobs:
        LOGGER.error("\n%s job is still running.", pubSubset)
        LOGGER.error("Job%s status: %s", currentJobs[0], currentJobs[2])
        LOGGER.error("Job%s type  : %s", currentJobs[0], currentJobs[1])
        raise Exception("Job%s still in process (%s: %s)" %
                        (currentJobs[0], pubSubset, currentJobs[2]))

    LOGGER.info("   OK to submit")

    # Submitting publishing job.  If an integer job ID is returned
    # we continue.  Otherwise, submitting the job failed and we exit.
    # ---------------------------------------------------------------
    LOGGER.info("Submitting publishing job ...")
    submit = cdr.publish(session, pubSystem, pubSubset, email=pubEmail)

    if submit[0] is None:
        LOGGER.error("*** Failure starting publishing job ***")
        LOGGER.error("%s", submit[1])
        sys.exit(1)
    else:
        LOGGER.info("Pub job started as Job%s", submit[0])
        LOGGER.info("Waiting for publishing job to complete ...")

    # We started the publishing job.  Now we need to wait until
    # publishing (and pushing) is complete before we exit the
    # program.  Otherwise the following SQL Server Agent steps
    # would start without the data being ready.
    # Checking the status every minute
    # ---------------------------------------------------------
    done = 0
    counter = 0
    while not done:
        time.sleep(wait)
        counter += 1
        jobInfo = checkJobStatus(submit[0])
        status = jobInfo[1]
        messages = jobInfo[4]

        # Don't print every time we're checking (every 15 minutes)
        # ---------------------------------------------------------
        if counter % 15 == 0:
            LOGGER.info("    Status: %s (%d sec)", status, counter*wait)

            if counter * wait > waitTotal:
                hours = waitTotal / (60 * 60)
                LOGGER.error("*** Publishing job failed to finish!!!")
                LOGGER.error("*** Completion exceeded maximum time allowed")
                LOGGER.error("*** Cancelled after %s hours", hours)
                subject = "Publishing Failure: Max time exceeded"
                msgBody = """
The publishing job failed.  It did not finish within the maximum time
allowed.
"""
                sendFailureMessage(subject, msgBody)
                statusPubJobFailure(submit[0])
                sys.exit(1)

        # Once the publishing job completed with status Success
        # we need to find the push job and wait for it to finish
        # We will continue after both jobs completed with Success.
        # --------------------------------------------------------
        if status in ('Verifying', 'Success'):
            LOGGER.info("Publishing job started at %s", jobInfo[2])
            LOGGER.info("         and completed at %s", jobInfo[3])
            try:
                pushId = getPushJobId(submit[0])
                LOGGER.info("Push job started as Job%s", pushId)
            except Exception:
                LOGGER.exception("*** Failed to submit Push job for Job%s",
                                 submit[0])
                sys.exit(1)

            pdone = 0
            pcounter = 0

            # Waiting for the push job to finish
            # -----------------------------------
            while not pdone:
                time.sleep(wait)
                pcounter += 1
                jobInfo = checkJobStatus(pushId)
                pstatus = jobInfo[1]
                if pcounter % 15 == 0:
                    args = pstatus, pcounter * wait
                    LOGGER.info("    Status: %s (%d sec)", *args)
                if pstatus in ('Verifying', 'Success'):
                    pdone = 1
                    LOGGER.info("   Pushing job started at %s", jobInfo[2])
                    LOGGER.info("         and completed at %s", jobInfo[3])
                elif pstatus == 'Failure':
                    LOGGER.error("*** Push job failed at %s", jobInfo[3])
                    LOGGER.info("         Status:  %s", pstatus)
                    LOGGER.info("%s", jobInfo[4])
                    sys.exit(1)
                else:
                    pdone = 0

            done = 1
        elif status == 'Failure':
            LOGGER.error("*** Error - Publication job failed")
            LOGGER.error("... %s", messages[-500:])
            subj = "*** Publishing Failure: The current job did not succeed!"
            msgBody = """
The publishing job started but did not complete successfully.
See logs below:
---------------
%s
""" % messages[-500:]
            sendFailureMessage(subj, msgBody)
            sys.exit(1)
        else:
            done = 0

    try:
        # Submitting the email notification including the error report
        # The mail is send two different groups depending if it's a
        # nightly or a weekly publishing job
        # ------------------------------------------------------------
        if fullMode:
            emailDL = cdr.getEmailList('Weekly Publishing Notification')
            addSubj = 'Weekly'
        else:
            emailDL = cdr.getEmailList('Nightly Publishing Notification')
            addSubj = 'Nightly'

        # If we're not running in production we want to avoid sending
        # these email messages to the users.  Overwriting the emailDL
        # group to a developers/testers list or recipients
        # -----------------------------------------------------------
        if not TIER == 'PROD':
            emailDL = cdr.getEmailList('Test Publishing Notification')

        args = TIER, addSubj
        subject = '[%s] Status and Error Report for %s Publishing' % args

        emailDL.sort()
        if not len(emailDL):
            emailDL = cdr.getEmailList("Developers Notification")
            subject = '*** DL Missing *** %s' % subject
            LOGGER.warning('*** Warning: No Email DL found')

        message = """\

Status and Error reports for the latest %s publishing/push jobs:

Publishing Job Report:
   %s/cgi-bin/cdr/PubStatus.py?id=%s

Push Job Report:
   %s/cgi-bin/cdr/PubStatus.py?id=%s

""" % (addSubj.lower(), url, submit[0], url, pushId)

        opts = dict(subject=subject, body=message)
        cdr.EmailMessage(cdr.OPERATOR, emailDL, **opts).send()
        LOGGER.info("Submitting Email: OK")
    except Exception:
        LOGGER.exception("*** Error sending email ***")
        raise

except Exception as arg:
    LOGGER.exception("*** Standard Failure")
    subject = '[%s] *** SubmitPubJob.py - Standard Failure' % TIER
    msgBody = "The publishing job failed:  %s" % arg
    sendFailureMessage(subject, msgBody)

sys.exit(0)
