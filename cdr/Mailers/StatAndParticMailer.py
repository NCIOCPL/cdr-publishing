#----------------------------------------------------------------------
#
# $Id: StatAndParticMailer.py,v 1.9 2003-08-21 19:43:06 bkline Exp $
#
# Master driver script for processing initial protocol status and
# participant verification mailers.
#
# $Log: not supported by cvs2svn $
# Revision 1.8  2003/05/05 21:08:08  bkline
# Restricted mailers to lead orgs with (sort of) active statuses.
#
# Revision 1.7  2003/02/07 22:36:23  bkline
# Added call to UnicodeToLatex.convert() for title.
#
# Revision 1.6  2002/10/24 02:39:39  bkline
# Added code to handle worst-case combinations of protocol/recipient/org.
#
# Revision 1.5  2002/10/23 22:05:17  bkline
# Updated ancient code to prepare for final testing.
#
# Revision 1.4  2002/10/23 11:44:08  bkline
# Removed obsolete code.
#
# Revision 1.3  2002/09/12 23:29:51  ameyer
# Removed common routine from individual mailers to cdrmailer.py.
# Added a few trace statements.
#
# Revision 1.2  2002/01/23 17:14:58  bkline
# Modifications to accomodate changed requirements.
#
# Revision 1.1  2001/12/04 13:38:05  bkline
# Initial version
#
#----------------------------------------------------------------------

import cdr, cdrdb, cdrmailer, re, sys, UnicodeToLatex

#----------------------------------------------------------------------
# Derived class for PDQ Editorial Board Member mailings.
#----------------------------------------------------------------------
class StatusAndParticipantMailer(cdrmailer.MailerJob):

    #------------------------------------------------------------------
    # Overrides method in base class for filling the print queue.
    #------------------------------------------------------------------
    def fillQueue(self):
        self.__getRecipients()
        self.__makeIndex()
        self.__makeCoverSheet()
        self.__makeMailers()

    #------------------------------------------------------------------
    # Find lead organization personnel who should receive these mailers.
    #------------------------------------------------------------------
    def __getRecipients(self):
        """
        Trickier than most mailers, because not only can each document
        get mailed to more than one recipient (not unusual in itself), and
        different documents for the same recipient can go to different
        addresses (this also happens with some other mailers) but different
        documents for the same recipient at the same address can have a
        different organization associated with the recipient.  So we keep
        track of which Org objects we have already constructed (with the
        orgs dictionary) and we have a map of each address+document combo
        (self.__orgMap) which remembers which organization is used.

        As if this complication weren't enough, we also have to filter
        each package separately, because the content for a given protocol
        varies based on the lead org whose PUP is getting the mailer!
        This means that we can't take advantage of our usual optimization
        of filtering each document only once.

        To top it all off, I just discovered that we can have the same
        receipient for the *same* protocol with more than one lead
        organization!  Aargh!

        But wait, it gets even worse!  Organizations can now have more
        than one OrganizationType element!
        """
        docType  = "InScopeProtocol"
        orgPath  = "/InScopeProtocol/ProtocolAdminInfo/ProtocolLeadOrg"\
                   "/LeadOrganizationID/@cdr:ref"
        pupPath  = "/InScopeProtocol/ProtocolAdminInfo/ProtocolLeadOrg"\
                   "/LeadOrgPersonnel/Person/@cdr:ref"
        rolePath = "/InScopeProtocol/ProtocolAdminInfo/ProtocolLeadOrg"\
                   "/LeadOrgPersonnel/PersonRole"
        modePath = "/Organization/OrganizationDetails"\
                   "/PreferredProtocolContactMode"
        otPath   = "/Organization/OrganizationType"
        try:
            self.getCursor().execute("""\
                SELECT DISTINCT person.id,
                                person.title,
                                org.id,
                                org.title,
                                protocol.id,
                                protocol.title,
                                doc_version.num,
                                person_link.value,
                                org_type.value
                           FROM document person
                           JOIN query_term person_link
                             ON person_link.int_val = person.id
                           JOIN query_term person_role
                             ON person_role.doc_id = person_link.doc_id
                            AND LEFT(person_role.node_loc, 12) =
                                LEFT(person_link.node_loc, 12)
                           JOIN query_term lead_org
                             ON lead_org.doc_id = person_link.doc_id
                            AND LEFT(lead_org.node_loc, 8) =
                                LEFT(person_link.node_loc, 8)
                           JOIN query_term lead_org_status
                             ON lead_org_status.doc_id = lead_org.doc_id
                            AND LEFT(lead_org.node_loc, 8) =
                                LEFT(lead_org_status.node_loc, 8)
                           JOIN document org
                             ON org.id = lead_org.int_val
                           JOIN document protocol
                             ON protocol.id = lead_org.doc_id
                           JOIN doc_version
                             ON doc_version.id = protocol.id
                           JOIN pub_proc_doc
                             ON pub_proc_doc.doc_version = doc_version.num
                            AND pub_proc_doc.doc_id      = doc_version.id
                           JOIN query_term org_type
                             ON org_type.doc_id = org.id
                          WHERE pub_proc_doc.pub_proc = ?
                            AND lead_org.path         = '%s'
                            AND person_link.path      = '%s'
                            AND person_role.path      = '%s'
                            AND org_type.path         = '%s'
                            AND person_role.value     = 'Update person'
                            AND lead_org_status.value IN (
                                                   'Active',
                                                   'Approved-not yet active',
                                                   'Temporarily closed')
                            AND NOT EXISTS (SELECT *
                                              FROM query_term contact_mode
                                             WHERE contact_mode.path = '%s'
                                               AND contact_mode.doc_id =
                                                   lead_org.int_val)""" %
                                (orgPath, pupPath, rolePath, otPath, modePath),
                                (self.getId(),))
            rows = self.getCursor().fetchall()
            self.__combos   = {}
            self.__orgTypes = {}
            orgs            = {}
            for row in rows:
                (recipId, recipName, orgId, orgName, docId, docTitle,
                 docVersion, addrLink, orgType) = row
                key = (addrLink, docId, orgId)
                #print "recipId=%d recipName=%s orgId=%d orgName=%s docId=%d docTitle=%s docVersion=%d addrLink=%s orgType=%s" % (
                #    recipId, recipName, orgId, orgName, docId, docTitle, docVersion, addrLink, orgType)
                recipient = self.getRecipients().get(addrLink)
                document  = self.getDocuments().get(docId)
                org       = orgs.get(orgId)
                if not recipient:
                    self.log("found recipient at address %s" % addrLink)
                    addr = self.__getRecipAddress(addrLink)
                    recipient = cdrmailer.Recipient(recipId, recipName, addr)
                    self.getRecipients()[addrLink] = recipient
                if not document:
                    document = cdrmailer.Document(docId, docTitle, docType,
                                                  docVersion)
                    self.getDocuments()[docId] = document
                if not org:
                    org = cdrmailer.Org(orgId, orgName)
                    orgs[orgId] = org
                    self.__orgTypes[orgId] = [orgType]
                else:
                    if not orgType in self.__orgTypes[orgId]:
                        self.__orgTypes[orgId].append(orgType)
                if not self.__combos.has_key(key):
                    self.__combos[key] = (recipient, document, org)
        except cdrdb.Error, info:
            raise "database error finding recipients: %s" % str(info[1][0])

    #------------------------------------------------------------------
    # Find a protocol lead organization personnel's mailing address.
    #------------------------------------------------------------------
    def __getRecipAddress(self, fragLink):
        try:
            docId, fragId = fragLink.split("#")
        except:
            raise "Invalid fragment link: %s" % fragLink
        parms = (("fragId", fragId),)
        filters = ["name:Person Address Fragment With Name"]
        rsp = cdr.filterDoc(self.getSession(), filters, docId, parm = parms)
        if type(rsp) in (type(""), type(u"")):
            raise "Unable to find address for %s: %s" % (str(fragLink), rsp)
        return cdrmailer.Address(rsp[0])

    #------------------------------------------------------------------
    # Generate an index of the mailers in order of postal codes.
    # Using new criterion for determining whether an organization is
    # a cooperative group supplied by Lakshmi in email dated 21Oct2002.
    #------------------------------------------------------------------
    def __makeIndex(self):
        self.__index     = []
        coopType         = "NCI-supported clinical trials group"
        for key in self.__combos.keys():
            recip, doc, org = self.__combos[key]
            address         = recip.getAddress()
            country         = address.getCountry()
            postalCode      = address.getPostalCode()
            orgTypes        = self.__orgTypes[org.getId()]
            isCoop          = coopType in orgTypes and 1 or 0
            sortKey         = (country, postalCode, recip, isCoop, doc, org)
            self.__index.append(sortKey)
        self.__index.sort()

    #------------------------------------------------------------------
    # Generate a main cover page and add it to the print queue.
    #------------------------------------------------------------------
    def __makeCoverSheet(self):
        filename = "MainCoverPage.txt"
        f = open(filename, "w")
        f.write("\n\n%s\n\n" % self.getSubset())
        f.write("Job Number: %d\n\n" % self.getId())
        for country, zip, recip, isCoop, doc, org in self.__index:
            title = doc.getTitle()
            f.write("  Recipient: %d\n" % recip.getId())
            f.write("       Name: %s\n" % recip.getName())
            f.write("    Country: %s\n" % country)
            f.write("Postal Code: %s\n" % zip)
            f.write("   Protocol: %d\n" % doc.getId())
            f.write("      Title: %s\n" % UnicodeToLatex.convert(title[:60]))
            f.write("     Org ID: %d\n" % org.getId())
            f.write("   Org Name: %s\n\n" % org.getName())
        f.write("\f")
        f.close()
        job = cdrmailer.PrintJob(filename, cdrmailer.PrintJob.PLAIN)
        self.addToQueue(job)

    #------------------------------------------------------------------
    # Walk through the index, generating protocol mailers.
    #------------------------------------------------------------------
    def __makeMailers(self):

        # Get the templates for the cover letters.        
        baseDir                = self.getMailerIncludePath() + "/"
        coverLetterParmCoop    = self.getParm("CoverLetterCoop")
        coverLetterParmNonCoop = self.getParm("CoverLetterNonCoop")
        coverLetterNameCoop    = baseDir + coverLetterParmCoop[0]
        coverLetterNameNonCoop = baseDir + coverLetterParmNonCoop[0]
        coverLetterCoopFile    = open(coverLetterNameCoop)
        coverLetterNonCoopFile = open(coverLetterNameNonCoop)
        coverLetterCoop        = coverLetterCoopFile.read()
        coverLetterNonCoop     = coverLetterNonCoopFile.read()
        coverLetterCoopFile.close()
        coverLetterNonCoopFile.close()

        # Gather the mailers into sets.  Everything going to the same
        # recipient address is collected, and then separated (if needed)
        # between the mailers for lead orgs which are cooperative groups
        # and for those which are not cooperative groups (because coops
        # and non-coops get different cover letters).  The recipFlagCombo
        # variable is a tuple representing a recipient address and the
        # flag for cooperative versus non-cooperative groups.  For each
        # of these recipient-flag combinations we collect all of the
        # combinations of protocol+lead org combinations which will be
        # sent to this recipient with the appropriate cover letter.
        # These sub-combinations (protocol doc + lead org) are represented
        # by the docOrgCombo(s) variables.
        lastRecipFlagCombo = None
        sets               = []
        for elem in self.__index:
            recip, isCoop, doc, org = elem[2:]
            recipFlagCombo = (recip, isCoop)
            docOrgCombo    = (doc, org)
            if lastRecipFlagCombo != recipFlagCombo:
                lastRecipFlagCombo = recipFlagCombo
                docOrgCombos       = []
                currentSet         = (recipFlagCombo, docOrgCombos)
                sets.append(currentSet)
            docOrgCombos.append(docOrgCombo)

        # Pump out each set of mailers.
        setNumber = 0
        for recipFlagCombo, docOrgCombos in sets:
            recip, isCoop = recipFlagCombo
            setNumber += 1

            # Create a mailing label.
            address   = recip.getAddress()
            latex     = self.createAddressLabelPage(address)
            basename  = 'MailingLabel-%d' % setNumber
            jobType   = cdrmailer.PrintJob.COVERPAGE
            self.addToQueue(self.makePS(latex, 1, basename, jobType))

            # Create a cover letter.
            template  = isCoop and coverLetterCoop or coverLetterNonCoop
            address   = self.formatAddress(address)
            latex     = template.replace('@@PUPADDRESS@@', address)
            basename  = 'CoverLetter-%d' % setNumber
            jobType   = cdrmailer.PrintJob.COVERPAGE
            self.addToQueue(self.makePS(latex, 1, basename, jobType))

            # Append each mailer to the set.
            for doc, org in docOrgCombos:
                self.__makeMailer(recip, doc, org)
        

    #------------------------------------------------------------------
    # Create a protocol abstract mailer.
    #------------------------------------------------------------------
    def __makeMailer(self, recip, doc, org):

        # Add document to the repository for tracking replies to the mailer.
        mailerId = self.addMailerTrackingDoc(doc, recip, self.getSubset(),
                                             protOrgId = org.getId())

        # Create the LaTeX for the document.
        orgId     = org.getId()
        docId     = doc.getId()
        self.log("generating LaTeX for CDR%010d" % docId)
        self.log("lead Organization CDR%010d" % orgId)
        filters   = ['name:InScopeProtocol Status and Participant Mailer']
        parms     = [('leadOrgId', 'CDR%010d' % orgId)]
        doc.latex = self.makeLatex(doc, filters, "StatusCheck", parms)

        # Customize the LaTeX for this copy of the protocol.
        nPasses   = doc.latex.getLatexPassCount()
        latex     = doc.latex.getLatex()
        latex     = latex.replace('@@MAILERID@@', str(mailerId))
        latex     = latex.replace('@@DOCID@@', str(docId))
        basename  = 'Mailer-%d-%d-%d' % (recip.getId(), docId, orgId)
        jobType   = cdrmailer.PrintJob.MAINDOC
        self.addToQueue(self.makePS(latex, nPasses, basename, jobType))

if __name__ == "__main__":
    sys.exit(StatusAndParticipantMailer(int(sys.argv[1])).run())
