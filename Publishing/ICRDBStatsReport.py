#!d:/python/python.exe
# *********************************************************************
# $Id$
#
# File Name: $RCSFile:$
#            ===============
# Management report to list a variety of counts (typically run for the
# previous month) regarding the number of documents published, updated,
# etc.
# ---------------------------------------------------------------------
# $Author$
# Created:          2012-02-10        Volker Englisch
#
# $Source: $
# $Revision$
# $Source: $
#
# BZIssue::5173 - ICRDB Stats Report
#
# *********************************************************************
import sys, cdr, cdrdb, os, time, optparse, smtplib, glob, cdrcgi
import calendar

OUTPUTBASE  = cdr.BASEDIR + "/reports"
DOC_FILE    = "ICRDBStats"
LOGNAME     = "ICRDBStats.log"
SMTP_RELAY  = "MAILFWD.NIH.GOV"
STR_FROM    = "PDQ Operator <operator@cips.nci.nih.gov>"

now         = time.localtime()
today       = time.strftime("%Y-%m-%d", now)
lastmonth   = time.localtime(time.mktime(now) - (now[2] + 1) * 24 * 60 * 60)
firstOfMonth= time.strftime("%Y-%m-01", lastmonth)
dateRange   = calendar.monthrange(lastmonth[0], lastmonth[1])
lastOfMonth = time.strftime("%Y-%m-%d", 
                time.strptime("%d-%d-%d" % (lastmonth[0], 
                                            lastmonth[1], dateRange[1]), 
                                                                "%Y-%m-%d"))

outputFile     = '%s_%s.html' % (DOC_FILE, time.strftime("%Y-%m-%dT%H%M%S", now))

testMode       = None
emailMode      = None
dispRows       = None
listNum        = 0

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

    parser.set_defaults(testMode = True)
    parser.set_defaults(emailMode = True)
    parser.set_defaults(listRows = False)
    parser.set_defaults(cdrids = False)
    parser.set_defaults(summary=False)
    parser.set_defaults(dis=False)
    parser.set_defaults(debug=False)
    parser.set_defaults(audio=False)
    parser.set_defaults(images=False)
    parser.set_defaults(glossary=False)
    parser.set_defaults(drug=False)
    parser.set_defaults(meetings=False)
    parser.set_defaults(bmembers=False)
    parser.set_defaults(listNum = 0)

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
    #parser.add_option('-f', '--filename',
    #                  action = 'store', dest = 'fname',
    #                  help = 'run diff on this file')
    parser.add_option('-s', '--startdate',
                      action = 'store', dest = 'start',
                      help = 'enter the start date (first day of month)')
    parser.add_option('-d', '--enddate',
                      action = 'store', dest = 'end',
                      help = 'enter the end date (last day of month)')
    parser.add_option('-r', '--include',
                      action = 'store_true', dest = 'listRows',
                      help = 'include table with list of document rows')
    parser.add_option('--cdrids',
                      action = 'store_true', dest = 'cdrids',
                      help = 'list the CDR-IDs when listing document rows')
    parser.add_option('-c', '--rowmax',
                      action = 'store', dest = 'rowmax',
                      help = 'limit the number of documents displayed to N rows')
    parser.add_option('--summary',
                      action = 'store_true', dest = 'summary',
                      help = 'list the summary section')
    parser.add_option('--dis',
                      action = 'store_true', dest = 'dis',
                      help = 'list the dis section')
    parser.add_option('--audio',
                      action = 'store_true', dest = 'audio',
                      help = 'list the audio section')
    parser.add_option('--images',
                      action = 'store_true', dest = 'images',
                      help = 'list the images section')
    parser.add_option('--glossary',
                      action = 'store_true', dest = 'glossary',
                      help = 'list the glossary/dictionary section')
    parser.add_option('--genetics',
                      action = 'store_true', dest = 'genetics',
                      help = 'list the Genetics Prof. section')
    parser.add_option('--drugterms',
                      action = 'store_true', dest = 'drug',
                      help = 'list the drug section')
    parser.add_option('--boardmembers',
                      action = 'store_true', dest = 'bmembers',
                      help = 'list the board member section')
    parser.add_option('--boardmeetings',
                      action = 'store_true', dest = 'meetings',
                      help = 'list the board meetings section')
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
    if not parser.values.listRows:
        l.write("Listing counts only", stdout = True)
    else:
        l.write("Listing counts and document rows", stdout = True)
    if parser.values.cdrids:
        l.write("Listing rows with CDR-IDs", stdout = True)
    else:
        l.write("Listing document rows without CDR-IDs", stdout = True)
    if parser.values.summary:
        l.write("Listing Summary records", stdout = True)
    if parser.values.dis:
        l.write("Listing Drug Info records", stdout = True)
    if parser.values.audio:
        l.write("Listing Audio records", stdout = True)
    if parser.values.images:
        l.write("Listing Images records", stdout = True)
    if parser.values.glossary:
        l.write("Listing Glossary records", stdout = True)
    if parser.values.genetics:
        l.write("Listing Genetics Prof records", stdout = True)
    if parser.values.drug:
        l.write("Listing Drug records", stdout = True)
    if parser.values.debug:
        l.write("Listing debug information", stdout = True)
    if parser.values.bmembers:
        l.write("Listing Board Member records", stdout = True)
    if parser.values.meetings:
        l.write("Listing Board Meetings records", stdout = True)
    if parser.values.drug:
        l.write("Listing Terminology/Drug records", stdout = True)
    #if parser.values.fname:
    #    fname = parser.values.fname
    #    l.write("Comparing output to file: %s" % fname, stdout = True)
    if parser.values.rowmax:
        rowmax = parser.values.rowmax
        l.write("Limit number of records: %s" % rowmax, stdout = True)
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
       '*** Error: Program ICRDB Stats Report failed!')

    mailHeader   += "Content-type: text/html; charset=utf-8\n"
    mailBody      = "<b>Error running ICRDBStatsReport.py</b><br>"
    mailBody     += "Most likely %s<br>" % msg
    mailBody     += "See log file for details."

    # Add a Separator line + body
    # ---------------------------
    message = mailHeader + "\n" + mailBody

    server = smtplib.SMTP(SMTP_RELAY)
    server.sendmail(STR_FROM, '***REMOVED***', message.encode('utf-8'))
    server.quit()


# -------------------------------------------------------------
# Check if the values given are within the specified time frame
# -------------------------------------------------------------
def checkTimeFrame(dates, startDate=firstOfMonth, endDate=lastOfMonth):
    try:
        enDate = time.strptime(dates[0] or '0001-01-01', '%Y-%m-%d')
    except:
        enDate = time.strptime(dates[0] or '0001-01-01 12:00:00', 
                                                         '%Y-%m-%d %H:%M:%S')
    try:
        esDate = time.strptime(dates[1] or '0001-01-01', '%Y-%m-%d')
    except:
        esDate = time.strptime(dates[1] or '0001-01-01 12:00:00', 
                                                         '%Y-%m-%d %H:%M:%S')

    sTF = time.strptime(startDate, '%Y-%m-%d')
    eTF = time.strptime(endDate, '%Y-%m-%d')

    return (enDate > sTF and enDate < eTF, 
            esDate > sTF and esDate < eTF)



# -------------------------------------------------------------
# List the reformatted summaries
# -------------------------------------------------------------
def getDocuments(cursor, startDate=firstOfMonth, endDate=lastOfMonth, 
                         docType='', repType=''):
    # Debug message listing the document type and report type
    # -------------------------------------------------------
    l.write('   docType = %s, repType = %s' % (docType, repType), stdout=True)
    if debug:
        l.write('   dispRows = %s' % dispRows, stdout=True)

    #if dispRows or dispSummary or dispDis or dispGlossary or dispImages or dispAudio or dispBoardMembers or dispBoardMeetings:
    if docType == 'DrugInformationSummary':
        selection = """\
           d.id as "CDR-ID", t.value as "Title",
           d.first_pub as "Publishing Date", dlm.value AS "DLM" """
        orderBy = "ORDER BY d.first_pub, dlm.value"
    elif docType == 'Summary':
        if repType == 'new':
            selection = """\
           d.id AS "CDR-ID", t.value AS "Title", l.value AS "Language", 
           a.value AS "Audience", d.first_pub """
            orderBy = "ORDER BY d.first_pub"
        elif repType == 'revised':
            selection = """\
           d.id AS "CDR-ID", t.value AS "Title", l.value AS "Language", 
           a.value AS "Audience", dlm.value AS "Date LM" """
            orderBy = "ORDER BY dlm.value"
    elif docType == 'GlossaryTermName':
        selection = """\
           d.id AS "CDR-ID", gte.value AS "Glossary (EN)", 
           gts.value AS "Glossary (ES)", d.first_pub as "Publishing Date" """
        orderBy = "ORDER BY d.first_pub"
    elif docType == 'GlossaryTermConcept':
        selection = """\
           d.id AS "CDR-ID", gtce.value AS "Glossary (EN)", 
           gtcs.value AS "Glossary (ES)" """
        orderBy = "ORDER BY gtce.value"
    elif docType == 'Terminology':
        selection = """\
           t.doc_id, a.value, d.first_pub """
        orderBy = "ORDER BY d.first_pub"
    elif docType == 'Media':
        if repType == 'IMG':
            selection = """\
           d.id as "CDR-ID", t.value as "Title",
           d.first_pub as "Publishing Date", dlm.value AS "DLM" """
            orderBy = "ORDER BY d.first_pub, dlm.value"
        elif repType == 'MTG':
            selection = """\
           d.id as "CDR-ID", d.title as "Title",
           v.dt as "Creation Date" """
            orderBy = "ORDER BY d.first_pub, v.dt"
        elif repType == 'AUDIO':
            selection = """\
           d.id as "CDR-ID", t.value as "Title",
           d.first_pub as "Publishing Date" """
            orderBy = "ORDER BY d.first_pub"
    elif docType == 'Glossary':
        if repType == 'GeneticsNewGTN':
            selection = """\
           t.doc_id AS "CDR-ID", t.value AS "GlossaryName [EN]", 
           gtn.int_val AS "Concept ID", dlm.value AS "DLM", 
           s.value AS "StatusDate", d.first_pub AS "FirstPub" """
            orderBy = "ORDER BY d.first_pub"
        elif repType == 'GeneticsNewGTC':
            selection = """\
           t.doc_id AS "CDR-ID", t.value AS "GlossaryName [EN]", 
           gtn.int_val AS "Concept ID", dlm.value AS "DLM", 
           s.value AS "StatusDate", d.first_pub AS "FirstPub" """
            orderBy = "ORDER BY s.value"
        elif repType == 'GeneticsRev':
            selection = """\
           t.doc_id AS "CDR-ID", t.value AS "GlossaryName [EN]", 
           gtn.int_val AS "Concept ID", dlm.value AS "DLM", 
           d.first_pub AS "FirstPub" """
            orderBy = "ORDER BY d.first_pub"

        # GTNP is a count-only report
        # ---------------------------
        elif repType == 'GTNP':
            dada = 1
        else:
            return None
    elif docType == 'Person':
        selection = """\
           d.id AS "CDR-ID", d.title AS "Name", 
           d.active_status AS "Doc Status", 
           d.first_pub AS "PubDate", s.value AS "Status" """
        orderBy = "ORDER BY d.first_pub"
    elif docType == 'PDQBoardMemberInfo':
        selection = """\
           d.id AS "CDR-ID", d.title AS "Name", t.value AS "Term Date", 
           n.value AS "Board" """
        orderBy = "ORDER BY d.id, t.value"
    elif docType == 'Organization':
        selection = """\
           d.id AS "CDR-ID", o.value AS "Board Name", m.value AS "Mtg Date", 
           w.value AS "WebEx" """
        orderBy = "ORDER BY d.id"
    else:
        return None
    #else:
    #    if docType == 'Summary':
    #        if repType == 'new':
    #            selection = """\
    #           d.id AS "CDR-ID", t.value AS "Title", l.value AS "Language", 
    #           a.value AS "Audience", d.first_pub """
    #            orderBy = "ORDER BY d.first_pub"
    #        elif repType == 'revised':
    #            selection = """\
    #           d.id AS "CDR-ID", t.value AS "Title", l.value AS "Language", 
    #           a.value AS "Audience", dlm.value AS "Date LM" """
    #            orderBy = "ORDER BY dlm.value"
    #    else:
    #        selection = "count(*)"
    #        orderBy = ""


    # Select the individual queries
    # -----------------------------
    if docType == 'DrugInformationSummary':
        query = """\
        SELECT %s
          FROM document d
LEFT OUTER JOIN query_term_pub dlm
            ON dlm.doc_id = d.id
           AND dlm.path = '/DrugInformationSummary/DateLastModified'
          JOIN query_term t
            on d.id = t.doc_id
           AND t.path = '/DrugInformationSummary/Title'
          JOIN pub_proc_cg cg
            on d.id = cg.id
         WHERE d.active_status = 'A'
           AND ISNULL(first_pub, 0) BETWEEN '%s' 
                         AND dateadd(DAY, 1, '%s')
               OR
               ISNULL(dlm.value, 0) BETWEEN '%s' 
                         AND dateadd(DAY, 1, '%s')
               %s
    """ % (selection, startDate, endDate, startDate, endDate,
           orderBy)
    elif docType == 'Summary':
        if repType == 'new':
            query = """\
            SELECT %s
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
             WHERE d.active_status = 'A'
               AND ISNULL(first_pub, 0) BETWEEN '%s' 
                             AND dateadd(DAY, 1, '%s')
                   %s
""" % (selection, startDate, endDate, orderBy)
        elif repType == 'revised':
            query = """\
            SELECT %s
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
             WHERE d.active_status = 'A'
               AND ISNULL(dlm.value, 0) BETWEEN '%s' 
                             AND dateadd(DAY, 1, '%s')
                   %s
""" % (selection, startDate, endDate,
       orderBy)
    elif docType == 'GlossaryTermName':
        query = """\
        SELECT %s
          FROM document d
          JOIN query_term_pub gte
            ON d.id = gte.doc_id
           AND gte.path = '/GlossaryTermName/TermName/TermNameString'
    LEFT OUTER JOIN query_term_pub gts
            ON d.id = gts.doc_id
           AND gts.path = '/GlossaryTermName/TranslatedName/TermNameString'
          JOIN pub_proc_cg cg
            ON cg.id = d.id
         WHERE d.active_status = 'A'
           AND ISNULL(first_pub, 0) BETWEEN '%s' 
                         AND dateadd(DAY, 1, '%s')
               %s
""" % (selection, startDate, endDate, orderBy)
    elif docType == 'GlossaryTermConcept':
        query = """\
        SELECT %s
          FROM document d
          JOIN doc_type dt
            ON d.doc_type = dt.id
          JOIN query_term_pub gtce
            ON d.id = gtce.doc_id
           AND gtce.path = '/GlossaryTermConcept/TermDefinition' +
                           '/DateLastModified'
    LEFT OUTER JOIN query_term_pub gtcs
            ON d.id = gtcs.doc_id
           AND gtcs.path = '/GlossaryTermConcept/TranslatedTermDefinition' +
                           '/DateLastModified'
         WHERE dt.name = '%s'
           AND d.active_status = 'A'
           AND ISNULL(gtce.value, 0) BETWEEN '%s'
                         AND dateadd(DAY, 1, '%s')
            or ISNULL(gtcs.value, 0) BETWEEN '%s'
                         AND dateadd(DAY, 1, '%s')
               %s
""" % (selection, docType, startDate, endDate, startDate, endDate,
       orderBy)
    elif docType == 'Terminology':
        query = """\
        SELECT %s
          FROM query_term t
          JOIN all_docs d
            on d.id = t.doc_id
          JOIN query_term s
            ON s.doc_id = t.doc_id
           AND s.path = '/Term/SemanticType/@cdr:ref'
          JOIN query_term dr
            ON dr.doc_id = s.int_val
           AND dr.path = '/Term/PreferredName'
           AND dr.value = 'Drug/agent'
          JOIN query_term a
            on a.doc_id = d.id
           AND a.path = '/Term/PreferredName'
          JOIN pub_proc_cg cg
            ON cg.id = d.id
         WHERE t.path = '/Term/Definition/DefinitionText/@cdr:id'
           AND ISNULL(d.first_pub, 0) BETWEEN '%s'
                          AND dateadd(DAY, 1, '%s')
               %s
        """ % (selection, startDate, endDate,
               orderBy)
    elif docType == 'Media':
        if repType == 'IMG':
            query = """\
        SELECT %s
          FROM document d
          JOIN query_term e
            ON d.id = e.doc_id
           and e.path = '/Media/PhysicalMedia' +
                        '/ImageData/ImageEncoding'
LEFT OUTER JOIN query_term dlm
            ON d.id = dlm.doc_id
           AND dlm.path = '/Media/DateLastModified'
           JOIN query_term t
             ON t.doc_id = d.id
            AND t.path = '/Media/MediaTitle'
           JOIN pub_proc_cg cg
             ON cg.id = d.id
         WHERE d.active_status = 'A'
           AND (ISNULL(first_pub, 0) BETWEEN '%s'
                          AND dateadd(DAY, 1, '%s')
                OR
                ISNULL(dlm.value, 0) BETWEEN '%s'
                          AND dateadd(DAY, 1, '%s')
               )
               %s
""" % (selection, startDate, endDate, startDate, endDate,
       orderBy)
        elif repType == 'MTG':
            query = """\
        SELECT %s
          FROM document d
          JOIN doc_type dt
            ON d.doc_type = dt.id
          JOIN query_term e
            ON d.id = e.doc_id
           and e.path = '/Media/MediaContent/Categories/Category'
          JOIN doc_version v
            ON d.id = v.id
           AND num = 1
         WHERE dt.name = 'Media'
           AND e.value = 'Meeting Recording'
           AND v.dt between '%s' 
                          AND dateadd(DAY, 1, '%s')
               %s
""" % (selection, startDate, endDate,
       orderBy)
        elif repType == 'AUDIO':
            query = """\
        SELECT %s
          FROM document d
          JOIN doc_type dt
            ON d.doc_type = dt.id
          JOIN query_term e
            ON d.id = e.doc_id
           and e.path = '/Media/MediaContent/Categories/Category'
          JOIN query_term t
            ON t.doc_id = d.id
           AND t.path = '/Media/MediaTitle'
          JOIN pub_proc_cg cg
            ON d.id = cg.id
         WHERE e.value = 'pronunciation'
           AND d.active_status = 'A'
           AND first_pub between '%s' and dateadd(DAY, 1, '%s') 
               %s
""" % (selection, startDate, endDate,
       orderBy)

    elif docType == 'Glossary':
        if repType == 'GeneticsNewGTN':
            query = """\
        SELECT %s
          FROM query_term_pub gtn
          JOIN query_term_pub t
            ON t.doc_id = gtn.doc_id
           AND t.path = '/GlossaryTermName/TermName/TermNameString'
          JOIN query_term_pub gtc
            ON gtc.doc_id = gtn.int_val
           AND gtn.path = '/GlossaryTermName/GlossaryTermConcept/@cdr:ref'
LEFT OUTER JOIN query_term_pub dlm
            ON dlm.doc_id = gtc.doc_id
           AND dlm.path = '/GlossaryTermConcept/TermDefinition/DateLastModified'
           AND left(gtc.node_loc, 4) = left(dlm.node_loc, 4)
LEFT OUTER JOIN query_term_pub s
            ON s.doc_id = gtc.doc_id
           AND s.path = '/GlossaryTermConcept/TermDefinition/StatusDate'
           AND left(gtc.node_loc, 4) = left(s.node_loc, 4)
          JOIN query_term_pub aud
            ON aud.doc_id = gtc.doc_id
           AND aud.path = '/GlossaryTermConcept/TermDefinition/Audience'
           AND left(gtc.node_loc, 4) = left(aud.node_loc, 4)
          JOIN document d
            ON d.id = gtn.doc_id
          JOIN doc_type dt
            ON d.doc_type = dt.id
           AND dt.name = 'GlossaryTermName'
         WHERE gtc.path = '/GlossaryTermConcept/TermDefinition/Dictionary'
           AND gtc.value = 'Genetics'
           AND d.active_status = 'A'
           AND aud.value = 'Health professional'
           AND ISNULL(d.first_pub, 0) BETWEEN '%s' 
                         AND dateadd(DAY, 1, '%s')
               %s
""" % (selection, startDate, endDate,
       orderBy)
        elif repType == 'GeneticsNewGTC':
            # We cannot easily identify a new genetics dictionary term
            # from the CDR.  If the concept has been created for a new
            # GTN we can look at the first_pub date of the GTN.  
            # However, if the GTN already exists and we're merely adding
            # a concept for the genetics dictionary we're looking here
            # at the definition status date.   We only pick it up if the 
            # DateLastModified is NULL because this date - supposed to 
            # only be entered when a term definition is updated but not
            # when it's created - should not exist.  If it does we're 
            # counting the defintion as an update.
            # ----------------------------------------------------------
            query = """\
        SELECT %s
          FROM query_term_pub gtn
          JOIN query_term_pub t
            ON t.doc_id = gtn.doc_id
           AND t.path = '/GlossaryTermName/TermName/TermNameString'
          JOIN query_term_pub gtc
            ON gtc.doc_id = gtn.int_val
           AND gtn.path = '/GlossaryTermName/GlossaryTermConcept/@cdr:ref'
LEFT OUTER JOIN query_term_pub dlm
            ON dlm.doc_id = gtc.doc_id
           AND dlm.path = '/GlossaryTermConcept/TermDefinition/DateLastModified'
           AND left(gtc.node_loc, 4) = left(dlm.node_loc, 4)
LEFT OUTER JOIN query_term_pub s
            ON s.doc_id = gtc.doc_id
           AND s.path = '/GlossaryTermConcept/TermDefinition/StatusDate'
           AND left(gtc.node_loc, 4) = left(s.node_loc, 4)
          JOIN query_term_pub aud
            ON aud.doc_id = gtc.doc_id
           AND aud.path = '/GlossaryTermConcept/TermDefinition/Audience'
           AND left(gtc.node_loc, 4) = left(aud.node_loc, 4)
          JOIN document d
            ON d.id = gtn.doc_id
          JOIN doc_type dt
            ON d.doc_type = dt.id
           AND dt.name = 'GlossaryTermName'
         WHERE gtc.path = '/GlossaryTermConcept/TermDefinition/Dictionary'
           AND gtc.value = 'Genetics'
           AND d.active_status = 'A'
           AND aud.value = 'Health professional'
           AND dlm.value IS NULL
           AND ISNULL(s.value, 0) BETWEEN '%s' 
                         AND dateadd(DAY, 1, '%s')
               %s
""" % (selection, startDate, endDate,
       orderBy)
        elif repType == 'GeneticsRev':
            query = """\
        SELECT %s
          FROM query_term_pub gtn
          JOIN query_term_pub t
            ON t.doc_id = gtn.doc_id
           AND t.path = '/GlossaryTermName/TermName/TermNameString'
          JOIN query_term_pub gtc
            ON gtc.doc_id = gtn.int_val
           AND gtn.path = '/GlossaryTermName/GlossaryTermConcept/@cdr:ref'
          JOIN query_term_pub dlm
            ON dlm.doc_id = gtc.doc_id
           AND dlm.path = '/GlossaryTermConcept/TermDefinition/DateLastModified'
           AND left(gtc.node_loc, 4) = left(dlm.node_loc, 4)
          JOIN query_term_pub aud
            ON aud.doc_id = gtc.doc_id
           AND aud.path = '/GlossaryTermConcept/TermDefinition/Audience'
           AND left(gtc.node_loc, 4) = left(aud.node_loc, 4)
          JOIN document d
            ON d.id = gtn.doc_id
          JOIN doc_type dt
            ON d.doc_type = dt.id
           AND dt.name = 'GlossaryTermName'
         WHERE gtc.path = '/GlossaryTermConcept/TermDefinition/Dictionary'
           AND gtc.value = 'Genetics'
           AND d.active_status = 'A'
           AND aud.value = 'Health professional'
           AND ISNULL(dlm.value, 0) BETWEEN '%s' 
                         AND dateadd(DAY, 1, '%s')
               %s
""" % (selection, startDate, endDate,
       orderBy)
        else:
            return None
    elif docType == 'Person':
        query = """\
        SELECT %s
          FROM document d
          JOIN doc_type dt
            ON dt.id = d.doc_type
          JOIN query_term_pub i
            ON i.doc_id = d.id
           AND i.path ='/Person/ProfessionalInformation' +
                       '/GeneticsProfessionalDetails'    +
                       '/AdministrativeInformation/Directory/Include'
          JOIN query_term_pub s
            ON s.doc_id = d.id
           AND s.path ='/Person/Status/CurrentStatus'
         WHERE dt.name = 'Person'
           AND i.value ='Include'
           AND s.value = 'Active'
           AND ISNULL(d.first_pub, 0) BETWEEN '%s' 
                         AND dateadd(DAY, 1, '%s')
               %s
""" % (selection, startDate, endDate,
       orderBy)
    elif docType == 'PDQBoardMemberInfo':
        query = """\
        SELECT %s
          FROM document d
          JOIN doc_type dt
            ON dt.id = d.doc_type
          JOIN query_term a
            ON a.doc_id = d.id
           AND a.path = '/PDQBoardMemberInfo/BoardMembershipDetails' +
                        '/ResponseToInvitation'
          JOIN query_term t
            ON t.doc_id = a.doc_id
           AND t.path = '/PDQBoardMemberInfo/BoardMembershipDetails' +
                        '/TermStartDate'
           AND left(t.node_loc, 4) = left(a.node_loc, 4)
          JOIN query_term n
            ON n.doc_id = a.doc_id
           AND n.path = '/PDQBoardMemberInfo/BoardMembershipDetails' +
                        '/BoardName'
           AND left(n.node_loc, 4) = left(a.node_loc, 4)
         WHERE dt.name = 'PDQBoardMemberInfo'
           AND d.active_status = 'A'
           AND a.value = 'Accepted'
           AND ISNULL(t.value, 0) BETWEEN '%s' 
                          AND dateadd(DAY, 1, '%s')
               %s
""" % (selection, startDate, endDate,
       orderBy)
    elif docType == 'Organization':
        query = """\
        SELECT %s
          FROM document d
          JOIN doc_type dt
            on dt.id = d.doc_type
          JOIN query_term o
            ON o.doc_id = d.id
           AND o.path = '/Organization/OrganizationNameInformation' +
                        '/OfficialName/Name'
          JOIN query_term m
            ON m.doc_id = o.doc_id
           AND m.path = '/Organization/PDQBoardInformation' +
                        '/BoardMeetings/BoardMeeting/MeetingDate'
         left outer JOIN query_term w
            ON w.doc_id = m.doc_id
           AND w.path = '/Organization/PDQBoardInformation' +
                        '/BoardMeetings/BoardMeeting/MeetingDate/@WebEx'
           AND left(w.node_loc, 12) = left(m.node_loc, 12)
         WHERE dt.name = 'Organization'
           AND d.active_status = 'A'
           AND ISNULL(m.value, 0) BETWEEN '%s' 
                          AND dateadd(DAY, 1, '%s')
               %s
""" % (selection, startDate, endDate,
       orderBy)
    else:
        return None
    

    if debug:
        l.write('********************************************************',
                                                              stdout=True)
        l.write('[SQL query submitted:]', stdout=True)
        l.write(query, stdout=True)

    cursor.execute(query, timeout=300)
    rows = cursor.fetchall()

    if debug:
        l.write('----------------', stdout=True)
        l.write('Rows: %s' % len(rows), stdout=True)
        l.write('********************************************************',
                                                              stdout=True)

    if not rows or rows[0][0] == 0:
        return None

    return rows


# ---------------------------------------------------------------------
# List the reformatted summaries
# ---------------------------------------------------------------------
def getSummariesReformatted(cursor, startDate=firstOfMonth, 
                                    endDate=lastOfMonth):

    #if dispRows or dispSummary:
    selection = """
   d.id as "CDR-ID", d.title as "Title",
   a.value AS "Audience",
   d.val_date as "Creation Date"
"""
    #else:
    #    selection = "count(*)"

    query = """\
SELECT %s
  FROM document d
  JOIN doc_type dt
    ON d.doc_type = dt.id
  JOIN query_term w
    ON d.id = w.doc_id
   AND w.path = '/Summary/WillReplace'
  JOIN query_term a
    ON d.id = a.doc_id
   AND a.path = '/Summary/SummaryMetaData/SummaryAudience'
 WHERE dt.name = 'Summary'
   AND d.active_status = 'I'
   AND d.val_date between '%s' 
                  AND dateadd(DAY, 1, '%s')
 -- ORDER BY a.value, d.val_date
    """ % (selection, startDate, endDate)

    cursor.execute(query)
    rows = cursor.fetchall()

    if not rows or rows[0][0] == 0:
        return None

    return rows


# --------------------------------------------------------
# Checking if any of the documents is checked out by users
# --------------------------------------------------------
def formatFullOutput(records, recordCount, heading, maxrows, 
                     displayCdrid, docType='', repType=''):
    if not records:
        html = "<p>No %s found during this time<p>\n" % heading
        return html

    # Sorting by CDR-id
    # -----------------
    records.sort()

    # For the full report we print by default the CDR-ID and the
    # document title but some other document types might need to
    # display additional columns
    # -----------------------------------------------------------
    # Header Row
    # ----------
    html  = """
  <br/>
  <h2>%d %s</h2>
  <table class='docstable'>
  <tr>
""" % (recordCount, heading)
    if dispCdrid:
        html += """\
   <th><B>CDR-ID</B></th>
"""
    html += """\
   <th><B>Title</B></th>
"""

    if docType == 'Summary':
        html += """\
   <th><B>Language</B></th>
   <th><B>Audience</B></th>
""" 
    elif docType == 'GlossaryTermName':
        html += """\
   <th><B>Title (Spanish)</B></th>
""" 
    elif docType == 'PDQBoardMemberInfo':
        html += """\
   <th><B>Board</B></th>
""" 
    elif docType == 'Organization':
        html += """\
   <th><B>Date</B></th>
   <th><B>WebEx?</B></th>
""" 
    elif docType == 'Media' and repType =='IMG':
        html += """\
   <th><B>First Pub</B></th>
   <th><B>Date Modified</B></th>
""" 
    elif docType == 'DrugInformationSummary':
        html += """\
   <th><B>First Pub</B></th>
   <th><B>Date Modified</B></th>
""" 
    html += """\
  </tr>
"""

    # if we're not listing the CDR-ID we want to display the 
    # rows sorted in alpha order
    # ------------------------------------------------------
    if not dispCdrid:
        records.sort(key=lambda x: x[1])

    # Data Row
    # --------
    rowCount = 0

    for row in records:
        rowCount += 1
        if dispCdrid:
            html += """\
  <tr>
   <td VALIGN='top'>CDR%010d</td>
""" % (row[0])

        html += """\
   <td VALIGN='top'>%s</td>
""" % (cdrcgi.unicodeToLatin1(row[1]))

        if docType == 'Summary':
            html += """\
   <td VALIGN='top'>%s</td>
   <td VALIGN='top'>%s</td>
""" % (row[2], row[3])

        elif docType == 'GlossaryTermName':
            html += """\
   <td VALIGN='top'>%s</td>
""" % (row[2])

        elif docType == 'PDQBoardMemberInfo':
            html += """\
   <td VALIGN='top'>%s</td>
""" % (row[3])
        elif docType == 'Organization':
            html += """\
   <td VALIGN='top'>%s</td>
   <td VALIGN='top'>%s</td>
""" % (row[2], row[3] or '')
        elif docType == 'Media' and repType == 'IMG':
            html += """\
   <td VALIGN='top'>%s</td>
   <td VALIGN='top'>%s</td>
""" % (row[2], row[3] or '')
        elif docType == 'DrugInformationSummary':
            html += """\
   <td VALIGN='top'>%s</td>
   <td VALIGN='top'>%s</td>
""" % (row[2], row[3] or '')

        html += """\
  </tr>
"""

        # Terminate the list of documents if a limit has been
        # specified
        # ----------------------------------------------------
        if rowCount + 1 > maxrows and maxrows < len(records):
            html += u"""\
  <tr>
   <td colspan="4">&nbsp;</td>
  </tr>
  <tr>
   <td valign='top' colspan="4">
   <b>[Output limited to %d records]</b></td>
  </tr>
""" % maxrows

            break

    html += u"""\
 </table>
"""
    return html


# --------------------------------------------------------
# Creating a single HTML Table row
# --------------------------------------------------------
def getCountsOnlyRow(label, number=''):
    html = u"""\
   <tr>
    <td>%s</td>
    <td>%s</td>
   </tr>
""" % (label, number)
    
    return html


# --------------------------------------------------------
# Creating email message body/report to be submitted
# --------------------------------------------------------
def getMessageHeaderFooter(startDate=firstOfMonth, endDate=lastOfMonth, 
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
   th      { background-color: #f0f0f0; }
   td      { padding: 1px 10px; }
   *.countstable  {  }
   *.docstable    {  }
  </style>
 </head>
 <body>
  <h2>%s</h2>
  <h3>Date: %s</h3>

  <table class='countstable'>
   <tr>
    <th>Document</th>
    <th>From %s <br>to %s</th>
   </tr>
""" % (title, title, date, startDate, endDate)
    else:
        html = u"""\
 </body>
</html>
"""

    return html



# --------------------------------------------------------
# Creating email message body/report to be submitted
# --------------------------------------------------------
def createMessageBody(title='Test Title', startDate=firstOfMonth, 
                                          endDate=lastOfMonth, maxRows=0):
    sumBoardMember = u''
    sumBoardMeeting = u''
    sumDis = u''
    sumDrugTerms = u''
    sumGeneticsProf = u''
    sumGlossaries = u''
    sumImage = u''
    sumSummariesNew = u''
    sumSummariesRev = u''
    sumSummariesReform = u''

    # Dictionary to be used for the misc. text labels by doc type
    # -----------------------------------------------------------
    textLabels = { 'audio':     ['Audio', 
                                 'Dictionary w/ pronunciation (Audio)'],
                   'gtnen':     [' - New (EN)', 
                                 'New Dictionary Files (EN and ES)']  ,
                   'gtnes':     [' - New (ES)', 'x']  ,
                   'gtcall':    ['Dictionary - Revised', 'x']  ,
                   'gtcen':     [' - Revised (EN)', 'x']  ,
                   'gtces':     [' - Revised (ES)', 'x']  ,
                   'gennewgtn': ['Genetics Dictionary - New (GTN)', 
                                 'New Genetics Dictionary Files (first_pub)']  ,
                   'gennewgtc': ['Genetics Dictionary - New (GTC)', 
                                 'New Genetics Dictionary Files (status)']  ,
                   'genrev':    ['Genetics Dictionary - Revised', 
                                 'Revised Genetics Dictionary Files']  ,
                   'genprof':   ['Genetics Professionals - New', 
                                 'New Genetics Professionals']  ,
                   'drug':      ['NCI Drug Dictionary', 
                                 'NCI Drug Terms']                  ,
                   'image':     ['PDQ Images', 
                                 'PDQ Image Files'],
                   'imgnew':    [' - New', ''],
                   'imgrev':    [' - Revised', ''],
                   'sumnew':    ['Total Summaries - New', 
                                 'Total New Summaries']  ,
                   'sumrev':    ['Total Summaries - Revised ', 
                                 'Total Revised Summaries'],
                   'hpennew':   [' - HP Summaries (EN)', ''],
                   'hpesnew':   [' - HP Summaries (ES)', ''],
                   'patennew':  [' - Pat. Summaries (EN)', ''],
                   'patesnew':  [' - Pat. Summaries (ES)', ''],
                   'hpenrev':   [' - HP Summaries (EN)', ''],
                   'hpesrev':   [' - HP Summaries (ES)', ''],
                   'patenrev':  [' - Pat. Summaries (EN)', ''],
                   'patesrev':  [' - Pat. Summaries (ES)', ''],
                   'dis':       ['Drug Information Summaries', 
                                 'Drug Information Summaries']  ,
                   'disnew':    [' - New', '']  ,
                   'disrev':    [' - Revised', '']  ,
                   'sumref':    ['Reformatted Summaries', 
                                 'Reformatted Summaries'],
                   'mtg':       [' - Onsite Meetings', 
                                 'PDQ Board Meetings'],
                   'mtgwebx':   [' - WebEx Meetings', ''],
                   'board':     ['PDQ Board Members',
                                 'New PDQ Board Members'],
                   'brded':     [' - Editorial', ''],
                   'brdad':     [' - Advisory', '']
               }

    conn = cdrdb.connect()
    cursor = conn.cursor()

    l.write("", stdout = True)
    l.write(title, stdout = True)

    # New Glossary Terms
    # ------------------
    if dispGlossary or dispAll:
        gtn = getDocuments(cursor, startDate, endDate, 
                                              docType='GlossaryTermName')

        countGtn = {'gtnen':0, 'gtnes':0}
        if gtn:
            for i in gtn:
                if type(i[1]) == type(u''):  countGtn['gtnen'] += 1
                if type(i[2]) == type(u''):  countGtn['gtnes'] += 1
        
        gtc = getDocuments(cursor, startDate, endDate, 
                                              docType='GlossaryTermConcept')

        countGtcAll = 0
        countGtc = {'gtcen':0, 'gtces':0}
        if gtc:
            countGtcAll = len(gtc)
            for i in gtc:
                isInTimeFrame = checkTimeFrame(i[1:], startDate, endDate)

                if (type(i[1]) == type(u'') and isInTimeFrame[0]):
                    countGtc['gtcen'] += 1
                if (type(i[2]) == type(u'') and isInTimeFrame[1]):
                    countGtc['gtces'] += 1
        
    if dispGlossary or dispAll:
        # geneticsNewGtn = getDocuments(cursor, startDate, endDate, 
        #                          docType='Glossary', repType='GeneticsNewGTN')
        # countGeneticsNewGtn = 0
        # if geneticsNewGtn:
        #    countGeneticsNewGtn = len(geneticsNewGtn)

        geneticsNewGtc = getDocuments(cursor, startDate, endDate, 
                                   docType='Glossary', repType='GeneticsNewGTC')
        countGeneticsNewGtc = 0
        if geneticsNewGtc:
            countGeneticsNewGtc = len(geneticsNewGtc)

        geneticsRev = getDocuments(cursor, startDate, endDate, 
                                   docType='Glossary', repType='GeneticsRev')
        countGeneticsRev = 0
        if geneticsRev:
            countGeneticsRev = len(geneticsRev)

    # New Drug Terms
    # ---------------
    if dispDrug or dispAll:
        drugTerms = getDocuments(cursor, startDate, endDate, 
                                                      docType='Terminology')
        countDrugTerms = 0
        if drugTerms:
            countDrugTerms = len(drugTerms)

    # New Images Files
    # ---------------
    if dispImages or dispAll:
        images = getDocuments(cursor, startDate, endDate, 
                              docType='Media', repType='IMG')
        countImageAll = 0
        countImage = {'imgnew':0, 'imgrev':0}
        if images:
            countImageAll = len(images)
            for i in images:
                isInTimeFrame = checkTimeFrame(i[2:], startDate, endDate)

                if (type(i[2]) in (type(u''), type('')) 
                    and isInTimeFrame[0]):
                    countImage['imgnew'] += 1
                if (type(i[3]) in (type(u''), type('')) 
                    and isInTimeFrame[1]):
                    countImage['imgrev'] += 1

    # New Audio Files
    # ---------------
    if dispAudio or dispGlossary or dispAll:
        audio = getDocuments(cursor, startDate, endDate, 
                             docType='Media', repType='AUDIO')
        countAudio = 0
        if audio:
            countAudio = len(audio)

    # Board Meetings Files
    # ----------------------------
    if dispBoardMeetings or dispAll:
        boardMeeting = getDocuments(cursor, startDate, endDate, 
                                     docType='Organization')
        countBoardMeetingAll = 0
        countBoardMeeting = {'mtg':0, 'mtgwebx':0}
        if boardMeeting:
            countBoardMeetingAll = len(boardMeeting)
            for i in boardMeeting:
                if i[3] == 'Yes': countBoardMeeting['mtgwebx'] += 1
                else:             countBoardMeeting['mtg'] += 1

    # New Summaries Files
    # -------------------------------
    if dispSummary or dispAll:
        summariesNew = getDocuments(cursor, startDate, endDate, 
                                    docType='Summary', repType='new')
        countSummariesNewAll = 0
        countSummariesNew = {'hpennew':0, 'hpesnew':0, 
                             'patennew':0, 'patesnew':0}
        if summariesNew:
            countSummariesNewAll = len(summariesNew)
            for i in summariesNew:
                if i[2] == 'English' and i[3] == 'Health professionals':
                    countSummariesNew['hpennew'] += 1
                elif i[2] == 'English' and i[3] == 'Patients': 
                    countSummariesNew['patennew'] += 1
                elif i[2] == 'Spanish' and i[3] == 'Health professionals': 
                    countSummariesNew['hpesnew'] += 1
                elif i[2] == 'Spanish' and i[3] == 'Patients': 
                    countSummariesNew['patesnew'] += 1

        # Revised Summaries Files
        # -------------------------------
        summariesRevised = getDocuments(cursor, startDate, endDate, 
                                        docType='Summary', repType='revised')
        countSummariesRevAll = 0
        countSummariesRev = {'hpenrev':0, 'hpesrev':0, 
                             'patenrev':0, 'patesrev':0}
        if summariesRevised:
            countSummariesRevAll = len(summariesRevised)
            for i in summariesRevised:
                if i[2] == 'English' and i[3] == 'Health professionals':
                    countSummariesRev['hpenrev'] += 1
                elif i[2] == 'English' and i[3] == 'Patients': 
                    countSummariesRev['patenrev'] += 1
                elif i[2] == 'Spanish' and i[3] == 'Health professionals': 
                    countSummariesRev['hpesrev'] += 1
                elif i[2] == 'Spanish' and i[3] == 'Patients': 
                    countSummariesRev['patesrev'] += 1

    # New DIS Files
    # -------------------------------
    if dispDis or dispAll:
        dis = getDocuments(cursor, startDate, endDate, 
                                         docType='DrugInformationSummary')
        countDisAll = 0
        countDis = {'disnew':0, 'disrev':0}
        if dis:
            countDisAll = len(dis)
            for i in dis:
                isInTimeFrame = checkTimeFrame(i[2:], startDate, endDate)

                if (type(i[2]) in (type(u''), type('')) 
                    and isInTimeFrame[0]):
                    countDis['disnew'] += 1
                if (type(i[3]) in (type(u''), type('')) 
                    and isInTimeFrame[1]):
                    countDis['disrev'] += 1

    # New Genetics Prof Files
    # -------------------------------
    if dispGenetics or dispAll:
        genProf = getDocuments(cursor, startDate, endDate, 
                                         docType='Person', repType="genetics")
        countGenProf = 0
        if genProf:
            countGenProf = len(genProf)

    # New Board Members Files
    # -------------------------------
    if dispBoardMembers or dispAll:
        boardMembers = getDocuments(cursor, startDate, endDate, 
                                         docType='PDQBoardMemberInfo')
        countBoardMemberAll = 0
        countBoardMember = {'brded':0, 'brdad':0}
        if boardMembers:
            countBoardMemberAll = len(boardMembers)
            for i in boardMembers:
                if i[3].find('Advisory') >= 0:
                    countBoardMember['brdad'] += 1
                else:
                    countBoardMember['brded'] += 1

    # New Reformatted Summaries Files
    # -------------------------------
    summariesReformatted = getSummariesReformatted(cursor, startDate, endDate)
    if summariesReformatted:
        if len(summariesReformatted[0]) == 1:
            countSummariesReform = summariesReformatted[0][0]
        else:
            countSummariesReform = len(summariesReformatted)
    else:
        countSummariesReform = 0

    # Prepare the table rows to be displayed as part of the executive
    # summary report displaying the counts
    # --------------------------------------------------------------
    if dispAll or dispSummary:
        sumSummariesNew = getCountsOnlyRow(textLabels['sumnew'][0], 
                                                countSummariesNewAll)
        mySortSumNew = countSummariesNew.keys()
        mySortSumNew.sort()
        # for sumRow in countSummariesNew.keys():
        for sumRow in mySortSumNew:
            sumSummariesNew += getCountsOnlyRow(textLabels[sumRow][0],
                                                countSummariesNew[sumRow])

        sumSummariesRev = getCountsOnlyRow(textLabels['sumrev'][0], 
                                                countSummariesRevAll)
        mySortSumRev = countSummariesRev.keys()
        mySortSumRev.sort()
        # for sumRow in countSummariesRev.keys():
        for sumRow in mySortSumRev:
            sumSummariesRev += getCountsOnlyRow(textLabels[sumRow][0],
                                                countSummariesRev[sumRow])

        # The reformatted Summaries will be temporarily suppressed
        # sumSummariesReform = getCountsOnlyRow(textLabels['sumref'][0], 
        #                                                   countSummariesReform)
    if dispAll or dispDis:
        #sumDis          = getCountsOnlyRow(textLabels['dis'][0], countDisAll)
        sumDis += getCountsOnlyRow(textLabels['dis'][0])
        mySortDis = countDis.keys()
        mySortDis.sort()
        for disRow in mySortDis:
            sumDis += getCountsOnlyRow(textLabels[disRow][0], 
                                                          countDis[disRow])

    if dispAll or dispGlossary:
        sumGlossaries += getCountsOnlyRow('Dictionary - New')
        mySortGtnNew = countGtn.keys()
        mySortGtnNew.sort()
        #for glossRow in countGtn.keys():
        for glossRow in mySortGtnNew:
            sumGlossaries += getCountsOnlyRow(textLabels[glossRow][0], 
                                                          countGtn[glossRow])
        #sumGlossaries += getCountsOnlyRow(textLabels['gtcall'][0], 
        #                                                  countGtcAll)
        sumGlossaries += getCountsOnlyRow('Dictionary - Revised')
        mySortGtnRev = countGtc.keys()
        mySortGtnRev.sort()
        #for glossRow in countGtc.keys():
        for glossRow in mySortGtnRev:
            sumGlossaries += getCountsOnlyRow(textLabels[glossRow][0], 
                                                          countGtc[glossRow])
        sumGlossaries  += getCountsOnlyRow(textLabels['audio'][0], countAudio)
        sumGlossaries  += getCountsOnlyRow('&nbsp;','&nbsp;')
        #sumGlossaries  += getCountsOnlyRow(textLabels['gennewgtn'][0],
        #                                                  countGeneticsNewGtn)
        sumGlossaries  += getCountsOnlyRow(textLabels['gennewgtc'][0],
                                                          countGeneticsNewGtc)
        sumGlossaries  += getCountsOnlyRow(textLabels['genrev'][0],
                                                          countGeneticsRev)

    if dispAudio:
        sumGlossaries  += getCountsOnlyRow(textLabels['audio'][0], countAudio)

    if dispAll or dispGenetics:
        sumGeneticsProf = getCountsOnlyRow(textLabels['genprof'][0],
                                                                countGenProf)
    if dispAll or dispDrug:
        sumDrugTerms    = getCountsOnlyRow(textLabels['drug'][0], 
                                                                countDrugTerms)
    if dispAll or dispImages:
        sumImage     = getCountsOnlyRow(textLabels['image'][0])
        #sumImage     += getCountsOnlyRow(textLabels['image'][0], countImageAll)
        mySortImage = countImage.keys()
        mySortImage.sort()
        for imageRow in countImage.keys():
            sumImage += getCountsOnlyRow(textLabels[imageRow][0], 
                                                          countImage[imageRow])
    if dispAll or dispBoardMembers:
        #sumBoardMember = getCountsOnlyRow(textLabels['board'][0], 
        #                                                    countBoardMemberAll)
        sumBoardMember = getCountsOnlyRow(textLabels['board'][0])
        mySortBoard = countBoardMember.keys()
        mySortBoard.sort()
        mySortBoard.reverse()
        for board in mySortBoard:
            sumBoardMember += getCountsOnlyRow(textLabels[board][0], 
                                                       countBoardMember[board])
    if dispAll or dispBoardMeetings:
        sumBoardMeeting = getCountsOnlyRow('PDQ Board Meetings')
        sumBoardMeeting += getCountsOnlyRow(textLabels['mtg'][0], 
                                           countBoardMeeting['mtg'])
        sumBoardMeeting += getCountsOnlyRow(textLabels['mtgwebx'][0], 
                                           countBoardMeeting['mtgwebx'])

    # Put together the email message body
    # -----------------------------------
    mailBody = getMessageHeaderFooter(startDate, endDate, title=title, 
                                      date=time.strftime("%m/%d/%Y", now))
    blankRow = getCountsOnlyRow('&nbsp;','&nbsp;')

    if sumSummariesNew:
        mailBody += sumSummariesNew + blankRow
    if sumSummariesRev:
        mailBody += sumSummariesRev + blankRow
    # if sumSummariesReform:
    #    mailBody += sumSummariesReform
    if sumGlossaries:
        mailBody += sumGlossaries + blankRow
    if sumGeneticsProf:
        mailBody += sumGeneticsProf + blankRow
    if sumDrugTerms:
        mailBody += sumDrugTerms + blankRow
    if sumDis:
        mailBody += sumDis + blankRow
    if sumBoardMember:
        mailBody += sumBoardMember + blankRow
    if sumBoardMeeting:
        mailBody += sumBoardMeeting + blankRow
    if sumImage:
        mailBody += sumImage + blankRow
    mailBody += u"""\
  </table>
"""

    # Prepare the tables to be attached to the report if the document
    # rows should be displayed
    # -------------------------------------------------------------------
    if dispRows:
        fullAudio = u''
        fullDrugTerms = u''
        fullImages = u''
        fullBoardMember = u''
        fullBoardMeeting = u''
        fullSummariesNew = u''
        fullSummariesRev = u''
        fullSummariesReform = u''
        fullDis = u''
        fullGlossary = u''
        fullGlossaryGen = u''
        fullGeneticsProf = u''

        if dispAll or dispSummary:
            fullSummariesNew  = formatFullOutput(summariesNew, 
                                                 countSummariesNewAll, 
                                                 textLabels['sumnew'][1], 
                                                 maxRows, dispCdrid,
                                                 docType='Summary')
            fullSummariesRev  = formatFullOutput(summariesRevised, 
                                                 countSummariesRevAll, 
                                                 textLabels['sumrev'][1], 
                                                 maxRows, dispCdrid,
                                                 docType='Summary')
            #fullSummariesReform = formatFullOutput(summariesReformatted, 
            #                                     countSummariesReform, 
            #                                     textLabels['sumref'][1], 
            #                                     maxRows)
        if dispAll or dispDis:
            fullDis           = formatFullOutput(dis, countDisAll, 
                                                 textLabels['dis'][1], 
                                                 maxRows, dispCdrid,
                                                docType='DrugInformationSummary')
        if dispAll or dispGlossary:
            fullGlossary     = formatFullOutput(gtn, countGtn['gtnen'], 
                                                 textLabels['gtnen'][1], 
                                                 maxRows, dispCdrid,
                                                 docType='GlossaryTermName')
            fullAudio         = formatFullOutput(audio, countAudio, 
                                                 textLabels['audio'][1], 
                                                 maxRows, dispCdrid)
            #fullGlossaryGen  = formatFullOutput(geneticsNewGtn, 
            #                                     countGeneticsNewGtn, 
            #                                     textLabels['gennewgtn'][1], 
            #                                     maxRows)
            fullGlossaryGen += formatFullOutput(geneticsNewGtc, 
                                                 countGeneticsNewGtc, 
                                                 textLabels['gennewgtc'][1], 
                                                 maxRows, dispCdrid)
            fullGlossaryGen += formatFullOutput(geneticsRev, 
                                                 countGeneticsRev, 
                                                 textLabels['genrev'][1], 
                                                 maxRows, dispCdrid)
        if dispAudio:
            fullAudio         = formatFullOutput(audio, countAudio, 
                                                 textLabels['audio'][1], 
                                                 maxRows, dispCdrid)
        if dispAll or dispGenetics:
            fullGeneticsProf    = formatFullOutput(genProf, countGenProf, 
                                                 textLabels['genprof'][1], 
                                                 maxRows, dispCdrid)
        if dispAll or dispDrug:
            fullDrugTerms     = formatFullOutput(drugTerms, countDrugTerms, 
                                                 textLabels['drug'][1], 
                                                 maxRows, dispCdrid)
        if dispAll or dispImages:
            fullImages        = formatFullOutput(images, countImageAll, 
                                                 textLabels['image'][1], 
                                                 maxRows, dispCdrid,
                                                 docType='Media', repType='IMG')
        # if dispAll or dispAudio:
        #     fullAudio         = formatFullOutput(audio, countAudio, 
        #                                          textLabels['audio'][1], 
        #                                          maxRows)
        if dispAll or dispBoardMembers:
            fullBoardMember = formatFullOutput(boardMembers, 
                                                 countBoardMemberAll, 
                                                 textLabels['board'][1], 
                                                 maxRows, dispCdrid,
                                                 docType='PDQBoardMemberInfo')
        if dispAll or dispBoardMeetings:
            fullBoardMeeting = formatFullOutput(boardMeeting, 
                                                 countBoardMeetingAll, 
                                                 textLabels['mtg'][1], maxRows,
                                                 dispCdrid,
                                                 docType='Organization')
        mailBody += fullSummariesNew
        mailBody += fullSummariesRev
        # mailBody += fullSummariesReform
        mailBody += fullGlossary
        mailBody += fullAudio
        mailBody += fullGlossaryGen
        mailBody += fullGeneticsProf
        mailBody += fullDrugTerms
        mailBody += fullDis
        mailBody += fullBoardMember
        mailBody += fullBoardMeeting
        mailBody += fullImages

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
        strTo = cdr.getEmailList('ICRDB Statistics Notification')
        #     strTo.append(u'register@clinicaltrials.gov')

    mailHeader = """\
From: %s
To: %s
Subject: %s: %s
""" % (STR_FROM, u', '.join(strTo), cdr.PUB_NAME.capitalize(), title)

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
l.write('ICRDB Stats Report - Started', stdout = True)
l.write('Arguments: %s' % sys.argv, stdout=True)
l.write('', stdout=True)

options   = parseArguments(sys.argv)
testMode  = options.values.testMode
# testMode = True
emailMode = options.values.emailMode
dispRows = options.values.listRows
dispCdrid = options.values.cdrids
debug = options.values.debug

# If we're not running the report for all sections we're setting the 
# option dispPartial to True
# ------------------------------------------------------------------
dispAudio = options.values.audio
dispBoardMembers = options.values.bmembers
dispBoardMeetings = options.values.meetings
dispDis = options.values.dis
dispDrug = options.values.drug
dispGenetics = options.values.genetics
dispGlossary = options.values.glossary
dispImages = options.values.images
dispSummary = options.values.summary

if (dispAudio or dispBoardMembers or dispBoardMeetings or dispDis or dispDrug
    or dispGenetics or dispGlossary or dispImages or dispSummary):
    dispPartial = True
    dispAll     = False
else:
    dispAll     = True
    dispPartial = False

#print "Partial = %s, DIS = %s" % (dispPartial, dispDis)
#print "dispRows = %s" % dispRows
#
#sys.exit()
startDate = options.values.start or firstOfMonth
endDate = options.values.end or lastOfMonth

if startDate == firstOfMonth and endDate == lastOfMonth:
    title = u'Monthly ICRDB Status Report for %s' % time.strftime("%B %Y", 
                                                              lastmonth)
else:
    title = u'ICRDB Status Report from %s to %s' % (startDate, endDate)

# Setting the number of rows to be displayed if the document rows are
# to be displayed (or no rows to be included)
# -------------------------------------------------------------------
if dispRows and options.values.rowmax:
    maxRows = int(options.values.rowmax)
elif dispRows and not options.values.rowmax:
    maxRows = 99999
else:
    maxRows = 0

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
    report = createMessageBody(title, startDate, endDate, maxRows)

    # Send the output as an email or print to screen
    # ----------------------------------------------
    if emailMode:
        l.write("Running in EMAIL mode.  Submitting email.", stdout = True)
        sendEmailReport(report, title)

    # We're writing the report to the reports directory but only if the
    # full report is run.  
    # -----------------------------------------------------------------
    if dispAll:
        l.write("Writing HTML output file.", stdout = True)
        f = open(path, 'w')
        f.write(report.encode('utf-8'))
        f.close()

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

l.write("ICRDB Stats Report - Finished", stdout = True)
sys.exit(0)
