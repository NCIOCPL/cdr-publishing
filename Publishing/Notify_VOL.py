#----------------------------------------------------------------------
# Script intended to submit an email to the Visuals OnLine (VOL)
# team when a media document has been updated or added to Cancer.gov.
# New addition - an image that has been made publishable should be
# included as well regardless if it's linked to a document or not.
#
# OCECDR-3752: Modify Media VOL (Visual Online) Report to include all
#              publishable media (images) docs.
# OCECDR-4036: Updated Media Docs Report- Correct Date Range
# OCECDR-4016: Modifications to Weekly CDR Images Automated Report
#----------------------------------------------------------------------
import os, sys, cdr, time, optparse, cdrdb
import datetime

FILEBASE           = "Notify_VOL"
LOGNAME            = "%s.log" % FILEBASE
jobTime            = time.localtime(time.time())
today              = datetime.date.today()
yesterday          = today - datetime.timedelta(1)


reportTitles = { 'new':'New Images',
                 'upd':'Revised Images',
                 'del':'Blocked (Removed) Images' }


testMode   = None

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
    parser.add_option('-s', '--startdate', dest = 'startDate',
                      metavar = 'STARTDATE',
                      help = 'start date of time frame (default one week)')
    parser.add_option('-e', '--enddate', dest = 'endDate',
                      metavar = 'ENDDATE',
                      help = 'end date of time frame (default yesterday)')

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

    if parser.values.startDate:
        startDate = parser.values.startDate
        l.write("Start Date: %s" % startDate, stdout = True)

    if parser.values.endDate:
        endDate = parser.values.endDate
        l.write("End   Date: %s" % endDate, stdout = True)

    return parser


# ------------------------------------------------------------
# Function to check the database if media documents where
# updated for the given time frame.
# If the type='new' is passed we're only listing document
# that have not publishable version prior to the start date.
# ------------------------------------------------------------
def checkForMediaUpdates(sDate, eDate, type=''):
    """
    Assign all input parameters to variables and perform some error
    checking.
    """
    if type == 'new':
        q_new = """
                    AND  not exists (  -- if any publishable version exists this is not a new doc
                   SELECT 'x' -- i.id
                     FROM doc_version i
                    WHERE i.id = dv.id
                      AND i.dt < '%s'
                      AND i.publishable = 'Y'
                   )
""" % sDate
    else:
        q_new = ""

    # Select all Media (Image) documents with a new publishable version
    # created during the previous week (or the specified time frame)
    # This includes new and updated images.
    # -----------------------------------------------------------------
    try:
        conn = cdrdb.connect()
        cursor = conn.cursor()
        cursor.execute("""\
        SELECT d.id
          FROM document d
          JOIN doc_type dt
            ON d.doc_type = dt.id
           AND dt.name = 'Media'
          JOIN doc_version dv
            ON dv.id = d.id
         WHERE d.val_status = 'V'
           AND d.active_status = 'A'
           AND NOT EXISTS (
                   SELECT 'x'
                     FROM query_term_pub i
                    WHERE i.doc_id = d.id
                      AND path = '/Media/PhysicalMedia/SoundData/SoundEncoding'
                   )
           AND dv.num = (
                   SELECT MAX(num)
                     FROM doc_version
                    WHERE id = dv.id
                   )
           AND dv.dt BETWEEN '%s' AND '%s'
           AND dv.publishable = 'Y'
           %s
         ORDER BY d.id
""" % (sDate, eDate, q_new), timeout=300)
        rows = cursor.fetchall()
        ids = []
        for row in rows:
            ids.append(row[0])

    except cdrdb.Error, info:
        l.write("Failure finding updated media documents: %s" % (info[1][0]))

    return ids


# ------------------------------------------------------------
# Function to check the database if media documents where
# blocked last week.  A document that is currently blocked
# and has a new version created is assumed to be blocked
# during the previous week.
# ------------------------------------------------------------
def checkForBlockedImages(sDate, eDate):
    """
    Assign all input parameters to variables and perform some error
    checking.
    """

    # Select all Media (Image) documents with a new version
    # which is currently blocked and a publishable version exists.
    # -----------------------------------------------------------------
    try:
        conn = cdrdb.connect()
        cursor = conn.cursor()
        cursor.execute("""\
        SELECT d.id
          FROM document d
          JOIN doc_version dv
            ON dv.id = d.id
          JOIN query_term q
            ON d.id = q.doc_id
          JOIN doc_type dt
            ON d.doc_type = dt.id
           AND dt.name = 'Media'
         WHERE d.active_status = 'I'
           AND dv.dt BETWEEN '%s' AND '%s'
           AND q.path = '/Media/MediaContent/Categories/Category'
           AND q.value not in ('pronunciation', 'meeting recording')
           AND EXISTS (SELECT 'x'
                         FROM doc_version i
                        WHERE i.id = d.id
                          AND i.publishable = 'Y')

         ORDER BY d.id
""" % (sDate, eDate), timeout=300)
        rows = cursor.fetchall()
        ids = []
        for row in rows:
            ids.append(row[0])

    except cdrdb.Error, info:
        l.write("Failure finding blocked media documents: %s" % (info[1][0]))

    return ids



# ------------------------------------------------------------
# Function to find the information to be displayed for blocked
# images
# Note:  Blocked documents will only be included if a
#        publishable version did exist in the past.  Images
#        without publishable version won't be included.
# ------------------------------------------------------------
def getVersions(ids, sDate, eDate, type=''):
    rows = ""

    # Looking for publishable versions only if type='pub'
    # ---------------------------------------------------
    if type == 'pub':
        pubType = """
           AND dv.publishable = 'Y'
"""
    else:
        pubType = ""

    try:
        conn = cdrdb.connect()
        cursor = conn.cursor()
        # dv.id      -> CDR-ID
        # dv.num     -> version number
        # t.value    -> title
        # fp.dt      -> date of first publishable version
        # dv.dt      -> date of last publishable version
        # dv.publishable ->
        # dv.comment -> version comment
        cursor.execute("""\
        SELECT dv.id, dv.num, t.value, fp.dt, dv.dt,
               v.value, dv.comment
          FROM doc_version dv
LEFT OUTER JOIN query_term v
            ON dv.id = v.doc_id
           AND v.path = '/Media/@BlockedFromVOL'
          JOIN query_term t
            ON t.doc_id = dv.id
           AND t.path = '/Media/MediaTitle'
          JOIN doc_version fp
            ON fp.id = dv.id
           AND fp.dt = (SELECT MIN(i.dt)
                          FROM doc_version i
                         WHERE i.id = dv.id
                           AND i.publishable = 'Y'
                       )
         WHERE dv.id IN (%s)
           %s
           AND dv.dt between '%s' AND '%s'
         ORDER BY id, num
""" % (', '.join("%s" % x for x in ids),
       pubType, sDate, eDate))

        rows = cursor.fetchall()
    except cdrdb.Error, info:
        l.write("Failure finding media data: %s" % (info[1][0]))

    return rows


# ------------------------------------------------------------
# Function to create the HTML table rows
# ------------------------------------------------------------
def createRows(versions):
    tableRows = ""
    host = "%s.%s" % cdr.h.host["APPC"]
    class_ = "even"

    for row in versions:
        class_ = class_ == "even" and "odd" or "even"
        tableRows += """
   <tr class="%s">
    <td class="link">
     <a href="https://%s/cgi-bin/cdr/QcReport.py?Session=guest&DocId=CDR%s&DocVersion=%s">%s</a>
    </td>
    <td>%s</td>
    <td class="link">
     <a href="https://%s/cgi-bin/cdr/GetCdrImage.py?id=CDR%s.jpg">%s</a>
    </td>
    <td>%s</td>
    <td>%s</td>
    <td align="center">%s</td>
    <td>%s</td>
   </tr>
       """ % (class_, host, row[0], row[1], row[0],
                            row[1],
                      host, row[0], row[2],
                            row[3] and row[3][:16] or '',
                            row[4] and row[4][:16] or '',
                            row[5] and 'Y' or '',
                            row[6] or '')
    return tableRows


# ------------------------------------------------------------
# *** Main ***
# Jetzt wird es ernst
# ------------------------------------------------------------
# Open Log file and enter start message
# -------------------------------------
l = cdr.Log(LOGNAME)
l.write('Notify_VOL - Started', stdout = True)
l.write('Arguments: %s' % sys.argv, stdout=True)
print ''

options   = parseArguments(sys.argv)
testMode  = options.values.testMode
emailMode = options.values.emailMode

# If only the start date is specified, the timeframe will be from
# the start date until yesterday.  If only the end date is
# specified, the timeframe will be the week prior (and including)
# that date. Otherwise it's whatever dates are passed
# or the week prior to today if no dates are specified.
# ---------------------------------------------------------------
endDate    = options.values.endDate   or str(yesterday)
endDateSql = datetime.datetime.strptime(endDate, "%Y-%m-%d").date() \
             + datetime.timedelta(1)
startDate = options.values.startDate \
            or datetime.datetime.strptime(endDate, "%Y-%m-%d").date() \
             - datetime.timedelta(6)

# Checking if Media documents were updated for the given
# time frame.
# ----------------------------------------------------------
pubVersionIds = checkForMediaUpdates(startDate, endDateSql)

# Get the list of new images
# --------------------------
newImages = checkForMediaUpdates(startDate, endDateSql, type='new')


# Get the list of updated images
# ------------------------------
updImages = list(set(pubVersionIds) - set(newImages))

# Get the list of blocked images
# ------------------------------
delImages = checkForBlockedImages(startDate, endDateSql)

# Get the data to be displayed for the media docs
# -----------------------------------------------
if updImages:
    updMediaChanges = getVersions(updImages, startDate, endDateSql,
                                  type='pub')
else:
    updMediaChanges = []

if newImages:
    newMediaChanges = getVersions(newImages, startDate, endDateSql,
                                  type='pub')
else:
    newMediaChanges = []

if delImages:
    delMediaChanges = getVersions(delImages, startDate, endDateSql)
else:
    delMediaChanges = []

# Print the result
# ----------------
l.write('Time Frame:  %s to %s' % (startDate, endDate), stdout = True)
l.write('New Media Documents:\n%s\n' % newMediaChanges, stdout = True)
l.write('Updated Media Documents:\n%s\n' % updMediaChanges, stdout = True)
l.write('Blocked Media Documents:\n%s\n' % delMediaChanges, stdout = True)

# Setting up email message to be send to users
# --------------------------------------------
# machine  = socket.gethostname().split('.')[0]
sender   = 'NCIPDQoperator@mail.nih.gov'
subject = cdr.emailSubject('List of Updated Media Documents')

html     = """
<html>
 <head>
  <title>Media List Report</title>
  <style type='text/css'>
    body         { background-color: white; }
    h3            { font-weight: bold;
                    font-family: Arial;
                    font-size: 16pt;
                    margin-left: 0pt; }
    TABLE.output  { margin-left: auto;
                    margin-right: auto; }
    TABLE.output  TD
                  { padding: 3px; }
    td.header     { font-weight: bold;
                    text-align: center; }
    tr.odd        { background-color: #E7E7E7; }
    tr.even       { background-color: #FFFFFF; }
    tr.head       { background-color: #D2D2D2; }
    .link         { color: blue;
                    text-decoration: underline; }
    p             { font-weight: bold;
                    font-family: Arial;
                    font-size: 10pt; }
    .sub-title    { font-weight: normal; }
   </STYLE>
 </head>
 <body>
"""

header = """
  <h3>%s</h3>

  <p class="sub-title">
  Report includes documents made publishable between
  <b>%s</b> and <b>%s</b><br/>
  </p>
"""
delHeader = """
  <h3>%s</h3>

  <p class="sub-title">
  Report includes blocked (removed) documents versioned between
  <b>%s</b> and <b>%s</b><br/>
  </p>
"""

tableHeader = """
  <table class="output" border="1">
   <tr class="head">
    <td class="header">CDR-ID</td>
    <td class="header">Doc<br>Version</td>
    <td class="header">Media Title</td>
    <td class="header">First Pub<br>Version Date</td>
    <td class="header">Version Date</td>
    <td class="header">Blocked<br>from<br/>VOL</td>
    <td class="header">Comment</td>
   </tr>
%s
  </table>
"""

# Creating the 'New Media Docs' section
# -------------------------------------
html += header % (reportTitles['new'], startDate, endDate)
if newImages:
    newReport = createRows(newMediaChanges)
    html += tableHeader % newReport
else:
    html += """
    <p class="none">None</p>
"""


# Creating the 'Revised Media Docs' section
# -----------------------------------------
html += header % (reportTitles['upd'], startDate, endDate)
if updImages:
    updReport = createRows(updMediaChanges)
    html += tableHeader % updReport
else:
    html += """
    <p class="none">None</p>
"""

# Creating the 'Blocked Media Docs' section
# -----------------------------------------
html += delHeader % (reportTitles['del'], startDate, endDate)
if delImages:
    delReport = createRows(delMediaChanges)
    html += tableHeader % delReport
else:
    html += """
    <p class="none">None</p>
"""

html += """
 </body>
</html>"""

# Don't send emails to everyone if we're testing
# ----------------------------------------------
emailDL = cdr.getEmailList('VOL Notification')
emailDL.sort()
if not len(emailDL) or testMode:
    recips = ["***REMOVED***"]
else:
    recips = emailDL

allChanges = newMediaChanges + updMediaChanges + delMediaChanges
if allChanges and recips:
    l.write("Email submitted to DL", stdout = True)
    cdr.sendMail(sender, recips, subject, html, html = 1)
else:
    # Else statement included to monitor the program
    recips = ["***REMOVED***"]
    l.write("Email NOT submitted to DL", stdout = True)
    cdr.sendMail(sender, recips, subject, html, html = 1)

# All done, going home now
# ------------------------
cpu = time.clock()
l.write('CPU time: %6.2f seconds' % cpu, stdout = True)
l.write('Notify_VOL - Finished', stdout = True)
sys.exit(0)
