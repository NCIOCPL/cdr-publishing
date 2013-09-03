#----------------------------------------------------------------------
#
# $Id$
#
# Script for generating mailers for board members (or prospective board
# members) as RTF documents to be edited by Microsoft Word.
#
#----------------------------------------------------------------------
import cdr, cdrmailer, RtfWriter, xml.dom.minidom, datetime, re, sys, time

def toRtf(t):
    return RtfWriter.fix(t)

def friendlyDate(date):
    pattern = "%%B %d, %%Y" % date.day
    return date.strftime(pattern)

def getNextMonth():
    now = list(time.localtime())
    now[1] += 1
    then = time.localtime(time.mktime(now))
    return friendlyDate(datetime.date(then[0], then[1], then[2]))

def lookupLetterTitle(letter):
    titles = {
        "adv-invitation": "Advisory Board Invitation",
        "adv-thankyou"  : "Advisory Board Thank-You",
        "ed-invitation" : "Editorial Board Invitation",
        "ed-welcome"    : "Editorial Board Welcome",
        "ed-renewal"    : "Editorial Board Renewal",
        "ed-goodbye"    : "Editorial Board Goodbye",
        "ed-thankyou"   : "Editorial Board Thank-You",
        "adv-summ-email": "Advisory Board Summaries (Email)",
        "adv-summ-fedex": "Advisory Board Summaries (FedEx)",
        "adv-interested": "Advisory Board Still Interested Letter"
    }
    title = titles.get(letter.lower(), "PDQ Board")
    return "%s Letter" % title

def createRtfFilename(forename, surname, names):
    name = (("%s %s" % (forename, surname)).strip().replace(" ", "_")
                                                   .replace(".", ""))
    counter = 0
    baseName = name
    while name in names:
        counter += 1
        name = "%s_%d" % (baseName, counter)
    names[name] = True
    return "%s.rtf" % name

class BoardValues:
    def __init__(self, summaryType, invitePara = '', workingGroupBlock = ""):
        self.summaryType         = summaryType
        self.invitationParagraph = invitePara
        self.workingGroupBlock   = workingGroupBlock
    def findBoardValues(name):
        bn = name.upper()
        if not bn in _boardValues:
            raise cdr.Exception(u"No board values found for board %s" % name)
        return _boardValues[bn]
    findBoardValues = staticmethod(findBoardValues)

_boardValues = {
    'PDQ ADULT TREATMENT EDITORIAL ADVISORY BOARD':
    BoardValues('adult treatment'),
    'PDQ ADULT TREATMENT EDITORIAL BOARD':
    BoardValues('adult treatment', 'Ed Bd Invite Letter - Adult Treatment'),
    ('PDQ CANCER COMPLEMENTARY AND ALTERNATIVE MEDICINE EDITORIAL '
     'ADVISORY BOARD'):
    BoardValues('complementary and alternative medicine'),
    'PDQ CANCER COMPLEMENTARY AND ALTERNATIVE MEDICINE EDITORIAL BOARD':
    BoardValues('complementary and alternative medicine',
                'Ed Bd Invite Letter - CAM'),
    'PDQ CANCER GENETICS EDITORIAL ADVISORY BOARD':
    BoardValues('cancer genetics'),
    'PDQ CANCER GENETICS EDITORIAL BOARD':
    BoardValues('cancer genetics', 'Ed Bd Invite Letter - Genetics',
                """\
\\par\\par
I would like to join the following genetics working group(s):\\line
[  ] Psychosocial issues   [  ] Breast/Ovarian Cancer  [  ] Colorectal Cancer
\line
[  ] Prostate Cancer       [  ] Skin Cancer            [  ] Syndromes (MEN2)
"""),
    'PDQ PEDIATRIC TREATMENT EDITORIAL ADVISORY BOARD':
    BoardValues('pediatric treatment'),
    'PDQ PEDIATRIC TREATMENT EDITORIAL BOARD':
    BoardValues('pediatric treatment', 'NO INVITATION LETTER AVAILABLE'),
    'PDQ SCREENING AND PREVENTION EDITORIAL ADVISORY BOARD':
    BoardValues('screening and prevention'),
    'PDQ SCREENING AND PREVENTION EDITORIAL BOARD':
    BoardValues('screening and prevention',
                'Ed Bd Invite Letter - Screening and Prevention'),
    'PDQ SUPPORTIVE AND PALLIATIVE CARE EDITORIAL ADVISORY BOARD': 
    BoardValues('supportive care'),
    'PDQ SUPPORTIVE AND PALLIATIVE CARE EDITORIAL BOARD':
    BoardValues('supportive care', 'Ed Bd Invite Letter - Supportive Care')
}

#----------------------------------------------------------------------
# Object representing a CDR document.
#----------------------------------------------------------------------
class Doc:
    def __init__(self, id, title):
        self.id    = id
        self.title = title
       
#----------------------------------------------------------------------
# Object for board information.
#----------------------------------------------------------------------
class Board:
    def __init__(self, id, cursor):
        self.today          = datetime.date.today()
        self.id             = id
        self.cursor         = cursor
        self.name           = None
        self.manager        = None
        self.meetingDates   = []
        self.summaryType    = None
        self.boardType      = None
        self.__parseBoardDoc(id)
        self.editorInChief  = self.__findEditorInChief(self.edBoardId)

    def formatMeetingDate(self):
        if not self.meetingDates:
            return "[no future dates scheduled]"
        return self.meetingDates[0].format()

    def formatMeetingDates(self):
        if not self.meetingDates:
            return "[no future dates scheduled]"
        elif len(self.meetingDates) == 1:
            return self.meetingDates[0].format()
        elif len(self.meetingDates) == 2:
            return "%s and %s" % (self.meetingDates[0].format(),
                                  self.meetingDates[1].format())
        else:
            dates = [d.format() for d in self.meetingDates]
            return "%s, and %s" % (", ".join(dates[:-1]), dates[-1])

    def getAdultTreatmentEditorInChief(self):
        self.cursor.execute("""\
            SELECT doc_id
              FROM query_term
             WHERE path = '/Organization/OrganizationNameInformation'
                        + '/OfficialName/Name'
               AND value = 'PDQ Adult Treatment Editorial Board'""")
        rows = self.cursor.fetchall()
        if not rows:
            raise cdr.Exception("Unable to find Adult Treatment "
                                "Editor-in-Chief")
        return self.__findEditorInChief(rows[0][0])

    def __parseBoardDoc(self, id):

        today = str(self.today)
        docId = "CDR%d" % id
        versions = cdr.lastVersions('guest', docId)
        ver = str(versions[0])
        doc = cdr.getDoc('guest', docId, version = ver, getObject = True)
        errors = cdr.getErrors(doc, errorsExpected = False, asSequence = True)
        if errors:
            raise cdr.Exception(u"loading doc for board %d: %s" %
                                (id, u"; ".join(errors)))
        dom = xml.dom.minidom.parseString(doc.xml)
        for node in dom.documentElement.childNodes:
            if node.nodeName == "OrganizationNameInformation":
                for child in node.childNodes:
                    if child.nodeName == "OfficialName":
                        for grandchild in child.childNodes:
                            if grandchild.nodeName == "Name":
                                self.name = cdr.getTextContent(grandchild)
            elif node.nodeName == "OrganizationType":
                self.boardType = cdr.getTextContent(node)
            elif node.nodeName == "PDQBoardInformation":
                managerNode = None
                phoneNode   = None
                emailNode   = None
                for child in node.childNodes:
                    if child.nodeName == "BoardManager":
                        managerNode = child
                    elif child.nodeName == "BoardManagerPhone":
                        phoneNode = child
                    elif child.nodeName == "BoardManagerEmail":
                        emailNode = child
                    elif child.nodeName == "BoardMeetings":
                        for grandchild in child.childNodes:
                            if grandchild.nodeName == 'BoardMeeting':
                                md = self.MeetingDate(grandchild)
                                if md.date >= today:
                                    self.meetingDates.append(md)
                    elif child.nodeName == "AdvisoryBoardFor":
                        edBoardId = child.getAttribute("cdr:ref")
                        self.edBoardId = cdr.exNormalize(edBoardId)[1]
                self.manager = self.Manager(managerNode, phoneNode, emailNode)
        if not self.name or not self.name.strip():
            raise cdr.Exception("no name found for board in document %d" % id)
        if not self.manager:
            raise cdr.Exception("no board manager found in document %d" % id)
        self.boardValues = BoardValues.findBoardValues(self.name)
        self.summaryType = self.boardValues.summaryType
        self.workingGroups = self.boardValues.workingGroupBlock
        self.invitePara = self.boardValues.invitationParagraph
        self.meetingDates.sort(lambda a,b: cmp(a.date, b.date))
        self.name = self.name.strip()
        if self.boardType.upper() == 'PDQ ADVISORY BOARD':
            self.advBoardId   = self.id
            self.advBoardName = self.name
            self.edBoardName  = self.__getBoardName(self.edBoardId)
        elif self.boardType.upper() == 'PDQ EDITORIAL BOARD':
            self.edBoardId    = self.id
            self.edBoardName  = self.name
            self.advBoardId   = self.__findAdvBoardFor(self.id)
            self.advBoardName = self.__getBoardName(self.advBoardId)
        else:
            raise cdr.Exception('Board type: %s' % self.boardType)

    def __findAdvBoardFor(self, id):
        self.cursor.execute("""\
            SELECT doc_id
              FROM query_term
             WHERE path = '/Organization/PDQBoardInformation'
                        + '/AdvisoryBoardFor/@cdr:ref'
               AND int_val = ?""", id)
        rows = self.cursor.fetchall()
        return rows and rows[0][0] or None

    def __getBoardName(self, id):
        if not id:
            return ""
        self.cursor.execute("""\
            SELECT DISTINCT value
                       FROM query_term
                      WHERE path = '/Organization/OrganizationNameInformation'
                                 + '/OfficialName/Name'
                        AND doc_id = ?""", id)
        rows = self.cursor.fetchall()
        if not rows:
            raise cdr.Exception("Unable to find name for org %s" % id)
        return rows[0][0]
    
    def __findEditorInChief(self, id):
        today = str(self.today)
        self.cursor.execute("""\
            SELECT DISTINCT p.int_val
                       FROM query_term p
                       JOIN query_term b
                         ON b.doc_id = p.doc_id
                       JOIN query_term s
                         ON s.doc_id = b.doc_id
                        AND LEFT(s.node_loc, 4) = LEFT(b.node_loc, 4)
            LEFT OUTER JOIN query_term e
                         ON e.doc_id = s.doc_id
                        AND LEFT(e.node_loc, 4) = LEFT(s.node_loc, 4)
                        AND e.path = '/PDQBoardMemberInfo'
                                   + '/BoardMembershipDetails'
                                   + '/EditorInChief/TermEndDate'
                      WHERE p.path = '/PDQBoardMemberInfo'
                                   + '/BoardMemberName/@cdr:ref'
                        AND b.path = '/PDQBoardMemberInfo'
                                   + '/BoardMembershipDetails'
                                   + '/BoardName/@cdr:ref'
                        AND s.path = '/PDQBoardMemberInfo'
                                   + '/BoardMembershipDetails'
                                   + '/EditorInChief/TermStartDate'
                        AND b.int_val = ?
                        AND s.value <= '%s'
                        AND (e.value IS NULL OR e.value > '%s')""" %
                                 (today, today), id)
        rows = self.cursor.fetchall()
        if not rows:
            raise cdr.Exception("No editor in chief for board %d" % id)
        if len(rows) > 1:
            raise cdr.Exception("Too many (%d) editors-in-chief for board %d" %
                                (len(rows), id))
        return self.EditorInChief(rows[0][0])

    class Manager:
        def __init__(self, nameNode, phoneNode, emailNode):
            if not nameNode:
                raise cdr.Exception("Missing BoardManager element")
            elif not phoneNode:
                raise cdr.Exception("Missing required phone for board manager")
            elif not emailNode:
                raise cdr.Exception("Missing required email for board manager")
            self.name  = cdr.getTextContent(nameNode).strip()
            self.phone = cdr.getTextContent(phoneNode).strip()
            self.email = cdr.getTextContent(emailNode).strip()
            if not self.name:
                raise cdr.Exception("Name required for board manager")
            if not self.phone:
                raise cdr.Exception("Phone required for board manager")
            if not self.email:
                raise cdr.Exception("Email required for board manager")
        
    class EditorInChief:
        def __init__(self, id):
            self.id   = id
            self.name = None
            docId = 'CDR%d' % id
            versions = cdr.lastVersions('guest', docId)
            ver = str(versions[0])
            doc = cdr.getDoc('guest', docId, version = ver, getObject = True)
            errors = cdr.getErrors(doc, errorsExpected = False,
                                   asSequence = True)
            if errors:
                raise cdr.Exception(u"loading doc %d for editor in chief: %s" %
                                    (id, u"; ".join(errors)))
            dom = xml.dom.minidom.parseString(doc.xml)
            for node in dom.documentElement.childNodes:
                if node.nodeName == "PersonNameInformation":
                    self.name = cdrmailer.PersonalName(node)
            if not self.name:
                raise cdr.Exception("No name found for editor-in-chief %d" % id)

    class MeetingDate:
        def __init__(self, node):
            self.date = u"0000-00-00"
            for child in node.childNodes:
                if child.nodeName == 'MeetingDate':
                    self.date = cdr.getTextContent(child)
        def format(self):
            parts = self.date.split('-', 2)
            date = datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
            return friendlyDate(date)

#----------------------------------------------------------------------
# Object for one board member.
#----------------------------------------------------------------------
class BoardMember:
    def __init__(self, memberId, memberVer, personId, personVer, board):
        self.memberId         = memberId
        self.memberVersion    = memberVer
        self.personId         = personId
        self.personVersion    = personVer
        self.board            = board
        self.address          = None
        self.contactId        = None
        self.name             = None
        self.summaries        = self.__findSummaries(memberId, board.cursor)
        self.renewalFrequency = "**** NO TERM RENEWAL FREQUENCY FOUND!!! ****"
        self.asstName         = None
        self.asstPhone        = None
        self.asstFax          = None
        self.asstEmail        = None

        self.__parseMemberDoc(memberId, memberVer)
        self.__parsePersonDoc(personId, personVer, board.cursor)
        if not self.name:
            raise cdr.Exception("No personal name information for board "
                                "member %d" % memberId)

    def getSummaryList(self):
        if not self.summaries:
            return "[No summaries assigned]"
        titles = [("{\\i %s}" % toRtf(s.title)) for s in self.summaries]
        if len(self.summaries) == 1:
            return "the %s summary" % titles[0]
        if len(self.summaries) == 2:
            return "the %s and %s summaries" % (titles[0], titles[1])
        else:
            return "the %s, and %s summaries" % (", ".join(titles[0:-1]),
                                                 titles[-1])

    def getTermYears(self):
        if self.renewalFrequency == 'Every year':
            return "1-year"
        elif self.renewalFrequency == 'Every two years':
            return "2-year"
        else:
            return self.renewalFrequency
        
    def __parseMemberDoc(self, id, ver):
        doc = cdr.getDoc('guest', id, version = str(ver), getObject = True)
        errors = cdr.getErrors(doc, errorsExpected = False, asSequence = True)
        if errors:
            raise cdr.Exception(u"loading member doc: %s" % u"; ".join(errors))
        dom = xml.dom.minidom.parseString(doc.xml)
        for node in dom.documentElement.childNodes:
            if node.nodeName == "BoardMemberContact":
                for child in node.childNodes:
                    if child.nodeName == "PersonContactID":
                        self.contactId = cdr.getTextContent(child)
            elif node.nodeName == "BoardMembershipDetails":
                self.__parseBoardMembershipDetails(node)
            elif node.nodeName == "BoardMemberAssistant":
                self.__parseBoardMemberAssistantInfo(node)

    def __parsePersonDoc(self, id, ver, cursor):

        # If we don't have a fragment ID, use the CIPS contact location
        if not self.contactId:
            cursor.execute("""\
                SELECT DISTINCT value
                           FROM query_term
                          WHERE path = '/Person/PersonLocations/CIPSContact'
                            AND doc_id = ?""", id)
            rows = cursor.fetchall()
            if not rows:
                raise cdr.Exception("No CIPS contact found for board member %d"
                                    % id)
            self.contactId = rows[0][0]

        # Get the address information.
        filters = ["name:Person Contact Fragment With Name"]
        #print "id=%s docVer=%s contactId=%s" % (id, str(ver), self.contactId)
        result  = cdr.filterDoc('guest', filters, id, docVer = str(ver),
                                parm = (('fragId', self.contactId),))
        if type(result) in (type(""), type(u"")):
            raise cdr.Exception("failure extracting contact address for %s: %s"
                                % (id, result))
        self.address = cdrmailer.Address(result[0], cdrmailer.TITLE_AFTER_NAME)
        self.name = self.address.getPersonalName()

    def __parseBoardMembershipDetails(self, node):
        boardId = None
        frequency = None
        for child in node.childNodes:
            if child.nodeName == "BoardName":
                attr = child.getAttribute("cdr:ref")
                if attr:
                    id = cdr.exNormalize(attr)
                    boardId = id[1]
                    if boardId != self.board.id:
                        return
            elif child.nodeName == "TermRenewalFrequency":
                frequency = cdr.getTextContent(child)
        if boardId and frequency:
            self.renewalFrequency = frequency
                
    def __parseBoardMemberAssistantInfo(self, node):
        for child in node.childNodes:
            if child.nodeName == "AssistantName":
                self.asstName = cdr.getTextContent(child)
            elif child.nodeName == "AssistantPhone":
                self.asstPhone = cdr.getTextContent(child)
            elif child.nodeName == "AssistantFax":
                self.asstFax = cdr.getTextContent(child)
            elif child.nodeName == "AssistantEmail":
                self.asstEmail = cdr.getTextContent(child)

    def formatAsstInfo(self):
        return """\
\\tab Asst Name:\\tab %s\\line
\\tab Asst Phone:\\tab %s\\line
\\tab Asst Fax:\\tab %s\\line
\\tab Asst E-mail:\\tab %s\\par""" % (
            self.asstName and RtfWriter.fix(self.asstName.strip()) or "",
            self.asstPhone and RtfWriter.fix(self.asstPhone.strip()) or "",
            self.asstFax and RtfWriter.fix(self.asstFax.strip()) or "",
            self.asstEmail and RtfWriter.fix(self.asstEmail.strip()) or "")

    def __findSummaries(self, id, cursor):
        summaries = []
        cursor.execute("""\
            SELECT DISTINCT t.doc_id, t.value
                       FROM query_term t
                       JOIN query_term b
                         ON b.doc_id = t.doc_id
                       JOIN active_doc a
                         ON a.id = b.doc_id
                      WHERE t.int_val = ?
                        AND t.path = '/Summary/SummaryTitle'
                        AND b.path = '/Summary/SummaryMetaData/PDQBoard'
                                   + '/BoardMember/@cdr:ref'""", id)
        row = cursor.fetchone()
        while row:
            summaries.append(Doc(row[0], row[1]))
            row = cursor.fetchone()
        return summaries

#----------------------------------------------------------------------
# Derived class for board member mailers.
#----------------------------------------------------------------------
class BoardMemberMailer(cdrmailer.MailerJob):

    #------------------------------------------------------------------
    # Nothing to do here (but we must override the method).
    #------------------------------------------------------------------
    def fillQueue(self):
        pass

    #------------------------------------------------------------------
    # This is what we're here to do.
    #------------------------------------------------------------------
    def createRtfMailers(self):

        # Create the separate directory used for RTF documents.
        self.initRtfMailers()

        # Gather the information we need for the board.
        self.__loadBoardInfo()
        
        # Collect the information needed to generate the mailers.
        boardMembers = []
        try:
            self.getCursor().execute("""\
        SELECT d.doc_id, d.doc_version, v.id, MAX(v.num)
          FROM pub_proc_doc d
          JOIN query_term m
            ON m.doc_id = d.doc_id
          JOIN doc_version v
            ON v.id = m.int_val
         WHERE m.path = '/PDQBoardMemberInfo/BoardMemberName/@cdr:ref'
           AND v.val_status = 'V'
           AND d.pub_proc = ?
      GROUP BY d.doc_id, d.doc_version, v.id""", self.getId())
            for row in self.getCursor().fetchall():
                boardMembers.append(BoardMember(row[0], row[1], row[2],
                                                row[3], self.__board))

        except Exception, e:
            raise cdr.Exception("database error building emailer list: %s" %
                                str(e))

        template = self.__prepareTemplate()

        # Pump out one RTF letter for each board member.
        names = {}
        for m in boardMembers:
            asstInfo    = m.formatAsstInfo()
            addrBlock   = m.address.format(useRtf = True,
                                           dropUS = True).getBlock()
            forename    = toRtf(m.name.getGivenName())
            surname     = toRtf(m.name.getSurname())
            memberName  = toRtf(m.name.format(False, False))
            fancyName   = toRtf(m.name.format(True, False))
            termYears   = m.getTermYears()
            summaryList = m.getSummaryList()
            contactInfo = m.address.format(contactFields = True,
                                           dropUS = True)
            letter      = (template.replace("@@ADDRBLOCK@@",   addrBlock)
                                   .replace("@@FORENAME@@",    forename)
                                   .replace("@@SURNAME@@",     surname)
                                   .replace("@@MEMBERNAME@@",  memberName)
                                   .replace("@@FANCYNAME@@",   fancyName)
                                   .replace("@@TERMYEARS@@",   termYears)
                                   .replace("@@SUMMARYLIST@@", summaryList)
                                   .replace("@@CONTACTINFO@@", contactInfo)
                                   .replace("@@ASSTINFO@@",    asstInfo))
            name = createRtfFilename(forename, surname, names)
            print "writing %s" % name
            fp = open(name, "wb")
            fp.write(letter)
            fp.close()
            self.bumpCount()
    
    #------------------------------------------------------------------
    # Prepare a template to be used by all letters in this batch.
    #------------------------------------------------------------------
    def __prepareTemplate(self):
        letter = self.getParm('Letter')
        if not letter:
            raise cdr.Exception("No Letter template specified")
        name       = '%s/%s.rtf' % (self.getMailerIncludePath(), letter[0])
        title      = lookupLetterTitle(letter[0])
        subject    = "Board Member Correspondence Mailer"
        imageName  = "%s/dhhslogo.png" % self.getMailerIncludePath()
        formLetter = RtfWriter.FormLetter(title      = title,
                                          subject    = subject,
                                          template   = name,
                                          pngName    = imageName,
                                          binImage   = False,
                                          invitePara = self.__board.invitePara)
        formLetter.defaultFont = formLetter.SANSSERIF
        formLetter.fSize = 24
        template     = formLetter.getRtf()
        
        date         = friendlyDate(self.__board.today)
        boardName    = toRtf(self.__board.name)
        meetingDate  = self.__board.formatMeetingDate()
        meetingDates = self.__board.formatMeetingDates()
        bmName       = toRtf(self.__board.manager.name)
        bmPhone      = toRtf(self.__board.manager.phone)
        bmEmail      = toRtf(self.__board.manager.email)
        adultTrEic   = self.__board.getAdultTreatmentEditorInChief()
        atEcName     = toRtf(adultTrEic.name.format(True, False))
        ecName       = toRtf(self.__board.editorInChief.name.format(True,
                                                                    False))
        summaryType  = toRtf(self.__board.summaryType)
        edBoardName  = toRtf(self.__board.edBoardName)
        advBoardName = toRtf(self.__board.advBoardName)
        workGroups   = self.__board.workingGroups
        oneMonthAway = getNextMonth()
        twoWeeksAway = friendlyDate(datetime.date.fromordinal(
                                    self.__board.today.toordinal() + 14))
        letter       = self.__plugInSummaryTopics(template, self.__board)
        letter       = self.__addConflictOfInterestForm(letter)
        return (letter.replace("@@DATE@@",           date)
                      .replace("@@BOARDNAME@@",      boardName)
                      .replace("@@MEETINGDATE@@",    meetingDate)
                      .replace("@@MEETINGDATES@@",   meetingDates)
                      .replace("@@BMNAME@@",         bmName)
                      .replace("@@BMPHONE@@",        bmPhone)
                      .replace("@@BMEMAIL@@",        bmEmail)
                      .replace("@@ECNAME@@",         ecName)
                      .replace("@@ATECNAME@@",       atEcName)
                      .replace("@@SUMMARYTYPE@@",    summaryType)
                      .replace("@@WORKGROUPS@@",     workGroups)
                      .replace("@@EDBOARDNAME@@",    edBoardName)
                      .replace("@@ADVBOARDNAME@@",   advBoardName)
                      .replace("@@DATEPLUS1MONTH@@", oneMonthAway)
                      .replace("@@DATEPLUS2WEEKS@@", twoWeeksAway))

    #------------------------------------------------------------------
    # Insert a conflict of interest form if appropriate.
    #------------------------------------------------------------------
    def __addConflictOfInterestForm(self, letter):
        placeholder = "@@CONFLICTOFINTERESTFORM@@"
        if placeholder not in letter:
            return letter
        name = "%s/conflict-of-interest-form.rtf" % self.getMailerIncludePath()
        fp = open(name, "rb")
        form = fp.read()
        fp.close()
        return letter.replace(placeholder, form)

    #------------------------------------------------------------------
    # Insert a list of summary topics if appropriate.
    #------------------------------------------------------------------
    def __plugInSummaryTopics(self, template, board):
        if "@@SUMMARYTOPICS@@" not in template:
            return template
        self.getCursor().execute("""\
            SELECT DISTINCT topic.value
                       FROM query_term topic
                       JOIN query_term board
                         ON board.doc_id = topic.doc_id
                       JOIN query_term audience
                         ON audience.doc_id = topic.doc_id
                       JOIN active_doc a
                         ON a.id = topic.doc_id
                       JOIN pub_proc_cg c
                         ON c.id = topic.doc_id
                      WHERE topic.path = '/Summary/SummaryTitle'
                        AND board.path = '/Summary/SummaryMetaData/PDQBoard'
                                       + '/Board/@cdr:ref'
                        AND board.int_val = ?
                        AND audience.path = '/Summary/SummaryMetaData'
                                          + '/SummaryAudience'
                        AND audience.value = 'Health professionals'
                   ORDER BY topic.value""", board.edBoardId)
        rows = self.getCursor().fetchall()
        if not rows:
            raise cdr.Exception("Unable to find topics for %s" %
                                board.edBoardName)
        lines = []
        for row in rows:
            lines.append("____ %s\line" % RtfWriter.fix(row[0].strip()))
        return template.replace("@@SUMMARYTOPICS@@", "\n".join(lines))
                         
    #------------------------------------------------------------------
    # Gather information about the board for this mailer.
    #------------------------------------------------------------------
    def __loadBoardInfo(self):
        boardId = self.getParm('Board')
        if not boardId:
            raise cdr.Exception("Missing BoardId for BoardMemberMailer")
        boardId = int(boardId[0])
        #print "boardId = %d" % boardId
        self.__board = Board(boardId, self.getCursor())

if __name__ == "__main__":
    sys.exit(BoardMemberMailer(int(sys.argv[1])).run())
