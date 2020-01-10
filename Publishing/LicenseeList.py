#!d:/python/python.exe
# *********************************************************************
# Program to create a list of active licensees (Production/Test)
# This job should run as a scheduled job once a month.
# ---------------------------------------------------------------------
# Created:          2013-06-05        Volker Englisch
#
# OCECDR-3898: Modify PDQ Partner Documents
# *********************************************************************
import sys, cdr, os, time, optparse, smtplib, glob
from cdrapi import db

OUTPUTBASE     = cdr.BASEDIR + "/reports"
DOC_FILE       = "Licensees"
LOGNAME        = "Licensees.log"

now            = time.localtime()
outputFile     = '%s_%s.html' % (DOC_FILE, time.strftime("%Y%m%d%H%M%S", now))

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

    usage = "usage: %prog [--email | --noemail] [--testmode | --livemode]"
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



# ---------------------------------------------------------------------
# Instantiate the Log class
# ---------------------------------------------------------------------
LOGGER = cdr.Logging.get_logger("Licensees", console=True)
LOGGER.info("LicenseeList Report - Started")
LOGGER.info('Arguments: %s', sys.argv)
print('')

options   = parseArguments(sys.argv)
testMode  = options.values.testMode
emailMode = options.values.emailMode

# If no file name is specified (the default) we're picking the last
# file created.
# -----------------------------------------------------------------
filename = OUTPUTBASE + '/' + outputFile
LOGGER.info("Content Partner report is: %s", outputFile)
LOGGER.info("  at path: %s", filename)

try:
    # Connect to the database to get the full list of protocols with
    # the CTGovDuplicate element.
    # 2019-09-02 (RMK): not sure what this comment means in this context???
    # --------------------------------------------------------------
    conn = db.connect(timeout=300)
    cursor = conn.cursor()

    cursor.execute("""\
         SELECT n.doc_id, n.value AS "Name",
                t.value AS "Status",
                a.value AS "Test Act", r.value AS "R-Date",
                ti.value AS "TI-Date", p.value AS "P-Date",
                pdi.value AS "Prod Inact"
           FROM query_term n
           JOIN query_term t
             ON t.doc_id = n.doc_id
            AND t.path = '/Licensee/LicenseeInformation' +
                         '/LicenseeStatus'
           JOIN query_term a
             ON a.doc_id = n.doc_id
            AND a.path = '/Licensee/LicenseeInformation' +
                         '/LicenseeStatusDates'          +
                         '/TestActivation'
LEFT OUTER JOIN query_term r
             ON r.doc_id = n.doc_id
            AND r.path = '/Licensee/LicenseeInformation' +
                         '/LicenseeStatusDates'          +
                         '/TestExtension'
LEFT OUTER JOIN query_term ti
             ON ti.doc_id = n.doc_id
            AND ti.path = '/Licensee/LicenseeInformation' +
                          '/LicenseeStatusDates'          +
                          '/TestInactivation'
LEFT OUTER JOIN query_term p
             ON p.doc_id = n.doc_id
            AND p.path = '/Licensee/LicenseeInformation' +
                         '/LicenseeStatusDates'          +
                         '/ProductionActivation'
LEFT OUTER JOIN query_term pdi
             ON pdi.doc_id = n.doc_id
            AND pdi.path = '/Licensee/LicenseeInformation' +
                           '/LicenseeStatusDates'          +
                           '/ProductionInactivation'
          WHERE n.path =   '/Licensee/LicenseeInformation' +
                           '/LicenseeNameInformation'      +
                           '/OfficialName/Name'
            AND t.value in ('Production', 'Test')
          ORDER BY t.value, n.value""")

    rows = cursor.fetchall()

    lCount = {'prod':0, 'test':0}
    for row in rows:
        if row[2] == 'Production':
            lCount['prod'] += 1
        else:
            lCount['test'] += 1

    cursor.close()

    # Create the message body and display the query results
    # -----------------------------------------------------
    LOGGER.info("")
    LOGGER.info('List of Current Content Partners (active and test)')
    mailBody = """\
<html>
 <head>
  <title>List of PDQ Content Distribution Partners</title>
  <style type='text/css'>
   th      { background-color: #f0f0f0; }
  </style>
 </head>
 <body>
  <h2>List of PDQ Distribution Partners</h2>
  <h3>Date: %s</h3>
  <b>Active Partners: %d&nbsp;&nbsp;&nbsp;Test Partners: %s<br></b>

  <table border='1px' cellpadding='2px' cellspacing='2px'>
   <tr>
    <th>CDR-ID</th>
    <th>Partner Name</th>
    <th>Status</th>
    <th>Test started</th>
    <th>Test renewed</th>
    <th>Test removed</th>
    <th>Prod started</th>
    <th>Prod removed</th>
   </tr>
""" % (time.strftime("%m/%d/%Y", now), lCount['prod'], lCount['test'])

    for (cdrId, orgName, status, testStart, testRenew, testRemove, prodStart, prodRemove) in rows:
        mailBody += """\
   <tr>
    <td>CDR%d</td>
    <td>%s</td>
    <td>%s</td>
    <td>%s</td>
    <td>%s</td>
    <td>%s</td>
    <td>%s</td>
    <td>%s</td>
   </tr>
""" % (cdrId, orgName, status, testStart, testRenew or '', testRemove or '', prodStart or '', prodRemove or '')

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
        strTo    = cdr.getEmailList('Test Publishing Notification')
    else:
        strTo    = cdr.getEmailList('Licensee Report Notification')

    args = cdr.Tier().name, 'PDQ Distribution Partner List'
    subject = "[%s] %s" % args

    mailHeader   = """\
From: %s
To: %s
Subject: %s
""" % (strFrom, ", ".join(strTo), subject)

    mailHeader   += "Content-type: text/html; charset=iso-8859-1\n"

    # Add a Separator line + body
    # ---------------------------
    message = mailHeader + "\n" + mailBody

    #print message

    # Sending out the email
    # ---------------------
    f = open(filename, 'w')
    f.write(mailBody)
    f.close()

    server = smtplib.SMTP(SMTP_RELAY)
    if emailMode:
        server.sendmail(strFrom, strTo, message)
    else:
        LOGGER.info("Running in NOEMAIL mode.  No message sent")

    server.quit()

except Exception as arg:
    LOGGER.exception("*** Standard Failure - %s", arg)
except:
    LOGGER.exception("*** Error - Program stopped with failure ***")
    raise

LOGGER.info("LicenseeList Report - Finished")
sys.exit(0)
