#!d:/python/python.exe
# *********************************************************************
#
# File Name: $RCSFile:$
#            ===============
# Program to check if a newly created file 'WithdrawnFromPDQ' (created
# by the CTGovExport process) contains a new protocol with the stats
# 'Withdrawn from PDQ'
# These protocols need to be submitted along to the versioning 
# information so that they can be removed from ClinicalTrials.gov
# if appropriate.
# ---------------------------------------------------------------------
# $Author$
# Created:          2007-12-03        Volker Englisch
# Last Modified:    $Date$
# 
# $Id$
# 
# BZIssue::4627
#
# Revision 1.1  2007/12/12 18:00:44  venglisc
# Initial version of program to take two directories created by the
# CTGovExport process and compare the files WithdrawnFromPDQ.txt in order
# to find if any protocols exist in the newer file that are not listed in
# the older file.  Those will need to be reported so that they can be
# handled properly by ClinicalTrials.gov to be removed or disabled. (Bug 3761)
#
# *********************************************************************
import sys, cdr, cdrdb, os, time, optparse, smtplib

OUTPUTBASE     = cdr.BASEDIR + "/Output/NLMExport"
WITHDRAWN_LIST = "WithdrawnFromPDQ.txt"
LOGNAME        = "CheckWithdrawn.log"
SMTP_RELAY     = "MAILFWD.NIH.GOV"
STR_FROM       = "PDQ Operator <NCIPDQoperator@mail.nih.gov>"
STR_TO         = "***REMOVED***"

now            = time.localtime(time.time())

testMode       = None
emailMode      = None

# Create an exception allowing us to break out if there are no new
# protocols found to report.
# ----------------------------------------------------------------
class NothingFoundError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

# ------------------------------------------------------------
# Function to parse the command line arguments
# ------------------------------------------------------------
def parseArguments(args):
    """
    Assign all input parameters to variables and perform some error
    checking.
    """

    usage = "usage: %prog [--livemode | --testmode] [options]"
    parser = optparse.OptionParser(usage = usage)

    parser.set_defaults(testMode = True)
    parser.set_defaults(emailMode = True)
    parser.add_option('-t', '--testmode',
                      action = 'store_true', dest = 'testMode',
                      help = 'running in TEST mode')
    parser.add_option('-l', '--livemode',
                      action = 'store_false', dest = 'testMode',
                      help = 'running in LIVE mode')
    parser.add_option('-e', '--email',
                      action = 'store_true', dest = 'emailMode',
                      help = 'running in EMAIL mode')
    parser.add_option('-n', '--noemail',
                      action = 'store_false', dest = 'emailMode',
                      help = 'running in NOEMAIL mode')
    parser.add_option('-d', '--directory',
                      action = 'append', dest = 'dirs',
                      help = 'run diff on file in this directory')

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

    if parser.values.emailMode:
        l.write("Running in EMAIL mode", stdout = True)
    else:
        l.write("Running in NOEMAIL mode", stdout = True)

    if parser.values.dirs:
        dirs = parser.values.dirs
        l.write("Directories to diff: %s" % dirs, stdout = True)

    return parser


# --------------------------------------------------------------------
# Module to submit an email message if the program fails
# --------------------------------------------------------------------
def sendErrorMessage(msg, recipient = STR_TO):
    # We want to send an email so that the query doesn't silently fail
    # ----------------------------------------------------------------
    mailHeader   = """\
From: %s
To: %s
Subject: %s: %s
""" % (STR_FROM, recipient, cdr.PUB_NAME.capitalize(),
       '*** Error: Program CheckWithdrawn failed!')

    mailHeader   += "Content-type: text/html; charset=utf-8\n"
    mailBody      = "<b>Error running CheckWithdrawn.py</b><br>"
    mailBody     += "Most likely %s<br>" % msg
    mailBody     += "See log file for details."

    # Add a Separator line + body
    # ---------------------------
    message = mailHeader + "\n" + mailBody

    server = smtplib.SMTP(SMTP_RELAY)
    server.sendmail(STR_FROM, recipient, message.encode('utf-8'))
    server.quit()


# ---------------------------------------------------------------------
# Instantiate the Log class
# ---------------------------------------------------------------------
l   = cdr.Log(LOGNAME)
l.write("CheckWithdrawn - Started", stdout = True)
l.write('Arguments: %s' % sys.argv, stdout=True)
print ''

options   = parseArguments(sys.argv)
testMode  = options.values.testMode
emailMode = options.values.emailMode
dirs      = options.values.dirs
dirs.sort()
 
path = OUTPUTBASE + '/%s/WithdrawnFromPDQ.txt'

try:
    if len(dirs) != 2:
        l.write("Need exactly two directories: %d given" % len(dirs), 
                                                           stdout = True)
        sys.exit("To many or too few directories specified")

    # Open the WithdrawnFromPDQ files and read the content
    # ----------------------------------------------------
    protocols = {}
    for dir in dirs:
        if not os.access(path % dir, os.F_OK):
            l.write("No manifest file in: %s" % dir, stdout = True)
            sys.exit('*** Error reading manifest file in %s' % dir)

        f = open(path % dir, 'r')
        protocols[dir] = f.readlines()
        f.close()

    # Create two lists of the WithdrawnFromPDQ content
    # ------------------------------------------------
    oldFile = []
    newFile = []
    for row in protocols[dirs[0]]:
        oldFile.append(row.split('\t'))
    for row in protocols[dirs[1]]:
        newFile.append(row.split('\t'))

    # Compare all records of the new file with the records
    # of the old file. If we find a match we exit the loop since
    # the protocol is not newly withdrawn.  If we don't find a 
    # match for any of the records in the old file we need to 
    # report this record.
    # ---------------------------------------------------------
    icount = 0
    newWithdrawn = []
    for new in newFile:
        for old in oldFile:
            # Found matching record.  Break out of the loop
            if old == new:
                break
        # The current "new" record didn't match.  Remember this one.
        else:
            icount += 1
            l.write("Newly withdrawn: %s" % new, stdout = True)
            newWithdrawn.append(new)

    # Connect to the database to get the reason for withdrawl
    # -------------------------------------------------------
    if len(newWithdrawn):
        conn = cdrdb.connect()
        cursor = conn.cursor()
        
        # Prepare CDR-IDs to query the reason for removal from PDQ from
        # the comment field.
        # We need to split these IDs and query them separately. It's 
        # possible that we picked up a document without an NCTID and this 
        # one would not get reported in the SQL query looking for the 
        # NCTID.
        # Note: If this program is run manually an NCT ID may have been 
        #       added to the protocol even if it was originally listed
        #       without one.  In this case the NCT ID would not be 
        #       queried from the database.
        # ---------------------------------------------------------------
        CdrIdWithNct    = []
        CdrIdWithoutNct = []
        for doc in newWithdrawn:
            NctId = doc[2].strip()
            if not NctId:
                CdrIdWithoutNct.append(str(cdr.exNormalize(doc[0])[1]))
            else:
                CdrIdWithNct.append(str(cdr.exNormalize(doc[0])[1]))

        CdrIds = ','.join(CdrIdWithNct)
        NoNctCdrIds = ','.join(CdrIdWithoutNct)


        # Query the database with the information that needs to
        # be reported.
        # -----------------------------------------------------
        if CdrIds:
            try:
                cursor.execute("""\
    SELECT dv.id, dv.num, comment, nct.value
      FROM doc_version dv
      JOIN (SELECT id, MAX(num) AS maxnum
              FROM doc_version
             GROUP BY id) dvmax
        ON dv.id  = dvmax.id
       AND dv.num = dvmax.maxnum
      JOIN query_term_pub nct
        ON dv.id = nct.doc_id
       AND nct.path = '/InScopeProtocol/ProtocolIDs/OtherID/IDString'
      JOIN query_term_pub qt
        ON qt.doc_id = nct.doc_id
       AND LEFT(qt.node_loc, 8) = LEFT(nct.node_loc, 8)
     WHERE dv.id in (%s)
       AND qt.value = 'ClinicalTrials.gov ID'
    """ % CdrIds, timeout = 300)

                rows = cursor.fetchall()
                cursor.close()
            except cdrdb.Error, info:
                l.write("Failure retrieving protocols with NCT-ID: \n%s" % 
                         info[1][0], stdout = True)
                sendErrorMessage('SQL query timeout error: Query 1')
                raise


        # Query the database with the information that needs to
        # be reported for records without an NCTID
        # -----------------------------------------------------
        if NoNctCdrIds:
            try:
                cursor.execute("""\
    SELECT dv.id, dv.num, comment
      FROM doc_version dv
      JOIN (SELECT id, MAX(num) AS maxnum
              FROM doc_version
             GROUP BY id) dvmax
        ON dv.id  = dvmax.id
       AND dv.num = dvmax.maxnum
     WHERE dv.id in (%s)
    """ % NoNctCdrIds, timeout = 300)

                noNctRows = cursor.fetchall()
                cursor.close()
            except cdrdb.Error, info:
                l.write("Failure retrieving protocols without NCT-ID: \n%s" % 
                         info[1][0], stdout = True)
                sendErrorMessage('SQL query timeout error: Query 2')
                raise

    # If there are no new records that need to be reported we can
    # stop here.  No messages are being send.
    # -----------------------------------------------------------
    else:
        raise NothingFoundError('Exiting.')

    # List the records we found since the last time the process ran
    # in the log file
    # -------------------------------------------------------------
    if CdrIds:
        l.write("Protocols with NCTID", stdout = True)
        for (cdrId, versionNum, comment, nctid) in rows:
            l.write("%s, %s, %s, %s" % (cdrId, versionNum, comment, nctid), 
                                        stdout = True)

    if NoNctCdrIds:
        l.write("Protocols without NCTID", stdout = True)
        for (cdrId, versionNum, comment) in noNctRows:
            l.write("%s, %s, %s" % (cdrId, versionNum, comment), 
                                        stdout = True)

    # Create the message body and display the query results
    # -----------------------------------------------------
    mailBody = """\
<html>
 <head>
  <title>Protocols Removed from PDQ</title>
  <style type='text/css'>
   table   { border-spacing: 20px 5px;
             empty-cells: show;
             border-collapse: collapse; }

   table, th, td {border: 1px solid black; }
   th      { background-color: #f0f0f0; }
   td      { padding: 1px 10px; }
  </style>
 </head>
 <body>
  <h2>Protocols Removed from PDQ</h2>
  <h3>Date: %s</h3>

  <table>
   <tr>
    <th>CDR-ID</th>
    <th>Version</th>
    <th>NCT-ID</th>
    <th>Comment</th>
   </tr>
""" % (time.strftime("%m/%d/%Y", now))

    # Display the records of protocols with NCT ID
    # --------------------------------------------
    if CdrIds:
        for (cdrId, versionNum, comment, nctid) in rows:
            mailBody += """\
   <tr>
    <td>%s</td>
    <td>%s</td>
    <td>
     <a href="http://www.clinicaltrials.gov/ct2/show/%s">%s</a>
    </td>
    <td>%s</td>
   </tr>
""" % (cdrId, versionNum, nctid, nctid, comment)

    # Display the records of protocols without NCT ID
    # -----------------------------------------------
    if NoNctCdrIds:
        for (cdrId, versionNum, comment) in noNctRows:
            mailBody += """\
   <tr>
    <td>CDR%010d</td>
    <td>%s</td>
    <td>&nbsp </td>
    <td>%s</td>
   </tr>
""" % (cdrId, versionNum, comment)

    mailBody += """\
  </table>

 </body>
</html>
"""

    # In Testmode we don't want to send the notification to the world
    # ---------------------------------------------------------------
    # Email constants
    # ---------------
    SMTP_RELAY   = "MAILFWD.NIH.GOV"
    strFrom      = "PDQ Operator <NCIPDQoperator@mail.nih.gov>"
    if testMode:
        strTo    = ["VE Test <***REMOVED***>"]
    else:
        strTo    = ["PDQ Operator <NCIPDQoperator@mail.nih.gov>", 
                    "William Osei-Poku <***REMOVED***>", 
                    "Diana Bitenas <Diana.bitenas@lmco.com>",
                    "Judy Morris <***REMOVED***>",
                    "Alexandra Valentine <***REMOVED***>",
                    "Cherryl Villanueva <***REMOVED***>"]
                    #"Kimberly Eckley <***REMOVED***>",

    mailHeader   = """\
From: %s
To: %s
Subject: %s: %s
""" % (strFrom, ", ".join(strTo), cdr.PUB_NAME.capitalize(),
       'Protocols Removed from PDQ')

    mailHeader   += "Content-type: text/html; charset=iso-8859-1\n"

    # Add a Separator line + body
    # ---------------------------
    message = mailHeader + "\n" + mailBody

    #print message

    # Sending out the email 
    # ---------------------
    server = smtplib.SMTP(SMTP_RELAY)
    if emailMode:
        server.sendmail(strFrom, strTo, message)
    else:
        l.write("Running in NOEMAIL mode.  No message send", stdout = True)
    server.quit()

except NothingFoundError, arg:
    msg  = "No new documents found with 'WithdrawnFromPDQ' status"
    l.write("%s" % msg, stdout = True)
    l.write("%s" % arg, stdout = True)
except Exception, arg:
    l.write("*** Standard Failure - %s" % arg, stdout = True, tback = 1)
except:
    l.write("*** Error - Program stopped with failure ***", stdout = True, 
                                                            tback = 1)
    raise

l.write("CheckWithdrawn - Finished", stdout = True)
sys.exit(0)
