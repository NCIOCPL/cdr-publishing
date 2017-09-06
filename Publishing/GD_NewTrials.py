#!d:/python/python.exe
# *********************************************************************
# This report is a modified version of the GD_ChangedDocs.py
#
# A report to list all new trials since last week
# to be delivered for GovDelivery reporting
# ---------------------------------------------------------------------
# Created:          2016-06-14        Volker Englisch
#
# OCECDR-4120: GovDelivery Report for ClinicalTrials
# *********************************************************************
import sys, cdr, cdrdb, os, time, optparse, smtplib, glob, cdrcgi
import calendar

OUTPUTBASE  = cdr.BASEDIR + "/reports"
DOC_FILE    = "GD_NewTrials"
LOGNAME     = "GD_NewTrials.log"
SMTP_RELAY  = "MAILFWD.NIH.GOV"
STR_FROM    = "PDQ Operator <NCIPDQoperator@mail.nih.gov>"

now        = time.localtime()
today      = time.strftime("%Y-%m-%d", now)
dayminus   = time.localtime(time.mktime(now) - 24 * 60 * 60)
yesterday  = time.strftime("%Y-%m-%d", dayminus)
lastweek   = time.localtime(time.mktime(now) - 7 * 24 * 60 * 60)
startWeek  = time.strftime("%Y-%m-%d", lastweek)
endWeek    = time.strftime("%Y-%m-%d", dayminus)

outputFile = '%s_%s.html' % (DOC_FILE, time.strftime("%Y-%m-%dT%H%M%S", now))

testMode   = None
emailMode  = None
dispRows   = None

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
    parser.set_defaults(summary=False)
    parser.set_defaults(dis=False)
    parser.set_defaults(debug=False)

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
    parser.add_option('-s', '--startdate',
                      action = 'store', dest = 'start',
                      help = 'enter the start date (first day of week)')
    parser.add_option('-d', '--enddate',
                      action = 'store', dest = 'end',
                      help = 'enter the end date (last day of week)')
    parser.add_option('--debug',
                      action = 'store_true', dest = 'debug',
                      help = 'list additional debug information')

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
    if parser.values.debug:
        l.write("Listing debug information", stdout = True)
    if parser.values.start:
        startDate = parser.values.start
        l.write("Setting Start Date: %s" % startDate, stdout = True)
    if parser.values.end:
        endDate = parser.values.end
        l.write("Setting End Date: %s" % endDate, stdout = True)

    return parser


# --------------------------------------------------------------------
# Module to submit an email message if the program fails
# --------------------------------------------------------------------
def sendErrorMessage(msg):
    # We want to send an email so that the query doesn't silently fail
    # ----------------------------------------------------------------
    recips = cdr.getEmailList("Developers Notification")
    mailHeader   = """\
From: %s
To: %s
Subject: %s: %s
""" % (STR_FROM, ", ".join(recips), cdr.PUB_NAME.capitalize(),
       '*** Error: GovDelivery New Trials Report failed!')

    mailHeader   += "Content-type: text/html; charset=utf-8\n"
    mailBody      = "<b>Error running GD_NewTrials.py</b><br>"
    mailBody     += "Most likely %s<br>" % msg
    mailBody     += "See log file for details."

    # Add a Separator line + body
    # ---------------------------
    message = mailHeader + "\n" + mailBody

    server = smtplib.SMTP(SMTP_RELAY)
    server.sendmail(STR_FROM, recips, message.encode('utf-8'))
    server.quit()


# -------------------------------------------------------------
# List the reformatted summaries
# -------------------------------------------------------------
def getTrials(cursor, startDate=startWeek, endDate=endWeek):
    # Query for brand new trials - first time published
    # -------------------------------------------------
    query = """\
         SELECT c.nlm_id AS "NCT-ID", c.cdr_id AS "CDR-ID", q.value AS "Title",
                c.became_active, c.title
           FROM ctgov_import c
           JOIN pub_proc_cg cg
             ON cg.id = c.cdr_id
           JOIN query_term_pub q
             ON q.doc_id = c.cdr_id
            AND q.path = '/CTGovProtocol/BriefTitle'
          WHERE  ISNULL(became_active, 0) >= '%s'
            AND ISNULL(became_active, 0) < dateadd(DAY, 1, '%s')
""" % (startDate, endDate)

    if debug:
        l.write('********************************************************',
                                                              stdout=True)
        l.write('[SQL query submitted:]', stdout=True)
        l.write(query, stdout=True)

    cursor.execute(query, timeout=600)
    rows = cursor.fetchall()

    if debug:
        l.write('----------------', stdout=True)
        l.write('Rows: %s' % len(rows), stdout=True)
        l.write('********************************************************',
                                                              stdout=True)

    l.write('   Number of trials = %d' % (len(rows)), stdout=True)
    if not rows or rows[0][0] == 0:
        return []

    return rows


# --------------------------------------------------------
# Formatting the report portion listing a table
# --------------------------------------------------------
def formatTableOutput(records, heading):
    if not records:
        html  = "<br/>\n<h3>%s<h3>\n" % heading
        html += "<p style='margin-bottom: 1em;'><b>None</b></p>"
        return html

    # Sorting by first element
    # ------------------------
    records.sort()

    n = 0
    for rec in records:
        n += 1
        l.write("%d *****" % n, stdout = True)
        l.write("%s" % rec, stdout = True)
        l.write('', stdout = True)

    # For the full report we print by default the document title
    # and the CDR-ID but some other document types might need to
    # display additional columns
    # -----------------------------------------------------------
    # Header Row
    # ----------
    html = """
  <table class='docstable'>
  <tr>
   <th>NCT-ID</th>
   <th>CDR-ID</th>
   <th>Official Title</th>
   <th>Activated</th>
  </tr>
"""

    # Data Row
    # --------
    for row in records:
        # Creating the link to the document
        # ---------------------------------
        html += """\
  <tr>
   <td VALIGN='top'>
    <a href='http://%s.%s/about-cancer/treatment/clinical-trials/search/view?cdrid=%s'>%s</a>
   </td>
   <td VALIGN='top'>%s</td>
""" % (cdr.h.host['CG'][0], cdr.h.host['CG'][1],
       row[1], cdrcgi.unicodeToLatin1(row[0]), row[1])

        html += """\
   <td VALIGN='top'>
    <a href='http://%s.%s/about-cancer/treatment/clinical-trials/search/view?cdrid=%s'>%s</a>
   </td>
   <td VALIGN='top'>%s</td>
  </tr>
""" % (cdr.h.host['CG'][0], cdr.h.host['CG'][1],
       row[1], cdrcgi.unicodeToLatin1(row[2]), row[3][:10])

    html += u"""\
 </table>
"""
    return html


# --------------------------------------------------------
# Formatting the report portion listing trials as bullets
# --------------------------------------------------------
def formatBulletOutput(records, heading):
    if not records:
        return ''

    # Sorting by first element
    # ------------------------
    records.sort()

    # For the full report we print by default the document title
    # and the CDR-ID but some other document types might need to
    # display additional columns
    # -----------------------------------------------------------
    # Header Row
    # ----------
    html = ""
    html += """
  <br/>
  <h3>Data from table above using bulleted list format</h3>
  <strong>Clinical Trials Now Accepting New Patients</strong>
  <ul>
"""

    # Data Row
    # --------
    for row in records:
        # The title links to the Changes-section (HP only)
        # ------------------------------------------------
        html += """\
  <li>
    <a href='http://%s.%s/about-cancer/treatment/clinical-trials/search/view?cdrid=%s'>%s</a>
  </li>
""" % (cdr.h.host['CG'][0], cdr.h.host['CG'][1],
       row[1], cdrcgi.unicodeToLatin1(row[2]))

    html += u"""\
 </ul>
"""
    return html


# --------------------------------------------------------
# Creating email message body/report to be submitted
# --------------------------------------------------------
def getMessageHeaderFooter(startDate=startWeek, endDate=endWeek,
                           section='Header', title='', date=''):
    if section == 'Header':
        html = u"""\
<html>
 <head>
  <title>%s</title>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  <style type='text/css'>
   table   { border-spacing: 20px 5px;
             empty-cells: show;
             border-collapse: collapse; }

   table, th, td {border: 1px solid black; }
   th      { background-color: #f0f0f0;
             font-weight: bold; }
   td      { padding: 1px 10px; }
   *.countstable  {  }
   *.docstable    {  }
  </style>
 </head>
 <body>
  <h3>Date: %s</h3>
  <h2>%s</h2>
""" % (title, date, title)
    else:
        html = u"""\
 </body>
</html>
"""

    return html



# --------------------------------------------------------
# Creating email message body/report to be submitted
# --------------------------------------------------------
def createMessageBody(title='Test Title', startDate=startWeek,
                                          endDate=endWeek):
    # Dictionary to be used for the misc. text labels by doc type
    # Note: Originally, the report was planned to have different
    #       sections - new, revised, new after being removed
    #       previously, etc.  The dictionary was holding headings
    #       used for the individual sections.
    # -----------------------------------------------------------
    textLabels = { 'new':  'New Trials'  }

    conn = cdrdb.connect()
    cursor = conn.cursor()

    l.write("", stdout = True)
    l.write(title, stdout = True)

    # Select the documents published with status 'active'
    # ---------------------------------------------------
    trialsNew = getTrials(cursor, startDate, endDate)

    # Put together the email message body
    # -----------------------------------
    mailBody = getMessageHeaderFooter(startDate, endDate, title=title,
                                      date=time.strftime("%m/%d/%Y", now))

    # Prepare the tables to be attached to the report
    # -------------------------------------------------------------------
    trialsTable = formatTableOutput(trialsNew, textLabels['new'])
    trialsBullet = formatBulletOutput(trialsNew, textLabels['new'])

    mailBody += trialsTable + trialsBullet

    mailBody += getMessageHeaderFooter(section='Footer')

    return mailBody


# --------------------------------------------------------
# Sending email report
# Note: The name for the foreign list is called '... NoUS'
#       because the group name is limited to 32 characters
# --------------------------------------------------------
def sendEmailReport(messageBody, title):

    # In Testmode we don't want to send the notification to the world
    # ---------------------------------------------------------------
    # Email constants
    # ---------------
    if testMode:
        strTo    = cdr.getEmailList('Test Publishing Notification')
    else:
        strTo = cdr.getEmailList('GovDelivery Trials Notification')

    subject   = "%s-%s: %s" %(cdr.h.org, cdr.h.tier, title)

    mailHeader = """\
From: %s
To: %s
Subject: %s
""" % (STR_FROM, u', '.join(strTo), subject)

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
        l.write(message, stdout=True)
    server.quit()

    return


# ---------------------------------------------------------------------
# Instantiate the Log class
# ---------------------------------------------------------------------
l   = cdr.Log(LOGNAME)
l.write('GovDelivery Trials Report - Started', stdout = True)
l.write('Arguments: %s' % sys.argv, stdout=True)
l.write('', stdout=True)

options   = parseArguments(sys.argv)
testMode  = options.values.testMode
testMode = True
emailMode = options.values.emailMode
debug     = options.values.debug

# We're running both, the summaries and DIS by default
# ----------------------------------------------------
dispDis = options.values.dis
dispSummary = options.values.summary

startDate = options.values.start or startWeek
endDate = options.values.end or endWeek

title = u'GovDelivery New Trials Report from %s to %s' % (
                                              startDate, endDate)

# If no file name is specified (the default) we're picking the last
# file created.
# -----------------------------------------------------------------
if testMode:
    outputFile = outputFile.replace('.html', '.test.html')

path = OUTPUTBASE + '/%s' % outputFile
l.write('', stdout=True)
l.write('Writing report to: %s' % path, stdout=True)

try:
    conn = cdrdb.connect()
    cursor = conn.cursor()

    # Preparing email message to be send out
    # --------------------------------------
    report = createMessageBody(title, startDate, endDate)

    if debug:
        print '----------------------'
        print report
        print '----------------------'

    # Send the output as an email or print to screen
    # ----------------------------------------------
    if emailMode:
        l.write("Running in EMAIL mode.  Submitting email.", stdout = True)
        sendEmailReport(report, title)

    # We're writing the report to the reports directory
    # -----------------------------------------------------------------
    l.write("Writing HTML output file.", stdout = True)
    f = open(path, 'w')
    f.write(report.encode('utf-8'))
    f.close()

except Exception, arg:
    l.write("*** Standard Failure - %s" % arg, stdout = True, tback = 1)
except:
    sendErrorMessage('Standard Exception in GovDelivery Trials Report')
    l.write("*** Error - Program stopped with failure ***", stdout = True,
                                                            tback = 1)
    raise

l.write("GovDelivery Trials Report - Finished", stdout = True)
sys.exit(0)
