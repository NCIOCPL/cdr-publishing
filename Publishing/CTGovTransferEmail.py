#!d:/python/python.exe
# *********************************************************************
#
# File Name: $RCSFile:$
#            ===============
# Program to identify and notify about protocols that need to be 
# transferred from PDQ to CTGov.
# ---------------------------------------------------------------------
# $Author: venglisc $
# Created:          2010-05-03        Volker Englisch
# Last Modified:    $
# 
# $Source: /usr/local/cvsroot/cdr/Publishing/CheckCTGovTransfer.py,v $
# $Revision: 1.9 $
#
# $Id: CheckCTGovTransfer.py,v 1.9 2009-09-17 14:52:40 venglisc Exp $
#
# BZIssue::4796 - Transfer notification email
#
# *********************************************************************
import sys, cdr, cdrdb, os, time, optparse, smtplib, glob

OUTPUTBASE     = cdr.BASEDIR + "/Output/CTGovTransfer"
DOC_FILE       = "CTGovTransfer"
LOGNAME        = "CTGovTransfer.log"
SMTP_RELAY     = "MAILFWD.NIH.GOV"
STR_FROM       = "PDQ Operator <operator@cips.nci.nih.gov>"

now            = time.localtime()

testMode       = None
emailMode      = None

# Create an exception allowing us to break out if there are no new
# protocols found to report.
# ----------------------------------------------------------------
class NoNewDocumentsError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)
class NothingFoundError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


# ---------------------------------------------------------------
# PUP class to identify the protocol update person information
# If the personRole is specified as 'Protocol chair' the chair's
# information is selected instead.
# ---------------------------------------------------------------
class PUP:
    def __init__(self, id, persRole = 'Update person'):
        self.cdrId       = id
        self.persId      = None
        self.persFname   = None
        self.persLname   = None
        self.persPhone   = None
        self.persEmail   = None
        self.persContact = None
        self.persRole    = persRole

        conn = cdrdb.connect()
        cursor = conn.cursor()

        # Get the person name
        # -------------------
        cursor.execute("""\
          SELECT q.doc_id, u.int_val, 
                 g.value as "FName", l.value as "LName", 
                 c.value as Contact  
            FROM query_term_pub q
            JOIN query_term_pub u
              ON q.doc_id = u.doc_id
             AND u.path   = '/InScopeProtocol/ProtocolAdminInfo' +
                            '/ProtocolLeadOrg/LeadOrgPersonnel'  +
                            '/Person/@cdr:ref'
             AND left(q.node_loc, 12) = left(u.node_loc, 12)
            JOIN query_term g
              ON u.int_val = g.doc_id
             AND g.path   = '/Person/PersonNameInformation/GivenName'
            JOIN query_term l
              ON g.doc_id = l.doc_id
             AND l.path   = '/Person/PersonNameInformation/SurName'
            JOIN query_term c
              ON g.doc_id = c.doc_id
             AND c.path   = '/Person/PersonLocations/CIPSContact'
           WHERE q.doc_id = %s
             AND q.value  = '%s'
        """ % (self.cdrId, self.persRole))

        rows = cursor.fetchall()

        for row in rows:
            self.cdrId       = row[0]
            self.persId      = row[1]
            self.persFname   = row[2]
            self.persLname   = row[3]
            self.persContact = row[4]

        # Get the person's email and phone if a PUP was found
        # ---------------------------------------------------
        if self.persId:
            cursor.execute("""\
          SELECT q.doc_id, c.value, p.value, e.value
            FROM query_term q
            JOIN query_term c
              ON c.doc_id = q.doc_id
             AND c.path = '/Person/PersonLocations' +
                          '/OtherPracticeLocation/@cdr:id'
 LEFT OUTER JOIN query_term p
              ON c.doc_id = p.doc_id
             AND p.path = '/Person/PersonLocations' +
                          '/OtherPracticeLocation/SpecificPhone'
             AND LEFT(c.node_loc, 8) = LEFT(p.node_loc, 8)
 LEFT OUTER JOIN query_term e
              ON c.doc_id = e.doc_id
             AND e.path = '/Person/PersonLocations' +
                          '/OtherPracticeLocation/SpecificEmail'
             AND LEFT(c.node_loc, 8) = LEFT(e.node_loc, 8)
           WHERE q.path = '/Person/PersonLocations/CIPSContact'
             AND q.value = c.value
             AND q.doc_id = %s
            """ % self.persId)

            rows = cursor.fetchall()

            for row in rows:
                self.persPhone   = row[2]
                self.persEmail   = row[3]


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
    global transferDate

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
    parser.add_option('-d', '--date',
                      action = 'store', dest = 'transferDate',
                      help = 'specify earliest tranfer date (YYYY-MM-DD)')

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

    if parser.values.transferDate:
        transferDate = parser.values.transferDate
        l.write("Transfer date set to: %s" % transferDate, stdout = True)
    else:
        transferDate = '2000-01-01'
        l.write("No Transfer date specified", stdout = True)
        l.write("  date set to: %s" % transferDate, stdout = True)

    return parser


# ---------------------------------------------------------------------
# Selecting the protocol list created last time this program ran
# ---------------------------------------------------------------------
def getLastProtocolList(directory = cdr.BASEDIR + '/Output/CTGovTransfer'):
    os.chdir(directory)
    if testMode:
        searchFor = '*.test.txt'
    else:
        searchFor = 'CTGovTransfer_??????????????.txt'

    fileList = glob.glob(searchFor)
    if not fileList: return
    fileList.sort()
    fileList.reverse()
    return (fileList[0])
    

# --------------------------------------------------------------------
# Module to submit an email message if the program fails
# --------------------------------------------------------------------
def sendErrorMessage(msg):
    # We want to send an email so that the query doesn't silently fail
    # ----------------------------------------------------------------
    mailHeader   = """\
From: %s
To: %s
Subject: %s: %s
""" % (STR_FROM, '***REMOVED***', cdr.PUB_NAME.capitalize(),
       '*** Error: Program CheckCTGovTransfer failed!')

    mailHeader   += "Content-type: text/html; charset=utf-8\n"
    mailBody      = "<b>Error running CheckCTGovTransfer.py</b><br>"
    mailBody     += "Most likely %s<br>" % msg
    mailBody     += "See log file for details."

    # Add a Separator line + body
    # ---------------------------
    message = mailHeader + "\n" + mailBody

    server = smtplib.SMTP(SMTP_RELAY)
    server.sendmail(STR_FROM, '***REMOVED***', message.encode('utf-8'))
    server.quit()


# -------------------------------------------
# Getting the Protocol Grant information
# -------------------------------------------
def getGrantNo(id):
    conn = cdrdb.connect()
    cursor = conn.cursor()

    cursor.execute("""\
        SELECT t.value, g.value
          FROM query_term g
          JOIN query_term t
            ON t.doc_id = g.doc_id
           AND t.path = '/CTGovProtocol/PDQAdminInfo/FundingInfo' +
                        '/NIHGrantContract/NIHGrantContractType'
           AND LEFT(g.node_loc, 8) = LEFT(t.node_loc, 8)
         WHERE g.doc_id = %s
           AND g.path = '/CTGovProtocol/PDQAdminInfo/FundingInfo' +
                        '/NIHGrantContract/GrantContractNo'
    """ % id)
    rows = cursor.fetchall()
    grantNo = []
    for row in rows:
        if row[0][:3] == row[1][:3]: 
            grantNo.append(u'%s' % row[1])
        else:
            grantNo.append(u'%s-%s' % (row[0], row[1]))

    grantNo.sort()

    return ", ".join(["%s" % g for g in grantNo])


# ---------------------------------------------------------------------
# Instantiate the Log class
# ---------------------------------------------------------------------
l   = cdr.Log(LOGNAME)
l.write("CTGovTransfer (Manual) - Started", stdout = True)
l.write('Arguments: %s' % sys.argv, stdout=True)
print ''

options   = parseArguments(sys.argv)
testMode  = options.values.testMode
emailMode = options.values.emailMode

# If no file name is specified (the default) we're picking the last
# file created.
# -----------------------------------------------------------------
### if options.values.file:
###     useFile = options.values.file
###     oldFile = getLastProtocolList(OUTPUTBASE)
###     l.write("  Last protocol list was: %s" % oldFile, stdout = True)
### else:
###     useFile = getLastProtocolList(OUTPUTBASE)
###     l.write("Comparing output to file: %s" % useFile, stdout = True)

try:
    # Open the latest manifest file (or the one specified) and read 
    # the content
    # -------------------------------------------------------------
    protocols = {}
    oldFile = []
    oldIds = []
    # A) If the file name has been passed as a parameter and the file 
    #    doesn't exist, exit.
    # B) If no file exists in the directory this is the first time the 
    #    process is run and we continue
    # --------------------------------------------------------------------
###     if options.values.file and not os.access(path % useFile, os.F_OK):
###         sys.exit('Invalid File Name: %s' % useFile)
###     elif not options.values.file and not os.access(path % useFile, os.F_OK):
###         l.write("No files found.  Assuming new directory", stdout = True)
###     else:
###         f = open(path % useFile, 'r')
###         protocols = f.readlines()
###         f.close()
### 
###         # Read the list of previously published protocols
###         # ------------------------------------------------
###         for row in protocols:
###             oldIds.append(int(row.split('\t')[0]))


    # Connect to the database and get all protocols without a 
    # TransferDate.
    # --------------------------------------------------------------
    newWithdrawn = []

    conn = cdrdb.connect()
    cursor = conn.cursor()
        
    try:
        cursor.execute("""\
        SELECT q.doc_id AS "CDR-ID", p.value AS "Primary ID", 
               n.value AS "NCT ID", o.value AS "Lead Sponsor",
               q.value AS "Transfer Owner", u.value AS "PRS User",
               c.value, v.dt
          FROM query_term q
          JOIN query_term p
            ON p.doc_id = q.doc_id
           AND p.path = '/CTGovProtocol/IDInfo/OrgStudyID'
          JOIN query_term n
            ON n.doc_id = q.doc_id
           AND n.path = '/CTGovProtocol/IDInfo/NCTID'
          JOIN query_term t
            ON t.doc_id = q.doc_id
           AND t.path = '/CTGovProtocol/PDQAdminInfo'            +
                        '/CTGovOwnershipTransferInfo'            +
                        '/CTGovOwnerOrganization'
          LEFT JOIN query_term u
            ON u.doc_id = t.doc_id
           AND u.path = '/CTGovProtocol/PDQAdminInfo'            +
                        '/CTGovOwnershipTransferInfo'            +
                        '/PRSUserName'
          JOIN doc_version v
            ON v.id = q.doc_id
          LEFT outer JOIN query_term o
            ON o.doc_id = q.doc_id
           AND o.path = '/CTGovProtocol/Sponsors/LeadSponsor'
-- Get the Ownership Comment
LEFT OUTER JOIN query_term c
             ON c.doc_id = q.doc_id
            AND c.path = '/CTGovProtocol/PDQAdminInfo'           +
                         '/CTGovOwnershipTransferInfo'           +
                           '/Comment'
         WHERE q.path = '/CTGovProtocol'                         +
                        '/PDQAdminInfo'                          +
                        '/CTGovOwnershipTransferInfo'            +
                        '/CTGovOwnerOrganization'
           AND q.doc_id IN (SELECT doc_id
                                  FROM query_term
                                 WHERE path = '/CTGovProtocol'   +
                                   '/PDQAdminInfo'               +
                                   '/CTGovOwnershipTransferInfo' +
                                   '/CTGovOwnershipTransferDate'
                                   AND value = ''
                                )
           AND v.num = (SELECT min(num)
                          FROM doc_version i
                          JOIN doc_type t
                            ON t.id = i.doc_type
                           AND t.name = 'CTGovProtocol'
                         WHERE i.id = v.id
                       )
           AND v.dt > '%s'
         ORDER BY q.doc_id""" % transferDate, timeout = 300)

        rows = cursor.fetchall()
        cursor.close()
    except cdrdb.Error, info:
        l.write("Failure retrieving protocols: \n%s" % info[1][0], 
                 stdout = True)
        sendErrorMessage('SQL query timeout error')
        raise

###    # Create the new manifest file and identify those records that
###    # are new since the last time this job ran (by comparing to the
###    # file created last time).
###    # -------------------------------------------------------------
###    f = open(path % outputFile, 'w')
###    newIds = []
###    l.write("", stdout = True)
###    l.write("List of new CTGovTransfer protocols", stdout = True)
###    l.write("-----------------------------------",   stdout = True)
###    for (cdrId, protocolId, nctId, orgName, transferOrg,
###         prsName, comment) in rows:
###        # l.write("%s, %s, %s, %s" % (cdrId, protocolId, nctId, orgName), 
###        #                             stdout = True)
###
###        try:
###            if cdrId not in oldIds:
###                l.write("%s, %s, %s, %s" % (cdrId, protocolId, nctId, orgName), 
###                                            stdout = True)
###                f.write("%10s\t%25s\t%12s\tNew\n" % (cdrId, 
###                                                    protocolId.encode('utf-8'), 
###                                                    nctId.encode('utf-8')))
###                newIds.append(cdrId)
###            else:
###                f.write("%10s\t%25s\t%12s\n" % (cdrId, 
###                                                protocolId.encode('utf-8'), 
###                                                nctId.encode('utf-8')))
###        except Exception, info:
###            l.write("Failure retrieving protocols: \n%s" % info[1][0], 
###                     stdout = True)
###            sendErrorMessage('writing Unicode convertion error')
###            raise
###
###    f.close()

    # Create the message body and display the query results
    # -----------------------------------------------------
    if len(rows):
        l.write("", stdout = True)
        l.write('List of transferred protocol IDs', stdout = True)
        l.write('--------------------------------', stdout = True)
        mailBody = u"""\
<html>
 <head>
  <title>Transfer Ownership to Responsible Party</title>
  <style type='text/css'>
   th      { background-color: #f0f0f0; }
  </style>
 </head>
 <body>
  <h2>Transfer Ownership to Responsible Party</h2>
  <h3>Date: %s</h3>

  <table border='1px' cellpadding='2px' cellspacing='2px'>
   <tr>
    <th>CDR-ID</th>
    <th>Primary ID</th>
    <th>NCT-ID</th>
    <th>Lead Org Name</th>
    <th>Transfer Org</th>
    <th>PRS Username</th>
    <th>Comment</th>
    <th>Grant No</th>
    <th>PUP Name</th>
    <th>PUP Email</th>
   </tr>
""" % (time.strftime("%m/%d/%Y", now))

        try:
            for (cdrId, protocolId, nctId, orgName, transOrgName,
                 PRSName, comment, updDate) in rows:
                l.write('%s' % cdrId, stdout = True)

                mailBody += u"""\
   <tr>
    <td>CDR%010d</td>
    <td>%s</td>
    <td>
     <a href="http://www.clinicaltrials.gov/ct2/show/%s">%s</a>
    </td>
    <td>%s</td>
    <td>%s</td>
    <td>%s</td>
    <td>%s</td>
""" % (cdrId, protocolId, nctId, nctId, orgName, transOrgName,
       PRSName, comment)

                # Populate the PUP information
                pup = PUP(cdrId)

                if not pup.persId:
                    pup = PUP(cdrId, 'Protocol chair')

                mailBody += u"""\
    <td>%s</td>
    <td>%s</td>
    <td>%s</td>
   </tr>
""" % (getGrantNo(cdrId), '%s %s' % (pup.persFname, pup.persLname), 
                                                              pup.persEmail)

        except Exception, info:
            l.write("Failure retrieving protocols: \n%s" % info[1][0], 
                     stdout = True)
            sendErrorMessage('Unicode convertion error')
            raise


        mailBody += u"""\
  </table>

 </body>
</html>
"""
    else:
        raise NoNewDocumentsError('NoNewDocumentsError')
        

    # In Testmode we don't want to send the notification to the world
    # ---------------------------------------------------------------
    # Email constants
    # ---------------
    if testMode:
        strTo    = cdr.getEmailList('Test Publishing Notification')
    else:
        strTo    = cdr.getEmailList('CTGov Transfer Notification')
        #strTo.append(u'register@clinicaltrials.gov')

    mailHeader   = """\
From: %s
To: %s
Subject: %s: %s
""" % (STR_FROM, u', '.join(strTo), cdr.PUB_NAME.capitalize(),
       'Transfer of Protocol(s) from NCI to Responsible Party')

    mailHeader   += "Content-type: text/html; charset=utf-8\n"

    # Add a Separator line + body
    # ---------------------------
    message = mailHeader + "\n" + mailBody

    #print message

    # Sending out the email 
    # ---------------------
    server = smtplib.SMTP(SMTP_RELAY)
    if emailMode:
        try:
            server.sendmail(STR_FROM, strTo, message.encode('utf-8'))
        except Exception, info:
            sys.exit("*** Error sending message: %s" % str(info))
    else:
        l.write("Running in NOEMAIL mode.  No message send", stdout = True)
    server.quit()

except NothingFoundError, arg:
    msg  = "No documents found with 'CTGovTransfer' element"
    l.write("   %s" % msg, stdout = True)
    l.write("   %s" % arg, stdout = True)
except NoNewDocumentsError, arg:
    msg  = "No new documents found with 'CTGovTransfer' element"
    l.write("", stdout = True)
    l.write("   %s" % msg, stdout = True)
    l.write("   %s" % arg, stdout = True)
except Exception, arg:
    l.write("*** Standard Failure - %s" % arg, stdout = True, tback = 1)
except:
    l.write("*** Error - Program stopped with failure ***", stdout = True, 
                                                            tback = 1)
    raise

l.write("CTGovTransfer (Manual) - Finished", stdout = True)
sys.exit(0)
