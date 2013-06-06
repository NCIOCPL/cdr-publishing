#!d:/python/python.exe
# *********************************************************************
#
# File Name: $RCSFile:$
#            ===============
# Program to create a list of active licensees (Production/Test)
# This job should run as a scheduled job once a month.
# ---------------------------------------------------------------------
# $Author: volker $
# Created:          2013-06-05        Volker Englisch
# Last Modified:    $$
# 
# $Source: $
# $Revision: $
#
# $Id: $
#
# *********************************************************************
import sys, cdr, cdrdb, os, time, optparse, smtplib, glob

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

    usage = "usage: %prog [--email | --noemail]"
    parser = optparse.OptionParser(usage = usage)

    parser.set_defaults(testMode = True)
    parser.set_defaults(emailMode = True)
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
    if parser.values.emailMode:
        l.write("Running in EMAIL mode", stdout = True)
    else:
        l.write("Running in NOEMAIL mode", stdout = True)

    return parser


    
# ---------------------------------------------------------------------
# Instantiate the Log class
# ---------------------------------------------------------------------
l   = cdr.Log(LOGNAME)
l.write("LicenseeList Report - Started", stdout = True)
l.write('Arguments: %s' % sys.argv, stdout=True)
print ''

options   = parseArguments(sys.argv)
emailMode = options.values.emailMode

# If no file name is specified (the default) we're picking the last
# file created.
# -----------------------------------------------------------------
filename = OUTPUTBASE + '/' + outputFile
l.write("Licensee report is: %s" % outputFile, stdout = True)
l.write("  at path: %s" % filename, stdout=True)
 
try:
    # Connect to the database to get the full list of protocols with
    # the CTGovDuplicate element.
    # --------------------------------------------------------------
    conn = cdrdb.connect()
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
          ORDER BY t.value, n.value""" , timeout=300)

    rows = cursor.fetchall()
    cursor.close()

    # Create the message body and display the query results
    # -----------------------------------------------------
    l.write("", stdout = True)
    l.write('List of Current Licensees (active and test)', stdout = True)
    mailBody = """\
<html>
 <head>
  <title>List of PDQ Licensees</title>
  <style type='text/css'>
   th      { background-color: #f0f0f0; }
  </style>
 </head>
 <body>
  <h2>List of PDQ Licensees</h2>
  <h3>Date: %s</h3>

  <table border='1px' cellpadding='2px' cellspacing='2px'>
   <tr>
    <th>CDR-ID</th>
    <th>Licensee</th>
    <th>Status</th>
    <th>Test started</th>
    <th>Test renewed</th>
    <th>Test removed</th>
    <th>Prod started</th>
    <th>Prod removed</th>
   </tr>
""" % (time.strftime("%m/%d/%Y", now))

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
    strFrom      = "PDQ Operator <operator@cips.nci.nih.gov>"
    strTo    = cdr.getEmailList('Test Publishing Notification')

    subject = 'Dada'
    if cdr.h.org == 'OCE':
        subject   = "%s: %s" % (cdr.PUB_NAME.capitalize(),
                    'PDQ Licensee List')
    else:
        subject   = "%s-%s: %s" %(cdr.h.org, cdr.h.tier,
                    'PDQ Licensee List')
    
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
        l.write("Running in NOEMAIL mode.  No message send", stdout = True)

    server.quit()

except Exception, arg:
    l.write("*** Standard Failure - %s" % arg, stdout = True, tback = 1)
except:
    l.write("*** Error - Program stopped with failure ***", stdout = True, 
                                                            tback = 1)
    raise

l.write("LicenseeList Report - Finished", stdout = True)
sys.exit(0)
