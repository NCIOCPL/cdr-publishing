#----------------------------------------------------------------------
#
# $Id: DirectoryMailer.py,v 1.2 2002-09-17 18:19:57 ameyer Exp $
#
# Master driver script for processing directory mailers.
#
# $Log: not supported by cvs2svn $
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
    def __init__(self, jobId):
        # Super class constructor
        cdrmailer.MailerJob.__init__(self, jobId)

        # Add a protocol count.  See __addProtocolInfo() and __makeMailer()
        self.__protocolCount = 0

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
        self.__getRecipients()

        # Retrieve the actual documents themselves, performing
        #   any necessary filtering and LaTeX generation, and
        #   writing the generated print images to disk
        self.__createMailerDocs()

        # Create an index of the documents
        self.makeIndex()

        # Generate a cover sheet for the job a whole, listing
        #   each individual mailer recipient
        self.__makeCoverSheet()

        # Fill the print queue with recipient+document object pairs
        #   telling the later print steps the order of printing
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

            # For directories, the document of the recipient is usually
            #   same as the document itself (but not always).
            # Assume they're the same for now.
            # Assume no remail tracker for now.
            recipId = docId
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
                # XXXX THIS ASSERTION MAY BE FALSE - CHECK - XXXX
                assert tempList[0][0] == docId, \
                    "Directory remailer should have recipient=doc id, but " \
                    "recipient=%d, document=%d" % (tempList[0][0], docId)

            # Filters are different for physicians and organizations
            # XXXX - These filters are certainly wrong
            #        I'll need to do more, possibly including
            #        writing custom filters for this purpose, though
            #        it seems like I shouldn't have to.
            if self.getParm ('docType')[0] == 'Person':
                addrFilters = ['name:Person Address Fragment With Name']
                addrFilterParms = []
            else:
                # XXXX - This one has to be changed to address to
                #        name = 'Administrator' if no CIPS contact
                #        Other changes may also be required
                addrFilters = ['name:Org Locations for Linking Persons']
                addrFilterParms = []

            # Find or create a recipient object for this doc
            # It may be rare to find one person as the contact for
            #   multiple organizations, but could happen
            recip = recipients.get(recipId)

            # If not found (the normal case), create recipient
            if not recip:
                # Use the filter module to generate an address
                resp = cdr.filterDoc(self.getSession(), addrFilters,
                                     recipId, addrFilterParms)

                # Response should be list of filtered doc + messages
                # If it's a single string, it's an error message
                if type(resp)==type("") or type(resp)==type(u""):
                    # XXXX DO WE HAVE A MORE FAIL-SOFT WAY TO HANDLE
                    #      THIS PROBLEM?
                    raise "Unable to find address for %d: %s" % (recipId, resp)

                # XXXX - May require post-processing here, depending on
                #   filters
                # I'll use the one Bob did - but may not need it in future
                addrXml = resp[0].replace("<ReportBody", "<Address")
                addrXml = addrXml.replace("</ReportBody>", "</Address>")

                # Create address and recipient object
                address = cdrmailer.Address (addrXml)
                recip   = cdrmailer.Recipient (recipId, address.getAddressee(),
                                               address)

                # Add the recipient to the dictionary
                recipients[recipId] = recip

            # We may need a remailer id for this recipient for the
            #   RemailerFor field in the new tracking document
            recip.remailTracker = trackId

            # Append the current document to the list of those that
            #   this recipient will receive
            recip.getDocs().append (docId)

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

                # Find out if physician is listed in any protocols
                self.__addProtocolInfo (doc)

                # If there are any, add a filter to put in
                #   @@PROTOCOL_AFFIL_COUNT@@ and
                #   @@SPECIFIC_PROTOCOL_ADDRESSES@@
                if doc.__protocolCount > 0:
                    # XXXX THIS DOESN'T EXIST YET
                    # filters.add ("name:Physician Protocol Mailer Variables")
                    pass

            self.log("generating LaTeX for CDR%010d" % docId)
            doc = self.getDocuments()[docId]
            doc.latex = self.makeLatex(doc, filters, '')

    #------------------------------------------------------------------
    # Generate a main cover page and add it to the print queue.
    # This lists all the mailers included in the job.
    #------------------------------------------------------------------
    def __makeCoverSheet(self):
        filename = "MainCoverPage.txt"
        f = open(filename, "w")
        f.write("\n\n%s\n\n" % self.getSubset())
        f.write("Job Number: %d\n\n" % self.getId())
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
    # Walk through the index, generating protocol mailers.
    #------------------------------------------------------------------
    def __makeMailers(self):
        coverLetterParm     = self.getParm("CoverLetter")
        if not coverLetterParm:
            raise StandardError ("CoverLetter parameter missing")
        coverLetterName     = "../%s" % coverLetterParm[0]
        coverLetterTemplate = open(coverLetterName).read()
        for elem in self.getIndex():
            recip, doc = elem[2:]
            self.__makeMailer(recip, doc, coverLetterTemplate)

    #------------------------------------------------------------------
    # Add protocol specific information for physician mailers
    # Must only be called on physicians
    #------------------------------------------------------------------
    def __addProtocolInfo(self, personDoc):

        """
        Look in the query term table for a physician's ID to see
        if he is listed as a lead organization or other site organization
        person.  If so, gather the information about him that must
        be printed in the mailer.

        Pass:
            Document object for person.

        Return:
            None.
                Information is added to the document object as:
                List containing for each lead organization particpation,
                  a sublist of:
                    Protocol document ID
                    Protocol title
                    Specific address if present (usually None)
                List containing for each site organization particpation,
                  a sublist of:
                    Protocol document ID
                    Protocol title
                    Specific phone number if present (usually None)
        """

        # Person not yet known to be listed in any protocols
        personDoc.__protocolParticipateCount = 0
        personDoc.__leadOrgRows = []
        personDoc.__orgSiteRows = []

        # Search query_term index to find protocols on which this
        #   person appears, together with any for which he has a
        #   protocol specific address
        try:
            # Find out where user is a LeadOrg person
            self.getCursor().execute ("""
                SELECT DISTINCT qt.doc_id
                  FROM query_term qt
                  JOIN document doc
                    ON qt.doc_id = doc.id
                 WHERE qt.path='/InScopeProtocol/ProtocolAdminInfo' +
                               '/ProtocolLeadOrg/LeadOrgPersonnel' +
                               '/Person/@cdr:ref'
                   AND qt.int_val = ?""", (personDoc.getId(),))

            # Fetch and add them to the Document object
            personDoc.__leadOrgRows = self.getCursor().fetchall()

            # Find out where user is simply an OrgSiteContact person
            self.getCursor().execute ("""
                SELECT DISTINCT qt.doc_id
                  FROM query_term qt
                  JOIN document doc
                    ON qt.doc_id = doc.id
                 WHERE qt.path='/InScopeProtocol/ProtocolAdminInfo' +
                               '/ProtocolLeadOrg/ProtocolSites' +
                               '/OrgSiteContact/Person/@cdr:ref'
                   AND qt.int_val = ?""", (personDoc.getId(),))

            # Fetch and add them to the Document object
            personDoc.__orgSiteRows = self.getCursor().fetchall()

            # Save the count
            personDoc.__protocolCount = \
                len (personDoc.__leadOrgRows) + \
                len (personDoc.__orgSiteRows)

            # XXXX - LEFT OFF HERE - XXXX
            # HAVE TO EITHER BRUTE FORCE SEARCH THE LINKED PROTOCOLS
            # OR DO ONE OF SEVERAL CLEVER, BUT MORE PROGRAMMING INTENSIVE
            # THINGS TO ACTUALLY GET THE SpecificContact and SpecificPhone
            # ELEMENTS.

        except cdrdb.Error, info:
            raise "database error finding person's protocols: %s" % \
                   str(info[1][0])

    #------------------------------------------------------------------
    # Replace @@ variables with information from the protocols
    #------------------------------------------------------------------
    def __replaceProtocolPlaceHolders (self, doc):
        pass # XXXX

    #------------------------------------------------------------------
    # Generate everything needed to add one mailer package to the queue
    #------------------------------------------------------------------
    def __makeMailer(self, recip, doc, template):

        # Add document to the repository for tracking replies to the mailer.
        mailerId = self.addMailerTrackingDoc(doc, recip, self.getSubset())

        # Create a cover letter.
        address   = self.formatAddress(recip.getAddress())
        addressee = "Dear %s:" % recip.getAddress().getAddressee()
        docId     = "%d (Tracking ID: %d)" % (doc.getId(), mailerId)
        latex     = template.replace('@@ADDRESS@@', address)
        latex     = latex.replace('@@SALUTATION@@', addressee)
        latex     = latex.replace('@@DOCID@@', docId)
        basename  = 'CoverLetter-%d-%d' % (recip.getId(), doc.getId())
        jobType   = cdrmailer.PrintJob.COVERPAGE
        self.addToQueue(self.makePS(latex, 1, basename, jobType))

        # Customize the LaTeX for this copy of the protocol.
        nPasses   = doc.latex.getLatexPassCount()
        latex     = doc.latex.getLatex()
        latex     = latex.replace('@@Recipient@@', recip.getName())
        latex     = latex.replace('@@MailerDocId@@', str(mailerId))

        # Physicians may have protocol info to add
        if doc.__protocolCount > 0:
            self.__replaceProtocolPlaceHolders (doc)

        basename  = 'Mailer-%d-%d' % (recip.getId(), doc.getId())
        jobType   = cdrmailer.PrintJob.MAINDOC
        self.addToQueue(self.makePS(latex, nPasses, basename, jobType))

if __name__ == "__main__":
    sys.exit(DirectoryMailer(int(sys.argv[1])).run())
