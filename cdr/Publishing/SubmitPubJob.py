#!d:/python/python.exe
# *********************************************************************
#
# File Name: $RCSFile:$
#            ===============
# Program to submit the interim and full export publishing job.
# ---------------------------------------------------------------------
# $Author: venglisc $
# Created:          2007-04-03        Volker Englisch
# Last Modified:    $Date: 2007-09-07 22:32:03 $
# 
# $Source: /usr/local/cvsroot/cdr/Publishing/SubmitPubJob.py,v $
# $Revision: 1.4 $
#
# $Id: SubmitPubJob.py,v 1.4 2007-09-07 22:32:03 venglisc Exp $
# $Log: not supported by cvs2svn $
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

# Setting directory and file names
# --------------------------------
log        = "d:\\cdr\\log\\Jobmaster.log" 
PUBPATH    = os.path.join('d:\\cdr', 'publishing')
# PUBPATH    = os.path.join('d:\\home', 'venglisch', 'cdr', 'publishing')

OUTPUTBASE = cdr.BASEDIR + "\\Output"
lockFile   = os.path.join(OUTPUTBASE, 'FtpExportData.txt')
wait       = 60    # number of seconds to wait between status checks

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
    try:
        conn = cdrdb.connect("cdr")
        cursor = conn.cursor()
        cursor.execute("""\
            SELECT id, status, started, completed, messages
              FROM pub_proc
             WHERE id = %d""" % int(jobId), timeout = 300)
        row = cursor.fetchone()

    except cdrdb.Error, info:
        l.write("Failure finding status for Job%d: %s" % (jobId, info[1][0]))
    return row
 

# --------------------------------------------------------------
# Function to find the job ID of the push job.
# --------------------------------------------------------------
def getPushJobId(jobId):
    time.sleep(15)
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

    except cdrdb.Error, info:
        l.write("Failure finding push job for Job%d: %s" % (int(jobId), 
                                                            info[1][0]))
    return row[0]


# ---------------------------------------------------------------------
# Function to check if an Interim job is already underway (maybe it runs
# longer then 24 hours or it has been started manually).
# Note:
# We may want to change the SQL query to make sure a weekly export can
# not be started if a nightly job hasn't finished yet.
# ---------------------------------------------------------------------
def checkPubJob(pubType):
    try:
        conn = cdrdb.connect()
        cursor = conn.cursor()
        cursor.execute("""\
            SELECT id, pub_subset, status, started, completed
              FROM pub_proc
             WHERE status not in ('Failure', 'Success')
               AND pub_system = 178
               AND pub_subset LIKE '%%_%s' """ % pubType, timeout = 300)
        row = cursor.fetchone()

        if row:
            #print "\n%s job already running." % pubType
            #print "Job%s status: %s" % (row[0], row[2])
            #raise StandardError("""Job%s still active (%s: %s)""" % 
            #                       (row[0], pubType, row[2]))
            return row
    
    except cdrdb.Error, info:
        l.write("Failure checking Interim-Export job queue: %s" % info[1][0])

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
        currentJobs = checkPubJob(pubSubset)
        if currentJobs:
            print "\n%s job already running." % pubSubset
            print "Job%s status: %s" % (currentJobs[0], currentJobs[2])
            raise StandardError("""Job%s still active (%s: %s)""" % 
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

        ### if counter % 1 == 0:
        ###    l.write("Job running %d seconds..." % (counter * wait), stdout=True)

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

        subject = '%s: Status and Error Report for %s Publishing' % (
                                                  cdr.PUB_NAME.capitalize(),
                                                  addSubj)
        emailDL.sort()
        if not len(emailDL):
            emailDL = ['***REMOVED***']
            subject = '*** DL Missing *** %s' % subject
            l.write('*** Warning: No Email DL found')

        message   = """\

Status and Error reports for the latest %s publishing/push jobs:

Publishing Job Summary Report:
   http://%s/cgi-bin/cdr/PubStatus.py?id=%s&type=Report&Session=Guest

Error Report of the publishing job:
   http://%s/cgi-bin/cdr/PubStatus.py?id=%s&type=FilterFailure&flavor=error

Warnings Report of the publishing job
   http://%s/cgi-bin/cdr/PubStatus.py?id=%s&type=FilterFailure&flavor=warning

Publishing Job Output:
   http://%s/cgi-bin/cdr/PubStatus.py?id=%s

Push Job Output:
   http://%s/cgi-bin/cdr/PubStatus.py?id=%s

""" % (addSubj.lower(), host, pushId, host, submit[0], host, submit[0], 
                     host, submit[0], host, pushId) 

        notify = cdr.sendMail(cdr.OPERATOR, emailDL, subject, message)

        l.write("Submitting Email: %s" % (notify or 'OK'), stdout=True)
    except:
        l.write("*** Error sending email ***", stdout=True)
        raise

except StandardError, arg:
    l.write("*** Standard Failure - %s" % arg, stdout=True)
except:
    l.write("*** Error - Program stopped with failure ***", stdout=True)
    raise

sys.exit(0)
