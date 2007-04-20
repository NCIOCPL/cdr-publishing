#----------------------------------------------------------------------
#
# $Id: BoardSummaryMailer.py,v 1.16 2007-04-20 18:28:53 kidderc Exp $
#
# Master driver script for processing PDQ Editorial Board Member mailings.
#
# $Log: not supported by cvs2svn $
# Revision 1.12  2004/04/27 15:44:00  bkline
# Added support for use of PDQBoardMemberInfo documents.
#
# Revision 1.11  2004/04/19 15:54:25  bkline
# Suppressed creation of mailing labels at Lakshmi's request (#1188).
#
# Revision 1.10  2003/05/13 19:57:21  bkline
# Replaced explitly enumerated filter list with named filter set invocation.
#
# Revision 1.9  2003/02/13 20:17:36  bkline
# Added filter to strip out "Changes to summary" SummarySection elements.
#
# Revision 1.8  2003/01/28 15:20:52  bkline
# Added date and mailer ID to summary mailer cover letters.
#
# Revision 1.7  2002/11/08 21:46:08  bkline
# Ready for user testing.
#
# Revision 1.6  2001/10/09 12:07:19  bkline
# Removed superfluous constructor override.  Removed title truncation
# from top cover page.  Fixed typo (this -> self).
#
# Revision 1.5  2001/10/07 15:16:25  bkline
# Added call to getDeadline().
#
# Revision 1.4  2001/10/07 12:49:12  bkline
# Reduced use of publicly accessible members.
#
# Revision 1.3  2001/10/06 23:42:08  bkline
# Changed parameters to makeLatex() method.
#
# Revision 1.2  2001/10/06 21:52:30  bkline
# Factored out base class MailerJob.
#
# Revision 1.1  2001/10/05 20:38:09  bkline
# Initial revision
#
#----------------------------------------------------------------------

import cdrdb, cdrmailer, re, sys, UnicodeToLatex, time

class SummaryWithVer:
    def __init__(self, Id, Ver):
        self.summaryId = Id
        self.ver = Ver
    
class MailToList:
    def __init__(self, memberId):
        self.memberId = memberId
        self.summaries = []

#----------------------------------------------------------------------
# Derived class for PDQ Editorial Board Member mailings.
#----------------------------------------------------------------------
class BoardSummaryMailerJob(cdrmailer.MailerJob):

    #----------------------------------------------------------------------
    # Parse up the person parameter. Will be empty if all mailers are
    # sent to all members.
    # Format of person is MemberID1 [SummaryID1 SummaryID2] MemberID2 [SummaryID1 SummaryID3 ....] ...
    #----------------------------------------------------------------------
    def __parsePerson(self):
        try:
            self.__Mailers = {}
            self.__HavePersons = 0
            personParm = self.getParm("Person")            
            Person = personParm[0]

            if (len(Person)>1):
                personSplit = Person.split("]")
                self.__HavePersons = 1
                
                for person in personSplit:
                    person = person.strip()
                    if ( len(person) > 0 ):
                        personSplit = person.split("[")
                        memberId = personSplit[0]
                        self.__Mailers[int(memberId)] = MailToList(int(memberId))
                        member = self.__Mailers[int(memberId)]

                        personSplit2 = personSplit[1]
                        personSplit3 = personSplit2.split(" ")
                        
                        for summaryTxt in personSplit3:
                            summaryTxt = summaryTxt.strip()
                            if (len(summaryTxt)>0):
                                summarySplit=summaryTxt.split("/")
                                summary = SummaryWithVer(int(summarySplit[0]),int(summarySplit[1]))
                                member.summaries.append(summary)
        except Exception, e:
            raise e

    #----------------------------------------------------------------------
    # Overrides method in base class for filling the print queue.
    #----------------------------------------------------------------------
    def fillQueue(self):
        self.__parsePerson()
        self.__getBoardId()
        self.__getBoardMembers()
        self.__getDocuments()
        self.__makeCoverSheet()
        self.__makePackets()

    #----------------------------------------------------------------------
    # Locate the parameter which specifies the board.
    #----------------------------------------------------------------------
    def __getBoardId(self):
        boardParm = self.getParm("Board")
        if not boardParm:
            raise "parameter for Board not specified"
        digits = re.sub("[^\d]", "", boardParm[0])
        self.__boardId = int(digits)
        self.log("processing board CDR%010d" % self.__boardId)

    #----------------------------------------------------------------------
    # Gather the list of board members.
    #----------------------------------------------------------------------
    def __getBoardMembers(self):
                      		
        memberPath = '/Summary/SummaryMetaData/PDQBoard/Board/@cdr:ref'
        boardPath  = '/Summary/SummaryMetaData/PDQBoard/BoardMember/@cdr:ref'
        infoPath   = '/PDQBoardMemberInfo/BoardMemberName/@cdr:ref'
        try:
            sWhere = ""
            if (self.__HavePersons):
                sWhere = " AND person.id in ( "
                for memberId in self.__Mailers:
                    sWhere += "%d," % int(memberId)
                sWhere = sWhere[0:len(sWhere)-1]
                sWhere += ")"
                
            sQuery = """\
                SELECT DISTINCT person.id,
                                person.title,
                                summary.id,
                                summary.title,
                                pub_proc_doc.doc_version,
                                member_info.doc_id
                           FROM document person
                           JOIN query_term member
                             ON member.int_val = person.id
                           JOIN document summary
                             ON summary.id = member.doc_id
                           JOIN query_term board
                             ON board.doc_id = summary.id
                           JOIN pub_proc_doc
                             ON pub_proc_doc.doc_id = summary.id
                           JOIN query_term member_info
                             ON member_info.int_val = person.id
                          WHERE board.int_val = %d
                            AND pub_proc_doc.pub_proc = %d
                            AND board.path = '%s'
                            AND member.path = '%s'
                            AND member_info.path = '%s'
                            %s
                            AND LEFT(board.node_loc, 8) =
                                LEFT(member.node_loc, 8)
                       ORDER BY person.title,
                                person.id,
                                summary.title,
                                summary.id""" % (int(self.__boardId),int(self.getId()),memberPath, boardPath,infoPath,sWhere)
           
            self.getCursor().execute(sQuery)
                                                 
            rows = self.getCursor().fetchall()
            for (personId, personTitle, summaryId, summaryTitle, docVer,
                 memberInfo) in rows:
                if summaryId in self.getDocIds():
                    recipient = self.getRecipients().get(personId)
                    doc       = self.getDocuments().get(summaryId)
                    if not recipient:
                        self.log("found board member %s" % personTitle)
                        addr      = self.getBoardMemberAddress(personId,
                                                               memberInfo)
                        recipient = cdrmailer.Recipient(personId, personTitle,
                                                        addr)
                        self.getRecipients()[personId] = recipient
                    if not doc:
                        doc = cdrmailer.Document(summaryId, summaryTitle,
                                                 "Summary", docVer)
                        self.getDocuments()[summaryId] = doc
                    recipient.getDocs().append(doc)
                    
        except cdrdb.Error, info:
            raise "database error finding board members: %s" % (
                info[1][0].encode('ascii'))

    #----------------------------------------------------------------------
    # Produce LaTeX source for all summaries to be mailed out.
    #----------------------------------------------------------------------
    def __getDocuments(self):
        filters = ["set:Mailer Summary Set"]
        for docId in self.getDocuments().keys():
            self.log("generating LaTeX for CDR%010d" % docId)
            doc = self.getDocuments()[docId]
            doc.latex = self.makeLatex(doc, filters)

    #------------------------------------------------------------------
    # Determine whether or not the document should be included in the
    # packet for the member
    #------------------------------------------------------------------
    def __ShouldIncludeDocInPacket(self, MemberID, DocID):
        retval = 1

        if (self.__HavePersons):
            retval = 0
            member = self.__Mailers[int(MemberID)]
            for summary in member.summaries:
                if ( int(summary.summaryId) == int(DocID) ):
                    retval = 1

        return retval
            
    #----------------------------------------------------------------------
    # Generate a main cover page and add it to the print queue.
    #----------------------------------------------------------------------
    def __makeCoverSheet(self):
        filename = "MainCoverPage.txt"
        f = open(filename, "w")
        f.write("\n\nPDQ Board Member Summary Review Mailer\n\n")
        f.write("Job Number: %d\n\n" % self.getId())        
        for key in self.getRecipients().keys():
            recipient = self.getRecipients()[key]
            f.write("Board Member: %s (CDR%010d)\n" % (recipient.getName(), 
                                                           recipient.getId()))
            for doc in recipient.getDocs():
                if (self.__ShouldIncludeDocInPacket(recipient.getId(), doc.getId())):
                    title = doc.getTitle().encode('latin-1', 'replace')
                    if len(title) > 50: title = title[:50] + " ..."
                    f.write("\tSummary CDR%010d: %s\n" % (doc.getId(), title))

        f.close()
        job = cdrmailer.PrintJob(filename, cdrmailer.PrintJob.PLAIN)
        self.addToQueue(job)

    #------------------------------------------------------------------
    # Walk through the board member list, generating packets for each.
    #------------------------------------------------------------------
    def __makePackets(self):
        coverLetterParm     = self.getParm("CoverLetter")
        basePath            = self.getMailerIncludePath() + "/"
        coverLetterName     = basePath + coverLetterParm[0]
        coverLetterFile     = open(coverLetterName)
        coverLetterTemplate = coverLetterFile.read()
        sepSheetName        = basePath + "ListOfSummaries.tex"
        sepSheetFile        = open(sepSheetName)
        sepSheetTemplate    = sepSheetFile.read()
        coverLetterFile.close()
        sepSheetFile.close()
        
        for key in self.getRecipients().keys():
            self.__makePacket(self.getRecipients()[key], coverLetterTemplate,
                                                         sepSheetTemplate)

    #------------------------------------------------------------------
    # Create a mailer packet for a single mailer recipient.
    #------------------------------------------------------------------
    def __makePacket(self, recipient, coverLetterTemplate, sepSheetTemplate):
        self.log("building packet for %s" % recipient.getName())

        # Create a separator sheet.
        docList   = ""
        basename  = 'SeparatorSheet-%d' % recipient.getId()
        jobType   = cdrmailer.PrintJob.COVERPAGE
        name      = recipient.getAddress().getAddressee()
        latex     = sepSheetTemplate.replace('@@REVIEWER@@', name)
        
        for doc in recipient.getDocs():
            if (self.__ShouldIncludeDocInPacket(recipient.getId(), doc.getId())):
                docList += "\\item %d: %s\n" % (doc.getId(),
                        UnicodeToLatex.convert(doc.getTitle().split(';')[0]))
                
        latex     = latex.replace('@@SUMMARYLIST@@', docList)
        self.addToQueue(self.makePS(latex, 1, basename, jobType))

        # Add the document mailers.
        for doc in recipient.getDocs():
            if (self.__ShouldIncludeDocInPacket(recipient.getId(), doc.getId())):
                self.__addDocToPacket(recipient, doc, coverLetterTemplate)

    #------------------------------------------------------------------
    # Add one summary document to a board member's packet.
    #------------------------------------------------------------------
    def __addDocToPacket(self, recipient, doc, template):

        # Add document to the repository for tracking replies to the mailer.
        mailerId = self.addMailerTrackingDoc(doc, recipient, self.getSubset())

        # Create a cover letter.
        docTitle = UnicodeToLatex.convert(doc.getTitle().split(';')[0])
        name     = recipient.getAddress().getAddressee()
        latex    = template.replace('@@REVIEWER@@', name)
        latex    = latex.replace('@@SUMMARYTITLE@@', docTitle)
        latex    = latex.replace('@@MAILERID@@', 'CDR%010d' % mailerId)
        latex    = latex.replace('@@DATE@@', time.strftime("%B %d, %Y"))
        basename = 'CoverLetter-%d-%d' % (recipient.getId(), doc.getId())
        jobType  = cdrmailer.PrintJob.COVERPAGE
        self.addToQueue(self.makePS(latex, 1, basename, jobType))

        # Customize the LaTeX for this copy of the summary.
        nPasses  = doc.latex.getLatexPassCount()
        latex    = doc.latex.getLatex()
        latex    = latex.replace('@@BoardMember@@', name)
        #latex   = latex.replace('@@MailerDocId@@', str(mailerId))
        basename = 'Mailer-%d-%d' % (recipient.getId(), doc.getId())
        jobType  = cdrmailer.PrintJob.MAINDOC
        self.addToQueue(self.makePS(latex, nPasses, basename, jobType))
        self.log("added CDR%010d to packet" % doc.getId())

if __name__ == "__main__":
    sys.exit(BoardSummaryMailerJob(int(sys.argv[1])).run())
