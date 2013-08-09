#!d:/python/python.exe
# *********************************************************************
#
# File Name: $RCSFile:$
#            ===============
# Program to submit the interim and full export publishing job.
# ---------------------------------------------------------------------
# $Author$
# Created:          2007-04-03        Volker Englisch
# Last Modified:    $Date$
# 
# $Source: /usr/local/cvsroot/cdr/Publishing/SubmitPubJob.py,v $
# $Revision$
#
# $Id$
# $Log: SubmitPubJob.py,v $
# Revision 1.9  2009/07/24 22:50:26  venglisc
# Fixed an error to write a string as an integer.
#
# Revision 1.8  2008/06/03 21:43:05  bkline
# Replaced StandardError (slated to be removed in the future) with
# Exception objects.
#
# Revision 1.7  2008/01/30 19:53:53  venglisc
# Preventing nightly job to be started id weekly job is still processing
#
# Revision 1.6  2007/10/15 18:37:36  venglisc
# Added code to redirect email output to developers/testers if run on a
# non-production system.
#
# Revision 1.5  2007/09/19 17:38:41  venglisc
# Added option to display a traceback in case of a system error.
#
# Revision 1.4  2007/09/07 22:32:03  venglisc
# Modified program to use multiple groups for receiving email messages.
# EmailDLs are retrieved from CDR instead from file.
#
# Revision 1.3  2007/08/29 21:27:42  venglisc
# Reducing the time interval for checking if the jobs completed.  Adding
# additional log messages.
#
# Revision 1.2  2007/08/10 16:42:11  venglisc
# Finalized initial version.  Added log comments.
#
# Revision 1.1  2007/07/06 22:50:05  venglisc
# Initial copy of MFP scheduling scripts.
#
# *********************************************************************
import sys, re, cdr, cdrdb, os, shutil, time, getopt

# Setting the host variable to submit the link for the error report
# -----------------------------------------------------------------
if cdr.PUB_NAME.upper() == "MAHLER":
    host   = cdr.DEV_HOST
elif cdr.PUB_NAME.upper() == "FRANCK":
    host   =  'franck.nci.nih.gov'
else:
    host   = cdr.PROD_HOST

if cdr.h.org == 'OCE':
    host = '%s.%s' % (cdr.h.host['APP'][0], cdr.h.host['APP'][1])
    url  = 'http://%s' % host
else:
    host = '%s.%s' % (cdr.h.host['APPC'][0], cdr.h.host['APPC'][1])
    url  = 'https://%s' % host

# Setting directory and file names
# --------------------------------
log        = "d:\\cdr\\log\\Jobmaster.log" 
PUBPATH    = os.path.join('d:\\cdr', 'publishing')
# PUBPATH    = os.path.join('d:\\home', 'venglisch', 'cdr', 'publishing')

OUTPUTBASE = cdr.BASEDIR + "\\Output"
MAX_RETRIES = 10
RETRY_MULTIPLIER = 5.0
lockFile   = os.path.join(OUTPUTBASE, 'FtpExportData.txt')
wait       = 60    # number of seconds to wait between status checks
if cdr.isProdHost():
    # waitTotal = 32400  #  9.0 hours
    # CBIIT PROD turns out to be much slower than expected.  Temporarily
    # increasing time out period.
    waitTotal = 64800  # 18.0 hours
else:
    waitTotal = 45000  # 12.5 hours

testMode   = None
fullMode   = None

credentials = ('CdrGuest', 'never.0n-$undaY')
pubSystem   = 'Primary'

pubEmail    = ['***REMOVED***', 'operator@cips.nci.nih.gov']

# ------------------------------------------------------------
# Function to parse the command line arguments
# ------------------------------------------------------------
def parseArgs(args):
    # args = argv

    global testMode
    global fullMode
    global l

    try:
        shortopts = "tlie"
        longopts  = ["testmode", "livemode", "interim", "export"]
        opts, args = getopt.getopt(args[1:], shortopts, longopts)
    except getopt.GetoptError, e:
        l.write("*** Error: Invalid option(s) - %s" % args[1:], stdout = True)
        l.write("    %s" % str(e), stdout = True)
        usage(args)

    for o, a in opts:
        if o in ("-o", "--logfile"):
            global LOGFILE
            LOGFILE = a
            l = cdr.Log(LOGFILE)
        elif o in ("-t", "--testmode"):
            l.write("running in TEST mode")
            testMode = True
        elif o in ("-l", "--livemode"):
            l.write("running in LIVE mode")
            testMode = False
        elif o in ("-n", "--interim"):
            l.write("running in INTERIM mode")
            fullMode = False
        elif o in ("-e", "--export"):
            l.write("running in EXPORT mode")
            fullMode = True

    if len(args) > 0:
        print "Additional command line options: %s" % rest
        usage(args)
    if testMode is None:
        usage(args)
    if fullMode is None:
        usage(args)

    return


# ------------------------------------------------------------
# Function to display the default usage
# ------------------------------------------------------------
def usage(args):
    print args
    sys.stderr.write("""\
usage: %s [--livemode|--testmode] [--interim|--export] [options]

options:
    -n, --interim
           running in interim (nightly) production mode

    -w, --export
           running in export (weekly) production mode

    -t, --testmode
           run in TEST mode

    -l, --livemode
           run in LIVE mode
""" % sys.argv[0].split('\\')[-1])
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
            conn = cdrdb.connect("cdr")
            cursor = conn.cursor()
            cursor.execute("""\
                SELECT id, status, started, completed, messages
                  FROM pub_proc
                 WHERE id = %d""" % int(jobId), timeout = 300)
            row = cursor.fetchone()

            # We can stop trying now, we got it.
            tries = 0

        except cdrdb.Error, info:
            l.write("*** Failure connecting to DB ***")
            l.write("*** Unable to check status for PubJob%d: %s" % (
                                             int(jobId), info[1][0]))
            waitSecs = (MAX_RETRIES + 1 - tries) * RETRY_MULTIPLIER
            l.write("    RETRY: %d retries left; waiting %f seconds" % (tries,
                                                               waitSecs))
            time.sleep(waitSecs)
            tries -= 1

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
            conn = cdrdb.connect()
            cursor = conn.cursor()
            cursor.execute("""\
                SELECT id, status, started, completed
                  FROM pub_proc
                 WHERE id > %d
                   AND pub_system = 178
                   AND (pub_subset LIKE '%%_Interim-Export'
                        OR
                        pub_subset LIKE '%%_Export')
                   """ % int(jobId), timeout = 300)
            row = cursor.fetchone()

            # If the SELECT returns nothing a push job was not submitted
            # because another job is still pending.
            # Otherwise the push job may already have completed.
            # -----------------------------------------------------------
            if row == None:
                l.write("*** Error - No push job waiting. Check for pending job",
                         stdout=True)
                cursor.execute("""\
                   SELECT id, messages
                     FROM pub_proc
                    WHERE id = %d""" % int(jobId), timeout = 300)
                row = cursor.fetchone()
                l.write("%s" % row[1], stdout=True)
                sys.exit(1)

            # We can stop trying now, we got it.
            tries = 0

        except cdrdb.Error, info:
            l.write("*** Failure connecting to DB ***")
            l.write("*** Unable to find status for PushJob%d: %s" % (
                                           int(jobId), info[1][0]))
            waitSecs = (MAX_RETRIES + 1 - tries) * RETRY_MULTIPLIER
            l.write("    RETRY: %d retries left; waiting %f seconds" % (tries,
                                                               waitSecs))
            time.sleep(waitSecs)
            tries -= 1

    if not row:
        raise Exception("*** (1) Tried to connect %d times. No Push Job-ID." %
                        MAX_RETRIES)

    return row[0]


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
            conn = cdrdb.connect()
            cursor = conn.cursor()
            cursor.execute("""\
                SELECT id, pub_subset, status, started, completed
                  FROM pub_proc
                 WHERE status not in ('Failure', 'Success')
                   AND pub_system = 178
                   AND pub_subset LIKE '%%Export' """, timeout = 300)
    #              AND pub_subset LIKE '%%_%s' """ % pubType, timeout = 300)
            row = cursor.fetchone()

            if row:
                return row

            # We can stop trying now, we got it.
            tries = 0
        
        except cdrdb.Error, info:
            l.write("*** Failure connecting to DB ***")
            l.write("*** Unable to find status for PubJob%d: %s" % (int(jobId), 
                                                              info[1][0]))
            waitSecs = (MAX_RETRIES + 1 - tries) * RETRY_MULTIPLIER
            l.write("    RETRY: %d retries left; waiting %f seconds" % (tries,
                                                               waitSecs))
            l.write("waitSecs: %d" % waitSecs)
            time.sleep(waitSecs)
            tries -= 1

    if not tries == 0:
        raise Exception("*** (2) Tried to connect %d times. No Pub Job-ID." %
                        MAX_RETRIES)

    return 0



# ---------------------------------------------------------------------
# Instantiate the Log class
# ---------------------------------------------------------------------
l   = cdr.Log('Jobmaster.log')
l.write("SubmitPubJob - Started", stdout = True)
l.write('Arguments: %s' % sys.argv, stdout=True)

parseArgs(sys.argv)
                    
# Based on the command line parameter passed we are submitting a
# interim publishing job or a full export
# ---------------------------------------------------------------
if fullMode:
    pubSubset = 'Export'
else:
    pubSubset = 'Interim-Export'

try:
    # Before we start we need to check if a publishing job is already
    # underway.  It could be in the process of publishing or pushing.
    # We do not allow two jobs of the same job type to run simultanously.
    # Also, if a publishing job ran but the push job failed the 
    # initiated push job would fail with a message 'Push job pending'.
    # ---------------------------------------------------------------
    l.write("Checking job queue ...", stdout=True)

    # checkPubJob will exit if another job is already running
    # -------------------------------------------------------
    try:
        # currentJobs = checkPubJob(pubSubset)
        currentJobs = checkPubJob()
        if currentJobs:
            l.write("\n%s job is still running." % pubSubset, 
                                                  stdout = True)
            l.write("Job%s status: %s" % (currentJobs[0], currentJobs[2]), 
                                                  stdout = True)
            l.write("Job%s type  : %s" % (currentJobs[0], currentJobs[1]), 
                                                  stdout = True)
            raise Exception("Job%s still in process (%s: %s)" % 
                            (currentJobs[0], pubSubset, currentJobs[2]))
    except:
        raise

    l.write("   OK to submit", stdout=True)

    # Submitting publishing job.  If an integer job ID is returned
    # we continue.  Otherwise, submitting the job failed and we exit.
    # ---------------------------------------------------------------
    l.write("Submitting publishing job...", stdout=True)
    jobDescription = "Auto %s, %s" % (pubSubset,  
                                    time.strftime('%Y-%m-%d %H:%M:%S'))
    submit = cdr.publish(credentials, pubSystem, pubSubset, 
                         parms = [('GKPushJobDescription', jobDescription)], 
                         email = pubEmail)

    if submit[0] == None:
        l.write("*** Failure starting publishing job ***", stdout = True)
        l.write("%s" % submit[1], stdout = True)
        sys.exit(1)
    else:
        l.write("Pub job started as Job%s" % submit[0], stdout = True)
        l.write("Waiting for publishing job to complete...", stdout = True)

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
        status  = jobInfo[1]
        # Don't print every time we're checking (every 15 minutes)
        # ---------------------------------------------------------
        if counter % 15 == 0:
            l.write("    Status: %s (%d sec)" % (status, counter * wait), 
                                                 stdout=True)

            #if counter * wait > 23000:
            if counter * wait > waitTotal:
                l.write("*** Publishing job failed to finish!!!", 
                                                            stdout=True)
                l.write("*** Completion exceeded maximum time allowed", 
                                                            stdout = True)
                sys.exit(1)

        # Once the publishing job completed with status Success
        # we need to find the push job and wait for it to finish
        # We will continue after both jobs completed with Success.
        # --------------------------------------------------------
        if status in ('Verifying', 'Success'): 
           l.write("Publishing job started at %s" % jobInfo[2], stdout=True)
           l.write("         and completed at %s" % jobInfo[3], stdout=True)
           try:
               pushId = getPushJobId(submit[0])
               l.write("Push job started as Job%s" % pushId, stdout=True)
           except:
               l.write("*** Failed to submit Push job for Job%s" % submit[0], 
                        stdout=True)
               # os.remove(lockFile)
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
                   l.write("    Status: %s (%d sec)" % (pstatus, 
                                                        pcounter * wait), 
                                                        stdout=True)

               if pstatus in ('Verifying', 'Success'):
                   pdone = 1
                   l.write("   Pushing job started at %s" % jobInfo[2], 
                                                             stdout=True)
                   l.write("         and completed at %s" % jobInfo[3], 
                                                             stdout=True)
               elif pstatus == 'Failure':
                   l.write("*** Push job failed at %s" % jobInfo[3], 
                           stdout=True)
                   l.write("         Status:  %s" % pstatus, stdout=True)
                   l.write("%s" % jobInfo[4], stdout=True)
                   sys.exit(1)
               else:
                   pdone = 0

           done = 1
        elif status == 'Failure':
           l.write("*** Error - Publication job failed", stdout=True)
           sys.exit(1)
        else: 
           done = 0

    # The publishing AND pushing job completed.  Add the pub jobID
    # to the FTP lock file so we know which file(s) need to be FTP'ed
    # to the FTP server
    # (currently only export data is provided to licensees)
    # ---------------------------------------------------------------
    if fullMode:
        f = open(lockFile, 'a')
        f.write('%s\n' % str(submit[0]))
        f.close()

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
        if not cdr.h.tier == 'PROD':
            emailDL = cdr.getEmailList('Test Publishing Notification')

        subject = '%s-%s: Status and Error Report for %s Publishing' % (
                                                  cdr.h.org, cdr.h.tier,
                                                  addSubj)
        emailDL.sort()
        if not len(emailDL):
            emailDL = ['***REMOVED***']
            subject = '*** DL Missing *** %s' % subject
            l.write('*** Warning: No Email DL found')

        message   = """\

Status and Error reports for the latest %s publishing/push jobs:

Publishing Job Summary Report:
   %s/cgi-bin/cdr/PubStatus.py?id=%s&type=Report&Session=Guest

Error Report of the publishing job:
   %s/cgi-bin/cdr/PubStatus.py?id=%s&type=FilterFailure&flavor=error

Warnings Report of the publishing job
   %s/cgi-bin/cdr/PubStatus.py?id=%s&type=FilterFailure&flavor=warning

Publishing Job Output:
   %s/cgi-bin/cdr/PubStatus.py?id=%s

Push Job Output:
   %s/cgi-bin/cdr/PubStatus.py?id=%s

""" % (addSubj.lower(), url, pushId, url, submit[0], url, submit[0], 
                     url, submit[0], url, pushId) 

        notify = cdr.sendMail(cdr.OPERATOR, emailDL, subject, message)

        l.write("Submitting Email: %s" % (notify or 'OK'), stdout = True)
    except:
        l.write("*** Error sending email ***", stdout = True)
        raise

except Exception, arg:
    l.write("*** Standard Failure - %s" % arg, stdout = True, tback = 1)
except:
    l.write("*** Error - Program stopped with failure ***", stdout = True, 
                                                            tback = 1)
    raise

sys.exit(0)
