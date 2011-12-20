#!d:/python/python.exe
# *********************************************************************
# $Id: CheckCTGovTransfer.py,v 1.9 2009-09-17 14:52:40 venglisc Exp $
#
# File Name: $RCSFile:$
#            ===============
# Program to identify and notify about protocols that need to be
# transferred from PDQ to CTGov and split those into US and Non-US
# trials.
# ---------------------------------------------------------------------
# $Author: venglisc $
# Created:          2009-03-17        Volker Englisch
# Last Modified:    $
#
# $Source: /usr/local/cvsroot/cdr/Publishing/CheckCTGovTransfer.py,v $
# $Revision: 1.9 $
# $Source: $
#
# $Id: CheckCTGovTransfer.py,v 1.9 2009-09-17 14:52:40 venglisc Exp $
#
# BZIssue::4687
# BZIssue::4826 - Modify "Transfer of Protocol(s)..." email report
# BZIssue::5140 - [CTGOV] Scheduled notification for foreign transfers 
#
# *********************************************************************
import sys, cdr, cdrdb, os, time, optparse, smtplib, glob, cdrcgi

OUTPUTBASE     = cdr.BASEDIR + "/Output/CTGovTransfer"
DOC_FILE       = "CTGovTransfer"
LOGNAME        = "CTGovTransfer.log"
SMTP_RELAY     = "MAILFWD.NIH.GOV"
STR_FROM       = "PDQ Operator <operator@cips.nci.nih.gov>"

now            = time.localtime()
outputFile     = '%s_%s.txt' % (DOC_FILE, time.strftime("%Y%m%d%H%M%S", now))

testMode       = None
emailMode      = None
repType        = ''

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
    parser.add_option('-f', '--filename',
                      action = 'store', dest = 'file',
                      help = 'run diff on this file')

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

    if parser.values.file:
        file = parser.values.file
        l.write("Comparing output to file: %s" % file, stdout = True)

    return parser


# ---------------------------------------------------------------------
# Selecting the protocol list created last time this program ran
# ---------------------------------------------------------------------
def getLastProtocolList(directory = cdr.BASEDIR + '/Output/CTGovTransfer'):
    os.chdir(directory)
    if testMode:
        searchFor = 'CTGovTransferUS_??????????????.test.txt'
    else:
        searchFor = 'CTGovTransferUS_??????????????.txt'

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
def getGrantNo(id, region='US'):
    conn = cdrdb.connect()
    cursor = conn.cursor()

    cursor.execute("""\
        SELECT t.value, g.value
          FROM query_term g
          JOIN query_term t
            ON t.doc_id = g.doc_id
           AND t.path = '/InScopeProtocol/FundingInfo' +
                        '/NIHGrantContract/NIHGrantContractType'
           AND LEFT(g.node_loc, 8) = LEFT(t.node_loc, 8)
         WHERE g.doc_id = %s
           AND g.path = '/InScopeProtocol/FundingInfo' +
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

    # Users like to display 'None' for the non-US report
    # --------------------------------------------------
    if region == 'US':
        grant = u", ".join(["%s" % g for g in grantNo])
    else:
        grant = u", ".join(["%s" % g for g in grantNo]) or u'None'

    return grant


# --------------------------------------------------------
# Checking if any of the documents is checked out by users
# --------------------------------------------------------
def checkedOutByUser(cdrIds):
    try:
        conn = cdrdb.connect()
        cursor = conn.cursor()
        query  = """\
            SELECT d.id, d.title, c.dt_out, u.name
              FROM usr u
              JOIN checkout c
                ON c.usr = u.id
              JOIN document d
                ON d.id = c.id
             WHERE dt_in IS NULL
               AND d.id in (%s)
""" % ",".join(['%s' % x for x in cdrIds])
        
        cursor.execute(query)
        rows = cursor.fetchall()

        if not rows:
            return ""
        else:
            html  = """\
      <br/>
      <br/>
      <br/>
      <h2>Documents Checked out by User(s)</h2>
      <table>
       <tr>
        <th><B>CDR-ID</B></th>
        <th><B>Title</B></th>
        <th><B>Username</B></th>
       </tr>
"""

        for row in rows:
            html += """\
       <tr>
        <td VALIGN='top'>CDR%010d</td>
        <td VALIGN='top'>%s</td>
        <td VALIGN='top'>%s</td>
       </tr>
    """ % (row[0], cdrcgi.unicodeToLatin1(row[1]), row[3])
    except cdrdb.Error, info:
        cdrcgi.bail('Database failure: %s' % info[1][0])

    return html


# --------------------------------------------------------
# Creating email message body/report to be submitted
# --------------------------------------------------------
def createMessageBody(trialIDs, rows, region='US'):
    titles = {}
    titles['US'] = ['List of US transferred protocol IDs',
                    '-----------------------------------',
                    'Transfer Ownership to Responsible Party',
                    ''
                  ]
    titles['NonUS'] = ['List of non-US transferred protocol IDs',
                       '---------------------------------------',
                       'Transfer of Ownership from NCI - Non-US Trials',
 """<p>
  Please transfer the following trial(s) to the Responsible Party. <br>
  <b>*When you have completed the transfers, notify 
  Judy Stringer (jstringer@icfi.com) with the date they were done.*</b><br>
  We need to record this information in our database.
  </p>"""

                  ]
    l.write("", stdout = True)
    l.write(titles[region][0], stdout = True)
    l.write(titles[region][1], stdout = True)
    l.write('%s' % trialIDs, stdout = True)
    mailBody = u"""\
<html>
 <head>
  <title>%s</title>
  <style type='text/css'>
   th      { background-color: #f0f0f0; }
  </style>
 </head>
 <body>
  <h2>%s</h2>
  <h3>Date: %s</h3>

  %s

  <table border='1px' cellpadding='2px' cellspacing='2px'>
   <tr>
    <th>CDR-ID</th>
    <th>Primary ID</th>
    <th>NCT-ID</th>
    <th>Lead Org Name</th>
    <th>Transfer Org</th>
    <th>PRS Username</th>
    <th>Comment</th>
    <th>Protocol Status</th>
    <th>Grant No</th>
    <th>PUP Name</th>
    <th>PUP Email</th>
   </tr>
""" % (titles[region][2], titles[region][2], time.strftime("%m/%d/%Y", now),
       titles[region][3])

    try:
        for (cdrId, protocolId, nctId, orgName, transOrgName,
             PRSName, comment, pStatus, orgId, country) in rows:

            if cdrId in trialIDs:
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
    <td>%s</td>
""" % (cdrId, protocolId, nctId, nctId, orgName, transOrgName,
       PRSName, comment, pStatus)

                # Populate the PUP information
                pup = PUP(cdrId)

                if not pup.persId:
                    pup = PUP(cdrId, 'Protocol chair')

                mailBody += u"""\
    <td>%s</td>
    <td>%s</td>
    <td>%s</td>
   </tr>
""" % (getGrantNo(cdrId, region), '%s %s' % (pup.persFname, pup.persLname), 
                                                              pup.persEmail)

    except Exception, info:
        l.write("Failure retrieving protocols: \n%s" % repr(info), 
                 stdout = True)
        # info[1][0], 
        sendErrorMessage('Unicode convertion error')
        raise

    mailBody += u"""\
  </table>
"""
    # User request to display the document IDs for protocols that
    # are currently checked out.
    # -----------------------------------------------------------
    attachment = checkedOutByUser(trialIDs)
    mailBody += attachment

    mailBody += u"""\
 </body>
</html>
"""
    return mailBody


# --------------------------------------------------------
# Sending email report
# Note: The name for the foreign list is called '... NoUS'
#       because the group name is limited to 32 characters
# --------------------------------------------------------
def sendEmailReport(messageBody, region='US'):
    titles = {}
    titles['US'] = ['Transfer of Protocol(s) from NCI to Responsible '
                    'Party - US']
    titles['NonUS'] = ['Transfer of Protocol(s) from NCI to Responsible '
                       'Party - Non-US']

    # In Testmode we don't want to send the notification to the world
    # ---------------------------------------------------------------
    # Email constants
    # ---------------
    if testMode:
        strTo    = cdr.getEmailList('Test Publishing Notification')
    else:
        if region == 'US':
            strTo = cdr.getEmailList('CTGov Transfer Notification')
        else:
            strTo = cdr.getEmailList('CTGov Transfer Notification NoUS')
            strTo.append(u'***REMOVED***')
            strTo.append(u'register@clinicaltrials.gov')

    mailHeader = """\
From: %s
To: %s
Subject: %s: %s
""" % (STR_FROM, u', '.join(strTo), cdr.PUB_NAME.capitalize(),
       titles[region][0])

    cType = "Content-type: text/html; charset=utf-8\n"
    mailHeader += cType

    # Add a Separator line + body
    # ---------------------------
    message = mailHeader + "\n" + messageBody

    # Sending out the email 
    # ---------------------
    server = smtplib.SMTP(SMTP_RELAY)
    if emailMode:
        try:
            server.sendmail(STR_FROM, strTo, message.encode('utf-8'))
        except Exception, info:
            sys.exit("*** Error sending message (%s): %s" % (region, 
                                                             str(info)))
    else:
        l.write("Running in NOEMAIL mode.  No message send", stdout = True)
    server.quit()

    return


# ---------------------------------------------------------------------
# Instantiate the Log class
# ---------------------------------------------------------------------
l   = cdr.Log(LOGNAME)
l.write("CTGovTransfer - Started", stdout = True)
l.write('Arguments: %s' % sys.argv, stdout=True)
print ''

options   = parseArguments(sys.argv)
testMode  = options.values.testMode
emailMode = options.values.emailMode

# If no file name is specified (the default) we're picking the last
# file created.
# -----------------------------------------------------------------
if options.values.file:
    useFile = options.values.file
    oldFile = getLastProtocolList(OUTPUTBASE)
    l.write("  Last protocol list was: %s" % oldFile, stdout = True)
else:
    useFile = getLastProtocolList(OUTPUTBASE)
    l.write("Comparing output to file: %s" % useFile, stdout = True)

if testMode:
    outputFile = outputFile.replace('.txt', '.test.txt')

outputUS = outputFile.replace('Transfer', 'TransferUS')
outputNonUS = outputFile.replace('Transfer', 'TransferNonUS')

path = OUTPUTBASE + '/%s'
l.write("    New protocol list (US) is:     %s" % outputUS, stdout = True)
l.write("    New protocol list (non-US) is: %s" % outputNonUS, stdout = True)
 
try:
    # Open the latest manifest file (or the one specified) and read 
    # the content
    # -------------------------------------------------------------
    protocolsUS = {}
    protocolsNonUS = {}
    oldFile = []
    oldIdsUS = []
    oldIdsNonUS = []
    # A) If the file name has been passed as a parameter and the file 
    #    doesn't exist, exit.
    # B) If no file exists in the directory this is the first time the 
    #    process is run and we continue
    # --------------------------------------------------------------------
    if options.values.file and not os.access(path % useFile, os.F_OK):
        sys.exit('Invalid File Name: %s' % useFile)
    elif not options.values.file and not os.access(path % useFile, os.F_OK):
        l.write("No files found.  Assuming new directory", stdout = True)
    else:
        f = open(path % useFile, 'r')
        protocolsUS = f.readlines()
        f.close()

        # Read the list of previously published protocols
        # ------------------------------------------------
        for row in protocolsUS:
            oldIdsUS.append(int(row.split('\t')[0]))

        g = open(path % useFile.replace('US', 'NonUS'), 'r')
        protocolsNonUS = g.readlines()
        g.close()

        # Read the list of previously published protocols
        # ------------------------------------------------
        for row in protocolsNonUS:
            oldIdsNonUS.append(int(row.split('\t')[0]))


    # Connect to the database to get the list of protocols with the
    # CTGovTransferInfo block
    # --------------------------------------------------------------
    newWithdrawn = []

    conn = cdrdb.connect()
    cursor = conn.cursor()
        
    try:
        cursor.execute("""\
        SELECT q.doc_id AS "CDR-ID", qid.value AS "Primary ID", 
                nid.value AS "NCTID", o.value AS "OrgName", 
                t.value AS "Transfer Org", q.value AS "PRS Name",
                c.value AS "Comment", s.value AS "Protocol Status", 
                o.doc_id AS "OrgID", 
                CASE us.value
                  WHEN 'U.S.A.' THEN 'US'
                  WHEN 'Canada' THEN 'US'
                  ELSE 'Non-US'
                END AS "Foreign"
           FROM query_term q
-- Get the Primar Protocol ID
           JOIN query_term qid
             ON q.doc_id = qid.doc_id
            AND qid.path = '/InScopeProtocol/ProtocolIds/PrimaryID/IDString'
-- Get Other-ID/NCTID
           JOIN query_term_pub nid
             ON q.doc_id = nid.doc_id
            AND nid.path = '/InScopeProtocol/ProtocolIDs/OtherID/IDString'
           JOIN query_term_pub nt
             ON q.doc_id = nt.doc_id
            AND nt.path = '/InScopeProtocol/ProtocolIDs/OtherID/IDType'
            AND nt.value = 'ClinicalTrials.gov ID'
            AND LEFT(nt.node_loc, 8) = LEFT(nid.node_loc, 8)
-- Get Lead Org ID
           JOIN query_term_pub oid
             ON q.doc_id = oid.doc_id
            AND oid.path = '/InScopeProtocol/ProtocolAdminInfo' + 
                           '/ProtocolLeadOrg/LeadOrganizationID/@cdr:ref'
-- Get Lead Org Name
           JOIN query_term_pub o
             ON oid.int_val = o.doc_id
            AND o.path = '/Organization/OrganizationNameInformation' + 
                         '/OfficialName/Name'
-- Get Country of Org
           JOIN query_term_pub cips
             ON cips.doc_id = o.doc_id
            AND cips.path = '/Organization/OrganizationLocations/CIPSContact'
           JOIN query_term_pub loc
             ON loc.doc_id = oid.int_val
            AND loc.value = cips.value
            AND loc.path = '/Organization/OrganizationLocations' +
                           '/OrganizationLocation/Location/@cdr:id'
           JOIN query_term us
             ON loc.doc_id = us.doc_id
            AND us.path = '/Organization/OrganizationLocations' +
                          '/OrganizationLocation/Location/PostalAddress/Country'
            AND left(loc.node_loc, 12) = left(us.node_loc, 12)
-- Get the protocol status
           JOIN query_term_pub s
             ON s.doc_id = q.doc_id
            AND s.path = '/InScopeProtocol/ProtocolAdminInfo/CurrentProtocolStatus'
-- Get the primary Lead Org
           JOIN query_term_pub poid
             ON oid.doc_id = poid.doc_id
            AND poid.path  = '/InScopeProtocol/ProtocolAdminInfo'     +
                             '/ProtocolLeadOrg/LeadOrgRole'
            AND poid.value = 'Primary'
            AND left(oid.node_loc, 8) = left(poid.node_loc, 8)

-- Get the Transfer Org Name
           JOIN query_term t
             ON t.doc_id = q.doc_id
            AND t.path = '/InScopeProtocol/CTGovOwnershipTransferInfo' +
                         '/CTGovOwnerOrganization'
-- Get the Ownership Comment
LEFT OUTER JOIN query_term c
             ON c.doc_id = q.doc_id
            AND c.path = '/InScopeProtocol/CTGovOwnershipTransferInfo' +
                           '/Comment'
-- Get the PRS Name
          where q.path = '/InScopeProtocol/CTGovOwnershipTransferInfo' +
                         '/PRSUserName'
           ORDER by us.value, q.doc_id
""", timeout = 500)

        rows = cursor.fetchall()
        cursor.close()
    except cdrdb.Error, info:
        l.write("Failure retrieving protocols: \n%s" % info[1][0], 
                 stdout = True)
        sendErrorMessage('SQL query timeout error')
        raise

    # Create the new manifest file and identify those records that
    # are new since the last time this job ran (by comparing to the
    # file created last time).
    # We need to split the output into two buckets: US trials and
    # non-US trials.
    # -------------------------------------------------------------
    f = open(path % outputUS, 'w')
    g = open(path % outputNonUS, 'w')

    newIdsUS = []
    newIdsNonUS = []

    l.write("", stdout = True)
    l.write("List of new CTGovTransfer protocols", stdout = True)
    l.write("-----------------------------------", stdout = True)

    # Loop through the list of trials found with our SELECT statement
    # listing ALL trials and identify which are old/new or US/non-US
    # ---------------------------------------------------------------
    for (cdrId, protocolId, nctId, orgName, transferOrg,
         prsName, comment, pStatus, orgId, country) in rows:

        try:
            if country == 'US':
                if cdrId not in oldIdsUS:
                    l.write("%s, %s, %s, %s, %s" % (cdrId, protocolId, nctId, 
                                                    orgName, country), 
                                                    stdout = True)
                    f.write("%10s\t%25s\t%12s\tNew\n" % (cdrId, 
                                                    protocolId.encode('utf-8'), 
                                                    nctId.encode('utf-8')))
                    newIdsUS.append(cdrId)
                else:
                    f.write("%10s\t%25s\t%12s\n" % (cdrId, 
                                                    protocolId.encode('utf-8'), 
                                                    nctId.encode('utf-8')))
            else:
                if cdrId not in oldIdsNonUS:
                    l.write("%s, %s, %s, %s, %s" % (cdrId, protocolId, nctId, 
                                                    orgName, country), 
                                                    stdout = True)
                    g.write("%10s\t%25s\t%12s\tNew\n" % (cdrId, 
                                                    protocolId.encode('utf-8'), 
                                                    nctId.encode('utf-8')))
                    newIdsNonUS.append(cdrId)
                else:
                    g.write("%10s\t%25s\t%12s\n" % (cdrId, 
                                                    protocolId.encode('utf-8'), 
                                                    nctId.encode('utf-8')))
        except Exception, info:
            l.write("Failure retrieving protocols: \n%s" % info[1][0], 
                     stdout = True)
            sendErrorMessage('writing Unicode convertion error')
            raise

    # Done writing the files
    # ----------------------
    f.close()
    g.close()

    # If there aren't any new documents we don't need to send an email
    # Exit here
    # ----------------------------------------------------------------
    if not newIdsUS and not newIdsNonUS:
        raise NoNewDocumentsError('NoNewDocumentsError')
        
    # Preparing email message to be send out
    # --------------------------------------
    region = ''
    if newIdsUS:
       region = 'US'
       reportUS = createMessageBody(newIdsUS, rows)
       sendEmailReport(reportUS)

    if newIdsNonUS:
       region = 'NonUS'
       reportNonUS = createMessageBody(newIdsNonUS, rows, region)
       sendEmailReport(reportNonUS, region)
        
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

l.write("CTGovTransfer - Finished", stdout = True)
sys.exit(0)
