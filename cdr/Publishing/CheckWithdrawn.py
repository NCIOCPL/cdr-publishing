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
# $Author: venglisc $
# Created:          2007-12-03        Volker Englisch
# Last Modified:    $Date: 2007-12-12 18:00:44 $
# 
# $Source: /usr/local/cvsroot/cdr/Publishing/CheckWithdrawn.py,v $
# $Revision: 1.1 $
#
# $Id: CheckWithdrawn.py,v 1.1 2007-12-12 18:00:44 venglisc Exp $
# $Log: not supported by cvs2svn $
# *********************************************************************
import sys, cdr, cdrdb, os, time, optparse, smtplib

OUTPUTBASE     = cdr.BASEDIR + "/Output/NLMExport"
WITHDRAWN_LIST = "WithdrawnFromPDQ.txt"
LOGNAME        = "CheckWithdrawn.log"

NothingFound   = 'Oops'
now            = time.localtime(time.time())

testMode       = None
emailMode      = None

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
        
        # Prepare CDR-IDs to query the reason for withdrawl
        # from the comment field.
        # ----------------------------------------------------
        CDRIDS = []
        for doc in newWithdrawn:
            CDRIDS.append(str(cdr.exNormalize(doc[0])[1]))

        CDRID = ','.join(CDRIDS)

        # Query the database with the information that needs to
        # be reported.
        # -----------------------------------------------------
        cursor.execute("""\
SELECT dv.id, dv.num, comment, nct.value
  FROM doc_version dv
  JOIN (select id, max(num) as maxnum
          from doc_version
         group by id) dvmax
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
""" % CDRID)

        rows = cursor.fetchall()
        cursor.close()

    # If there are no new records that need to be reported we can
    # stop here.  No messages are being send.
    # -----------------------------------------------------------
    else:
        raise NothingFound

    # List the records we found since the last time the process ran
    # -------------------------------------------------------------
    for (cdrId, versionNum, comment, nctid) in rows:
        l.write("%s, %s, %s, %s" % (cdrId, versionNum, comment, nctid), 
                                    stdout = True)

    # Create the message body and display the query results
    # -----------------------------------------------------
    mailBody = """\
<html>
 <head>
  <title>Recent Protocols with status: Withdrawn from PDQ</title>
  <style type='text/css'>
   th      { background-color: #f0f0f0; }
  </style>
 </head>
 <body>
  <h2>Recent Protocols with status: Withdrawn from PDQ</h2>
  <h3>Date: %s</h3>

  <table border='1px' cellpadding='2px' cellspacing='2px'>
   <tr>
    <th>CDR-ID</th>
    <th>Version</th>
    <th>NCT-ID</th>
    <th>Comment</th>
   </tr>
""" % (time.strftime("%m/%d/%Y", now))

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
    strFrom      = "PDQ Operator <operator@cips.nci.nih.gov>"
    if testMode:
        strTo    = ["VE Test <***REMOVED***>"]
    else:
        strTo    = ["PDQ Operator <operator@cips.nci.nih.gov>", 
                    "Sheri Khanna <***REMOVED***>", 
                    "Kim Eckley <***REMOVED***>",
                    "Leech, Mark J <mark.j.leech@lmco.com>",
                    "James Silk <james.d.silk@lmco.com", 
                    "Cherryl Villanueva <***REMOVED***>"]
        strTo    = ["Volker H. Englisch <volker@englisch.us>",
                    "Volker W. Englisch <***REMOVED***>"]

    mailHeader   = """\
From: %s
To: %s
Subject: %s: %s
""" % (strFrom, ", ".join(strTo), cdr.PUB_NAME.capitalize(),
       'Protocols with status: Withdrawn from PDQ')

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

except NothingFound, arg:
    msg  = "No new documents found with 'WithdrawnFromPDQ' status"
    l.write("%s" % msg, stdout = True)
except StandardError, arg:
    l.write("*** Standard Failure - %s" % arg, stdout = True, tback = 1)
except:
    l.write("*** Error - Program stopped with failure ***", stdout = True, 
                                                            tback = 1)
    raise

l.write("CheckWithdrawn - Finished", stdout = True)
sys.exit(0)
