#!d:/python/python.exe
# *********************************************************************
#
# File Name: $RCSFile:$
#            ===============
# Program to identify and notify about documents whose status has 
# changed resulting in having them pulled from Cancer.gov via a manual
# Hotfix-Remove request.
# These are several individual SQL queries (by DocType) based on the 
# content of the publishing document.  Submitting an email message to
# a select group if one (or more) document(s) have been identified
# to be removed from Cancer.gov.
# ---------------------------------------------------------------------
# $Author$
# Created:          2010-06-21        Volker Englisch
# Last Modified:    $
# 
# $Source: $
# $Revision$
#
# $Id$
#
# BZIssue::4732 - Change in logic for pulling documents from Cancer.gov
#
# *********************************************************************
import sys, cdr, cdrdb, os, time, optparse, smtplib, glob

OUTPUTBASE     = cdr.BASEDIR + "/Output/HotfixRemove"
DOC_FILE       = "HotfixRemove"
LOGNAME        = "HotfixRemove.log"
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

    return parser


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
       '*** Error: Program CheckHotfixRemove failed!')

    mailHeader   += "Content-type: text/html; charset=utf-8\n"
    mailBody      = "<b>Error running HotfixRemove.py</b><br>"
    mailBody     += "Most likely %s<br>" % msg
    mailBody     += "See log file for details."

    # Add a Separator line + body
    # ---------------------------
    message = mailHeader + "\n" + mailBody

    server = smtplib.SMTP(SMTP_RELAY)
    server.sendmail(STR_FROM, '***REMOVED***', message.encode('utf-8'))
    server.quit()


# ---------------------------------------------------------------------
# Instantiate the Log class
# ---------------------------------------------------------------------
l   = cdr.Log(LOGNAME)
l.write("CheckHotfixRemove - Started", stdout = True)
l.write('Arguments: %s' % sys.argv, stdout=True)
print ''

options   = parseArguments(sys.argv)
testMode  = options.values.testMode
emailMode = options.values.emailMode

try:
    # Open the latest manifest file (or the one specified) and read 
    # the content
    # -------------------------------------------------------------
    protocols = {}
    oldFile = []
    oldIds = []

    # Connect to the database and get all protocols without a 
    # TransferDate.
    # --------------------------------------------------------------
    newWithdrawn = []

    conn = cdrdb.connect()
    cursor = conn.cursor()
    allDocs = []
        

    # Selecting Hotfix-Remove candidates for Glossary Term
    # ----------------------------------------------------
    try:
        cursor.execute("""\
        SELECT dt.name AS "Doc Type", cg.id   AS "CDR-ID", 
               d.title AS "Title",    p.value AS "Status"
          FROM pub_proc_cg cg
          JOIN document d
            ON d.id  = cg.id
          JOIN doc_type dt
            ON dt.id = d.doc_type
          JOIN query_term_pub p
            ON d.id  = p.doc_id
         WHERE dt.name = 'GlossaryTermName'
           AND p.path  = '/GlossaryTermName/TermNameStatus'
           AND p.value NOT IN ('Approved', 'Revision pending')
""", timeout = 300)

        rows = cursor.fetchall()
    except cdrdb.Error, info:
        l.write("Failure retrieving protocols: \n%s" % info[1][0], 
                 stdout = True)
        sendErrorMessage('SQL query timeout error')
        raise

    allDocs += rows

    # Selecting Hotfix-Remove candidates for Term
    # -------------------------------------------
    try:
        cursor.execute("""\
        SELECT dt.name AS "Doc Type", cg.id   AS "CDR-ID", 
               d.title AS "Title",    p.value AS "Status"
          FROM pub_proc_cg cg
          JOIN document d
            ON d.id  = cg.id
          JOIN doc_type dt
            ON dt.id = d.doc_type
          JOIN query_term_pub p
            ON d.id  = p.doc_id
         WHERE dt.name = 'Term'
           AND p.path = '/Term/TermStatus'
           AND p.value NOT IN ('Reviewed-Problematic', 
                              'Reviewed-Retain', 
                              'Unreviewed')
""", timeout = 300)
        rows = cursor.fetchall()
    except cdrdb.Error, info:
        l.write("Failure retrieving protocols: \n%s" % info[1][0], 
                 stdout = True)
        sendErrorMessage('SQL query timeout error')
        raise

    allDocs += rows

    # Selecting Hotfix-Remove candidates for InScopeProtocol
    # ------------------------------------------------------
    try:
        cursor.execute("""\
        SELECT dt.name AS "Doc Type", cg.id   AS "CDR-ID", 
               d.title AS "Title",    p.value AS "Status"
          FROM pub_proc_cg cg
          JOIN document d
            ON d.id  = cg.id
          JOIN doc_type dt
            ON dt.id = d.doc_type
          JOIN query_term_pub p
            ON d.id  = p.doc_id
         WHERE dt.name = 'InScopeProtocol'
           AND p.path = '/InScopeProtocol/ProtocolAdminInfo' +
                        '/CurrentProtocolStatus'
           AND p.value NOT IN ('Active', 
                               'Approved-not yet active', 
                               'Enrolling by invitation',
                               'Closed', 
                               'Completed', 
                               'Temporarily closed')
""", timeout = 300)
        rows = cursor.fetchall()
    except cdrdb.Error, info:
        l.write("Failure retrieving protocols: \n%s" % info[1][0], 
                 stdout = True)
        sendErrorMessage('SQL query timeout error')
        raise

    allDocs += rows

    # Selecting Hotfix-Remove candidates for GeneticsProfessionals
    # ------------------------------------------------------------
    try:
        cursor.execute("""\
        SELECT dt.name AS "Doc Type", cg.id   AS "CDR-ID", 
               d.title AS "Title",    p.value AS "Status"
          FROM pub_proc_cg cg
          JOIN document d
            ON d.id  = cg.id
          JOIN doc_type dt
            ON dt.id = d.doc_type
          JOIN query_term_pub p
            ON d.id  = p.doc_id
         WHERE dt.name = 'Person'
           AND p.path = '/Person/ProfessionalInformation' +
                        '/GeneticsProfessionalDetails'    +
                        '/AdministrativeInformation/Directory/Include'
           AND p.value NOT IN ('Include')
""", timeout = 300)
        rows = cursor.fetchall()
    except cdrdb.Error, info:
        l.write("Failure retrieving protocols: \n%s" % info[1][0], 
                 stdout = True)
        sendErrorMessage('SQL query timeout error')
        raise

    allDocs += rows

    # Selecting Hotfix-Remove candidates for Organization
    # ---------------------------------------------------
    try:
        cursor.execute("""\
        SELECT DISTINCT dt.name AS "Doc Type", cg.id   AS "CDR-ID", 
               d.title AS "Title",    p.value AS "Status"
          FROM pub_proc_cg cg
          JOIN document d
            ON d.id  = cg.id
          JOIN doc_type dt
            ON dt.id = d.doc_type
          JOIN query_term_pub p
            ON d.id  = p.doc_id
          JOIN query_term_pub po
            ON po.int_val = p.doc_id
         WHERE dt.name = 'Organization'
           AND p.path = '/Organization/Status/CurrentStatus'
           AND p.value IN ('Inactive')
           AND po.path LIKE '%/@cdr:%ref'
""", timeout = 300)
        rows = cursor.fetchall()
    except cdrdb.Error, info:
        l.write("Failure retrieving protocols: \n%s" % info[1][0], 
                 stdout = True)
        sendErrorMessage('SQL query timeout error')
        raise

    allDocs += rows

    # Create the message body and display the query results
    # -----------------------------------------------------
    if len(allDocs):
        l.write("", stdout = True)
        l.write('List of Hotfix-Remove Candidates', stdout = True)
        l.write('--------------------------------', stdout = True)
        mailBody = u"""\
<html>
 <head>
  <title>Document Candidates to be removed from Cancer.gov</title>
  <style type='text/css'>
   table   { border-spacing: 20px 5px;
             empty-cells: show; 
             border-collapse: collapse; }

   table, th, td {border: 1px solid black; }
   th      { background-color: #f0f0f0; }
  </style>
 </head>
 <body>
  <h2>Document Candidates to be removed from Cancer.gov</h2>
  <h3>Date: %s</h3>

  <table border='1px' cellpadding='2px' cellspacing='2px'>
   <tr>
    <th>Doc Type</th>
    <th>CDR-ID</th>
    <th>Doc Title</th>
    <th>Status</th>
   </tr>
""" % (time.strftime("%m/%d/%Y", now))

        try:
            for doc in allDocs:
                l.write('%s - %s' % (doc[0], doc[1]), stdout = True)

                mailBody += u"""\
   <tr>
    <td>%s</td>
    <td>CDR%010d</td>
    <td>%s</td>
    <td>%s</td>
   </tr>
""" % (doc[0], doc[1], doc[2], doc[3])
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
        strTo    = cdr.getEmailList('Hotfix Remove Notification')
        #strTo.append(u'register@clinicaltrials.gov')

    mailHeader   = """\
From: %s
To: %s
Subject: %s: %s
""" % (STR_FROM, u', '.join(strTo), cdr.PUB_NAME.capitalize(),
       'Document Candidates to be removed from Cancer.gov')

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

l.write("CheckHotfixRemove - Finished", stdout = True)
sys.exit(0)
