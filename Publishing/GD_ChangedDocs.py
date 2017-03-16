#!d:/python/python.exe
# *********************************************************************
# This report is a modified version of the ICRDBStatsReport.py
#
# A report to list all summaries and drug info summaries modified in
# the previous week to be delivered for GovDelivery reporting
# The report needs to run for English and Spanish audiences.
# ---------------------------------------------------------------------
# Created:          2012-02-10        Volker Englisch
#
# OCECDR-3989: [GovDelivery] Report of New/Revised Summaries and DIS
# *********************************************************************
import sys, cdr, cdrdb, os, time, optparse, smtplib, glob, cdrcgi
import calendar

OUTPUTBASE  = cdr.BASEDIR + "/reports"
DOC_FILE    = "GD_ChangedDocs"
LOGNAME     = "GD_ChangedDocs.log"
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
language   = None

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
    parser.set_defaults(language = 'EN')

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
                      help = 'enter the start date (first day of month)')
    parser.add_option('-d', '--enddate',
                      action = 'store', dest = 'end',
                      help = 'enter the end date (last day of month)')
    parser.add_option('--summary',
                      action = 'store_true', dest = 'summary',
                      help = 'list the summary section')
    parser.add_option('--dis',
                      action = 'store_true', dest = 'dis',
                      help = 'list the dis section')
    parser.add_option('--language',
                      action = 'store', dest = 'language',
                      help = 'enter the language (EN)')
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
    if parser.values.summary:
        l.write("Listing Summary records", stdout = True)
    if parser.values.dis:
        l.write("Listing Drug Info records", stdout = True)
    if parser.values.debug:
        l.write("Listing debug information", stdout = True)
    if parser.values.language:
        l.write("Listing language: %s" % language, stdout = True)
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
    mailHeader   = """\
From: %s
To: %s
Subject: %s: %s
""" % (STR_FROM, '***REMOVED***', cdr.PUB_NAME.capitalize(),
       '*** Error: GovDelivery Changes Report failed!')

    mailHeader   += "Content-type: text/html; charset=utf-8\n"
    mailBody      = "<b>Error running GD_ChangedDocs.py</b><br>"
    mailBody     += "Most likely %s<br>" % msg
    mailBody     += "See log file for details."

    # Add a Separator line + body
    # ---------------------------
    message = mailHeader + "\n" + mailBody

    server = smtplib.SMTP(SMTP_RELAY)
    server.sendmail(STR_FROM, '***REMOVED***', message.encode('utf-8'))
    server.quit()


# -------------------------------------------------------------
# List the reformatted summaries
# -------------------------------------------------------------
def getDocuments(cursor, startDate=startWeek, endDate=endWeek,
                         docType='', repType='', language=''):
    # Debug message listing the document type and report type
    # -------------------------------------------------------
    l.write('   docType = %s, repType = %s' % (docType, repType), stdout=True)
    l.write('  language = %s' % language, stdout=True)

    # Select the individual queries
    # -----------------------------
    if docType == 'DrugInformationSummary':
        if repType == 'new':
            query = """\
            SELECT t.value as "Title", d.id as "CDR-ID",
                   u.value AS "URL", d.first_pub as "Publishing Date",
                   v.dt AS "PubDate"
              FROM document d
              JOIN query_term t
                on d.id = t.doc_id
               AND t.path = '/DrugInformationSummary/Title'
              JOIN pub_proc_cg cg
                on d.id = cg.id
              JOIN query_term_pub u
                ON d.id = u.doc_id
               AND u.path = '/DrugInformationSummary/DrugInfoMetaData/URL/@cdr:xref'
              JOIN doc_version v
                ON d.id = v.id
             WHERE d.active_status = 'A'
               AND ISNULL(first_pub, 0) >= '%s'
               AND ISNULL(first_pub, 0) < dateadd(DAY, 1, '%s')
               AND v.publishable = 'Y'
               AND v.num = (SELECT MAX(num)
                              FROM doc_version i
                             WHERE i.id = v.id
                               AND i.publishable = 'Y'
                            )
             ORDER BY d.first_pub
        """ % (startDate, endDate)
        elif repType == 'revised':
            query = """\
            SELECT t.value as "Title", d.id as "CDR-ID",
                   u.value AS "URL", dlm.value AS "DLM",
                   v.dt AS "PubDate"
              FROM document d
    LEFT OUTER JOIN query_term_pub dlm
                ON dlm.doc_id = d.id
               AND dlm.path = '/DrugInformationSummary/DateLastModified'
              JOIN query_term t
                ON d.id = t.doc_id
               AND t.path = '/DrugInformationSummary/Title'
              JOIN pub_proc_cg cg
                ON d.id = cg.id
              JOIN query_term_pub u
                ON d.id = u.doc_id
               AND u.path = '/DrugInformationSummary/DrugInfoMetaData/URL/@cdr:xref'
              JOIN doc_version v
                ON d.id = v.id
             WHERE d.active_status = 'A'
               AND ISNULL(dlm.value, 0) >= '%s'
               AND ISNULL(dlm.value, 0) < dateadd(DAY, 1, '%s')
               AND v.publishable = 'Y'
               AND v.num = (SELECT MAX(num)
                              FROM doc_version i
                             WHERE i.id = v.id
                               AND i.publishable = 'Y'
                            )
             ORDER BY dlm.value
        """ % (startDate, endDate)
    elif docType == 'Summary':
        if repType == 'new':
            query = """\
            SELECT t.value AS "Title", d.id AS "CDR-ID",
                   a.value AS "Audience", l.value AS "Language",
                   u.value AS "URL", f.value as "Fragment",
                   d.first_pub, v.dt AS "PubDate"
              FROM document d
              JOIN query_term_pub t
                ON d.id = t.doc_id
               AND t.path = '/Summary/SummaryTitle'
              JOIN query_term_pub l
                ON d.id = l.doc_id
               AND l.path = '/Summary/SummaryMetaData/SummaryLanguage'
              JOIN query_term_pub a
                ON d.id = a.doc_id
               AND a.path = '/Summary/SummaryMetaData/SummaryAudience'
              JOIN pub_proc_cg cg
                ON cg.id = d.id
              JOIN query_term_pub u
                ON d.id = u.doc_id
               AND u.path = '/Summary/SummaryMetaData/SummaryURL/@cdr:xref'
              JOIN query_term_pub c
                ON d.id = c.doc_id
               AND c.path = '/Summary/SummarySection/SectMetaData/SectionType'
              JOIN query_term_pub f
                ON f.doc_id = c.doc_id
               AND f.path = '/Summary/SummarySection/@cdr:id'
               AND SUBSTRING(f.node_loc, 1, 4) = SUBSTRING(c.node_loc, 1, 4)
              JOIN doc_version v
                ON d.id = v.id
             WHERE d.active_status = 'A'
               AND ISNULL(first_pub, 0) >= '%s'
               AND ISNULL(first_pub, 0) < dateadd(DAY, 1, '%s')
               AND l.value = '%s'
               AND c.value = 'Changes to summary'
               AND v.publishable = 'Y'
               AND v.num = (SELECT MAX(num)
                              FROM doc_version i
                             WHERE i.id = v.id
                               AND i.publishable = 'Y'
                            )
             ORDER BY d.first_pub
""" % (startDate, endDate, language)

        elif repType == 'revised':
            query = """\
            SELECT t.value AS "Title", d.id AS "CDR-ID",
                   a.value AS "Audience", l.value AS "Language",
                   u.value AS "URL", f.value as "Fragment",
                   dlm.value AS "Date LM", v.dt AS "PubDate"
              FROM document d
              JOIN query_term_pub t
                ON d.id = t.doc_id
               AND t.path = '/Summary/SummaryTitle'
              JOIN query_term_pub l
                ON d.id = l.doc_id
               AND l.path = '/Summary/SummaryMetaData/SummaryLanguage'
              JOIN query_term_pub a
                ON d.id = a.doc_id
               AND a.path = '/Summary/SummaryMetaData/SummaryAudience'
              JOIN query_term_pub dlm
                ON d.id = dlm.doc_id
               AND dlm.path = '/Summary/DateLastModified'
              JOIN pub_proc_cg cg
                ON cg.id = d.id
              JOIN query_term_pub u
                ON d.id = u.doc_id
               AND u.path = '/Summary/SummaryMetaData/SummaryURL/@cdr:xref'
              JOIN query_term_pub c
                ON d.id = c.doc_id
               AND c.path = '/Summary/SummarySection/SectMetaData/SectionType'
              JOIN query_term_pub f
                ON f.doc_id = c.doc_id
               AND f.path = '/Summary/SummarySection/@cdr:id'
               AND SUBSTRING(f.node_loc, 1, 4) = SUBSTRING(c.node_loc, 1, 4)
              JOIN doc_version v
                ON d.id = v.id
             WHERE d.active_status = 'A'
               AND ISNULL(dlm.value, 0) >= '%s'
               AND ISNULL(dlm.value, 0) < dateadd(DAY, 1, '%s')
               AND l.value = '%s'
               AND c.value = 'Changes to summary'
               AND v.publishable = 'Y'
               AND v.num = (SELECT MAX(num)
                              FROM doc_version i
                             WHERE i.id = v.id
                               AND i.publishable = 'Y'
                            )
             ORDER BY dlm.value
""" % (startDate, endDate, language)
    else:
        return None


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

    if not rows or rows[0][0] == 0:
        return []

    return rows


# --------------------------------------------------------
# Checking if any of the documents is checked out by users
# --------------------------------------------------------
def formatFullOutput(records, heading, docType='', repType=''):
    if not records:
        html  = "<br/>\n<h3>%s<h3>\n" % heading
        html += "<p style='margin-bottom: 1em;'><b>None</b></p>"
        return html

    # Sorting by first element
    # ------------------------
    records.sort()

    # For the full report we print by default the document title
    # and the CDR-ID but some other document types might need to
    # display additional columns
    # -----------------------------------------------------------
    # Header Row
    # ----------
    html  = """
  <br/>
  <h3>%s</h3>
""" % heading

    html += """
  <table class='docstable'>
  <tr>
   <th>Title</th>
   <th>CDR-ID</th>
  </tr>
"""

    # Data Row
    # --------
    for row in records:
        # Only include one type of audience in table
        # ------------------------------------------
        if docType == 'Summary' and row[2] != repType:
            continue

        if docType == 'Summary':
            # The title links to the Changes-section (HP only)
            # ------------------------------------------------
            if row[2] == 'Patients':
                html += """\
  <tr>
   <td VALIGN='top'>%s</td>
""" % (cdrcgi.unicodeToLatin1(row[0]))
            else:
                html += """\
  <tr>
   <td VALIGN='top'>
    <a href='%s#section/%s'>%s</a>
""" % (row[4], row[5], cdrcgi.unicodeToLatin1(row[0]))

            # Creating the link to the document
            # ---------------------------------
            html += """\
   <td VALIGN='top'>
    <a href='%s'>%d</a>
   </td>
""" % (row[4], row[1])

        elif docType == 'DrugInformationSummary':
            html += """\
   <td VALIGN='top'>%s</td>
   <td VALIGN='top'>
    <a href='%s'>%d</a>
   </td>
""" % (row[0], row[2], row[1] or '')


        html += """\
  </tr>
"""

    html += u"""\
 </table>
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
                                          endDate=endWeek, language=''):
    # Dictionary to be used for the misc. text labels by doc type
    # -----------------------------------------------------------
    textLabels = {
                   'hprev':  'Revised Health Professional Summaries'  ,
                   'patrev': 'Revised Patient Summaries',
                   'hpnew':  'New Health Professional Summaries'  ,
                   'patnew': 'New Patient Summaries',
                   'disnew': 'New Drug Information Summaries'  ,
                   'disrev': 'Revised Drug Information Summaries'  ,
               }

    conn = cdrdb.connect()
    cursor = conn.cursor()

    l.write("", stdout = True)
    l.write(title, stdout = True)

    countSummariesNewAll = 0
    countSummariesRevAll = 0
    countSummariesNew = {'hpnew':0, 'patnew':0}
    countSummariesRev = {'hprev':0, 'patrev':0}
    if dispSummary:
        # New Summaries Files
        # -------------------------------
        summariesNew = getDocuments(cursor, startDate, endDate,
                                    docType='Summary', repType='new',
                                    language=language)
        if summariesNew:
            countSummariesNewAll = len(summariesNew)
            for i in summariesNew:
                if i[2] == 'Health professionals':
                    countSummariesNew['hpnew'] += 1
                elif i[2] == 'Patients':
                    countSummariesNew['patnew'] += 1

        # Revised Summaries Files
        # -------------------------------
        summariesRevised = getDocuments(cursor, startDate, endDate,
                                        docType='Summary', repType='revised',
                                        language=language)
        if summariesRevised:
            countSummariesRevAll = len(summariesRevised)
            for i in summariesRevised:
                if i[2] == 'Health professionals':
                    countSummariesRev['hprev'] += 1
                elif i[2] == 'Patients':
                    countSummariesRev['patrev'] += 1

    # New DIS Files
    # -------------------------------
    countDisNew = 0
    countDisRev = 0
    if language == 'English' and dispDis:
        disNew = getDocuments(cursor, startDate, endDate,
                              docType='DrugInformationSummary', repType='new',
                              language=language)
        if disNew:
            if debug:
                print '******************************'
                print disNew

            countDisNew = len(disNew)

        disRevised = getDocuments(cursor, startDate, endDate,
                                  docType='DrugInformationSummary',
                                  repType='revised', language=language)
        if disRevised:
            if debug:
                print disRevised
                print '******************************'

            countDisRev = len(disRevised)

    # Put together the email message body
    # -----------------------------------
    mailBody = getMessageHeaderFooter(startDate, endDate, title=title,
                                      date=time.strftime("%m/%d/%Y", now))

    # Prepare the tables to be attached to the report
    # -------------------------------------------------------------------
    if dispSummary:
        summariesHpNew = formatFullOutput(summariesNew,
                                             textLabels['hpnew'],
                                             docType='Summary',
                                             repType='Health professionals')
        summariesHpRev = formatFullOutput(summariesRevised,
                                             textLabels['hprev'],
                                             docType='Summary',
                                             repType='Health professionals')
        summariesPatNew = formatFullOutput(summariesNew,
                                             textLabels['patnew'],
                                             docType='Summary',
                                             repType='Patients')
        summariesPatRev = formatFullOutput(summariesRevised,
                                             textLabels['patrev'],
                                             docType='Summary',
                                             repType='Patients')

    if language == 'English' and dispDis:
        disNew = formatFullOutput(disNew,
                                  textLabels['disnew'],
                                  docType='DrugInformationSummary',
                                  repType='new')
        disRev = formatFullOutput(disRevised,
                                  textLabels['disrev'],
                                  docType='DrugInformationSummary',
                                  repType='revised')

    if dispSummary:
        mailBody += summariesHpNew + summariesHpRev
        mailBody += summariesPatNew + summariesPatRev

    if language == 'English' and dispDis:
        mailBody += disNew + disRev

    mailBody += getMessageHeaderFooter(section='Footer')

    return mailBody


# --------------------------------------------------------
# Sending email report
# Note: The name for the foreign list is called '... NoUS'
#       because the group name is limited to 32 characters
# --------------------------------------------------------
def sendEmailReport(messageBody, title, language):

    # In Testmode we don't want to send the notification to the world
    # ---------------------------------------------------------------
    # Email constants
    # ---------------
    if testMode:
        strTo    = cdr.getEmailList('Test Publishing Notification')
    else:
        if language == 'Spanish':
            strTo = cdr.getEmailList('GovDelivery ES Docs Notification')
        else:
            strTo = cdr.getEmailList('GovDelivery EN Docs Notification')

    subject   = "%s-%s: %s (%s)" %(cdr.h.org, cdr.h.tier, title, language)

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
l.write('GovDelivery Report - Started', stdout = True)
l.write('Arguments: %s' % sys.argv, stdout=True)
l.write('', stdout=True)

options   = parseArguments(sys.argv)
testMode  = options.values.testMode
# testMode = True
emailMode = options.values.emailMode
repLang   = options.values.language
debug     = options.values.debug

# Which language are we using?
# ----------------------------
if repLang == 'ES':
    language = 'Spanish'
elif repLang == 'EN':
    language = 'English'
else:
    l.write("Invalid language specified. Use [EN|ES]!", stdout = True)
    sys.exit("*** Exiting with Error ***")

# We're running both, the summaries and DIS by default
# ----------------------------------------------------
dispDis = options.values.dis
dispSummary = options.values.summary

if not dispDis and not dispSummary:
    dispDis = True
    dispSummary = True

startDate = options.values.start or startWeek
endDate = options.values.end or endWeek

title = u'GovDelivery Changed Docs Report (%s) from %s to %s' % (
                                              language, startDate, endDate)

# If no file name is specified (the default) we're picking the last
# file created.
# -----------------------------------------------------------------
if testMode:
    outputFile = outputFile.replace('.html', '.test.html')

path = OUTPUTBASE + '/%s' % outputFile
l.write('Writing report to: %s' % path, stdout=True)

try:
    conn = cdrdb.connect()
    cursor = conn.cursor()

    # Preparing email message to be send out
    # --------------------------------------
    report = createMessageBody(title, startDate, endDate, language)

    if debug:
        print '----------------------'
        print report
        print '----------------------'

    # Send the output as an email or print to screen
    # ----------------------------------------------
    if emailMode:
        l.write("Running in EMAIL mode.  Submitting email.", stdout = True)
        sendEmailReport(report, title, language)

    # We're writing the report to the reports directory
    # -----------------------------------------------------------------
    l.write("Writing HTML output file.", stdout = True)
    f = open(path, 'w')
    f.write(report.encode('utf-8'))
    f.close()

except Exception, arg:
    l.write("*** Standard Failure - %s" % arg, stdout = True, tback = 1)
except:
    l.write("*** Error - Program stopped with failure ***", stdout = True,
                                                            tback = 1)
    raise

l.write("GovDelivery Report - Finished", stdout = True)
sys.exit(0)
