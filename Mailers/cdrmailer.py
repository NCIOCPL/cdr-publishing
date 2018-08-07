#----------------------------------------------------------------------
# Base class for mailer jobs
# BZIssue::5018
#----------------------------------------------------------------------
import cdr, cdrdb, cdrxmllatex, os, re, sys, time, xml.dom.minidom, socket
import UnicodeToLatex, tarfile, glob, shutil, RtfWriter, cdrdocobject

debugCtr = 1

_LOGFILE = "d:/cdr/log/mailer.log"
_STAPLE_NAME = "duplex-stapled"

#------------------------------------------------------------------
# Constants for adding a person's title to his address
#------------------------------------------------------------------
from cdrdocobject import TITLE_OMITTED, TITLE_AFTER_NAME, TITLE_AFTER_ORG

#----------------------------------------------------------------------
# Object for a personal name.
#----------------------------------------------------------------------
from cdrdocobject import PersonalName

#----------------------------------------------------------------------
# Object for managing mailer processing.
#----------------------------------------------------------------------
class MailerJob:
    """
    Base class for mailer job processing.  Cannot be used directly.
    Public methods include:

        run()
            Top-level method to invoke job processing.

        log(message)
            Appends progress or error information to logfile.

        fillQueue()
            Overridden by derived classes to define processing
            appropriate to each mailer type.  See documentation
            for this method below.

        addToQueue(job)
            Called by the derived classes' implementations of
            fillQueue() to add a PrintJob object to the print
            queue for the mailer job.

        addMailerTrackingDoc(doc, recipient, mailerType)
            Invoked by the derived classes' imlementations of
            fillQueue() to insert a Mailer document into the CDR.

        formatAddress(addr)
            Formats address information into a block of printable
            text lines and returns the block.

        createAddressLabelPage(addr, upperCase)
            Creates LaTeX for a sheet containing just an address label.
            If upperCase is true (which it is by default, the address
            strings are uppercased before being marked up for LaTeX.

        getCipsContactAddress(id)
            Returns an Address object for the ContactDetail information
            in a Person document identified as the CIPS contact address.

        getOrganizationAddress (id):
            Returns an Address object for the ContactDetail information
            in an Organization document.  Handles cases of directly
            referenced CIPSContactPerson, and generic Administrators.

        makeIndex()
            Builds an index list of recipients from the dictionary
            of Recipient objects and sorts it by country and
            postalCode.

        makeLatex(doc, filters, mailType)
            Obtains a document from the repository, applies the
            caller's filters to it, and uses the cdrxmllatex
            module to generate the appropriate LaTeX source for
            the specified mailer type.

        makePS(latex, passCount, jobName, jobType)
            Takes the LaTeX source from an in-memory string and
            writes it out as converted PostScript, returning the
            new PrintJob object corresponding to the file.

        getId()
            Returns the ID for the publishing job.

        getSubset()
            Returns the string identifying the specific type
            of publishing job.

        getCursor()
            Returns object for executing database queries.

        getSession()
            Returns key for current CDR session.

        getDocIds()
            Returns the tuple of document IDs found in the
            pub_proc_doc table.

        getRecipients()
            Returns the dictionary containing the Recipient
            objects associated with this job.  Populated by
            the derived classes during the process of filling
            the print queue.  For jobs which use a single
            address for all packages sent to a given person,
            the Person document ID is used as the dictionary
            key.  For jobs in which different addresses can
            be used for the same person, the keys used for
            the dictionary are the fragment links which
            identify a person and a specific address, so
            the same person can appear more than once if
            multiple addresses are used.

        getDocuments()
            Returns the dictionary containing the Document objects
            for the documents which will be mailed out for this job.
            Populated by the derived classes during the process
            of filling the print queue.

        getParm(name)
            Returns a possibly empty tuple of values stored in
            the pub_proc_parm table for this job.  Filled
            by the base class.

        getDeadline()
            Returns a string in the form YYYY-MM-DD for the deadline
            by which the mailer must be responded to.  Can be
            overridden by the derived classes as appropriate.

        getJobTime()
            Returns a string in the form YYYY-MM-DDTHH:MM:SS
            representing the date/time the job processing began.

        commit()
            Commits the current open database transaction.
    """

    #------------------------------------------------------------------
    # Class-level values.
    #------------------------------------------------------------------
    ### __CDR_EMAIL     = "cdr@%s.nci.nih.gov" % socket.gethostname()
    __TIER          = cdr.Tier()
    __CDR_EMAIL     = "PDQ Operator <NCIPDQoperator@mail.nih.gov"
    __SMTP_RELAY    = "MAILFWD.NIH.GOV"
    __LOGFILE       = _LOGFILE
    __DEF_PRINTER   = "\\\\CIPSFS1\\HP8100"
    __INCLUDE_PATH  = "d:/cdr/Mailers/include"
    __TEMPLATE_FILE = __INCLUDE_PATH + "/template.tex"
    __ERR_PATTERN   = re.compile("<Err>(.*)</Err>")
    __LATEX_OPTS    = "-halt-on-error -quiet -interaction batchmode "\
                      "-include-directory d:/cdr/mailers/style"

    #------------------------------------------------------------------
    # Constructor for base class.
    #------------------------------------------------------------------
    def __init__(self, jobId, batchPrinting = 1):
        """
        Parameters:
            jobId               - Integer for publication job number.
        """
        self.__id               = jobId
        self.__nMailers         = 0
        self.__docIds           = []
        self.__recipients       = {}
        self.__index            = []
        self.__documents        = {}
        self.__parms            = {}
        self.__printer          = MailerJob.__DEF_PRINTER
        self.__batchPrinting    = batchPrinting
        self.__letterLink       = ""
        self.__cursor           = None
        self.__email            = None

    #------------------------------------------------------------------
    # Public access methods.
    #------------------------------------------------------------------
    def getId        (self): return self.__id
    def getCursor    (self): return self.__cursor
    def getSubset    (self): return self.__subset
    def getSession   (self): return self.__session
    def getDeadline  (self): return self.__deadline
    def getDocIds    (self): return self.__docIds
    def getRecipients(self): return self.__recipients
    def getIndex     (self): return self.__index
    def getDocuments (self): return self.__documents
    def getJobTime   (self): return self.__now
    def getCount     (self): return self.__nMailers
    def getMailerIncludePath(self): return self.__INCLUDE_PATH
    def bumpCount    (self): self.__nMailers += 1
    def printDirect  (self): self.__batchPrinting = 0
    def addToQueue   (self, job):   self.__queue.append(job)
    def commit       (self):        self.__conn.commit()
    def getParm      (self, name):
        v = self.__parms.get(name)
        return v and tuple(v) or ()

    #------------------------------------------------------------------
    # Driver for mailer job processing.
    #------------------------------------------------------------------
    def run(self):
        """
        Invokes the processing for a CDR mailer job.  Catches and
        logs all exceptions.  Returns 0 for success and 1 for failure.
        """
        try:
            self.log("******** starting mailer job ********")
            self.__loadSettings()
            self.log("~~Finished __loadSettings")
            self.__mailerCleanup()
            self.log("~~Finished __mailerCleanup")
            self.__createQueue()
            self.log("~~Finished __createQueue")
            self.fillQueue()
            self.__printQueue(self.__batchPrinting)
            self.createEmailers()
            self.createRtfMailers()
            self.__cleanup("Success", "Processed %d mailers" % self.__nMailers)
            self.log("******** finished mailer job ********")
            return 0
        except:
            (eType, eValue) = sys.exc_info()[:2]
            errMessage = eValue or eType
            self.log("ERROR: %s" % errMessage, tback=1)
            self.__packageFailureFiles()
            self.__cleanup("Failure", errMessage)
            return 1

    #------------------------------------------------------------------
    # Append message to logfile.
    #------------------------------------------------------------------
    def log(self, message, tback=None):
        """
        Appends progress or error information to a log file.  Each
        entry is stamped with the current date and time and the
        number of the current publication job.  No return value.
        No exceptions raised.
        """
        try:
            msg = "Job %d: %s" % (self.__id, message)
            cdr.logwrite (msg, MailerJob.__LOGFILE, tback)
            # now = time.ctime(time.time())
            # msg = "[%s] Job %d: %s" % (now, self.__id, message)
            # open(MailerJob.__LOGFILE, "a").write(msg + "\n")
        except:
            pass

    #------------------------------------------------------------------
    # Placeholder for method to populate the print queue for the job.
    #------------------------------------------------------------------
    def fillQueue(self):
        """
        The primary responsibility of the classes derived from MailerJob
        is to provide a definition of this method.  This method must
        populate the object's print queue by invoking addToQueue() with
        instances of the PrintJob class, defined below.  Each PrintJob
        object must represent a file which is ready to be written
        directly to the printer (for example, PostScript, or plain text,
        but not RTF files or Microsoft Word documents).  Furthermore,
        for each copy of each document added to the print queue, the
        implementation of fillQueue() must invoke the addMailerTrackingDoc()
        method to add a new document to the repository for tracking the
        responses to the mailer.  The mailerType argument passed to that
        method must be a string which matches one of the valid values for
        MailerType enumerated in the schema for Mailer documents.

        The files created for the queue should be written to the
        current working directory (as should any intermediate working
        files), and the filenames provided to the constructor for the
        PrintJob objects should not include any path information.
        """
        raise cdr.Exception("fillQueue() must be defined by derived class")

    #------------------------------------------------------------------
    # Placeholder for method to create electronic mailers (if any).
    #------------------------------------------------------------------
    def createEmailers(self):
        """
        Do nothing if the derived class does not override this method.
        """
        pass

    #------------------------------------------------------------------
    # Placeholder for method to create rtf mailers (if any).
    #------------------------------------------------------------------
    def createRtfMailers(self):
        """
        Do nothing if the derived class does not override this method.
        """
        pass

    #------------------------------------------------------------------
    # Generate a document for tracking a mailer.
    #------------------------------------------------------------------
    def addMailerTrackingDoc(self, doc, recipient, mailerType,
                             remailerFor = None, protOrgId = None,
                             email = None):
        """
        Parameters:
            doc         - Object of type Document, defined below
            recipient   - Object of type Recipient, defined below
            mailerType  - String containing a values matching the
                          list of valid values for MailerType
                          enumerated in the schema for Mailer docs.
            remailerFor - optional integer for the document ID of
                          an earlier mailer that was sent out and
                          never responded to, and for which this
                          is a followup remailer.
            protOrgId   - string or integer form of CDR ID for a
                          protocol's lead organization (the one to
                          which this mailer is being sent); used to
                          distinguish between Status and Participant
                          mailers for the same protocol in the
                          same job.
            email       - address used for electronic mailer.
        Return value:
            Integer ID for the newly inserted Mailer document.
        """

        if remailerFor:
            remailerFor = "\n   <RemailerFor cdr:ref='%s'/>" % \
                          cdr.normalize(remailerFor)
        else:
            remailerFor = ""
        if protOrgId:
            protOrg     = "\n   <ProtocolOrg cdr:ref='%s'/>" % \
                          cdr.normalize(protOrgId)
        else:
            protOrg     = ""
        if email:
            mode        = "Web-based"
            address     = """\
   <MailerAddress>
    <Email>%s</Email>
   </MailerAddress>""" % email
        else:
            mode        = "Mail"
            address     = recipient.getAddress().getXml()
        recipId         = "CDR%010d" % recipient.getId()
        docId           = "CDR%010d" % doc.getId()
        xml             = u"""\
<CdrDoc Type="Mailer">
 <CdrDocCtl>
  <DocTitle>Mailer for document %s sent to %s</DocTitle>
 </CdrDocCtl>
 <CdrDocXml><![CDATA[
  <Mailer xmlns:cdr="cips.nci.nih.gov/cdr">
   <Type Mode='%s'>%s</Type>%s
   <JobId>%d</JobId>
   <Recipient cdr:ref="%s">%s</Recipient>%s
%s
   <Document cdr:ref="%s">%s</Document>
   <Sent>%s</Sent>
   <Deadline>%s</Deadline>
  </Mailer>]]>
 </CdrDocXml>
</CdrDoc>
""" % (docId, recipId, mode, mailerType, remailerFor, self.__id, recipId,
       recipient.getName(), protOrg, address, docId, doc.getTitle(),
       self.__now, self.getDeadline())
        rsp   = cdr.addDoc(self.__session, doc = xml.encode('utf-8'),
                           checkIn = "Y", ver = "Y", val = 'Y')
        match = self.__ERR_PATTERN.search(rsp)
        if match:
            err = match.group(1)
            raise cdr.Exception("failure adding tracking document for %s: %s" %
                                (docId, err))
        self.__nMailers += 1
        digits = re.sub("[^\d]", "", rsp)
        return int(digits)

    #------------------------------------------------------------------
    # Convert Unicode string to Latin-1 character set.
    #------------------------------------------------------------------
    def encodeLatin1(self, unicodeString):
        return unicodeString.encode('latin-1')

    #------------------------------------------------------------------
    # Retrieve the CIPS contact Address for a mailer recipient.
    #------------------------------------------------------------------
    def getCipsContactAddress(self, id, withPersonTitle=TITLE_OMITTED):
        """
        Constructs and returns a new Address object for the document.

        Parameters:
            id              - Integer ID for CDR Person document.
            docType         - 'Person' (default) or 'Organization'
            withPersonTitle - For Address constructor.
        Return value:
            Returns an Address object for the CIPS contact.
        """
        # Make string version of id
        docId  = cdr.normalize(id)

        # Find fragment ID for CIPS contact location in Person doc
        rows = cdr.getQueryTermValueForId (
                '/Person/PersonLocations/CIPSContact', id, self.__conn)
        if not rows:
            raise cdr.Exception("no CIPSContact for %s" % docId)
        fragId = rows[0]

        # Filter to create AddressElement XML
        filters = ["name:Person Address Fragment With Name"]
        result  = cdr.filterDoc(self.__session, filters, docId,
                                parm = (('fragId', fragId),))

        # Expecting tuple of xml fragment, messages.  Single string is error.
        if type(result) == type(""):
            raise cdr.Exception("failure extracting contact address "
                                "for %s: %s" % (docId, result))
        return Address(result[0], withPersonTitle)

    #------------------------------------------------------------------
    # Retrieve the contact address for a board member.
    #------------------------------------------------------------------
    def getBoardMemberAddress(self, personId, memberId):

        # Find fragment ID for CIPS contact location in BoardMemberInfo doc
        path  = '/PDQBoardMemberInfo/BoardMemberContact/PersonContactID'
        rows  = cdr.getQueryTermValueForId(path, memberId, self.__conn)

        # Filter to create AddressElement XML
        if rows:
            docId   = cdr.normalize(personId)
            parms   = (('fragId', rows[0]),)
            filters = ["name:Person Address Fragment With Name"]
        else:
            docId   = cdr.normalize(memberId)
            parms   = ()
            filters = ["name:Board Member Address Fragment With Name"]
        result = cdr.filterDoc(self.__session, filters, docId, parm = parms)
        if type(result) in (type(""), type(u"")):
            raise cdr.Exception("failure extracting contact address "
                                "for %s: %s" % (docId, result))
        return Address(result[0])

    #------------------------------------------------------------------
    # Retrieve the CIPS contact Address object for an Organization
    #------------------------------------------------------------------
    def getOrganizationAddress (self, id):
        """
        Parameters:
            id - Integer ID of the organization document.
        Return value:
            Address object for organization.
        """
        # Default 'name' of the recipient
        nameStr = 'Administrator'

        # See if we have a CIPS contact person whose real name we can use
        rows = cdr.getQueryTermValueForId (
             '/Organization/OrganizationDetails/CIPSContactPerson/@cdr:ref',
             id, self.__conn)
        if rows:
            # Construct and Address object for person, to get real name
            # Fatal error if we can't find one
            personAddr = self.getCipsContactAddress (rows[0])
            nameStr = personAddr.getAddressee()

        # Find the fragment id in the Organization doc for
        #   the address we need to send to
        # Filter the organization to construct an address
        rows = cdr.getQueryTermValueForId (
             '/Organization/OrganizationLocations/CIPSContact',
             id, self.__conn)
        if not rows:
            raise cdr.Exception("No CIPSContact element found for "
                                "Organization %d" % id)

        filters = ["name:Organization Address Fragment"]
        parms   = (("fragId", rows[0]),)
        result  = cdr.filterDoc(self.__session, filters, id, parm=parms)

        # Expecting tuple of xml fragment, messages.  Single string is error.
        if type(result) == type(""):
            raise cdr.Exception("failure extracting contact address "
                                "for %d: %s" % (id, result))

        # Construct an address from returned XML
        orgAddr = Address(result[0])

        # Add or replace the name string with the one we constructed above
        orgAddr.setAddressee (nameStr)

        return orgAddr

    #------------------------------------------------------------------
    # Generate an index of the mailers in order of country + postal code.
    #------------------------------------------------------------------
    def makeIndex(self):
        self.__index   = []
        recipients     = self.getRecipients()
        for recipKey in recipients.keys():
            recip      = recipients[recipKey]
            address    = recip.getAddress()
            country    = address.getCountry()
            postalCode = address.getPostalCode()
            for doc in recip.getDocs():
                self.__index.append((country, postalCode, recip, doc))
        self.__index.sort()

    #------------------------------------------------------------------
    # Generate LaTeX source for a mailer document.
    #------------------------------------------------------------------
    def makeLatex(self, doc, filters, mailType = '', parms = None):
        """
        Parameters:
            doc         - Object of type Document, defined below
            filters     - List of names of filters to be applied
                          to the document's XML.
            mailType    - String used by the makeLatex() function
                          of the cdrxmllatex module to distinguish
                          between different mailer types produced
                          for this document's type; one of:
                                "initial"
                                "update"
                                "reminder"
            parms       - possibly empty set of parameters for filtering.
        Return value:
            Returns an object with the following methods:
                getLatex()          - reference to string with
                                      LaTeX source
                getLatexPassCount() - number of times to run
                                      the LaTeX processor on the
                                      source
                getStatus()         - 0 for success
                getMessages()       - tuple of informational or
                                      warning messages
        """

        parm = parms or []
        docId = cdr.normalize(doc.getId())
        result = cdr.filterDoc(self.__session, filters, docId, parm = parm,
                               docVer = doc.getVersion())
        if type(result) in (type(""), type(u"")):
            raise cdr.Exception("failure filtering document %s: %s" %
                                (docId, result))
        try:
            global debugCtr
            fname = "%d.xml" % debugCtr
            debugCtr += 1
            open(fname, "w").write(result[0])
            docDom = xml.dom.minidom.parseString(result[0])
            return cdrxmllatex.makeLatex(docDom, doc.getDocType(),
                                         mailType, self.log)
        except:
            (eType, eValue) = sys.exc_info()[:2]
            cdr.logwrite("Contents of result[0] when following exception "
                         "raised:\n%s"\
                         % result[0], MailerJob.__LOGFILE, tback = True)
            eMsg = eValue or eType
            raise cdr.Exception("failure generating LaTeX for %s: %s" %
                                (docId, eMsg))

    #------------------------------------------------------------------
    # Create a formatted address block from an Address object.
    #------------------------------------------------------------------
    def formatAddress(self, addr):
        return addr.format().getBlock()

    #------------------------------------------------------------------
    # Create LaTeX for a sheet containing just an address label.
    #------------------------------------------------------------------
    def createAddressLabelPage(self, addr, upperCase = 1):
        """
        Parameters:
            addr        - Object representing an address.
            upperCase   - Optional flag requesting that the address
                          strings be converted to uppercase.
        Notes:
            The window for the address labels is small, and the
            envelope is larger than the sheet, so we drop the
            country name line for U.S. addresses to save space.
        Return value:
            String containing LaTeX for address label sheet.
        """
        formattedAddress = addr.format(upperCase = upperCase, dropUS = 1,
                                       wrapAt = 63)
        return cdrxmllatex.createAddressLabelPage(formattedAddress)

    #------------------------------------------------------------------
    # Convert LaTeX to PostScript.
    #------------------------------------------------------------------
    def makePS(self, latex, passCount, basename, jobType):
        """
        Parameters:
            latex       - In-memory string containing LaTex source
                          for the current document.
            passCount   - Number of times the LaTeX processor must
                          be invoked for the document in order to
                          resolve such things as bibliographic
                          references.
            jobType     - Passed to the constructor for the new
                          PrintJob object.  Must be one of:
                                PrintJob.MAINDOC
                                PrintJob.COVERPAGE
        Return value:
            New PrintJob object representing the converted document.
        """

        try:

            # Save the LaTeX source.
            filename = basename + ".tex"
            open(filename, "w").write(latex)

            # Convert it to PostScript.
            # Give the PostScript some header commands for stapling, duplex.
            for unused in range(passCount):
                rc = os.system("latex %s %s" % (self.__LATEX_OPTS, filename))
                if rc:
                    raise cdr.Exception("failure running LaTeX processor "
                                        "on %s" % filename)
            rc = os.system("dvips -q -h %s %s" % (_STAPLE_NAME, basename))
            if rc:
                raise cdr.Exception("failure running dvips processor "
                                    "on %s.dvi" % basename)
            return PrintJob(basename + ".ps", jobType)

        except:
            (eType, eValue) = sys.exc_info()[:2]
            eMsg = eValue or eType
            raise cdr.Exception("failure converting %s.tex to %s.ps: %s" %
                                (basename, basename, eMsg))

    #------------------------------------------------------------------
    # Create the directory for electronic mailers.  Callback used by
    # the derived class where appropriate.
    #------------------------------------------------------------------
    def initEmailers(self, loadLookupTables=True):

        # Load a fresh copy of the emailer lookup tables.
        try:
            if loadLookupTables:
                import EmailerLookupTables
                EmailerLookupTables.loadTables()
        except Exception, e:
            try:
                self.log("unable to build emailer lookup tables: %s" % str(e))
                sender  = MailerJob.__CDR_EMAIL
                tier    = self.__TIER.name
                subject = "[%s] Emailer lookup table failure" % tier
                message = """\
Unable to generate a fresh set of lookup values for the electronic
mailer system (mailer job %s):

%s

Please do not reply to this message.
""" % (self.__id, str(e))
                recip = cdr.getEmailList("Developers Notification")
                cdr.sendMail(sender, recip, subject, message)
            except:
                pass

        # Does the output directory already exist
        try:
            os.chdir(self.__emailerDir)
        except:
            # Doesn't exist, try to create it
            try:
                os.makedirs(self.__emailerDir)
            except:
                self.log ("Unable to create emailer directory", tback=1)
                raise cdr.Exception("failure creating emailer directory %s" %
                                    self.__emailerDir)
            try:
                os.chdir(self.__emailerDir)
            except:
                self.log ("Unable to change to emailer directory", tback=1)
                raise cdr.Exception("failure setting working directory to %s" %
                                    self.__emailerDir)

    #------------------------------------------------------------------
    # Create the directory for RTF mailers.  Callback used by the
    # derived class where appropriate.
    #------------------------------------------------------------------
    def initRtfMailers(self):

        # Does the output directory already exist
        try:
            os.chdir(self.__rtfMailerDir)
        except:
            # Doesn't exist, try to create it
            try:
                os.makedirs(self.__rtfMailerDir)
            except:
                self.log ("Unable to create rtf mailer directory", tback=1)
                raise cdr.Exception("failure creating rtf mailer directory %s"
                                    % self.__rtfMailerDir)
            try:
                os.chdir(self.__rtfMailerDir)
            except:
                self.log ("Unable to change to rtf mailer directory", tback=1)
                raise cdr.Exception("failure setting working directory to %s"
                                    % self.__rtfMailerDir)

        # Specify the hostname based on the environment we're in
        # ------------------------------------------------------
        args = cdr.APPC, "GetBoardMemberLetters.py", self.__id
        url = "https://{}/cgi-bin/cdr/{}?job={:d}".format(*args)

        self.__letterLink = """
You can retrieve the letters at:

    %s
""" % url
#""" % (socket.gethostname(), self.__id)

    #------------------------------------------------------------------
    # Retrieve the string for an email address from an XML address
    # fragment document.
    #------------------------------------------------------------------
    def extractEmailAddress(self, docXml):
        dom = xml.dom.minidom.parseString(docXml)
        for node in dom.documentElement.childNodes:
            if node.nodeName == "ContactDetail":
                for child in node.childNodes:
                    if child.nodeName == "Email":
                        return cdr.getTextContent(child)

    #------------------------------------------------------------------
    # Clear out orphaned mailer tracking documents (from failed jobs).
    #------------------------------------------------------------------
    def __mailerCleanup(self):
        if os.getenv('SKIP_MAILER_CLEANUP'):
            return # for faster testing
        try:
            results = cdr.mailerCleanup(self.__session)
            if results[0]:
                self.log("%d tracking document(s) marked as deleted" %
                         len(results[0]))
            for err in results[1]:
                self.log(u"__mailerCleanup: %s" % err)
        except:
            self.log("mailerCleanup failure", 1)

    #------------------------------------------------------------------
    # Prepare initial settings for job.
    #------------------------------------------------------------------
    def __loadSettings(self):
        self.__getDates()
        self.__getDbConnection()
        self.__getCdrSession()
        self.__loadDbInfo()

    #------------------------------------------------------------------
    # Calculate needed dates (now and two months from now).
    #------------------------------------------------------------------
    def __getDates(self):
        now             = time.localtime(time.time())
        deadline        = (now[0], now[1], now[2] + 60, 0, 0, 0, 0, 0, -1)
        deadline        = time.localtime(time.mktime(deadline))
        self.__now      = time.strftime("%Y-%m-%dT%H:%M:%S", now)
        self.__deadline = time.strftime("%Y-%m-%d", deadline)

    #------------------------------------------------------------------
    # Log into the CDR server.
    #------------------------------------------------------------------
    def __getCdrSession(self):
        rsp          = str(cdr.login("cdrmailers", cdr.getpw("cdrmailers")))
        match        = self.__ERR_PATTERN.search(rsp)
        if match:
            raise cdr.Exception("CDR login failure: %s" % match.group(1))
        self.__session = rsp

    #------------------------------------------------------------------
    # Log into the CDR database.
    #------------------------------------------------------------------
    def __getDbConnection(self):
        try:
            self.__conn   = cdrdb.connect("CdrPublishing")
            self.__cursor = self.__conn.cursor()
        except cdrdb.Error, info:
            raise cdr.Exception("database connection failure: %s" % info[1][0])

    #------------------------------------------------------------------
    # Load the settings for this job from the database.
    #------------------------------------------------------------------
    def __loadDbInfo(self):
        self.__getPubProcRow()
        self.__getPubProcDocRows()
        self.__getPubProcParmRows()

    #------------------------------------------------------------------
    # Load the row which matches this job from the pub_proc table.
    #------------------------------------------------------------------
    def __getPubProcRow(self):
        try:
            self.__cursor.execute("""\
                SELECT output_dir, email, pub_subset
                  FROM pub_proc
                 WHERE id = ?""", (self.__id,))
            row = self.__cursor.fetchone()
            if not row:
                raise cdr.Exception("unable to find job %d" % self.__id)
            (self.__outputDir, self.__email, self.__subset) = row
            self.__emailerDir = self.__outputDir + "-e"
            self.__rtfMailerDir = self.__outputDir + "-r"
        except cdrdb.Error, info:
            raise cdr.Exception("database error retrieving pub_proc row: %s" %
                                info[1][0])

    #------------------------------------------------------------------
    # Load the list of document IDs and other descriptive information
    # for each document to be mailed by this job.
    #------------------------------------------------------------------
    def __getPubProcDocRows(self):

        try:
            # Find id, version, title, document type name
            #   for each document previously selected for mailing
            self.__cursor.execute("""\
                SELECT pub.doc_id, pub.doc_version,
                       doc.title, type.name
                  FROM pub_proc_doc pub
                  JOIN document doc
                    ON pub.doc_id = doc.id
                  JOIN doc_type type
                    ON doc.doc_type = type.id
                 WHERE pub_proc = ?""", (self.__id,))
            docDescriptorList = self.__cursor.fetchall()

            # Can't continue if there aren't any
            if not docDescriptorList:
                raise cdr.Exception("no documents found for job %d" %
                                    self.__id)

            # Build a list of pure docIds (used by some software)
            #   and of fuller information
            for row in docDescriptorList:

                # Append the id to plain list of ids
                self.__docIds.append(row[0])

                # Create a document object and add it to list of objects
                self.__documents[row[0]] = \
                    Document (row[0], row[2], row[3], row[1])

            if not docDescriptorList:
                raise cdr.Exception("no documents found for job %d" % self.__id)

            # Convert the id list to a faster tuple
            # [Not sure why Bob did this]
            self.__docIds = tuple(self.__docIds)

        except cdrdb.Error, err:
            raise cdr.Exception("database error retrieving pub_proc_doc rows: "
                                "%s" % err[1][0])

    #------------------------------------------------------------------
    # Load the parameters stored in the pub_proc_parm table for this job.
    #------------------------------------------------------------------
    def __getPubProcParmRows(self):
        try:
            self.__cursor.execute("""\
                SELECT parm_name, parm_value
                  FROM pub_proc_parm
                 WHERE pub_proc = ?
              ORDER BY id""", (self.__id))
            rows = self.__cursor.fetchall()
            if rows:
                for row in rows:
                    if not self.__parms.has_key(row[0]):
                        self.__parms[row[0]] = []
                    self.__parms[row[0]].append(row[1])
                    if row[0] == "Printer":
                        self.__printer = row[1]
        except cdrdb.Error, info:
            raise cdr.Exception("database error retrieving job parms: %s" %
                                info[1][0])

    #------------------------------------------------------------------
    # Create and populate the print queue.
    # Also creates and changes to the output directory.
    #------------------------------------------------------------------
    def __createQueue(self):
        self.__queue = []

        # Does the output directory already exist
        try:
            os.chdir(self.__outputDir)
        except:
            # Doesn't exist, try to create it
            try:
                os.makedirs(self.__outputDir)
            except:
                self.log ("Unable to create working directory", tback=1)
                raise cdr.Exception("failure creating working directory %s" %
                                    self.__outputDir)
            try:
                os.chdir(self.__outputDir)
            except:
                self.log ("Unable to change to working directory", tback=1)
                raise cdr.Exception("failure setting working directory to %s" %
                                    self.__outputDir)
        try:
            src = self.__TEMPLATE_FILE
            dst = "./template.tex"
            shutil.copy2(src, dst)
        except Exception, info:
            self.log("Failure copying %s to %s" % (src, dst), tback = 1)
            raise cdr.Exception("Failure copying %s to %s: %s" %
                                (src, dst, str(info)))

        # New method for turning on duplex printing (BZIssue::5018)
        try:
            fp = open("./%s" % _STAPLE_NAME, "w")
            fp.write("<< /Duplex true >> setpagedevice\n")
            fp.write("<< /Staple 3 >> setpagedevice\n")
            fp.close()
        except Exception, e:
            self.log("Failure creating duplex file", tback=1)
            raise cdr.Exception("Failure creating duplex file: %s" % e)

    #------------------------------------------------------------------
    # Print the jobs in the queue.
    #------------------------------------------------------------------
    def __printQueue(self, batchPrint = 1):

        # If no mailers at this point, we're just doing electronic mailers.
        if not self.__nMailers:
            for file in os.listdir("."):
                os.unlink("./%s" % file)
            os.chdir("..")
            os.rmdir(self.__outputDir)

            # Nothing to print.
            return

        if batchPrint:
            outputFile = open("PrintJob.cmd", "w")
            outputFile.write("@echo off\n")
            outputFile.write("if %1. == . goto usage\n")
            outputFile.write("if %1. == howmany. goto showcount\n")
            outputFile.write("if %2. == . goto L1\n")
            for i in range(len(self.__queue)):
                outputFile.write("if %%2. == %d. goto L%d\n" % (i + 1, i + 1))
            outputFile.write("goto usage\n")
        else:
            outputFile = self.__printer
        i = 1
        for job in self.__queue:
            job.Print(outputFile, self.log, batchPrint, i)
            i += 1
        if batchPrint:
            outputFile.write("goto done\n")
            outputFile.write(":usage\n")
            outputFile.write("echo usage: PrintJob path-to-printer "
                             "[first [last]]\n")
            outputFile.write("echo    or: PrintJob howmany\n")
            outputFile.write("echo     (to show how many files the script "
                             "has without printing anything)\n")
            outputFile.write("echo  e.g.: PrintJob \\\\CIPSFS1\\HP8100\n")
            outputFile.write("echo    or: PrintJob \\\\CIPSFS1\\HP8100 "
                             "201 400\n")
            outputFile.write("echo     (to print the second 200 files)\n")
            outputFile.write(":showcount\n")
            outputFile.write("echo this script contains %d files\n" %
                             len(self.__queue))
            outputFile.write(":done\n")
            outputFile.close()
            self.__packageFiles()

    #------------------------------------------------------------------
    # Create archive packages for the job's files.
    # Assumption: the current working directory is the job's output
    # output directory.  We switch to the parent of that directory.
    # This side effect should have no undesirable consequences,
    # because this is the last thing we do for the job.
    # Note: all files with the extensions '.xml', '.tex', '.log',
    # '.aux', and '.dvi' are packaged in a separate compressed tar
    # archive for intermediate files.  Everything else goes into a
    # second tar archive, used to print the actual mailer documents.
    # Make sure nothing needed by this second archive gets a filename
    # extension used for the intermediate file archive.
    #------------------------------------------------------------------
    def __packageFiles(self):
        self.log("~~In packageFiles")
        workExt   = ('xml', 'tex', 'log', 'aux', 'dvi', 'toc')
        dir       = "Job%d" % self.getId()
        workName  = "SupportFilesForJob%d.tar.bz2" % self.getId()
        printName = "PrintFilesForJob%d.tar.bz2" % self.getId()
        os.chdir("..")
        if not os.path.isdir(dir):
            raise cdr.Exception("INTERNAL ERROR: cannot find "
                                "directory %s" % dir)
        try:
            workFile = tarfile.open(workName, 'w:bz2')
            for ext in workExt:
                for file in glob.glob('%s/*.%s' % (dir, ext)):
                    workFile.add(file)
            workFile.close()
            for ext in workExt:
                for file in glob.glob('%s/*.%s' % (dir, ext)):
                    os.unlink(file)
        except:
            raise cdr.Exception("failure packing working files for job")

        try:
            printFile = tarfile.open(printName, 'w:bz2')
            for file in os.listdir(dir):
                printFile.add("%s/%s" % (dir, file))
            printFile.close()
            for file in os.listdir(dir):
                os.unlink("%s/%s" % (dir, file))
        except:
            raise cdr.Exception("failure creating print job package")
        os.rmdir(dir)

    #------------------------------------------------------------------
    # Create single archive package for a failed job's files.
    #------------------------------------------------------------------
    def __packageFailureFiles(self):
        self.log("~~In packageFailureFiles")
        dir  = "Job%d" % self.getId()
        name = "FailedJob%d.tar.bz2" % self.getId()
        try:
            os.chdir(self.__outputDir)
            os.chdir("..")
        except:
            return
        if not os.path.isdir(dir):
            self.log("Cannot find directory %s" % dir)
            return
        try:
            file = tarfile.open(name, 'w:bz2')
            for fName in glob.glob('%s/*' % dir):
                file.add(fName)
            file.close()
            for file in glob.glob('%s/*' % dir):
                os.unlink(file)
        except Exception, e:
            self.log("failure packing files for failed job: %s" % str(e))
            return
        os.rmdir(dir)

    #------------------------------------------------------------------
    # Clean up.
    #------------------------------------------------------------------
    def __cleanup(self, status, message):
        self.log("~~In cleanup")
        try:
            self.__updateStatus(status, message)
            self.__sendMail()
            if self.__session: cdr.logout(self.__session)
        except:
            self.log ("__cleanup failed, status was '%s'" % status,
                      tback=1)

    #------------------------------------------------------------------
    # Update the pub_proc table's status.
    #------------------------------------------------------------------
    def __updateStatus(self, status, message = None):
        self.log("~~In update status, status=%s" % status)
        message = message and str(message)
        try:
            if message:
                self.log ("  (message: %s)" % message)
            self.__cursor.execute("""\
                UPDATE pub_proc
                   SET status = ?,
                       messages = ?,
                       completed = GETDATE()
                 WHERE id = ?""", (status, message, self.__id))
            self.__conn.commit()
        except:
            self.log ("__updateStatus failed, status was '%s'" % status,
                      tback=1)

    #------------------------------------------------------------------
    # Inform the user that the job has completed.
    #------------------------------------------------------------------
    def __sendMail(self):
        try:
            if self.__email:
                self.log("Sending mail to %s" % self.__email)
                sender  = MailerJob.__CDR_EMAIL
                subject = "[%s] CDR Mailer Job Status" % self.__TIER.name

                # Specify the hostname based on the environment we're in
                # ------------------------------------------------------
                args = cdr.APPC, "PubStatus.py", self.__id
                url = "https://{}/cgi-bin/cdr/{}?id={:d}".format(*args)

                message = """\
Job %d has completed.  You can view a status report for this job at:

    %s
%s
Please do not reply to this message.
""" % (self.__id, url, self.__letterLink)
                cdr.sendMail(sender, [self.__email], subject, message)
        except:
            self.log("failure sending email to %s: %s" % (self.__email,
                                                          cdr.exceptionInfo()))

#----------------------------------------------------------------------
# Object to hold a document to be sent to the printer.
#----------------------------------------------------------------------
class PrintJob:
    """
    Public members:

        MAINDOC
            Used for constructor's filetype parameter to identify
            a primary document which should be stapled if it is
            not too large.

        COVERPAGE
            Used for constructor's filetype parameter to identify
            an ancillary document which should not be stapled.

        PLAIN
            Used for non-PostScript which should not be stapled.

        Print()
            Writes the current print job to the specified printer.
    """
    MAINDOC          = 1
    COVERPAGE        = 2
    PLAIN            = 3
    __PAGES_PATTERN  = re.compile("%%Pages: (\\d+)")
    __MAX_STAPLED    = 100
    def __init__(self, filename, filetype):
        self.__filename = filename
        self.__filetype = filetype
        self.__staple   = 0
        if self.__filetype == PrintJob.MAINDOC:
            pages = None
            ps = open(self.__filename)
            while 1:
                line = ps.readline()
                match = PrintJob.__PAGES_PATTERN.match(line)
                if match:
                    pages = int(match.group(1))
                    break
            if not pages:
                raise cdr.Exception("can't find page count in %s" %
                                    self.__filename)
            if pages <= PrintJob.__MAX_STAPLED:
                self.__staple = True
            ps.close()

    #------------------------------------------------------------------
    # Send the current print job to the specified printer.
    # Have to use Print instead of print to avoid conflict with the
    # keyword.
    #------------------------------------------------------------------
    def Print(self, outFile, logFunc, batch = 1, n = 0):
        logFunc("printing %s %s" % (
            self.__filename,
            self.__staple and "(stapled)" or ""))

        if batch:
            outFile.write(":L%d\n" % n)
            outFile.write("if %%3. == %d. goto :done\n" % (n - 1))
            outFile.write("copy %s %%1\n" % self.__filename)
        else:
            prn = open(outFile, "w")
            doc = open(self.__filename).read()
            prn.write(doc)
            prn.close()

#----------------------------------------------------------------------
# Object to hold information about a mailer organization.
#----------------------------------------------------------------------
class Org:
    """
    Public members:

        getId()
            Returns the integer for the primary key of the CDR document
            for a recipient of this mailer.

        getName()
            Returns the value of the title column of the document table
            in the CDR database for a recipient of this mailer.
    """
    def __init__(self, id, name):
        self.__id      = id
        self.__name    = name
    def getId     (self): return self.__id
    def getName   (self): return self.__name

#----------------------------------------------------------------------
# Object to hold information about a mailer recipient.
#----------------------------------------------------------------------
class Recipient:
    """
    Public members:

        getId()
            Returns the integer for the primary key of the CDR document
            for a recipient of this mailer.

        getName()
            Returns the value of the title column of the document table
            in the CDR database for a recipient of this mailer.

        getAddress()
            Returns the Address object used used for addressing the
            mailer to this recipient.

        getDocs()
            Returns the list of Document objects representing documents
            sent to this recipient.

        getEmailers()
            Returns the list of Emailer objects for this recipient.
    """
    def __init__(self, id, name, address = None):
        self.__id       = id
        self.__name     = name
        self.__address  = address
        self.__docs     = []
        self.__emailers = []
    def getId      (self): return self.__id
    def getName    (self): return self.__name
    def getAddress (self): return self.__address
    def getDocs    (self): return self.__docs
    def getEmailers(self): return self.__emailers

#----------------------------------------------------------------------
# Object to hold information about a mailer document.
#----------------------------------------------------------------------
class Document:
    """
    Public members:

        getId()
            Returns the integer for the primary key of the CDR document.

        getTitle()
            Returns the value of the title column of the document table
            in the CDR database.

        getDocType()
            Returns the name of this document's CDR document type (e.g.,
            "Summary").

        getVersion()
            Returns the version number in the version archive of the
            document to be mailed.  If None, we are mailing the
            current working document.

    """
    def __init__(self, id, title, docType, version=None):
        self.__id         = id
        self.__title      = title
        self.__docType    = docType
        self.__version    = version
    def getId     (self): return self.__id
    def getTitle  (self): return self.__title
    def getDocType(self): return self.__docType
    def getVersion(self): return self.__version

#----------------------------------------------------------------------
# Object to hold information about a mailer address.
#----------------------------------------------------------------------
class Address(cdrdocobject.ContactInfo):
    """
    Public methods (in addition to those inherited from ContactInfo):

        format(upperCase, dropUS, wrapAt, useRtf, contactFields)
            Returns address in a format ready for inclusion in a
            LaTeX document.  If upperCase is true (default is false),
            then the address uses uppercase versions of the data
            for the formatted block.  If dropUS is true (default
            is false), the last line is omitted if it contains
            only the abbreviation for the United States.  The
            optional wrapAt parameter can be used to control the
            maximum width of the result.  If the optional useRtf
            parameter is set to True, the address will be formatted
            as RTF rather than LaTeX markup.  Finally, if the
            optional contactFields parameter is True the result
            will be an RTF block of labeled contact information.

        getXml()
            returns a serialized version of the address information
            needed for a Mailer (tracking) document.

    """

    #------------------------------------------------------------------
    # Constructor for CDR mailer Address object.
    #------------------------------------------------------------------
    def __init__(self, xmlFragment, withPersonTitle=TITLE_OMITTED):
        """
        Parameters:
            xmlFragment    - Either DOM object for parsed address XML,
                             or the string containing the XML for the
                             address.
                             The top node should be <AddressElements>
        """
        cdrdocobject.ContactInfo.__init__(self, xmlFragment, withPersonTitle)

        # Turned off if format() is called with contactFields == True.
        self.__includeNameAndTitle = True

    #------------------------------------------------------------------
    # Create a LaTeX- (or RTF-) ready string representing this address.
    #------------------------------------------------------------------
    def format(self, upperCase=False, dropUS=False, wrapAt=sys.maxint,
               useRtf=False, contactFields=False, useRtfTable=False):
        self.__includeNameAndTitle = not contactFields
        lines = self.getAddressLines(self.__includeNameAndTitle)
        if upperCase:
            upperLines = []
            for line in lines:
                upperLines.append(line.upper())
            lines = upperLines
        if dropUS and len(lines) and self.lineIsUS(lines[-1]):
            lines = lines[:-1]
        lines = self.wrapLines(lines, wrapAt)
        if contactFields:
            return self.__formatContactFields(lines, useRtfTable)
        return self.__formatAddressFromLines(lines, useRtf)

    #------------------------------------------------------------------
    # Create XML string from address information.
    #------------------------------------------------------------------
    def getXml(self):
        xml        = ["<MailerAddress>"]
        country    = self.getCountry()
        postalCode = self.getPostalCode()
        if country:
            xml.append("<Country>%s</Country>" % country)
        if postalCode:
            xml.append("<PostalCode>%s</PostalCode>" % postalCode)
        for line in self.getAddressLines(self.__includeNameAndTitle):
            xml.append("<AddressLine>%s</AddressLine>" % line)
        xml.append("</MailerAddress>")
        return "".join(xml)

    #------------------------------------------------------------------
    # Assemble an RTF table row for two-column contact information.
    #------------------------------------------------------------------
    @staticmethod
    def formatRtfContactTableRow(label, value):
        value = value or ""
        return """\
{
\\trowd\\trleft1050\\cellx2500\\cellx10000
\\pard\\intbl %s:\\cell
\\pard\\intbl %s\\cell
\\row
}""" % (RtfWriter.fix(label),
        RtfWriter.fix(value.strip()).replace("@@LINE@@", "\\line"))

    #------------------------------------------------------------------
    # Create RTF for contact fields on fax-back form.
    #------------------------------------------------------------------
    def __formatContactFields(self, lines, useRtfTable):
        if useRtfTable:
            makeRow = Address.formatRtfContactTableRow
            rows = [
                makeRow("Name", self.getAddressee()),
                makeRow("Title", self.getPersonTitle()),
                makeRow("Address", "@@LINE@@\n".join(lines)),
                makeRow("Phone", self.getPhone()),
                makeRow("Fax", self.getFax()),
                makeRow("E-mail", self.getEmail()),
            ]
            return "\n".join(rows)
        title = RtfWriter.fix(self.getPersonTitle() or "")
        phone = RtfWriter.fix(self.getPhone() or "")
        fax   = RtfWriter.fix(self.getFax() or "")
        email = RtfWriter.fix(self.getEmail() or "")
        rtfLines = [
            "\\tab Name:\\tab %s\\line" % RtfWriter.fix(self.getAddressee()),
            "\\tab Title:\\tab %s\\line" % title
        ]
        prefix = "\\tab Address:\\tab "
        for line in lines:
            rtfLines.append("%s%s\\line" % (prefix, RtfWriter.fix(line)))
            prefix = "\\tab\\tab "
        rtfLines += [
            "\\tab Phone:\\tab %s\\line" % phone,
            "\\tab Fax:\\tab %s\\line" % fax,
            "\\tab E-mail:\\tab %s\\par" % email
        ]
        return "\n".join(rtfLines)

    #------------------------------------------------------------------
    # Format an address block from its address lines.
    #------------------------------------------------------------------
    def __formatAddressFromLines(self, lines, useRtf = False):
        block = ""
        for line in lines:
            if useRtf:
                block += "%s\\line\n" % RtfWriter.fix(line)
            else:
                block += "%s \\\\\n" % UnicodeToLatex.convert(line)
        return self.FormattedAddress(block, len(lines))

    #----------------------------------------------------------------------
    # Object to hold a formatted address.
    #----------------------------------------------------------------------
    class FormattedAddress:
        def __init__(self, block, numLines):
            self.__block = block
            self.__numLines = numLines
        def getBlock(self):     return self.__block
        def getNumLines(self):  return self.__numLines

#----------------------------------------------------------------------
# Object for an electronic mailer.
#----------------------------------------------------------------------
class Emailer:
    def __init__(self, document, recipient, leadOrg = None):
        self.__document  = document
        self.__recipient = recipient
        self.__leadOrg   = leadOrg
    def getLeadOrgId(self): return self.__leadOrg
    def getRecipient(self): return self.__recipient
    def getDocument (self): return self.__document
