#!d:/python/python.exe
# *********************************************************************
# Program to identify and notify about documents whose status has
# changed resulting in having them pulled from Cancer.gov via a manual
# Hotfix-Remove request.
# These are several individual SQL queries (by DocType) based on the
# content of the publishing document.  Submitting an email message to
# a select group if one (or more) document(s) have been identified
# to be removed from Cancer.gov.
# ---------------------------------------------------------------------
# Created:          2010-06-21        Volker Englisch
#
# BZIssue::4732 - Change in logic for pulling documents from Cancer.gov
# *********************************************************************
import sys, cdr, os, time, optparse, smtplib, glob
from cdrapi import db

# OUTPUTBASE     = cdr.BASEDIR + "/Output/HotfixRemove"
# DOC_FILE       = "HotfixRemove"
SMTP_RELAY     = "MAILFWD.NIH.GOV"
STR_FROM       = "PDQ Operator <NCIPDQoperator@mail.nih.gov>"

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
# class NothingFoundError(Exception):
#     def __init__(self, value):
#         self.value = value
#     def __str__(self):
#         return repr(self.value)

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
        LOGGER.info("Running in TEST mode")
    else:
        LOGGER.info("Running in LIVE mode")

    if parser.values.emailMode:
        LOGGER.info("Running in EMAIL mode")
    else:
        LOGGER.info("Running in NOEMAIL mode")

    return parser


# --------------------------------------------------------------------
# Module to submit an email message if the program fails
# --------------------------------------------------------------------
def sendErrorMessage(msg):
    # We want to send an email so that the query doesn't silently fail
    # ----------------------------------------------------------------
    args = cdr.Tier().name, "*** Error: Program CheckHotfixRemove failed!"
    subject = "[%s] %s" % args

    recips = cdr.getEmailList("Developers Notification")
    mailHeader   = """\
From: %s
To: %s
Subject: %s
""" % (STR_FROM, ", ".join(recips), subject)

    mailHeader   += "Content-type: text/html; charset=utf-8\n"
    mailBody      = "<b>Error running HotfixRemove.py</b><br>"
    mailBody     += "Most likely %s<br>" % msg
    mailBody     += "See log file for details."

    # Add a Separator line + body
    # ---------------------------
    message = mailHeader + "\n" + mailBody

    server = smtplib.SMTP(SMTP_RELAY)
    server.sendmail(STR_FROM, recips, message.encode('utf-8'))
    server.quit()


# ---------------------------------------------------------------------
# Instantiate the logging class
# ---------------------------------------------------------------------
LOGGER = cdr.Logging.get_logger("HotfixRemove", console=True)
LOGGER.info("CheckHotfixRemove - Started")
LOGGER.info('Arguments: %s', sys.argv)
print('')

options   = parseArguments(sys.argv)
testMode  = options.values.testMode
emailMode = options.values.emailMode

try:
#     # Initiallize variables
#     # -------------------------------------------------------------
#     oldFile = []
#     oldIds = []
#     newWithdrawn = []

    # Connect to the database and retrieve documents to be removed
    # --------------------------------------------------------------
    conn = db.connect(timeout=300)
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
""")

        rows = cursor.fetchall()
    except Exception:
        LOGGER.exception("Failure retrieving GlossaryTerms")
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
""")
        rows = cursor.fetchall()
    except Exception:
        LOGGER.exception("Failure retrieving Terms")
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
""")
        rows = cursor.fetchall()
    except Exception:
        LOGGER.exception("Failure retrieving Genetics Profs")
        sendErrorMessage('SQL query timeout error')
        raise

    allDocs += rows

    # Create the message body and display the query results
    # -----------------------------------------------------
    if len(allDocs):
        LOGGER.info("")
        LOGGER.info('List of Hotfix-Remove Candidates')
        LOGGER.info('--------------------------------')
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
                LOGGER.info('%s - %s', doc[0], doc[1])

                mailBody += u"""\
   <tr>
    <td>%s</td>
    <td>CDR%010d</td>
    <td>%s</td>
    <td>%s</td>
   </tr>
""" % (doc[0], doc[1], doc[2], doc[3])
        except Exception as info:
            LOGGER.exception("Failure creating report")
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

    args = cdr.Tier().name, "Document Candidates to be removed from Cancer.gov"
    subject = "[%s] %s" % args

    mailHeader   = """\
From: %s
To: %s
Subject: %s
""" % (STR_FROM, u', '.join(strTo), subject)

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
        except Exception as info:
            LOGGER.exception("Failure sending message")
            sys.exit(f"*** Error sending message: {info}")
    else:
        LOGGER.info("Running in NOEMAIL mode.  No message send")
    server.quit()

# except NothingFoundError, arg:
#     msg  = "No documents found with 'CTGovTransfer' element"
#     LOGGER.info("   %s", msg)
#     LOGGER.info("   %s", arg)
except NoNewDocumentsError as arg:
    msg  = "No new documents found to be removed"
    LOGGER.info("")
    LOGGER.info("   %s", msg)
    LOGGER.info("   %s", arg)
except Exception as arg:
    LOGGER.exception("*** Standard Failure - %s", arg)
except:
    LOGGER.exception("*** Error - Program stopped with failure ***")
    raise

LOGGER.info("CheckHotfixRemove - Finished")
sys.exit(0)
