#----------------------------------------------------------------------
#
# $Id: DirectoryMailer.py,v 1.4 2002-10-11 03:36:48 ameyer Exp $
#
# Master driver script for processing directory mailers.
#
# $Log: not supported by cvs2svn $
# Revision 1.3  2002/10/09 02:00:01  ameyer
# Myriad changes.  First version to actually produce output.  Not fully tested
# at all.
#
# Revision 1.2  2002/09/17 18:19:57  ameyer
# Last version from mmdb2.  Still not working yet.
#
#
#----------------------------------------------------------------------

import cdr, cdrdb, cdrmailer, cdrmailcommon, string, re, sys


#----------------------------------------------------------------------
# Derived class for all directories
#----------------------------------------------------------------------
class DirectoryMailer(cdrmailer.MailerJob):

    #------------------------------------------------------------------
    # Add some information to the subclass not needed in the superclass
    #------------------------------------------------------------------
    def __init__(self, jobId, suppressPrinting = 0):
        # Super class constructor
        cdrmailer.MailerJob.__init__(self, jobId, suppressPrinting)

    #------------------------------------------------------------------
    # Override method in base class to fill the print queue
    #
    # When this method is called, the run() method has already
    # invoked:
    #    super.__loadSettings()
    #    super.__createQueue()
    # We've already:
    #    Connected to the database
    #    Established a session,
    #    Retrieved the list of docIds from pub_proc_doc
    #    Retrieved job info from pub_proc and pub_proc_parm
    #    Created an output directory and cd'd to it
    # Now we just have to do directory specific stuff.
    # This should be the first routine invoked (other than init) in
    #   this subclass.
    #------------------------------------------------------------------
    def fillQueue(self):

        self.log("~~Started DirectoryMailer.fillQueue()")

        # Is this job a remailer?
        # Can't do this until pub_proc_parms are loaded by superclass.
        self.rms = None
        self.remailer = 0
        if string.find (self.getSubset(), "remail") >= 0:
            self.remailer = 1
            self.rms = cdrmailcommon.RemailSelector (conn=None,
                                                     jobId=self.getId())

        # Get all the recipients corresponding to the docIds in
        #   the pub_proc_doc table
        self.log("~~About to __getRecipients");
        self.__getRecipients()

        # Retrieve the actual documents themselves, performing
        #   any necessary filtering and LaTeX generation, and
        #   writing the generated print images to disk
        self.log("~~About to __createMailerDocs");
        self.__createMailerDocs()

        # Create an index of the documents
        self.log("~~About to __makeIndex");
        self.makeIndex()

        # Generate a cover sheet for the job a whole, listing
        #   each individual mailer recipient
        self.log("~~About to __makeCoverSheet");
        self.__makeCoverSheet()

        # Fill the print queue with recipient+document object pairs
        #   telling the later print steps the order of printing
        self.log("~~About to __makeMailers");
        self.__makeMailers()

    #------------------------------------------------------------------
    # Create the list of Recipient objects
    #------------------------------------------------------------------
    def __getRecipients(self):

        # We'll add recipients to this (initially empty) dictionary
        recipients = self.getRecipients()

        # Look at each document object
        for docId in self.getDocuments().keys():

            # Document object for the id
            doc = self.getDocuments()[docId]

            # For person directories, the document of the recipient is
            #   same as the document itself.
            # For organizations it's more complicated.  But the recipient
            #   is generated from the organization, so it is effectively
            #   still the same.
            recipId = docId

            # Assume no remail tracker for now.
            trackId = None

            # For remailers, get id of recipient and tracking doc
            #   from the remailer selection
            # Should normally be only one recipient, but we allow
            #   more than one per document - consistent with other
            #   mailers.
            # Remailers must only have one.
            if self.remailer:
                # Get list of pairs of (recipient, tracker)
                tempList = self.rms.getRelatedIds (docId)
                trackId  = tempList[0][1]

                # Some debug checks
                assert len(tempList) == 1, \
                    "Should be exactly one directory remailer recipient. " \
                    "Found %d recipients for document id=%d" % \
                     (len(tempList), docId)
                assert tempList[0][0] == docId, \
                    "Directory remailer should have recipient=doc id, but " \
                    "recipient=%d, document=%d" % (tempList[0][0], docId)

            # Filters are different for physicians and organizations
            docType = self.getParm("docType")[0]
            if not docType:
                raise StandardError ("docType parameter missing")

            # Find or create a recipient object for this doc
            # It may be rare to find one person as the contact for
            #   multiple organizations, but could happen
            recip = recipients.get(recipId)

            # If not found (the normal case), create recipient
            if not recip:
                address = self.getCipsContactAddress (recipId, docType)

                # Response should be list of filtered doc + messages
                # If it's a single string, it's an error message
                if type(address)==type("") or type(address)==type(u""):
                    raise StandardError (
                        "Unable to find address for %d: %s" % (recipId,
                                                               address))

                # Construct a recipient with this address
                recip = cdrmailer.Recipient (recipId, address.getAddressee(),
                                             address)

                # Add the recipient to the dictionary
                recipients[recipId] = recip

            # We may need a remailer id for this recipient for the
            #   RemailerFor field in the new tracking document
            recip.remailTracker = trackId

            # Append the current document to the list of those that
            #   this recipient will receive
            recip.getDocs().append (doc)

    #------------------------------------------------------------------
    # Generate each document to a file
    #------------------------------------------------------------------
    def __createMailerDocs(self):

        docDict = self.getDocuments()

        for docId in docDict.keys():

            # Get full Document object
            doc = docDict[docId]

            # Identify filters for each mailer
            if doc.getDocType() == 'Organization':
                # Organization filters denormalize data
                filters = ['name:Denormalization Filter (1/1): Organization']
            else:
                # Person denormalization filters
                filters = ['name:Denormalization Filter (1/1): Person']

            self.log("generating LaTeX for CDR%010d" % docId)
            doc = self.getDocuments()[docId]
            doc.latex = self.makeLatex(doc, filters, '')

    #------------------------------------------------------------------
    # Generate a main cover page and add it to the print queue.
    # This lists all the documents included in the job.
    #------------------------------------------------------------------
    def __makeCoverSheet(self):
        filename = "MainCoverPage.txt"
        f = open(filename, "w")
        f.write("\n\n%s\n\n" % self.getSubset())
        f.write("Job Number: %d\n\n" % self.getId())

        # Doc ids are listed in the order that they come back
        #   from the pub_proc_doc table, i.e., document id order
        recipients = self.getRecipients()
        for key in recipients.keys():
            # Show recipient identification
            recip = recipients[key]
            f.write ("Recipient: %s (CDR%010d)\n" % (recip.getName(),
                                                    recip.getId()))
            # Show each doc to be sent to recipient
            for doc in recip.getDocs():
                f.write ("  CDR%010d: %s\n" % (doc.getId(), doc.getTitle()))
            f.write ("\n")
        f.close()

        # Put the coverpage in the print queue for this job
        job = cdrmailer.PrintJob(filename, cdrmailer.PrintJob.COVERPAGE)
        self.addToQueue(job)

    #------------------------------------------------------------------
    # Walk through the index, generating mailers.
    #------------------------------------------------------------------
    def __makeMailers(self):
        coverLetterParm = self.getParm("CoverLetter")

        # Cover letters aren't required for all directory types
        if coverLetterParm:
            coverLetterName = "%s/%s" % (self.getMailerIncludePath(),
                                         coverLetterParm[0])
            coverLetterTemplate = open(coverLetterName).read()
        else:
            coverLetterTemplate = None

        # Make mailers in index order
        for elem in self.getIndex():
            recip, doc = elem[2:]
            self.__makeMailer(recip, doc, coverLetterTemplate)

    #------------------------------------------------------------------
    # Generate everything needed to add one mailer package to the queue
    #------------------------------------------------------------------
    def __makeMailer(self, recip, doc, template):

        # Add document to the repository for tracking replies to the mailer.
        mailerId = self.addMailerTrackingDoc(doc, recip, self.getSubset())

        # Create a cover letter, if needed
        if template:
            address   = self.formatAddress(recip.getAddress())
            latex     = template.replace('@@ADDRESS@@', address)

            # Current thinking is to not include these elements - XXXX ASK BOB
            # addressee = "Dear %s:" % recip.getAddress().getAddressee()
            #latex     = latex.replace('@@SALUTATION@@', addressee)
            #docId     = "%d (Tracking ID: %d)" % (doc.getId(), mailerId)
            #latex     = latex.replace('@@DOCID@@', docId)

            basename  = 'CoverLetter-%d-%d' % (recip.getId(), doc.getId())
            jobType   = cdrmailer.PrintJob.COVERPAGE
            self.addToQueue(self.makePS(latex, 1, basename, jobType))

        # Customize the LaTeX for this copy of the mailer.
        nPasses   = doc.latex.getLatexPassCount()
        latex     = doc.latex.getLatex()
        latex     = latex.replace('@@DOCID@@', str(doc.getId()))
        latex     = latex.replace('@@MAILERID@@', str(mailerId))

        basename  = 'Mailer-%d-%d' % (recip.getId(), doc.getId())
        jobType   = cdrmailer.PrintJob.MAINDOC
        self.addToQueue(self.makePS(latex, nPasses, basename, jobType))

if __name__ == "__main__":
    suppressPrinting = 1    # For DEBUG, change to 1
    sys.exit(DirectoryMailer(int(sys.argv[1]), suppressPrinting).run())
