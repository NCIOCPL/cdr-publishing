#!d:/python/python.exe
# *********************************************************************
# Control file to start the publishing scripts.
# ---------------------------------------------------------------------
# Created:          2007-04-03        Volker Englisch
#
# BZIssue::4732 - Change in logic for pulling documents from cancer.gov
# BZIssue::4903 - Transfer Protocols without transfer date
# BZIssue::5215 - Fix Publishing Job to Ignore Warnings
# OCECDR-3962: Simplify Rerunning Jobmaster Job (Windows)
# *********************************************************************
import sys, re, string, os, shutil, cdr, getopt, time, glob

# Setting directory and file names
# --------------------------------
PUBPATH    = os.path.join('d:\\cdr', 'publishing')

UTIL       = os.path.join('d:\\cdr', 'Utilities')
UBIN       = os.path.join('d:\\cdr', 'Utilities', 'bin')
LOGFILE    = 'Jobmaster.log'

weekDay    = time.strftime("%a")
testMode   = None
fullUpdate = None
refresh    = True
istep      = 0

# ------------------------------------------------------------
# Function to parse the command line arguments
# Note:  testmode/livemode is currently only used to be passed
#        to the called program
# ------------------------------------------------------------
def parseArgs(args):

    global testMode
    global fullUpdate
    global jobId
    global refresh
    global l

    try:
        longopts = ["testmode", "livemode", "interim", "export", "jobid="]
        opts, args = getopt.getopt(args[1:], "tliej:", longopts)
    except getopt.GetoptError, e:
        usage(args)

    for o, a in opts:
        if o in ("-o", "--logfile"):
            global LOGFILE
            LOGFILE = a
            l = cdr.Log(LOGFILE)
        elif o in ("-t", "--testmode"):
            testMode = True
            l.write("running in TEST mode")
        elif o in ("-l", "--livemode"):
            testMode = False
            l.write("running in LIVE mode")
        elif o in ("-i", "--interim"):
            fullUpdate = False
            l.write("running in INTERIM mode")
        elif o in ("-e", "--export"):
            fullUpdate = True
            l.write("running in EXPORT mode")
        elif o in ("-j", "--jobid"):
            if a[0:3].lower() == "job":
                jobId = a[3:]
            else:
                jobId = a
            l.write("processing Job%s" % jobId)

    if len(args) > 0:
        usage(args)
    if testMode is None:
        usage(args)
    if fullUpdate is None:
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
    -i, --interim
           running in interim (nightly) production mode

    -e, --export
           running in export (weekly) production mode

    -t, --testmode
           run in TEST mode

    -l, --livemode
           run in LIVE mode

    -j, --jobid=NNNNN
           processing JobNNNN data
""" % sys.argv[0].split('\\')[-1])
    sys.exit(1)


# ------------------------------------------------------------
# *** Main ***
# Jetzt wird es ernst
# ------------------------------------------------------------

# Open Log file and enter start message
# -------------------------------------
l = cdr.Log(LOGFILE)
l.write('Jobmaster Publishing - Started', stdout = True)
l.write('Arguments: %s' % sys.argv, stdout=True)
jobId  = ''  # export job id
cg2dir = ''  # cg2public parameter
expid  = ''  # export parameter
ftpdir = ''  # ExportOtherData parameter

parseArgs(sys.argv)

# Setting the options for jobs which we are going to submit
# ---------------------------------------------------------
if testMode:
    runmode = '--testmode'
else:
    runmode = '--livemode'

if fullUpdate:
    pubmode = '--export'
else:
    pubmode = '--interim'

# If the JobmasterNoPub needs to be restarted after another publishing
# job already ran since the Friday job we'll have to specify the job-id
# By default the publishing jobs are processing the output from the last
# publishing job.
# ----------------------------------------------------------------------
if jobId:
    try:
        myJob = int(jobId)
        cg2dir = '--inputdir=Job%d' % myJob
        expid  = '--jobid=%d' % myJob
        ftpdir = '--dir=Job%d' % myJob
    except:
        l.write('Invalid job-id: %s' % repr(jobId))
        sys.exit()

# Process the licensee data that's running on weekends only
# ---------------------------------------------------------
if fullUpdate:

    # FTP the publishing data (Vendor output) to CIPSFTP
    # Note: Step only needed for weekly publishing
    # --------------------------------------------------
    try:
        istep += 1
        l.write('--------------------------------------------', stdout = True)
        l.write('Step %d: CG2Public Job' % istep, stdout = True)
        cmd = os.path.join(PUBPATH, 'CG2Public.py %s %s %s' % (runmode,
                                                               pubmode,
                                                               cg2dir))

        l.write('Submitting command...\n%s' % cmd, stdout = True)
        ### cmd = 'ls' ###
        myCmd = cdr.runCommand(cmd, joinErr2Out = False)

        if myCmd.error:
            l.write('*** Error submitting command:\n%s' % myCmd.error,
                     stdout = True)
            subject = '*** Error in CG2Public.py'
            message = 'Program returned with error code.  Please see logfile.'
            cmd     = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
                                        (subject, message))
            myCmd   = cdr.runCommand(cmd)
            raise Exception
    except:
        l.write('*** Error: Submitting CG2Public Job failed', stdout = True)
        pass

    # FTP the publishing data (Vendor output) to CIPSFTP
    # Note: Step only needed for weekly publishing
    # --------------------------------------------------
    try:
        istep += 1
        l.write('--------------------------------------------', stdout = True)
        l.write('Step %d: FtpExportData Job' % istep, stdout = True)
        cmd = os.path.join(PUBPATH, 'FtpExportData.py %s %s %s' % (runmode,
                                                                   pubmode,
                                                                   expid))

        l.write('Submitting command...\n%s' % cmd, stdout = True)
        ### cmd = 'ls' ###
        myCmd = cdr.runCommand(cmd, joinErr2Out = False)

        if myCmd.error:
            l.write('*** Error submitting command:\n%s' % myCmd.error,
                     stdout = True)
            subject = '*** Error in FtpExportData.py'
            message = 'Program returned with error code.  Please see logfile.'
            cmd     = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
                                        (subject, message))
            myCmd   = cdr.runCommand(cmd)
            raise Exception
    except:
        l.write('*** Error: Submitting FtpExportData Job failed', stdout = True)
        pass


# FTP the NCICB Terminolofy data to CIPSFTP
# This data contains an extra element not intended for licensees
# Note: Step only needed for weekly publishing
# Note: As of 2009-09-13 the NCICB data should be transferred
#       nightly.
# --------------------------------------------------------------
try:
    istep += 1
    l.write('--------------------------------------------', stdout = True)
    l.write('Step %d: FtpOtherData Job' % istep, stdout = True)
    cmd = os.path.join(PUBPATH, 'FtpOtherData.py %s %s %s' % (runmode,
                                                              pubmode,
                                                              ftpdir))

    l.write('Submitting command...\n%s' % cmd, stdout = True)
    ### cmd = 'ls' ###
    myCmd = cdr.runCommand(cmd, joinErr2Out = False)

    if myCmd.error:
        l.write('*** Error submitting command:\n%s' % myCmd.error,
                 stdout = True)
        l.write('Code: %s' % myCmd.code, stdout = True)
        subject = '*** Error in FtpOtherData.py'
        message = 'Program returned with error code.  Please see logfile.'
        cmd     = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
                                    (subject, message))
        # cmd = 'ls'
        myCmd   = cdr.runCommand(cmd)
        raise Exception
except:
    l.write('*** Error: Submitting FtpOtherData Job failed', stdout = True)
    pass

if fullUpdate:
    # Submit the job to check for newly published media
    # documents and send a notification email
    # Note: Step only needed for weekly publishing
    # -------------------------------------------------------
    try:
        istep += 1
        l.write('--------------------------------------------', stdout = True)
        l.write('Step %d: Notify_VOL Job' % istep, stdout = True)
        cmd = os.path.join(PUBPATH, 'Notify_VOL.py %s' % (runmode))

        l.write('Submitting command...\n%s' % cmd, stdout = True)
        # cmd = 'ls'
        myCmd = cdr.runCommand(cmd, joinErr2Out = False)

        if myCmd.error:
            l.write('*** Error submitting command:\n%s' % myCmd.error,
                     stdout = True)
            subject = '*** Error in Notify_VOL.py'
            message = 'Program returned with error code.  Please see logfile.'
            cmd     = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
                                        (subject, message))
            myCmd   = cdr.runCommand(cmd)
            raise Exception
    except:
        l.write('*** Error: Submitting Notify_VOL Job failed', stdout = True)
        pass


    # Submit the job to check for documents that will need to
    # be removed manually from Cancer.gov.
    # Only blocked documents are being removed but for
    # document types for which the status is being set to
    # remove or withdrawn, for instance, the document won't
    # necessarily be removed as part of the publishing job.
    # -------------------------------------------------------
    try:
        istep += 1
        l.write('--------------------------------------------', stdout = True)
        l.write('Step %d: CheckHotfixRemove Job' % istep, stdout = True)
        cmd = os.path.join(PUBPATH, 'CheckHotfixRemove.py %s' % (runmode))

        l.write('Submitting command...\n%s' % cmd, stdout = True)
        # cmd = 'ls'
        myCmd = cdr.runCommand(cmd, joinErr2Out = False)

        if myCmd.error:
            l.write('*** Error submitting command:\n%s' % myCmd.error,
                     stdout = True)
            subject = '*** Error in CheckHotfixRemove.py'
            message = 'Program returned with error code.  Please see logfile.'
            cmd     = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
                                        (subject, message))
            myCmd   = cdr.runCommand(cmd)
            raise Exception
    except:
        l.write('*** Error: Submitting CheckHotfixRemove Job failed',
                                                            stdout = True)
        pass


# Send final Notification that publishing on CDR servers has finished
# Note: More processing to be completed on Cancer.gov and CIPSFTP
# -------------------------------------------------------------------
try:
    istep += 1
    l.write('--------------------------------------------', stdout = True)
    l.write('Step %d: Jobmaster Job Complete notification' % istep,
                                                           stdout = True)
    if fullUpdate:
        subject = 'Weekly Publishing Finished'
        message = 'Weekly Job Finished Successfully'
        cmd = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
                                     (subject, message))
    else:
        subject = 'Nightly Publishing Finished'
        message = 'Nightly Job Finished Successfully'
        cmd = os.path.join(PUBPATH, 'PubEmail.py "%s" "%s"' % \
                                    (subject, message))
    l.write('Submitting command...\n%s' % cmd, stdout = True)

    # cmd = 'ls'
    myCmd = cdr.runCommand(cmd, joinErr2Out = False)

    if myCmd.error:
        l.write('*** Error submitting email\n%s' % myCmd.error,
                 stdout = True)
        raise Exception
except:
    # No need to interrupt the program if the email doesn't go out
    l.write('*** Error: Submitting Final Email failed', stdout = True)
    pass

# All done, going home now
# ------------------------
l.write('Jobmaster Publishing - Finished', stdout = True)
sys.exit(0)
