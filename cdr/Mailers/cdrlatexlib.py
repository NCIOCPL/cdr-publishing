#----------------------------------------------------------------------
# $Id: cdrlatexlib.py,v 1.40 2003-05-09 03:44:06 ameyer Exp $
#
# Rules for generating CDR mailer LaTeX.
#
# $Log: not supported by cvs2svn $
# Revision 1.39  2003/04/09 14:33:21  bkline
# Fixed problem with trial group membership (mismatch between integer and
# string version of document ID).
#
# Revision 1.38  2003/03/18 16:37:00  bkline
# Added support for multiple site contacts on S&P mailers (Request #591).
#
# Revision 1.37  2003/03/14 01:32:28  bkline
# Added an extra line for the Physician mailer so the Organization name
# can be provided for new OtherPracticeLocation information.
#
# Revision 1.36  2003/03/03 20:08:23  bkline
# Implemented changes requested by Sheri in issue #591.
#
# Revision 1.35  2003/02/19 16:49:48  bkline
# Removed "Principal Investigator" from label for Contact column of
# S&P mailers.  Set \footskip to 60pt for S&P mailers.
#
# Revision 1.34  2003/02/11 21:28:47  bkline
# Added code to pick up CitySuffix.
#
# Revision 1.33  2003/02/10 17:23:07  bkline
# Changed fax number for protocol summary mailer.
#
# Revision 1.32  2003/02/06 23:00:44  ameyer
# Trimmed whitespace from text retrieved via getText function.
# Resolved some pychecker warnings.
#
# Revision 1.31  2003/02/06 19:36:19  ameyer
# Made modifications designed by Volker to significantly reduce the problem
# of blank pages in the person directory mailers.
#
# Revision 1.30  2003/01/28 14:23:33  bkline
# Added code to handle protocols with no PI for status and participant
# check.
#
# Revision 1.29  2003/01/23 19:28:49  ameyer
# Changed handling of Publish Email address circles again.
#
# Revision 1.28  2003/01/16 23:35:42  ameyer
# Added \YESno and \yesNO macros to centralize handling of default values
# for check circles.
# Added default handling for three more check circles in the form.
#
# Revision 1.27  2003/01/15 04:52:34  ameyer
# Added 'x' in circles for public email Yes or No for each email address.
#
# Revision 1.26  2003/01/15 03:12:44  bkline
# Added code to handle multiple roles for LeadOrgPerson elements; changed
# code to get the MailAbstractTo value to avoid calling UnicodeToLatex().
#
# Revision 1.25  2002/12/30 19:55:47  bkline
# Suppressed DRAFT marking.
#
# Revision 1.24  2002/12/27 02:11:19  ameyer
# Added ability to output an 'x' in the directory include circle.
#
# Revision 1.23  2002/12/26 13:53:23  bkline
# Modifications made for issue #551: moved protocol information before
# practice information.  Added a fourth question to the practice
# information section, with additional instructions.
#
# Revision 1.22  2002/12/03 17:04:28  bkline
# Fixed several bugs in list handling reported by Margaret.
#
# Revision 1.21  2002/11/14 21:42:40  ameyer
# Added number of latex passes to ControlTable.
# Cleaned up some errors revealed by pychecker.
#
# Revision 1.20  2002/11/08 21:40:46  bkline
# Inserted newline between bibliographic items to prevent TeX from
# choking on monstrously long lines.
#
# Revision 1.19  2002/11/08 16:11:45  bkline
# Added spacing changes requested by Lakshmi (issue #511).
#
# Revision 1.18  2002/11/07 21:21:20  bkline
# Improved table support.
#
# Revision 1.17  2002/11/06 03:09:27  ameyer
# Changed initial values of address lines from None to "", to avoid
# rare cases where xxx.strip() would fail because address line named xxx
# didn't exist.
#
# Revision 1.16  2002/10/31 20:00:23  bkline
# Added stripLines filter for table cells.
#
# Revision 1.15  2002/10/23 22:05:54  bkline
# Added rule for StatusCheck.
#
# Revision 1.14  2002/10/14 12:47:44  bkline
# Removed unwanted comma from CIPS address.
#
# Revision 1.13  2002/10/10 13:44:43  bkline
# Mods to final page of prot abstract mailer.
#
# Revision 1.12  2002/10/07 21:33:51  bkline
# Added aliases for protocol abstract mailer.
#
# Revision 1.11  2002/10/02 20:51:03  bkline
# Added code to find the counts of active and closed protocols with
# which a physician is involved.  Cleaned up the indentenation in the
# older code.
#
# Revision 1.10  2002/09/30 14:25:25  bkline
# Second draft for protocol summary and status mailers.
#
# Revision 1.9  2002/09/26 22:05:29  bkline
# Second draft for person and org mailers.
#
# Revision 1.8  2002/09/25 18:30:42  bkline
# First working status and participant site check mailers.
#
# Revision 1.7  2002/09/17 22:10:23  bkline
# Cleaned up, added comments.
#
#----------------------------------------------------------------------
import sys, re, xml.dom.minidom, UnicodeToLatex, cdrlatextables, time

#----------------------------------------------------------------------
# Module-level variables.
#----------------------------------------------------------------------
personLists = None
listStack   = []

# Pattern for checking attribute name =/!= value
_attrPat = re.compile(r'([A-Za-z_]+)\s*(!?)=\s*(.*)')

class XProc:
    """
    All information needed to perform one step in a conversion.

    A control table defined in cdrlatexlib.py will contain a tuple
    of these which describes how to process a document in a format.

     Fields:

       element   - XML element to process, None if this is pure processing
                   Elements may be specifed as simple names, or as fully
                    qualified names starting at the root, e.g.:
                      Title
                     or:
                      /Summary/SummarySection/Title
                   The program will search for a match on the fully qualified
                    name first and, only if it doesn't find anything, will it
                    look to see if there is an XProc for a simple name.
                    Therefore if both "Title" and "/Summary...Title" are
                    specified, the Title for the SummarySection will be
                    processed according to the SummarySection/Title rule
                    and all other Titles will be processed according to the
                    other rule.
                   Full XPath notation is NOT supported.
       attr      - Attribute specification.  If not None, only process this
                    element if the specification fits the element.
                    Valid specifications are:
                      attrname=attrValue
                     or
                      attrname!=attrValue
                    Only used if there is an element tag.
       occs      - Max num occs to process, 0 = unlimited
                    Only used if there is an element tag
       order     - How we order an xml element during output, one of:
                    XProc.ORDER_DOCUMENT:
                      This is the default order for processing document nodes.
                      If no other order is specified the nodes are processed
                      in the order they appear in the input document.  For
                      this ordering mode, the order in which the processing
                      rules are specified is not significant.
                    XProc.ORDER_TOP:
                      A processing rule can be specified to use ORDER_TOP to
                      cause the matching nodes to be processed before any
                      other nodes or after all other nodes.  Place all
                      ORDER_TOP rules which should be processed first at the
                      beginning of the list of rules.  These rules will be
                      processed in their order of appearance in the list.
                      Place all ORDER_TOP rules which should be processed
                      last at the end of the list of rules.  These, too,
                      will be processed in their order of appearance in the
                      list.
                    XProc.ORDER_PARENT:
                      This mode of ordering behaves similarly to ORDER_TOP,
                      but only with respect to the sibling elements which
                      are children of the same parent element.  In other
                      words, the engine collects all of the nodes which are
                      children of a given parent, and finds the rule which
                      matches each of those nodes.  The nodes in this set
                      whose rules are designated as ORDER_PARENT, and whose
                      rules are specified before any ORDER_DOCUMENT rules in
                      this set will be processed first (in the order in which
                      these rules appear in the rule list), followed by the
                      nodes whose matching rules are designated as
                      ORDER_DOCUMENT (in the order of node appearance in the
                      input document), followed by those nodes matching the
                      remaining ORDER_PARENT rules (that is, ORDER_PARENT
                      rules which were specified following an ORDER_DOCUMENT
                      rule within the set of rules which match this set of
                      siblings).
                   Example showing how XProc.ORDER_DOCUMENT works:
                    Instructions:
                      Element='A', order=XProc.ORDER_TOP
                      Element='B', order=XProc.ORDER_TOP
                      Element='C', order=XProc.ORDER_DOCUMENT
                      Element='D', order=XProc.ORDER_DOCUMENT
                      Element='E', order=XProc.ORDER_TOP
                    Input record has elements in following order:
                      C1 C2 D3 A4 B5 C6 E7 C8 D9
                    Output record gets:
                      A4 B5 C1 C2 D3 C6 C8 D9 E7
                    (That's perfectly clear, isn't it?)
                    Only used if there is an element tag.
       prefix    - Latex constant string to output prior to processing
       preProcs  - List of routines+parms to call before textOut output
       textOut   - True=Output the text of this element
                    Only used if there is an element tag
       descend   - True=Examine children of element, else skip them
                    Only used if there is an element tag
       postProcs - List of routines+parms tuples to call at end
       suffix    - Latex constant string to output after processing
       filters   - Optional sequence of filters to be applied to the
                   collected output for the children of a node; each
                   filter must be a function which takes a string
                   and returns a string.
    """

    ORDER_TOP      = 1  # Process in order given in instructions, at top level
    ORDER_PARENT   = 2  # Process in order given in instructions, within parent
    ORDER_DOCUMENT = 3  # Process in order found in the document

    def __init__(self,
                 element = None,         # No element involved unless specified
                 attr = None,            # Attribute specification for element
                 occs = 0,               # Default= all occurrences
                 order = ORDER_DOCUMENT, # Assume element ordered same as list
                 prefix = None,          # No prefix before output of text
                 preProcs = None,        # No procedures to run
                 textOut = 1,            # Output the text
                 descend = 1,            # Examine child elements
                 postProcs = None,       # No procedures to run after output
                 suffix = None,          # No suffix
                 filters = None):        # No filters
        self.element   = element
        self.attr      = attr
        self.occs      = occs
        self.order     = order
        self.prefix    = prefix
        self.preProcs  = preProcs
        self.textOut   = textOut
        self.descend   = descend
        self.postProcs = postProcs
        self.suffix    = suffix
        self.filters   = filters

        # If an attribute specification was given, parse it here
        if attr != None:
            matchObj = _attrPat.search (attr)
            if matchObj == None:
                raise XmlLatexException ("Bad attr specification: '%s'" % attr)
            attrParts = matchObj.groups()
            self.attrName = attrParts[0]
            self.attrValue = attrParts[2]
            if attrParts[1] == '!':
                self.attrNegate = 1
            else:
                self.attrNegate = 0


    #---------------------------------------------------------------
    # checkAttr
    #
    #   Check to see whether a node conforms, or does not conform to
    #   an attribute spec
    #
    #   Attribute specs are of the form:
    #       "name=value"
    #     or
    #       "name!=value"
    #
    #   If a specified attribute does not exist in the element, then
    #   if '=' is requested, the node does not conform.  If '!=' is
    #   requested, the node does conform.
    #
    # Pass:
    #   Reference to dom node.
    #
    # Return:
    #   1 = true = conforms.
    #   2 = false = does not conform.
    #---------------------------------------------------------------
    def checkAttr (self, node):

        # If there is no attribute specification, the node passes
        if self.attr == None:
            return 1

        # If node has no attributes, return value is based on presence of !
        if node.hasAttributes() == 0:
            if self.attrNegate:
                return 1
            return 0

        # Collect the attributes and search them
        attrs = node.attributes
        i = 0
        while i < attrs.length:
            if attrs.item(i).name == self.attrName:
                if attrs.item(i).nodeValue == self.attrValue:
                    # Attribute name and value both match
                    if self.attrNegate:
                        return 0
                    return 1
            i += 1

        # Attribute not found
        if self.attrNegate:
            return 1
        return 0

    #---------------------------------------------------------------
    # toString
    #   Dump the contents of the current XProc in human readable
    #   format.  For debugging.
    #---------------------------------------------------------------
    def toString (self):
        str =  'XProc:\n'
        str += '  element=' + showVal (self.element)
        str += '  attr=' + showVal (self.attr)
        str += '  occs=' + showVal (self.occs)
        str += '  order' + showVal (self.order)
        str += '  textOut=' + showVal (self.textOut)
        str += '  descend=' + showVal (self.descend) + '\n'
        str += '  --prefix=' + showVal (self.prefix) + '\n'
        str += '  --suffix=' + showVal (self.suffix) + '\n'
        str += '  count preProcs='
        if self.preProcs != None:
            str += showVal(len(self.preProcs))
        else:
            str += '0'
        str += '  count postProcs='
        if self.postProcs != None:
            str += showVal(len(self.postProcs))
        else:
            str += '0'

        return str


class ProcParms:
    """
       A reference to an instance of procParms is passed to any preProc
       or postProc executed during the conversion.

       It acts as a container for information made available to the
       procedure, and for information coming back.

       Fields include:

           topNode - Reference to DOM node at top of XML document, i.e.
                     the document element.
           curNode - The current DOM node, i.e., the one for the current
                     element.  This may be None if the procedure is
                     is invoked outside the context of an element (if
                     XProc.element=None.)
           args    - A tuple of arguments associated with the current
                     procedure in the XProc.preProcs or postProcs field.
           output  - Initially, an empty string.
                     If the procedure needs to output data, place a string
                     in ProcParms.output and the conversion driver will
                     handle it.

       The output element is handled by the conversion driver as follows:

           Initialize output=''
           Invoke each preProc (or postProc) in the XProc tuple of procedures
           (Note: each procedure sees the previous output, which may no longer
               be ''.  Each subsequent procedure can, if desired, examine,
               replace, or append to the current output.
           Write the last value of output to the actual Latex output string.
    """

    def __init__(self, top, cur, args, output):
        self.topNode = top
        self.curNode = cur
        self.args    = args
        self.output  = output

    def getTopNode(self):
        return self.topNode

    def getCurNode(self):
        return self.curNode

    def getArgs(self):
        return self.args

    def getOutput(self):
        return self.output

    def setOutput(self, output):
        self.output = output

class XmlLatexException(Exception):
    "Used for all exceptions thrown back to cdrxmllatex callers."
    pass

class OrgProtStatus:
    "Object representing an organization's protocol status."
    def __init__(self, statuses):
        self.value = None
        self.date  = None
        child      = statuses.firstChild
        while child:
            if child.nodeName == "CurrentOrgStatus":
                for grandchild in child.childNodes:
                    if grandchild.nodeName == "StatusName":
                        self.value = getText(grandchild)
                    elif grandchild.nodeName == "StatusDate":
                        self.date = getText(grandchild)
                return
            child = child.nextSibling

class PersonName:
    "Object representing a person's name, including professional suffixes."
    def __init__(self, node):
        self.givenName    = ""
        self.surname      = ""
        self.profSuffixes = []
        self.genSuffix    = ""
        self.prefix       = ""
        self.initials     = ""
        for child in node.childNodes:
            if child.nodeName == "GivenName":
                self.givenName = getText(child)
            elif child.nodeName == "SurName":
                self.surname = getText(child)
            elif child.nodeName == "GenerationSuffix":
                self.genSuffix = getText(child)
            elif child.nodeName == "MiddleInitial":
                self.initials = getText(child)
            elif child.nodeName == "Prefix":
                self.prefix = getText(child)
            elif child.nodeName == "ProfessionalSuffix":
                for grandchild in child.childNodes:
                    if grandchild.nodeName in ("StandardProfessionalSuffix",
                                               "CustomProfessionalSuffix"):
                        suffix = getText(grandchild)
                        if suffix:
                            self.profSuffixes.append(suffix)

    def format(self, full = 0):
        name = ("%s %s" % (self.givenName, self.initials)).strip()
        name = ("%s %s" % (name, self.surname)).strip()
        if self.genSuffix:
            name = "%s, %s" % (name, self.genSuffix)
        if not full: return name
        profSuffixes = ", ".join(self.profSuffixes).strip()
        if profSuffixes:
            name = "%s, %s" % (name, profSuffixes)
        return name

class Address:
    "Object holding an address (not including company names)."

    def __init__(self, node = None):
        self.street     = []
        self.city       = ""
        self.state      = ""
        self.country    = ""
        self.zip        = ""
        self.zipPos     = ""
        self.citySuffix = ""
        if node:
            stateShortName   = ""
            stateFullName    = ""
            countryShortName = ""
            countryFullName  = ""
            for child in node.childNodes:
                if child.nodeName == "Street":
                    self.street.append(getText(child))
                elif child.nodeName == "City":
                    self.city = getText(child)
                elif child.nodeName == "CitySuffix":
                    self.citySuffix = getText(child)
                elif child.nodeName == "PoliticalSubUnitShortName":
                    stateShortName = getText(child)
                elif child.nodeName == "PoliticalSubUnitFullName":
                    stateFullName = getText(child)
                elif child.nodeName == "CountryShortName":
                    countryShortName = getText(child)
                elif child.nodeName == "CountryFullName":
                    countryFullName = getText(child)
                elif child.nodeName == "PostalCodePosition":
                    self.zipPos = getText(child)
                elif child.nodeName == "PostalCode_ZIP":
                    self.zip = getText(child)
            self.state = stateShortName or stateFullName
            self.country = countryShortName or countryFullName

    def format(self, includeCountry = 0):
        output = ""
        for street in self.street:
            output += "  %s \\\\\n" % street
        statePlusZip = "%s %s" % (self.state or "", self.zip or "")
        statePlusZip = statePlusZip.strip()
        city = ("%s %s" % (self.city, self.citySuffix)).strip() or ""
        comma = city and statePlusZip and ", " or ""
        lastLine = "%s%s%s" % (city, comma, statePlusZip)
        if lastLine:
            output += "  %s \\\\\n" % lastLine
        if self.country and includeCountry:
            output += "  %s \\\\\n" % self.country
        return output

class List:
    "Remembers list style and type."
    def __init__(self, compact, listType):
        self.compact  = compact
        self.listType = listType

class LeadOrgPerson:
    "Object representing a Protocol Lead Organization person."
    def __init__(self, node):
        self.name    = None
        self.phone   = None
        self.roles   = []
        self.address = Address()
        self.id      = node.getAttribute("id")
        self.orgs    = []
        for child in node.childNodes:
            if child.nodeName == "Person":
                for grandchild in child.childNodes:
                    if grandchild.nodeName == "PersonNameInformation":
                        self.name = PersonName(grandchild)
                    elif grandchild.nodeName == "OrganizationAddressNames":
                        for org in grandchild.childNodes:
                            if org.nodeName == "OrganizationName":
                                self.orgs.append(getText(org))
                    elif grandchild.nodeName == "Phone":
                        self.phone = getText(grandchild)
                    elif grandchild.nodeName == "Street":
                        self.address.street.append(
                                getText(grandchild))
                    elif grandchild.nodeName == "City":
                        self.address.city = getText(grandchild)
                    elif grandchild.nodeName == "PoliticalSubUnit_State":
                        self.address.state = getState(grandchild)
                    elif grandchild.nodeName == "PostalCode_ZIP":
                        self.address.zip = getText(grandchild)
                    elif grandchild.nodeName == "Country":
                        shortName = None
                        fullName  = None
                        for cName in grandchild.childNodes:
                            if cName.nodeName == "CountryFullName":
                                fullName = getText(cName)
                            elif cName.nodeName == "CountryShortName":
                                shortName = getText(cName)
                        self.address.country = shortName or fullName
            elif child.nodeName == "PersonRole":
                self.roles.append(getText(child))
    def hasRole(self, role):
        return role in self.roles

class ProtLeadOrg:
    "Object representing a Protocol Lead Organization."
    def __init__(self, orgNode):
        sendMailerTo       = ""
        self.personnel     = {}
        self.sendMailerTo  = None
        self.officialName  = None
        self.orgRoles      = {}
        self.protChair     = None
        self.currentStatus = None
        for child in orgNode.childNodes:
            if child.nodeName == "MailAbstractTo":
                sendMailerTo = getText(child, transformToLatex = 0)
            elif child.nodeName == "LeadOrgProtocolStatuses":
                self.currentStatus = OrgProtStatus(child)
            elif child.nodeName == "OfficialName":
                for grandchild in child.childNodes:
                    if grandchild.nodeName == "Name":
                        self.officialName = getText(grandchild)
            elif child.nodeName == "LeadOrgPersonnel":
                person = LeadOrgPerson(child)
                self.personnel[person.id] = person
                for role in person.roles:
                    if role.upper() != "UPDATE PERSON":
                        self.protChair = person
        if sendMailerTo and self.personnel.has_key(sendMailerTo):
            self.sendMailerTo = self.personnel[sendMailerTo]

class OrgLoc:
    "Object representing an organization location."
    def __init__(self, node):
        self.id          = None
        self.cipsContact = ""
        self.address     = None
        self.phone       = None
        self.fax         = None
        self.email       = None
        self.web         = None
        self.emailPublic = ""
        self.orgNames    = []
        for child in node.childNodes:
            if child.nodeName == "Location":
                self.id = child.getAttribute("id")
                for grandchild in child.childNodes:
                    if grandchild.nodeName == "CIPSContact":
                        self.cipsContact = getText(grandchild)
                    elif grandchild.nodeName == "PostalAddress":
                        self.address = Address(grandchild)
                    elif grandchild.nodeName == "Phone":
                        self.phone = getText(grandchild)
                    elif grandchild.nodeName == "Fax":
                        self.fax = getText(grandchild)
                    elif grandchild.nodeName == "Email":
                        self.email = getText(grandchild)
                        self.emailPublic = grandchild.getAttribute("Public")
                    elif grandchild.nodeName == "WebSite":
                        self.web = getText(grandchild)
                    elif grandchild.nodeName == "OrganizationAddressNames":
                        for ggc in grandchild.childNodes:
                            if ggc.nodeName == "OrganizationName":
                                self.orgNames.append(getText(ggc))

class PersonLists:
    "Gathers lists of boards, specialties, etc., needed for Person mailers."
    def __init__(self):
        import cdr, cdrdb
        personType = cdr.getDoctype('guest', 'Person')
        if personType.error:
            raise XmlLatexException(
                "getDoctype(Person): %s" % personType.error)
        if not personType.vvLists:
            raise XmlLatexException(
                "No valid value lists found for Person type")
        conn = cdrdb.connect('CdrGuest')
        self.boardSpecialties = self.__getBoardSpecialties(personType)
        self.otherSpecialties = self.__getOtherSpecialties(personType)
        self.profSocieties    = self.__getProfSocieties(personType)
        self.trialGroups      = self.__getTrialGroups(conn)
        self.oncologyPrograms = self.__getOncologyPrograms(conn)
    def __getBoardSpecialties(self, personType):
        for vvList in personType.vvLists:
            if vvList[0] == "BoardCertifiedSpecialtyName":
                return vvList[1]
        raise XmlLatexException("Unable to find valid board specialties")
    def __getOtherSpecialties(self, personType):
        for vvList in personType.vvLists:
            if vvList[0] == "OtherSpecialty":
                return vvList[1]
        raise XmlLatexException("Unable to find list of non-board specialties")
    def __getProfSocieties(self, personType):
        for vvList in personType.vvLists:
            if vvList[0] == "MemberOfMedicalSociety":
                return vvList[1]
        raise XmlLatexException("Unable to find list of medical societies")
    def __getTrialGroups(self, conn):
        cursor = conn.cursor()
        cursor.execute("""\
       SELECT DISTINCT d.id,
                       o.value
                  FROM document d
                  JOIN query_term o
                    ON o.doc_id = d.id
                  JOIN query_term t
                    ON t.doc_id = d.id
                 WHERE o.path   = '/Organization/OrganizationNameInformation'
                                + '/OfficialName/Name'
                   AND t.path   = '/Organization/OrganizationType'
                   AND t.value  = 'NCI-supported clinical trials group'
              ORDER BY o.value""")
        return cursor.fetchall()
    def __getOncologyPrograms(self, conn):
        cursor = conn.cursor()
        cursor.execute("""\
       SELECT DISTINCT d.id,
                       o.value
                  FROM document d
                  JOIN query_term o
                    ON o.doc_id = d.id
                  JOIN query_term t
                    ON t.doc_id = d.id
                 WHERE o.path = '/Organization/OrganizationNameInformation'
                              + '/OfficialName/Name'
                   AND t.path = '/Organization/OrganizationType'
                   AND t.value IN ('NCI-funded community clinical ' +
                                   'oncology program',
                                   'NCI-funded minority community clinical ' +
                                   'oncology program')
              ORDER BY o.value""")
        return cursor.fetchall()

class PersonLocation:
    """
    Base class for a person's private practice and other practice locations.
    Note that the denormalized Person document has already matched up the
    CIPSContact element with the location it points to, so the presence
    of that element inside a location element (Home, PrivatePractice,
    or OtherPracticeLocation) indicates the CIPS contact location, without
    the necessity to inspect the actual value of the CIPSContact element.
    There is one twist, though.  For a PrivatePractice, the CIPSContact
    element is down one level, underneath the child PrivatePracticeLocation
    element for some reason.
    """
    def __init__(self):
        self.id             = None
        self.cipsContact    = ""
        self.personTitle    = None
        self.address        = None
        self.phone          = None
        self.tollFreePhone  = None
        self.fax            = None
        self.email          = None
        self.web            = None
        self.orgNames       = []
        self.emailPublic    = ""
    def formatAddress(self, includeCountry = 0):
        result = self.address.format(includeCountry)
        isContact = self.cipsContact and len(self.cipsContact) > 0
        # Create person title followed by orgname, or vice versa
        orgNames = ""
        if isContact and self.personTitle:
            orgNames += "  %s \\\\\n" % self.personTitle
        for orgName in self.orgNames:
            orgNames += "  %s \\\\\n" % orgName
        if not isContact and self.personTitle:
            orgNames += "  %s \\\\\n" % self.personTitle
        return orgNames + result

class PrivatePracticeLocation(PersonLocation):
    "Derived class for a physician's private practice location."
    def __init__(self, node):
        PersonLocation.__init__(self)
        for child in node.childNodes:
            if child.nodeName == "PrivatePracticeLocation":
                self.id = child.getAttribute("id")
                for grandchild in child.childNodes:
                    if grandchild.nodeName == "PostalAddress":
                        self.address = Address(grandchild)
                    elif grandchild.nodeName == "CIPSContact":
                        self.cipsContact = getText(grandchild)
            elif child.nodeName == "Phone":
                self.phone = getText(child)
            elif child.nodeName == "TollFreePhone":
                self.tollFreePhone = getText(child)
            elif child.nodeName == "Fax":
                self.fax = getText(child)
            elif child.nodeName == "Email":
                self.email = getText(child)
                self.emailPublic = child.getAttribute("Public")

class OtherPracticeLocation(PersonLocation):
    "Derived class for an other practice location for a person."
    def __init__(self, node):
        PersonLocation.__init__(self)
        self.id = node.getAttribute("id")
        orderParentNameFirst = 0
        for child in node.childNodes:
            if child.nodeName == "SpecificPostalAddress":
                self.address = Address(child)
            elif child.nodeName in ("Phone", "SpecificPhone"):
                self.phone = getText(child)
            elif child.nodeName in ("TollFreePhone", "SpecificTollFreePhone"):
                self.tollFreePhone = getText(child)
            elif child.nodeName in ("Fax", "SpecificFax"):
                self.fax = getText(child)
            elif child.nodeName in ("Email", "SpecificEmail"):
                self.email = getText(child)
                self.emailPublic = child.getAttribute("Public")
            elif child.nodeName == "CIPSContact":
                self.cipsContact = getText(child)
            elif child.nodeName == "OrganizationAddressNames":
                for grandchild in child.childNodes:
                    if grandchild.nodeName == "OrganizationName":
                        name = getText(grandchild)
                        if name: self.orgNames.append(name)
            elif child.nodeName == "OrganizationLocation":
                if child.getAttribute("OrderParentNameFirst") == "Yes":
                    orderParentNameFirst = 1
            elif child.nodeName == "PersonTitle":
                self.personTitle = getText(child)
        if orderParentNameFirst and len(self.orgNames) > 1:
            self.orgNames.reverse()

class HomeLocation(PersonLocation):
    "Derived class for a home location for a person."
    def __init__(self, node):
        PersonLocation.__init__(self)
        self.id = node.getAttribute("id")
        for child in node.childNodes:
            if child.nodeName == "CIPSContact":
                self.cipsContact = getText(child)
            if child.nodeName == "PostalAddress":
                self.address = Address(child)
            elif child.nodeName == "Phone":
                self.phone = getText(child)
            elif child.nodeName == "TollFreePhone":
                self.tollFreePhone = getText(child)
            elif child.nodeName == "Fax":
                self.fax = getText(child)
            elif child.nodeName == "Email":
                self.email = getText(child)
                self.emailPublic = child.getAttribute("Public")

class SiteContact:
    "Contains name string and phone for Status & Participant site contact."
    def __init__(self, name = "", phone = ""):
        self.name   = name
        self.phone  = phone

class ParticipatingSite:
    "Interesting information for an org participating in a protocol."
    def __init__(self, node):
        self.name           = None
        self.contacts       = []
        self.status         = None
        for child in node.childNodes:
            if child.nodeName == "OrgSiteName":
                self.name = getText(child)
            elif child.nodeName == "PrivatePracticeSiteName":
                self.name = PersonName(child).format(1)
            elif child.nodeName == "SiteStatus":
                self.status = getText(child)
            elif child.nodeName == "SpecificPerson":
                self.contacts.append(SiteContact(PersonName(child).format()))
            elif child.nodeName == "GenericPerson":
                self.contacts.append(SiteContact(getText(child)))
            elif child.nodeName == "Phone":
                phone = getText(child)
                if not self.contacts or self.contacts[-1].phone:
                    self.contacts.append(SiteContact(phone = phone))
                else:
                    self.contacts[-1].phone = phone

    def __cmp__(self, other):
        if self.status == "Active":
            if other.status != "Active":
                return -1
        elif other.status == "Active":
            return 1
        return cmp(self.name, other.name)

def getText(node, transformToLatex = 1, trimSpace = 1):
    """
    Extracts and concatenates the text nodes from an element, and
    filters the characters to make them ready for insertion into a
    LaTeX source document.

    Parameters:
       tranformToLatex - Changes the character set since Latex can't handle
                         Unicode
       trimSpace       - Trims whitespace from both ends of data.
    """
    result = ""
    for child in node.childNodes:
        if child.nodeType == node.TEXT_NODE:
            result = result + child.data
    if trimSpace:
        result = result.strip()
    if transformToLatex:
        return UnicodeToLatex.convert(result)
    else:
        return result

def getTextByPath(path, node):
    """
    Finds a node by its relative XPath and extract its text value.  Very
    crude tool; does not handle attributes, and assumes that there is
    exactly one occurrence of each element in the path name.
    """
    if not node:
        return None
    for elemName in path.split("/"):
        newNode = None
        for child in node.childNodes:
            if child.nodeName == elemName:
                newNode = child
                break
        if not newNode:
            return None
        node = newNode
    return getText(node)

def findControls (docFmt, fmtType):
    "Retrieve the instructions for a given doc format and format type."
    try:
        ctl = ControlTable[(docFmt, fmtType)]
    except (KeyError):
        sys.stderr.write (
          "No control information stored for '%s':'%s'" % (docFmt, fmtType))
        sys.exit()
    return ctl

def cite (pp):
    "Retrieves the instructions for a given doc format and format type."

    # Build output string here
    citeString = ''

    # Get the current citation node
    citeNode = pp.getCurNode()

    # If it's a sibling to another one, we've already processed it
    # Don't neeed to do any more
    prevNode = citeNode.previousSibling
    if prevNode and prevNode.nodeName == 'CitationLink':
        return 0

    # Beginning of list of one or more citation numbers
    citeString = r"\cite{"

    # Capture the text of all contiguous citation references,
    #   separating them with commas
    count = 0
    while citeNode != None and \
        citeNode.nodeName == 'CitationLink':

        # Comma separator before all but the first one
        if count > 0:
            citeString += r","

        # Reference index number is in the refidx attribute
        # Extract the attribute value from the Citation
        # tag
        # ------------------------------------------------------
        attrValue = citeNode.getAttribute ('refidx')
        if (attrValue != None):
            citeString += attrValue

        # Increment count and check the next sibling
        count += 1
        citeNode = citeNode.nextSibling

    # Terminate the Latex for the list of citation
    citeString += r"} "

    # Return info to caller, who will output it to the Latex
    pp.setOutput (citeString)

    return 0

def bibitem (pp):
    """
    Creates the link between the citations listed within the text
    and the references as listed in the Reference block of each
    chapter of a summary.
    """

    # Build output string here
    refString = ''

    # Get the current citation node
    refNode = pp.getCurNode()

    # Beginning of the bibitem element
    refString = "\n  \\bibitem{"

    # Reference index number is in the refidx attribute
    # Extract the attribute value from the Citation
    # tag
    # ------------------------------------------------------
    attrValue = refNode.getAttribute ('refidx')
    if (attrValue != None):
        refString += attrValue
        ## refString += refNode.nextSibling


    # Terminate the Latex for the list of citation
    refString += r"}"

    # Return info to caller, who will output it to the Latex
    pp.setOutput (refString)

    return 0

def protocolTitle (pp):
    "Get the PDQ and original protocol titles for the summary mailer."
    node = pp.getCurNode()
    attr = node.getAttribute("Type")
    macro = None
    if attr == "Professional":
        macro = "\\newcommand\\PDQProtocolTitle{{\\bfseries PDQ Title:}"
    elif attr == "Original":
        macro = "\\newcommand\\OriginalProtocolTitle{{\\bfseries "\
                "Original Title:}"
    if macro:
        pp.setOutput("  %s %s \\\\}\n" % (macro, getText(node)))

def street (pp):
    """
    Retrieves multiple street lines and separate each element with
    a newline to be displayed properly in LaTeX.
    """

    # Build output string here
    streetString = ''

    # Get the current street node
    streetNode = pp.getCurNode()

    # Beginning of list of one or more street lines
    streetString = "  \\renewcommand{\\Street}{%\n    "

    # If the current Street element is a sibling to another Street
    # element we've already processed it as part of the first
    # street line.
    # Don't need to do any more and can exit here.
    # -------------------------------------------------------------
    prevNode = streetNode.previousSibling
    while prevNode != None:
        if prevNode.nodeName == 'Street':
            return 0
        prevNode = prevNode.previousSibling

    # Capture the text of all contiguous street lines separating,
    # them with a LaTeX newline and line break
    # ------------------------------------------------------------
    streetNode = pp.getCurNode()
    while streetNode != None and \
          streetNode.nodeName == 'Street':

        # The street line text is a child of the Street node
        # Loop through all children of the node to extract the
        # text
        # Note:  If the text nodes are parents to other children
        #        this part will need to be expanded to include those
        # ----------------------------------------------------------
        count = 0
        while streetNode != None:

            txtNode = streetNode.firstChild
            while txtNode != None:
                if count > 0:
                    streetString += " \\newline \n"
                if streetNode.nodeName == 'Street':
                    streetString += UnicodeToLatex.convert(txtNode.nodeValue)
                txtNode = txtNode.nextSibling
                count += 1

            streetNode = streetNode.nextSibling


    # Terminate the Latex for the list of street line
    streetString += "\n  }\n"

    # Return info to caller, who will output it to the Latex
    pp.setOutput (streetString)

    return 0


def yesno (pp):
    """
    Used to create records within a LaTeX table of the format
       Description     Yes     No
    ===============================
     My Description     X
     Next Description           X

    After the description field is printed this procedure finds
    the sibling element with the Yes/No flag information and prints
    a predefined LaTeX command called
         \Check{X}
         with X = Y  -->  Output:     X   space
              else   -->  Output:    space  X

    If the Description field is a SpecialtyCategory an additional
    check is set for the board certification.
    """
    rootField  = pp.args[0]
    checkField = pp.args[1]
    # Build output string here
    checkString = ''

    # Get the current citation node
    checkNode = pp.getCurNode()
    boardNode = pp.getCurNode()

    # Capture the text of all contiguous street lines separating,
    # them with a LaTeX newline and line break
    # ------------------------------------------------------------
    checkNode = pp.getCurNode()
    while checkNode != None and \
           checkNode.nodeName == rootField:

        # The YesNo text is a child of the YesNo node
        # Loop through all siblings of the node and pick up text
        # as the child
        # ----------------------------------------------------------
        checkNode = checkNode.nextSibling
        while checkNode != None:
           if checkNode.nodeName == checkField:
              txtNode = checkNode.firstChild
              checkit = txtNode.nodeValue
              if checkit == "Yes":
                 checkString += " \\Check{Y}"
              else:
                 checkString += " \\Check{N}"

              # For the Specialty category loop through the list of
              # siblings again since we may have passed a board
              # certification earlier.  However, the Check{} for this
              # certification must come as a second entry in LaTeX
              # -----------------------------------------------------
              if checkNode.nodeName == "BoardCertifiedSpecialtyName":
                 while boardNode != None:
                    if boardNode.nodeName == "BoardCertified":
                       txtNode = boardNode.firstChild
                       checkboard = txtNode.nodeValue
                       if checkboard == "Yes":
                          checkString += " \\Check{Y}"
                       else:
                          checkString += " \\Check{B}"
                    boardNode = boardNode.nextSibling

           checkNode = checkNode.nextSibling

        # Once we know the YesNo value we can end the LaTeX line and
        # return to the calling program
        # ----------------------------------------------------------
        checkString += " \\Check{B} \\\\ \hline\n"
        pp.setOutput (checkString)

        return 0

    return 0

def findListDepth(listType):
    global listStack
    listDepth = 0
    for list in listStack:
        if list.listType == listType:
            listDepth += 1
    return listDepth

def openList(pp):
    "Processes the start of a list element."

    global listStack

    node = pp.getCurNode()

    # Honor the kind of numbering requested in the source document.
    style = node.getAttribute("Style")
    listStyle = ""
    listLevel = None
    enumStyle = None
    listDepth = findListDepth(node.nodeName)
    if listDepth == 0: listLevel = "i"
    elif listDepth == 1: listLevel = "ii"
    elif listDepth == 2: listLevel = "iii"
    elif listDepth == 3: listLevel = "iv"
    elif listDepth == 4: listLevel = "v"
    if node.nodeName == "ItemizedList":
        command = "itemize"
        if listLevel:
            if style == "bullet": enumStyle = "$\\bullet$"
            elif style == "dash": enumStyle = "--"
            elif style == "simple": enumStyle = ""
            else: enumStyle = "$\\bullet$"
            listStyle = "  \\renewcommand{\\labelitem%s}{%s}\n" % (listLevel,
                                                                    enumStyle)
    else:
        command = "enumerate"
        if listLevel:
            if style == "Arabic": enumStyle = "arabic"
            elif style == "UAlpha": enumStyle = "Alph"
            elif style == "URoman": enumStyle = "Roman"
            elif style == "LAlpha": enumStyle = "alph"
            elif style == "LRoman": enumStyle = "roman"
            if enumStyle:
                listStyle = r"""
  \renewcommand{\theenum%s}{\%s{enum%s}}
  \renewcommand{\labelenum%s}{\theenum%s.}
""" % (listLevel, enumStyle, listLevel, listLevel, listLevel)

    # If Compact is set to 'No' then we insert an additional blank line.
    compact = node.getAttribute("Compact")
    output = "  \\setlength{\\parskip}{0pt}\n"
    if compact == "No":
        compact = 0
        output += "  \\setlength{\\itemsep}{10pt}\n  \\vspace{6pt}\n"
    else:
        compact = 1
        output += "  \\setlength{\\itemsep}{-2pt}\n"

    # Pick up the list titles if there are any.
    for child in node.childNodes:
        if child.nodeName == "ListTitle":
            output += "  \\par {\\it \\bfseries %s}\n" % getText(child)

    # Remember the list so we know how deeply nested we are.
    listStack.append(List(compact, node.nodeName))

    # Start the list.
    pp.setOutput(output + listStyle + "  \\begin{%s}\n" % command)

def closeList(pp):
    "Forgets the list style we've finished processing."
    global listStack
    thisList = listStack.pop()
    if thisList.listType == "ItemizedList":
        output = "\n  \\end{itemize}\n"
    else:
        output = "\n  \\end{enumerate}\n"
    if not listStack:
        output += "  \\setlength{\\parskip}{1.2mm}\n"
    pp.setOutput(output)

def preserveLines(str):
    "Filter which adds line preservation to output."
    return str.replace('\n', '\\\\\n')

def stripLines(str):
    "Filter which removes paragraph breaks."
    return str.replace('\r', '').replace('\n', ' ')

def stripEnds(str):
    "Filter which strips leading and trailing whitespace."
    return str.strip()

def orgLocs(pp):
    "Handle organization locations."

    # Gather in all the locations for the organization.
    otherLocs = []
    blankLine = r"\makebox[200pt]{\hrulefill}"
    cipsContact = None
    cipsContactName = ""
    topNode = pp.getTopNode()
    cipsContactPersons = topNode.getElementsByTagName("CIPSContactPerson")
    if cipsContactPersons:
        cipsContactPerson = PersonName(cipsContactPersons[0])
        cipsContactName   = "  %s \\\\\n" % cipsContactPerson.format(1)
    for child in pp.getCurNode().childNodes:
        if child.nodeName == "OrganizationLocation":
            loc = OrgLoc(child)
            if loc.cipsContact:
                cipsContact = loc
            else:
                otherLocs.append(loc)

    # Start the output for the body of the mailer.
    # centerHead = "  \\afterpage{\\fancyhead[C]{{\\bfseries \\OrgName}}}"
    output = "\n  \\OrgIntro\n\n" #% centerHead

    # Add the CIPS contact information.
    adminOnly = "(For administrative use only)"
    if cipsContact and cipsContact.address:
        formattedAddress = cipsContact.address.format()
        if formattedAddress:
            output = r"""
  \OrgIntro


  \subsection*{Primary Contact Location}

%s  \OrgName \\
%s

   \newcommand{\ewidth}{180pt}
   \begin{entry}
      \item[Main Organization Phone]                     %s      \\
      \item[Main Organization Fax]                       %s      \\
                                                         %s      \\
      \item[Main Organization E-Mail]                    %s      \\
      \item[Publish E-Mail to PDQ/Cancer.gov]            \yesno  \\
      \item[Website]                                     %s
   \end{entry}
""" % (cipsContactName,
       cipsContact.address.format(1),
       cipsContact.phone or blankLine,
       cipsContact.fax   or blankLine, adminOnly,
       cipsContact.email or blankLine,
       cipsContact.web   or blankLine)

    # Add the other locations for the organization.
    if otherLocs:
        output += r"""
  \subsection*{Other Locations}
  \begin{enumerate}
"""
        for loc in otherLocs:
            if loc.address:
                formattedAddress = loc.address.format(1)
                if formattedAddress:
                    output += r"""
  \item
  \OrgName \\
%s
  \renewcommand{\ewidth}{180pt}
  \begin{entry}
    \item[Phone]                                      %s       \\
    \item[Fax]                                        %s       \\
                                                      %s       \\
    \item[E-Mail]                                     %s       \\
    \item[Publish E-Mail to PDQ/Cancer.gov]           \yesno   \\
    \item[Website]                                    %s
  \end{entry}
  \vspace{15pt}
""" % (formattedAddress,
       loc.phone or blankLine,
       loc.fax   or blankLine, adminOnly,
       loc.email or blankLine,
       loc.web   or blankLine)
        output += """
  \end{enumerate}
"""

    # Pump out the location information for the organization.
    pp.setOutput(output)

def getCoopMemberships(node):
    "Extract an organization's memberships in cooperative groups."
    coops = []
    pathToCoopName = "CooperativeGroup/OfficialName/Name"
    for child in node.childNodes:
        if child.nodeName in ("AffiliateMemberOf", "MainMemberOf"):
            coopName = getTextByPath(pathToCoopName, child)
            if coopName:
                coops.append(coopName)
            #for grandchild in child.childNodes:
            #    if grandchild.nodeName == "CooperativeGroup":
            #        for greatgrandchild in grandchild.childNodes:
            #            if greatgrandchild.nodeName == "OfficialName":
            #                for greatgreatgrandchild in \
            #                        greatgrandchild.childNode:
            #                    if greatgreatgrandchild.nodeName == "Name":
            #                        coops.append(getText(
            #                            greatgreatgrandchild))
    return coops

def orgAffil(pp):
    "Handle the organization's affiliations."

    # Gather up the affiliation information.
    profOrgs = []
    coops    = []
    for child in pp.getCurNode().childNodes:
        if child.nodeName == "MemberOfProfessionalOrganization":
            profOrgs.append(getText(child))
        elif child.nodeName == "MemberOfCooperativeGroups":
            coops = getCoopMemberships(child)

    # Do nothing if there are no affiliations.
    if not profOrgs and not coops:
        return
    else:
        output = "  \\subsection*{Affiliations}\n"

    # Format the professional organization affiliations.
    output = r"""
  \subsection*{Affiliations}
"""
    if profOrgs:
        output += r"""
  \subsubsection*{Professional Organizations}
  \begin{itemize}
"""
        for org in profOrgs:
            output += "  \\item %s\n" % org
        output += "  \\end{itemize}\n"

    # Format the cooperative group affiliations.
    if coops:
        output += r"""
  \subsubsection*{Clinical Trial Groups}
  \begin{itemize}
"""
        for org in coops:
            output += "  \\item %s\n" % org
        output += "  \\end{itemize}\n"
    pp.setOutput(output)

def getState(node):
    """
    Extract the state name from a PoliticalSubUnit_State element.
    Use the short name if there is one; otherwise take the long one.
    """
    shortName = None
    fullName  = None
    for child in node.childNodes:
        if child.nodeName == "PoliticalSubUnitShortName":
            shortName = getText(child)
        elif child.nodeName == "PoliticalSubUnitFullName":
            fullName = getText(child)
    return shortName or fullName

def protLeadOrg(pp):
    "Extract everything we need from the ProtocolLeadOrg element into macros."

    # Extract the information we need into a convenient object.
    leadOrg = ProtLeadOrg(pp.getCurNode())

    # Do nothing if this isn't the org we're sending the mailer to.
    if not leadOrg.sendMailerTo:
        return

    # Set the values for the macros.
    if leadOrg.currentStatus and leadOrg.currentStatus.date:
        statDate = leadOrg.currentStatus.date
    else:
        statDate = "Unknown"
    orgName = leadOrg.officialName or "Name Unknown"
    if not leadOrg.protChair:
        address   = "Not specified"
        protChair = "Not specified"
        phone     = ""
    else:
        addressOrgs = ""
        roles = ", ".join(leadOrg.protChair.roles)
        for addressOrg in leadOrg.protChair.orgs:
            addressOrgs += "  %s \\\\\n" % addressOrg
        if not leadOrg.protChair.name:
            protChair = "[Name Unknown], %s" % roles
        else:
            protChair = "%s, %s" % (leadOrg.protChair.name.format(1), roles)
        phone = leadOrg.protChair.phone or "Not specified"
        if not leadOrg.protChair.address:
            address = "Not specified"
        else:
            address = addressOrgs + leadOrg.protChair.address.format(1)
            if not address:
                address = "Not specified"

    # Assemble the macros.
    pp.setOutput(r"""
  \newcommand{\ProtocolActiveDate}{%s}
  \renewcommand{\ProtocolLeadOrg}{%s}
  \newcommand{\ProtocolChair}{%s}
  \renewcommand{\ChairPhone}{%s}
  \newcommand{\ChairAddress}{
%s}
""" % (statDate, orgName, protChair, phone, address))

def leadOrgRole(pp):
    "Remember if this is a secondary lead organization"
    if getText(pp.getCurNode()) == "Secondary":
        pp.setOutput("  \\renewcommand{\\secondaryLeadOrg}{ (Secondary)}\n")

def sectPrefix(level, name):
    "Create the prefix for a protocol (sub)section."
    return r"""
  \setcounter{qC}{0}
  \%s{%s}
""" % (level, name)

def optProtSect(pp):
    "Create prefix for a protocol (sub)section if it's not empty."
    if pp.getCurNode().hasChildNodes():
        pp.setOutput(r"""
  \setcounter{qC}{0}
  \%s{%s}
""" % (pp.args[0], pp.args[1]))

def protPhaseAndDesign(pp):
    """
    Extract the protocol phase and design information.  The protocol phase
    section is required, even if no data is found.  The design section is
    only shown if at least one ProtocolDesign element is found.
    """
    phases = []
    designs = []
    for child in pp.getTopNode().childNodes:
        if child.nodeName == "ProtocolPhase":
            phases.append(getText(child))
        elif child.nodeName == "ProtocolDesign":
            designs.append(getText(child))
    output = "  \\newcommand\\ProtocolPhaseAndDesign{\\item[Protocol Phase] "
    if phases:
        output += ", ".join(phases) + " \n"
    else:
        output += "*** MISSING ***\n"
    if designs:
        output += "\\item[Protocol Design] %s \n" % ", ".join(designs)
    pp.setOutput(output + "}\n")

def protRetrievalTerms(pp):
    """
    Gather terms for the Disease Retrieval Terms section of the protocol
    abstract mailer.  The terms are pulled from the conditions listed in
    the ProtocolDetail element, and the diagnoses listed in the Eligibility
    element.  The terms are merged into a single list, de-duplicated, and
    sorted into a single alphabet listing.
    """
    terms = {}
    for child in pp.getTopNode().childNodes:
        if child.nodeName == "ProtocolDetail":
            for term in child.getElementsByTagName("SpecificCondition"):
                terms[getText(term)] = "Condition"
        elif child.nodeName == "Eligibility":
            for term in child.getElementsByTagName("SpecificDiagnosis"):
                terms[getText(term)] = "Diagnosis"
    keys = terms.keys()
    keys.sort()
    output = r"""\
  \subsection*{Disease Retrieval Terms}
  \begin{itemize}{\setlength{\itemsep}{-5pt}}
  \setlength{\parskip}{0mm}
"""
    for term in keys:
        output += "  \\item %s\n" % term
    pp.setOutput(output + r"""\
  \end{itemize}
  \setlength{\parskip}{1.2mm}
""")

def checkNotAbstracted(pp):
    "Check for a missing optional protocol section."
    topNode = pp.getTopNode()
    target, section = pp.args
    nodes = topNode.getElementsByTagName(target)
    if nodes and nodes[0].hasChildNodes():
        return
    pp.setOutput(r"""
  \subsection*{%s}

  Not abstracted.
""" % section)

def getDeadline():
    "Create the string format for a deadline 60 days from now."
    now = list(time.localtime())
    now[2] += 60
    then = time.mktime(now)
    return time.strftime("%b. %d, %Y", time.localtime(then))

def personName(pp):
    "Extract everything we need from the PersonNameInformation element."
    name = PersonName(pp.getCurNode())
    formattedName = name.format(0)
    nameWithSuffixes = name.format(1)
    pp.setOutput(r"""
  \newcommand{\PersonName}{%s}
  \newcommand{\PersonNameWithSuffixes}{%s}
""" % (formattedName, nameWithSuffixes))

def personLocs(pp):
    "Extract all of the locations from a person document."

    # Gather all the location information together.
    cipsContact = None
    otherLocs   = []
    blankLine   = r"\makebox[200pt]{\hrulefill}"
    for node in pp.getCurNode().childNodes:
        loc = None
        if node.nodeName == "OtherPracticeLocation":
            loc = OtherPracticeLocation(node)
        elif node.nodeName == "PrivatePractice":
            loc = PrivatePracticeLocation(node)
        elif node.nodeName == "Home":
            loc = HomeLocation(node)
        if loc:
            if loc.cipsContact:
                cipsContact = loc
            else:
                otherLocs.append(loc)

    # Output the address block for the mailer.
    adminOnly = "(For administrative use only)"
    address = cipsContact and cipsContact.formatAddress() or ""
    cipsContactInfo = "  \\PersonNameWithSuffixes \\\\\n"
    blankTemplate = r"""\
  \begin{entry}
    \item[Name of Organization]                          %s      \\
    \item[Address of Organization]                       %s      \\
                                                         %s      \\
                                                         %s      \\
                                                         %s      \\
                                                         %s      \\
    \item[Title]                                         %s      \\
    \item[Phone]                                         %s      \\
    \item[Fax]                                           %s      \\
                                                         %s      \\
    \item[E-Mail]                                        %s      \\
    \item[Publish E-Mail to PDQ/Cancer.gov]              \yesno  \\
    \item[Website]                                       %s      \\
  \end{entry}
""" % (blankLine,
       blankLine,
       blankLine,
       blankLine,
       blankLine,
       blankLine,
       blankLine,
       blankLine,
       blankLine, adminOnly,
       blankLine,
       blankLine)
    if not cipsContact and not otherLocs:
        pp.setOutput(r"""\
  \newcommand{\ewidth}{180pt}
  \PersonNameWithSuffixes
""" + blankTemplate)
        return

    if cipsContact:
        cipsContactInfo += address
        if cipsContact.address.country:
            cipsContactInfo += "  %s \\\\\n" % cipsContact.address.country
        # Make email public Yes or No
        cipsContactInfo += personEmailPublic(cipsContact.email,
                                             cipsContact.emailPublic)
        # Form itself
        cipsContactInfo += r"""
  \renewcommand{\ewidth}{180pt}
  \begin{entry}
    \item[Phone]                                         %s      \\
    \item[Fax]                                           %s      \\
                                                         %s      \\
    \item[E-Mail]                                        %s      \\
    \item[Publish E-Mail to PDQ/Cancer.gov]              \emailPublicYesOrNoCircles  \\
    \item[Website]                                       %s      \\
  \end{entry}
""" % (cipsContact.phone or blankLine,
       cipsContact.fax   or blankLine, adminOnly,
       cipsContact.email or blankLine,
       cipsContact.web   or blankLine)

    # Output the CIPS contact location's information.
    output = r"""
  \newcommand{\ewidth}{180pt}

  \PersonIntro

  \subsection*{Primary Contact Location}

%s

  \subsection*{Other Practice Locations}

""" % cipsContactInfo

    # Add any other locations.
    if otherLocs:
        output += "  \\begin{enumerate}\n"
        for loc in otherLocs:
            # Make email public Yes or No for this location
            output += personEmailPublic(loc.email, loc.emailPublic)
            # Full location data
            output += r"""
  \item
  %s

  \renewcommand{\ewidth}{180pt}
  \begin{entry}
    \item[Phone]                                         %s      \\
    \item[Fax]                                           %s      \\
                                                         %s      \\
    \item[E-Mail]                                        %s      \\
    \item[Publish E-Mail to PDQ/Cancer.gov]              \emailPublicYesOrNoCircles  \\
    \item[Website]                                       %s      \\
  \end{entry}
  \vspace{15pt}
""" % (loc.formatAddress(1),
       loc.phone or blankLine,
       loc.fax   or blankLine, adminOnly,
       loc.email or blankLine,
       loc.web   or blankLine)

        output += "  \\end{enumerate}\n"

    else:
        output += r"""\
  \renewcommand{\ewidth}{180pt}
""" + blankTemplate

    # Pump out the results.
    pp.setOutput(output)

def personSpecialties(pp):
    "Build tables showing a person's specialties and memberships."

    # Lists of standard specialties and groups are cached.
    global personLists
    if not personLists:
        personLists = PersonLists()

    # Start with a clean slate.
    boardSpecialties = {}
    otherSpecialties = {}
    profSocieties    = {}
    trialGroups      = {}
    # oncologyPrograms = {}

    # Gather the information specific to this physician.
    node = pp.getTopNode()
    for elem in node.getElementsByTagName("BoardCertifiedSpecialty"):
        name = ""
        certified = 0
        for child in elem.childNodes:
            if child.nodeName == "BoardCertifiedSpecialtyName":
                name = getText(child)
            elif child.nodeName == "Certified":
                if getText(child) == "Yes":
                    certified = 1
        boardSpecialties[name] = certified
    for elem in node.getElementsByTagName("OtherSpecialty"):
        otherSpecialties[getText(elem)] = 1
    for elem in node.getElementsByTagName("MemberOfMedicalSociety"):
        profSocieties[getText(elem)] = 1
    for elem in node.getElementsByTagName("CooperativeGroup"):
        child = elem.firstChild
        link = None
        while child and not link:
            if child.nodeName == "Ref":
                link = getText(child)
            child = child.nextSibling
        if link:
            tail = link.find('#')
            if tail != -1:
                link = link[:tail]
            link = re.sub(r"[^\d]", "", link)
            try:
                trialGroups[int(link)] = 1
            except:
                pass

    # Don't yet know how to find out what oncology programs they're members of.
    # Find out from Lakshmi. XXX

    # Start the table for the specialties.
    output = r"""
  \pagebreak
  \subsection*{Specialty Information}
  \hspace{1mm}
  \vspace{-\baselineskip}
  %\subsubsection*{Board Certified Specialties}
  \setlength{\doublerulesep}{0.5pt}
  \begin{longtable}[l]{||p{250pt}||p{35pt}|p{35pt}||p{35pt}|p{35pt}||}
  \caption*{\bfseries Board Certified Specialties} \\
    \hline
  & \multicolumn{2}{c||}{\bfseries{ }}
  & \multicolumn{2}{c||}{\bfseries{Board}} \\
  & \multicolumn{2}{c||}{\bfseries{Specialty}}
  & \multicolumn{2}{c||}{\bfseries{Certification}} \\
    \bfseries{Specialty Name}
  & \multicolumn{1}{c|}{\bfseries{Yes}}
  & \multicolumn{1}{c||}{\bfseries{No}}
  & \multicolumn{1}{c|}{\bfseries{Yes}}
  & \multicolumn{1}{c||}{\bfseries{No}} \\
    \hline
    \hline
  \endfirsthead

    \multicolumn{5}{l}{(continued from previous page)} \\
    \hline
  & \multicolumn{2}{c||}{\bfseries{ }}
  & \multicolumn{2}{c||}{\bfseries{Board}} \\
  & \multicolumn{2}{c||}{\bfseries{Specialty}}
  & \multicolumn{2}{c||}{\bfseries{Certification}} \\
    \bfseries{Specialty Name}
  & \multicolumn{1}{c|}{\bfseries{Yes}}
  & \multicolumn{1}{c||}{\bfseries{No}}
  & \multicolumn{1}{c|}{\bfseries{Yes}}
  & \multicolumn{1}{c||}{\bfseries{No}} \\
    \hline
    \hline
  \endhead
"""

    # Populate the table.
    personLists.boardSpecialties.sort()
    for specialty in personLists.boardSpecialties:
        if boardSpecialties.has_key(specialty):
            hasSpecialty = "\\Check{Y}"
            if boardSpecialties[specialty]:
                isCertified = "\\Check{Y}"
            else:
                isCertified = "\\Check{N}"
        else:
            hasSpecialty = isCertified = "\\Check{N}"
        output += "  %s %s %s \\\\ \\hline\n" % (specialty, hasSpecialty,
                                                            isCertified)
    # Start the table for non-board-certified specialties.
    output += r"""
  \end{longtable}

  \hspace{1mm}
  \vspace{-\baselineskip}

  %\subsubsection*{Other Specialties}
  \begin{longtable}[l]{||p{344pt}||p{35pt}|p{35pt}||}
  \caption*{\bfseries Other Specialties} \\
    \hline
  \bfseries{Specialty Training}
  & \multicolumn{1}{c|}{\bfseries{Yes}}
  & \multicolumn{1}{c||}{\bfseries{No}} \\
    \hline
    \hline
  \endfirsthead
    \multicolumn{3}{l}{(continued from previous page)} \\
    \hline
    \bfseries{Specialty Training}
  & \multicolumn{1}{c|}{\bfseries{Yes}}
  & \multicolumn{1}{c||}{\bfseries{No}} \\
    \hline
    \hline
  \endhead
"""

    # Populate the table.
    personLists.otherSpecialties.sort()
    for specialty in personLists.otherSpecialties:
        flag = otherSpecialties.has_key(specialty) and "Y" or "N"
        output += "  %s \\Check{%s} \\\\ \\hline\n" % (specialty, flag)

    # Start the table for membership in professional medical societies.
    output += r"""
  \end{longtable}

  \subsection*{Membership Information}
  \hspace{1mm}
  \vspace{-\baselineskip}
  \nopagebreak
  \begin{longtable}[l]{|p{350pt}||p{35pt}|p{35pt}||}
  \caption*{\bfseries Professional Societies} \\
    \hline
  & \multicolumn{2}{c||}{\bfseries{Member of:}}  \\
    \bfseries{Society Name}
  & \multicolumn{1}{c|}{\bfseries{Yes}}
  & \multicolumn{1}{c||}{\bfseries{No}} \\
    \hline
    \hline
  \endfirsthead
    \multicolumn{3}{l}{(continued from previous page)} \\
    \hline
  & \multicolumn{2}{c|}{\bfseries{Member of:}}  \\
    \bfseries{Society Name}
  & \multicolumn{1}{c|}{\bfseries{Yes}}
  & \multicolumn{1}{c|}{\bfseries{No}} \\
    \hline
    \hline
  \endhead
"""

    # Populate the table.
    personLists.profSocieties.sort()
    for society in personLists.profSocieties:
        flag = profSocieties.has_key(society) and "Y" or "N"
        output += "  %s \\Check{%s} \\\\ \\hline\n" % (society, flag)

    # Start the table for affiliation with trial groups.
    output += r"""
  \end{longtable}

  \hspace{1mm}
  \vspace{-\baselineskip}
  %\subsubsection*{NCI Clinical Trials Groups}
  \begin{longtable}[l]{|p{344pt}||p{35pt}|p{35pt}||}
  \caption*{\bfseries NCI Clinical Trials Groups} \\
    \hline
    \bfseries{Group Name}
  & \multicolumn{1}{c|}{\bfseries{Yes}}
  & \multicolumn{1}{c||}{\bfseries{No}} \\
    \hline
    \hline
  \endfirsthead
    \multicolumn{3}{l}{(continued from previous page)} \\
    \hline
    \bfseries{Group Name}
  & \multicolumn{1}{c|}{\bfseries{Yes}}
  & \multicolumn{1}{c||}{\bfseries{No}} \\
    \hline
    \hline
  \endhead
"""

    # Populate the table.
    for group in personLists.trialGroups:
        flag = trialGroups.has_key(group[0]) and "Y" or "N"
        output += "  %s \\Check{%s} \\\\ \\hline\n" % (group[1], flag)
    output += r"""
  \end{longtable}
"""

    # Pump it out.
    pp.setOutput(output)

def personProtocols(pp):
    """
    Find out how many protocols the person is associated with.
    """
    import cdrdb
    loStatPath       = '/InScopeProtocol/ProtocolAdminInfo/ProtocolLeadOrg' \
                       '/LeadOrgProtocolStatuses/CurrentOrgStatus/StatusName'
    loPersonPath     = '/InScopeProtocol/ProtocolAdminInfo/ProtocolLeadOrg' \
                       '/LeadOrgPersonnel/Person/@cdr:ref'
    loPersonRolePath = '/InScopeProtocol/ProtocolAdminInfo/ProtocolLeadOrg' \
                       '/LeadOrgPersonnel/PersonRole'
    ppSiteIdPath     = '/InScopeProtocol/ProtocolAdminInfo/ProtocolLeadOrg' \
                       '/ProtocolSites/PrivatePracticeSite' \
                       '/PrivatePracticeSiteID/@cdr:ref'
    ppStatusPath     = '/InScopeProtocol/ProtocolAdminInfo/ProtocolLeadOrg' \
                       '/ProtocolSites/PrivatePracticeSite' \
                       '/PrivatePracticeSiteStatus'
    spPath           = '/InScopeProtocol/ProtocolAdminInfo/ProtocolLeadOrg' \
                       '/ProtocolSites/OrgSite/OrgSiteContact' \
                       '/SpecificPerson/Person/@cdr:ref'
    orgSiteStatus    = '/InScopeProtocol/ProtocolAdminInfo/ProtocolLeadOrg' \
                       '/ProtocolSites/OrgSite/OrgSiteStatus'
    docId = None
    for child in pp.getTopNode().childNodes:
        if child.nodeName == "DocId":
            docId = int(re.sub(r"[^\d]+", "", getText(child)))
            break
    if not docId: return
    conn   = cdrdb.connect('CdrGuest')
    cursor = conn.cursor()
    conn.setAutoCommit(1)
    cursor.execute("""\
SELECT DISTINCT lead_org_stat.doc_id prot_id,
                lead_org_stat.value lead_org_status
           INTO #lead_org_person
           FROM query_term lead_org_stat
           JOIN query_term person
             ON person.doc_id = lead_org_stat.doc_id
            AND LEFT(person.node_loc, 8) = LEFT(lead_org_stat.node_loc, 8)
           JOIN query_term person_role
             ON person.doc_id = person_role.doc_id
            AND LEFT(person.node_loc, 12) = LEFT(person_role.node_loc, 12)
          WHERE lead_org_stat.path = '%s'
            AND person.path = '%s'
            AND person_role.path = '%s'
            AND person_role.value <> 'Update Person'
            AND EXISTS (SELECT *
                          FROM primary_pub_doc
                         WHERE doc_id = lead_org_stat.doc_id)
            AND person.int_val = %d""" % (loStatPath,
                                         loPersonPath,
                                         loPersonRolePath,
                                         docId))
    cursor.execute("""\
SELECT DISTINCT lead_org_stat.doc_id prot_id
           INTO #private_practice_person
           FROM query_term lead_org_stat
           JOIN query_term person
             ON person.doc_id = lead_org_stat.doc_id
            AND LEFT(person.node_loc, 8) = LEFT(lead_org_stat.node_loc, 8)
           JOIN query_term person_status
             ON person_status.doc_id = person.doc_id
            AND LEFT(person_status.node_loc, 16) = LEFT(person.node_loc, 16)
          WHERE lead_org_stat.path = '%s'
            AND person.path = '%s'
            AND person_status.path = '%s'
            AND lead_org_stat.value = 'Active'
            AND person_status.value = 'Active'
            AND EXISTS (SELECT *
                          FROM primary_pub_doc
                         WHERE doc_id = lead_org_stat.doc_id)
            AND person.int_val = %d""" % (loStatPath,
                                         ppSiteIdPath,
                                         ppStatusPath,
                                         docId))
    cursor.execute("""\
SELECT DISTINCT lead_org_stat.doc_id prot_id
           INTO #org_site_person
           FROM query_term lead_org_stat
           JOIN query_term person
             ON person.doc_id = lead_org_stat.doc_id
            AND LEFT(person.node_loc, 8) = LEFT(lead_org_stat.node_loc, 8)
           JOIN query_term site_status
             ON site_status.doc_id = person.doc_id
            AND LEFT(site_status.node_loc, 16) = LEFT(person.node_loc, 16)
          WHERE lead_org_stat.path = '%s'
            AND person.path = '%s'
            AND site_status.path = '%s'
            AND lead_org_stat.value = 'Active'
            AND site_status.value = 'Active'
            AND EXISTS (SELECT *
                          FROM primary_pub_doc
                         WHERE doc_id = lead_org_stat.doc_id)
            AND person.int_val = %d""" % (loStatPath,
                                         spPath,
                                         orgSiteStatus,
                                         docId))
    cursor.execute("""\
SELECT COUNT(*) FROM (
         SELECT prot_id
           FROM #lead_org_person
          WHERE lead_org_status IN ('Approved-not yet active', 'Active')
          UNION
         SELECT prot_id
           FROM #private_practice_person
          UNION
         SELECT prot_id
           FROM #org_site_person
) AS all_three_temp_tables""")
    row = cursor.fetchone()
    activeTrials = row[0]
    cursor.execute("""\
         SELECT COUNT(*)
           FROM #lead_org_person
          WHERE lead_org_status IN ('Closed',
                                    'Completed',
                                    'Temporarily Closed')""")
    row = cursor.fetchone()
    closedTrials = row[0]
    pp.setOutput(r"""\
  \subsection*{PDQ/Cancer.gov Clinical Trial Listing}
  \begin{tabbing}
    Closed Protocols: \= \kill
    Open Protocols: \> %d \\
    Closed Protocols: \> %d
  \end{tabbing}
""" % (activeTrials, closedTrials))

def personDirectoryInclude(pp):
    """
    Changes the meaning of a macro to put out circles for a user to check for
    inclusion in a person directory or not.
    Redefines \directoryIncludeYesOrNoCircles and retiredYesOrNoCircles.
    Must be called with the current element = to the Include element.

    The directoryInclude... macro affects multiple questions.  See
    PERSON_MISC_INFO.
    """
    # Current node should be Include element
    node = pp.getCurNode()
    if node.nodeName != "Include":
        raise XmlLatexException (\
            "personDirectoryInclude() called on wrong element")
    includeInDirectory = getText (node)

    # Redefine command if we know whether to include or not
    if includeInDirectory == "Include":
        pp.setOutput (\
            r"\renewcommand{\directoryIncludeYesOrNoCircles}{\YESno}" + \
            r"\renewcommand{\retiredYesOrNoCircles}{\yesNO}")
    elif includeInDirectory == "Do not include":
        pp.setOutput (\
            r"\renewcommand{\directoryIncludeYesOrNoCircles}{\yesNO}" + \
            r"\renewcommand{\retiredYesOrNoCircles}{\YESno}")

    # If value is anything else ("Pending"), do nothing

def personEmailPublic(emailAddr, noString):
    """
    Same concept as personDirectoryInclude, but used to tell whether
    Email is public or not.

    Redefines \emailPublicYesOrNoCircles.

    This routine is called from inside routines that are assembling
    LaTeX strings, so we return the required LaTeX for inclusion in the
    assembly rather than appending it directly to output.

    Pass:
        noString = "No" = Put an x in the "no" circle.
                   Else put an x in the "yes" circle.
    Return:
        A LaTeX string containing the renewcommand for
        emailPublicYesOrNoCircles.
    """
    # Redefine command based on whether email exists and is public
    if not emailAddr or emailAddr == "":
        return r"\renewcommand{\emailPublicYesOrNoCircles}{\yesno}"
    if not noString or noString != "No":
        # Undefined, empty, or something other than 'No'
        return r"\renewcommand{\emailPublicYesOrNoCircles}{\YESno}"
    # Email exists and attribute said Public="No"
    return r"\renewcommand{\emailPublicYesOrNoCircles}{\yesNO}"

def statPup(pp):
    "Build the address block for the protocol update person."
    name    = ""
    title   = ""
    address = ""
    org     = ""
    phone   = ""
    for node in pp.getCurNode().childNodes:
        if node.nodeName == "Name":
            name = PersonName(node)
        elif node.nodeName == "Location":
            for child in node.childNodes:
                if child.nodeName == "PersonTitle":
                    title = ", " + getText(child)
                elif child.nodeName == "Org":
                    org = getText(child)
                elif child.nodeName == "PostalAddress":
                    address = Address(child)
                elif child.nodeName == "Phone":
                    phone = getText(child)
    output = r"""
  \newcommand{\PUP}{%s}
  %s%s \\
""" % (name, name, title)

    # This is all we do now.
    pp.setOutput("  \\newcommand{\\PUP}{%s}\n" % name.format())
    """
    if org:
        output += "  %s \\\\\n" % org
    if address:
        output += address.format(1)
    if phone:
        output += "  Ph.: %s \\\\\n" % phone
    pp.setOutput(output)
    """

def statPersonnel(pp):
    "Generate macros for the other lead org's personnel."
    name = ""
    role = ""
    address = ""
    phone = ""
    for node in pp.getCurNode().childNodes:
        if node.nodeName == "Name":
            name = PersonName(node).format(1)
        elif node.nodeName == "Location":
            for child in node.childNodes:
                if child.nodeName == "PostalAddress":
                    address = Address(child)
                elif child.nodeName == "Phone":
                    phone = getText(child)
        elif node.nodeName == "Role":
            role = getText(node)
    address = address.format(1)
    while address and address[-1] in " \n\r\\": address = address[:-1]
    pp.setOutput(r"""
  \newcommand{\LeadPerson}{%s}
  \newcommand{\LeadRole}{%s}
  \newcommand{\LeadPhone}{%s}
  \newcommand{\LeadAddress}{%%
%s}
""" % (name, role, phone, address))

def statProtSites(pp):
    """
    Originally did these one at a time, in pieces, using Alan's
    model for element-driven processing.  But then Lakshmi and
    Margaret asked for complex sorting, which couldn't be done
    in the XSL/T phase without adding an additional filter.
    """
    sites = []
    output = ""
    for child in pp.getCurNode().childNodes:
        if child.nodeName == "ParticipatingSite":
            sites.append(ParticipatingSite(child))
    sites.sort()
    for site in sites:
        template = " %s & %%s & %%s \\Check{%s} \\\\ \\hline \n" % \
            (site.name, site.status == 'Active' and 'Y' or 'N')
        if not site.contacts:
            site.contacts.append(SiteContact())
        for contact in site.contacts:
            output += template % (contact.name, contact.phone)
            template = " & %s & %s & & \\\\ \\hline \n"
        """
        contact = ""
        phone   = site.phone
        if site.specificPerson:
            contact = site.specificPerson.format()
        elif site.genericPerson:
            contact = site.genericPerson
        output += " %s & %s & %s \\Check{%s} \\\\ \\hline \n" % (
            site.name, contact, phone,
            site.status == 'Active' and 'Y' or 'N')
        """
    pp.setOutput(output)

def statSiteStatus(pp):
    "Add the status for a protocol participating organization."
    status = getText(pp.getCurNode())
    flag = (status == 'Active') and 'Y' or 'N'
    pp.setOutput("  \\Check{%s} \\\\ \\hline \n" % flag)


####################################################################
# Constants
####################################################################

# Starting LaTeX document and document preamble.
# - uses package textcompt for UNICODE processing
# - sets parameters to limit line break problems during processing
# Used by:  All
# ----------------------------------------------------------------
LATEXHEADER=r"""
  %% LATEXHEADER %%
  %% ----------- %%
  %% This LaTeX Document has been automatically generated!!!
  %% Do not edit this file unless for temporary use.
  %%
  %% -- START -- Document Declarations and Definitions
  \documentclass[letterpaper,12pt]{article}
  \usepackage{textcomp}
  \usepackage{array}
  \usepackage{longtable}
  \usepackage{longerlists}
  %\usepackage{supertabular}
  \usepackage{graphicx}
  %\usepackage{afterpage}
  \newcommand{\Special}[1]{{\fontencoding{T1}\selectfont\symbol{#1}}}
  %% OR MAYBE:
  %% \documentclass[11pt]{article}
  %% \usepackage{vmargin}
  %% \setpapersize{USletter}
  %% \setmarginsrb{.9in}{.9in}{.9in}{0pt}{0mm}{0pt}{0mm}
  %% \renewcommand{\familydefault}{cmss}

  %% Eliminate warnings on overfull hbox by adjusting the stretch parameters
  \tolerance=1000
  \emergencystretch=20pt

% -----
"""


# Prints word "Draft" at bottom of pages during testing
# Used by:  All
# -----------------------------------------------------
DRAFT=r"""
  %% DRAFT %%
  %% ----- %%
  %% Remove next 3 lines for production %%%
  \usepackage[none,light,bottom]{draftcopy}
  \draftcopySetGrey{0.90}
  \draftcopyVersion{1.0~~}
%
% -----
"""


# Defines the default font to be used for the document
# Used by:  All
# ----------------------------------------------------
FONT=r"""
  %% FONT %%
  %% ---- %%
  % Changing Font
  %\renewcommand{\familydefault}{\myfont}
  %\newcommand{\myfont}{phv}
%
% -----
"""


# Settings to format the table of contents
# Used by:  Summary
# ----------------------------------------
TOCHEADER=r"""
  %% TOCHEADER %%
  %% --------- %%
  % Note:  tocloft.sty modified to eliminate '...' leader for subsections
  \usepackage{tocloft}
  \setlength{\cftbeforetoctitleskip}{50pt}
  \setlength{\cftbeforesecskip}{5pt}
  \setlength{\cftsecindent}{-17pt}
  \setlength{\cftsubsecindent}{30pt}
%
% -----
"""


PROTOCOL_HDRTEXT=r"""
  %%%% PROTOCOL_HDRTEXT%%%%
  %%%% --------------- %%%%
  \newcommand{\LeftHdr}{PDQ/Cancer.gov Abstract Update \\ %s \\}
  \newcommand{\CenterHdr}{{\bfseries Protocol ID: \ProtocolID}}
  \newcommand{\RightHdr}{Mailer ID:  @@MailerDocID@@ \\ Doc ID: @@DOCID@@ \\}
%%
%% -----
""" % time.strftime("%B %Y")


SUMMARY_HDRTEXT=r"""
  %% SUMMARY_HDRTEXT%%
  %% --------------- %%
  \newcommand{\CenterHdr}{{\bfseries \SummaryTitle} \\ }
  \newcommand{\RightHdr}{Reviewer:  @@BoardMember@@}
  \newcommand{\LeftHdr}{\today}
%
% -----
"""

STATPART_HDRTEXT=r"""
  %%%% STATPART_HDRTEXT %%%%
  %%%% ---------------- %%%%
  \newcommand{\CenterHdr}{{\bfseries Protocol Update Person: \PUP}}
  \newcommand{\RightHdr}{Mailer ID: @@MAILERID@@ \\ Doc ID: @@DOCID@@ \\}
  \newcommand{\LeftHdr}{PDQ/Cancer.gov Status \& Participant Site Check \\
                        %s \\}
%%
%% -----
""" % time.strftime("%B %Y")

# Defining the document header for each page
# Used by:  Organization
# ------------------------------------------
ORG_HDRTEXT=r"""
  %%%% ORG_HDRTEXT %%%%
  %%%% ----------- %%%%
  \newcommand{\CenterHdr}{{\bfseries \OrgName}}
  %%\newcommand{\CenterHdr}{%%
  %%    \raisebox{.5in}[.5in]{%%
  %%        \includegraphics[width=100pt]{%%
  %%            /cdr/mailers/include/ncilogo.eps}} \\ {\bfseries \OrgName}}
  \newcommand{\RightHdr}{Mailer ID: @@MAILERID@@ \\ Doc ID: @@DOCID@@ \\}
  \newcommand{\LeftHdr}{PDQ/Cancer.gov Organization Update \\ %s \\}
%%
%% -----
""" % time.strftime("%B %Y")

# Defining the document header for each page
# Used by:  Person
#   \directoryIncludeYesOrNoCircles defaults to two empty circles.
#    Will be redefined later if "Include" is 'Include' or 'Do not Include'
#   Ditto for emailPublicYesOrNoCircles.
# ------------------------------------------
PERSON_HDRTEXT=r"""
  %%%% PERSON_HDRTEXT %%%%
  %%%% -------------- %%%%
  \newcommand{\LeftHdr}{PDQ/Cancer.gov Physician Update \\ %s \\}
  \newcommand{\CenterHdr}{{\bfseries \PersonNameWithSuffixes}}
  \newcommand{\RightHdr}{Mailer ID: @@MAILERID@@ \\ Doc ID: @@DOCID@@ \\}
  \newcommand{\directoryIncludeYesOrNoCircles}{\yesno}
  \newcommand{\retiredYesOrNoCircles}{\yesno}
  \newcommand{\emailPublicYesOrNoCircles}{\yesno}
%%
%% -----
""" % time.strftime("%B %Y")

FANCYHDR=r"""
  %% FANCYHDR %%
  %% -------- %%
  % Package Fancyhdr for Header/Footer/Reviewer Information
  % -------------------------------------------------------
  \usepackage{fancyhdr}
  \fancypagestyle{myheadings}{%
      \setlength{\headheight}{120pt}
      %\setlength{\textheight}{6.0in}
      \fancyhead[L]{\LeftHdr}
      \fancyhead[R]{\RightHdr}
      \fancyfoot[C]{\thepage}
      \fancyhead[C]{%
          \includegraphics[width=75pt]{/cdr/mailers/include/nciLogo.eps} \\
          \vspace{40pt}
          {\bfseries \CenterHdr }}}

  \pagestyle{fancy}

  % Placing information in header
  % -----------------------------
  \fancyhead[C]{\CenterHdr}
  \fancyhead[L]{\LeftHdr}
  \fancyhead[R]{\RightHdr}
  \fancyfoot[C]{\thepage}
  \renewcommand\headrulewidth{1pt}
  \renewcommand\footrulewidth{1pt}
%
% -----
"""


TEXT_BOX=r"""
  %% TEXT_BOX %%
  %% -------- %%
  \setlength{\headwidth}{6.5in}
  \setlength{\textwidth}{6.5in}
  \setlength{\textheight}{8.0in}
  \setlength{\oddsidemargin}{0in}
%
% -----
"""


CITATION=r"""
  %% CITATION %%
  %% -------- %%
  %% START - Definitions for Summary Mailers
  %% Style file to
  %% - format citations (exponented and in bold)
  %% - create literature reference for each chapter
  \usepackage{overcite}
  \renewcommand\citeform[1]{\bfseries #1}
  \makeatletter\def\@cite#1{\textsuperscript{[#1]}}\makeatother

  \usepackage{chapterbib}

  % Modify the default header "References" for Citation section
  \renewcommand\refname{References:}

  % Define the format of the Reference labels
  \makeatletter \renewcommand\@biblabel[1]{#1.} \makeatother

  % Define the number of levels and numbering to be displayed in the TOC
  \setcounter{secnumdepth}{1}
  \setcounter{tocdepth}{2}

  %% END - Definitions for Summary Mailers
%
% -----
"""

QUOTES=r"""
  %% QUOTES %%
  %% ------ %%
  % Package and code to set correct double-quotes
  % ---------------------------------------------
  \usepackage{ifthen}
  \newcounter{qC}
  \newcommand{\tQ}{%
        \addtocounter{qC}{1}%
        \ifthenelse{\isodd{\value{qC}}}{``}{''}%
  }
%
% -----
"""

STYLES=r"""
  %% Styles %%
  %% ------ %%
  % Package longtable used to print tables over multiple pages
  % ----------------------------------------------------------
  \usepackage{longtable}
  \usepackage{array}
  \usepackage{ulem}
  \usepackage{datenumber}
%
% -----
"""

ENTRYBFLIST=r"""
  %% ENTRYBFLIST %%
  %% ----------- %%
  % Package calc used in following list definition
  % ----------------------------------------------
  \usepackage{calc}

  % Define list environment
  % -----------------------
  \newcommand{\ewidth}{}
  \newcommand{\entrylabel}[1]{\mbox{\bfseries{#1:}}\hfil}
  \newenvironment{entry}
     {\begin{list}{}%
         {\renewcommand{\makelabel}{\entrylabel}%
          \setlength{\labelwidth}{\ewidth}%
          \setlength{\itemsep}{-2pt}%
          \setlength{\leftmargin}{\labelwidth+\labelsep}%
         }%
  }%
  {\end{list}}
%
% -----
"""

ENTRYLIST=r"""
  %% ENTRYLIST %%
  %% --------- %%
  % Package calc used in following list definition
  % ----------------------------------------------
  \usepackage{calc}

  % Define list environment
  % -----------------------
  \newcommand{\entrylabel}[1]{\mbox{#1:}\hfil}
  \newenvironment{entry}
     {\begin{list}{}%
         {\renewcommand{\makelabel}{\entrylabel}%
          \setlength{\labelwidth}{\ewidth}%
          \setlength{\itemsep}{-10pt}%
          \setlength{\leftmargin}{\labelwidth+\labelsep}%
         }%
  }%
  {\end{list}}
%
% -----
"""

PHONE_RULER=r"""
  %% PHONE_RULER %%
  %% ----------- %%
  % Provide On/Off radio button:  Button is either on or off
  % Syntax: \yes{Y} or \yew{N}
  % --------------------------------------------------------
  \newcommand{\yes}[1]{%
      \ifthenelse{\equal{#1}{Y}}{$\bigotimes$}{$\bigcirc$}}
  \newcommand{\yesno}{$\bigcirc$ Yes \qquad $\bigcirc$ No}
  \newcommand{\YESno}{$\textcircled{x}$ Yes \qquad $\bigcirc$ No}
  \newcommand{\yesNO}{$\bigcirc$ Yes \qquad $\textcircled{x}$ No}

  % Define the check marks for the 3 column tables
  % enter \Check{Y} or \Check{N} to set the mark
  % in either the left or right column
  % ----------------------------------------------
  \newcommand{\Check}[1]{%
      \ifthenelse{\equal{#1}{Y}}{ & \centerline{$\surd$} & }{ & &\centerline{$\surd$}}}
%
% -----
"""

PERSON_MISC_INFO=r"""
   %% PERSON_MISC_INFO %%
   %% ---------------- %%

   \subsection*{Preferred Contact Mode}
   $\bigcirc$ E-mail at primary contact \qquad $\bigcirc$ Mail

   \subsection*{Practice Information}
    Are you a physician (MD, DO, or foreign equivalent)?   \hfill
        \directoryIncludeYesOrNoCircles \\
    Do you currently treat cancer patients?                \hfill
        \directoryIncludeYesOrNoCircles \\
    Are you retired from practice?                         \hfill
        \retiredYesOrNoCircles  \\
    If you are not retired from practice, do you want
    to be listed in the                                    \hfill \\
    PDQ/Cancer.gov Directory of Physicians?                \hfill
        \directoryIncludeYesOrNoCircles \\

    If you answered Yes to the question above, please make sure you
    complete Specialty Information and Membership Information sections.
    This information is required for inclusion in the Directory.

%
% -----
"""

STATUS_TAB_INTRO=r"""
   %% STATUS_TAB_INTRO %%
   %% ------------------ %%

   \StatusTableIntro

%
% -----
"""


STATUS_TAB_CCOPINTRO=r"""
   %% STATUS_TAB_CCOPINTRO %%
   %% -------------------- %%

   \StatusTableCCOPMainIntro

%
% -----
"""


STATUS_CCOPMAIN_TAB=r"""
   %% STATUS_CCOPMAIN_TAB %%
   %% ------------------- %%
\begin{longtable}{|>{\raggedright }p{160pt}|>{\raggedright }p{115pt}|p{75pt}|p{27pt}|p{27pt}|}  \hline
    \bfseries           & \bfseries Principal &
    \bfseries           & \multicolumn{2}{c|}{\bfseries Partici-} \\
    \bfseries Site      & \bfseries Investigator/ &
    \bfseries Contact   & \multicolumn{2}{c|}{\bfseries pating} \\
    \bfseries (Main Members) & \bfseries Contact &
    \bfseries Phone     & \multicolumn{1}{c|}{\bfseries Yes} & \multicolumn{1}{c|}{\bfseries No} \\ \hline \hline
\endfirsthead
    \multicolumn{5}{l}{(continued from previous page)} \\ \hline
                        & \bfseries Principal &
                        & \multicolumn{2}{c|}{\bfseries Partici-} \\
    \bfseries Site      & \bfseries Investigator/ &
    \bfseries Contact   & \multicolumn{2}{c|}{\bfseries pating} \\
    \bfseries (Main Members) & \bfseries Contact &
    \bfseries Phone     & \multicolumn{1}{c|}{\bfseries Yes} & \multicolumn{1}{c|}{\bfseries No} \\ \hline \hline
\endhead
%
% -----
"""


STATUS_CCOPAFFL_TAB=r"""
   %% STATUS_CCOPAFFL_TAB %%
   %% ------------------- %%
\begin{longtable}{|>{\raggedright }p{160pt}|>{\raggedright }p{115pt}|p{75pt}|p{27pt}|p{27pt}|}  \hline
    \bfseries           & \bfseries Principal &
    \bfseries           & \multicolumn{2}{c|}{\bfseries Partici-} \\
    \bfseries Site      & \bfseries Investigator/ &
    \bfseries Contact   & \multicolumn{2}{c|}{\bfseries pating} \\
    \bfseries (Affiliate Members) & \bfseries Contact &
    \bfseries Phone     & \multicolumn{1}{c|}{\bfseries Yes} & \multicolumn{1}{c|}{\bfseries No} \\ \hline \hline
\endfirsthead
    \multicolumn{5}{l}{(continued from previous page)} \\ \hline
                        & \bfseries Principal &
                        & \multicolumn{2}{c|}{\bfseries Partici-} \\
    \bfseries Site      & \bfseries Investigator/ &
    \bfseries Contact   & \multicolumn{2}{c|}{\bfseries pating} \\
    \bfseries (Affiliate Members) & \bfseries Contact &
    \bfseries Phone     & \multicolumn{1}{c|}{\bfseries Yes} & \multicolumn{1}{c|}{\bfseries No} \\ \hline \hline
\endhead
%
% -----
"""


STATUS_TAB=r"""
   %% STATUS_TAB %%
   %% --------------- %%
\begin{longtable}{|>{\raggedright }p{160pt}|>{\raggedright }p{115pt}|p{75pt}|p{27pt}|p{27pt}|}  \hline
    \bfseries           &  &
    \bfseries           & \multicolumn{2}{c|}{\bfseries Partici-} \\
    \bfseries           &  &
    \bfseries Contact   & \multicolumn{2}{c|}{\bfseries pating} \\
    \bfseries Site      & \bfseries Contact &
    \bfseries Phone     & \multicolumn{1}{c|}{\bfseries Yes} & \multicolumn{1}{c|}{\bfseries No} \\ \hline \hline
\endfirsthead
    \multicolumn{5}{l}{(continued from previous page)} \\ \hline
                        & &
                        & \multicolumn{2}{c|}{\bfseries Partici-} \\
    \bfseries           & &
    \bfseries Contact   & \multicolumn{2}{c|}{\bfseries pating} \\
    \bfseries Site      & \bfseries Contact &
    \bfseries Phone     & \multicolumn{1}{c|}{\bfseries Yes} & \multicolumn{1}{c|}{\bfseries No} \\ \hline \hline
\endhead
%
% -----
"""


END_TABLE=r"""
   %% END_TABLE %%
   %% --------- %%
   \end{longtable}
%
% -----
"""

ENDSUMMARYPREAMBLE=r"""
  %% ENDSUMMARYPREAMBLE %%
  %% ------------------ %%
  \setlength{\parskip}{1.2mm}
  \setlength{\parindent}{0mm}
  \setlength{\headheight}{28pt}

  \renewcommand{\thesection}{\hspace{-1.0em}}

  \renewcommand{\footskip}{70pt}

  %% -- END -- Document Declarations and Definitions

  \begin{document}

  % Tell fancyhdr package to modify the plain style (plain style is
  % default on a cover page), e.g. put header on first page as well.
  % ----------------------------------------------------------------
  %\fancypagestyle{plain}{%
  %   \fancyhead[C]{\bfseries \SummaryTitle\\}
  %   \fancyhead[L]{\today}
  %   \fancyhead[R]{\TheBoardMember}
  %   \fancyfoot[C]{Font phv \\ \thepage}
  %   \renewcommand\headrulewidth{1pt}
  %   \renewcommand\footrulewidth{1pt}}

  \begin{center}{\bfseries \Large
    \SummaryTitle \\
%    Font: \myfont
    }
  \end{center}
  \tableofcontents

%
% -----
"""


STATPART_TITLE=r"""
  %% STATPART_TITLE %%
  %% -------------- %%
  \newcommand{\mailertitle}{%
    National Cancer Institute's PDQ Database \\
    Cooperative Group Clinical Trial Status and Participating Sites Check
  }
  \newcommand{\secondaryLeadOrg}{}
  \setlength{\hoffset}{-18pt}

%
% -----
"""

ENDPREAMBLE=r"""
  %% ENDPREAMBLE %%
  %% ----------- %%
  \setlength{\parskip}{1.2mm}
  \setlength{\parindent}{0mm}
  \setlength{\headheight}{48pt}

  \renewcommand{\thesection}{\hspace{-1.0em}}
  \newcommand{\deadline}{""" + getDeadline() + r"""}

  %% -- END -- Document Declarations and Definitions


  \begin{document}
  \include{/cdr/mailers/include/template}

  \begin{center}\bfseries \large
    \mailertitle
  \end{center}
%  \centerline{Font: \myfont}
%
% -----
"""

ALTENDPREAMBLE=r"""
  %% ALTENDPREAMBLE %%
  %% -------------- %%
  \setlength{\parskip}{1.2mm}
  \setlength{\parindent}{0mm}
  \setlength{\headheight}{48pt}
  \setlength{\footskip}{60pt}

  \renewcommand{\thesection}{\hspace{-1.0em}}
  %\newcommand{\deadline}{""" + getDeadline() + r"""}

  %% -- END -- Document Declarations and Definitions


  \begin{document}
  \include{/cdr/mailers/include/template}

%
% -----
"""


ENDPROTOCOLPREAMBLE=r"""
  %% ENDPROTOCOLPREAMBLE %%
  %% ----------- %%
  \setlength{\parskip}{1.2mm}
  \setlength{\parindent}{0mm}
  \setlength{\headheight}{48pt}
  \setlength{\hoffset}{-40pt}
  \setlength{\hoffset}{-18pt}
  %\setlength{\textwidth}{7in}
  \setlength{\headwidth}{6.5in}
  \setlength{\textwidth}{6.5in}
  \setlength{\textheight}{8.0in}
  \setlength{\oddsidemargin}{0in}

  \renewcommand{\thesection}{\hspace{-1.0em}}
  \renewcommand{\theenumii}{\Roman{enumii}}
  \renewcommand{\labelenumii}{\theenumii.}

  %% -- END -- Document Declarations and Definitions


  \begin{document}
  \include{/cdr/mailers/include/template}

%
% -----
"""

PROTOCOLDEF=r"""
  %% PROTOCOLDEF %%
  %% ----------- %%
  \newcommand{\HighAge}{XXX}
  \newcommand{\LowAge}{XXX}
  \newcommand{\Disease}{XXX}
  \newcommand{\EligibilityText}{XXX}
  \newcommand{\Outline}{XXX}
  \newcommand{\BaselineTreatmentProcedures}{XXX}
  \newcommand{\MeasureofResponse}{XXX}
  \newcommand{\ProjectedAccrual}{XXX}
  \newcommand{\DiseaseCaveat}{XXX}
  \newcommand{\StratificationParameters}{XXX}
  \newcommand{\DosageFormulation}{XXX}
  \newcommand{\DosageSchedule}{XXX}
  \newcommand{\DiseaseCharacteristics}{XXX}
  \newcommand{\PatientCharacteristics}{XXX}
  \newcommand{\PriorConcurrentTherapy}{XXX}
  \newcommand{\ProtocolLeadOrg}{XXX}
  \newcommand{\ChairPhone}{XXX}
%
% -----
"""


PROTOCOLTITLE=r"""
  %% PROTOCOLTITLE %%
  %% ------------- %%

  % Tell fancyhdr package to modify the plain style (plain style is
        % default on a cover page), e.g. put header on first page as well.
  % ----------------------------------------------------------------
  \fancypagestyle{plain}{%
      % \fancyhf{}%
      \fancyhead[L]{\today}
      \fancyfoot[C]{\thepage}
      \renewcommand\headrulewidth{1pt}
      \renewcommand\footrulewidth{1pt}}

      \makeatletter \renewcommand\@biblabel[1]{[#1]} \makeatother

  \setcounter{qC}{0}
  \subsection*{Protocol Title}
  \OriginalProtocolTitle
  \PDQProtocolTitle
%
% -----
"""

PROTOCOLINFO=r"""
  %% PROTOCOLINFO %%
  %% ------------ %%

  \subsection*{General Protocol Information}

  \par
    \setcounter{qC}{0}

  \renewcommand{\ewidth}{180pt}
  \begin{entry}
     \item[Protocol ID]                \ProtocolID
                                       \OtherID
%    \item[Protocol Activation Date]   \ProtocolActiveDate
     \item[Current Protocol Status]    \ProtocolStatus
     \item[Lead Organization]          \ProtocolLeadOrg
     \item[Protocol Personnel]         \ProtocolChair
     \item[Phone]                      \ChairPhone
     \item[Address]                    \ChairAddress
     %\vspace{6pt}
     \item[Eligible Patient Age Range] \AgeText
     \item[Lower Age Limit]            \LowAge
     \item[Upper Age Limit]            \HighAge
     \ProtocolPhaseAndDesign
  \end{entry}
%
% -----
"""

PROTOCOLBOILER=r"""
  %% PROTOCOLBOILER %%
  %% ----------- %%
  % Following Text is Boilerplate

  \newpage
  If there are no changes to the abstract, please initial this page and
  fax or mail hard copy in the enclosed envelope to the PDQ/Cancer.gov
  Protocol Coordinator at the fax number/address below.  If you are
  requesting any changes to the abstract, please initial this page
  and return it with the revised abstract by fax or mail using the
  enclosed envelope.

  \vspace{24pt}

  \renewcommand{\ewidth}{80pt}
  \begin{entry}
     \item[Fax]          301-402-6728
     \item[Address]      PDQ Cancer.gov Protocol Coordinator \\
                         Attn: CIAT \\
                         Cancer Information Products and Systems, NCI, NIH \\
                         6116 Executive Blvd., Suite 3002B MSC-8321 \\
                         Bethesda MD 20892-8321
  \end{entry}

  \vspace{12pt}

  \newcommand\chkbox{\makebox[20pt]{\hrulefill}\ \ \ }

  If the status of this protocol has changed, please indicate
  the current status:
  \vspace{6pt}

  \begin{tabular}{llp{4in}}
  \chkbox & Approved-not yet active & Approved by NCI, but not yet
                                      accepting patients for \mbox{accrual} \\
  \chkbox & Active & Accepting patients for accrual \\
  \chkbox & Temporarily closed & Patient accrual on hold, pending
                                 evaluation \\
  \chkbox & Closed & No longer accepting patients; previously entered
                     patients will continue treatment \\
  \chkbox & Completed & Study closed, data collection completed \\
  \chkbox & Withdrawn & Study discontinued, and to be removed from the
                        PDQ/Cancer.gov database
  \end{tabular}

  \vspace{20pt}

  Please list/attach any citations resulting from this study.
  \vspace{6pt} \\
  \makebox[6.5in]{\hrulefill} \\
  \makebox[6.5in]{\hrulefill} \\
  \makebox[6.5in]{\hrulefill} \\

  \vspace{20pt}

  Please initial here if the abstract is satisfactory to you.
  \hrulefill

%
% -----
"""

###################################################################
# Processing instructions for mailers
#
#   Each of the following blocks defines a list of
#   instructions for converting a particular xml document type
#   into a particular latex format mailer.
#
# Structure:
#   Each set of instruction is a cdrxmllatex.XProc object.
#   The object may or may not have a tag associated with it.
#   Note that for XProcs with no element tag, some of the components
#   of the object, like "textOut" and "descend", are ignored
#
#   Example:
#       OversimplifedExampleInstructions = [\
#          XProc(\
#               preProcs=doThisFirst, ("With this arg", "and this one")),\
#          XProc(element="Author",\
#               descend=0,\
#               prefix="\fancyhead[C]{\bfseries \",\
#               suffix=" \\")),\
#          XProc(element="Title"),\
#          XProc(element="SummarySection",\
#               descend=0,\
#               preProcs=((handleSummary,),),\
#               textOut=0)),\
#          XProc(\
#               suffix="\End{document}")\
#       ]
#
###################################################################

CommonMarkupRules = (
    XProc(element   = "ItemizedList",
          textOut   = 0,
          preProcs  = ((openList, ()), ),
          postProcs = ((closeList, ()), )),
    XProc(element   = "OrderedList",
          textOut   = 0,
          preProcs  = ((openList, ()), ),
          postProcs = ((closeList, ()), )),
    XProc(element   = "ListItem",
          prefix    = "  \\item ",
          suffix    = "\n",
          filters   = [stripEnds, stripLines]),
    XProc(element   = "Para",
          filters   = [stripLines],
          prefix    = "  \\setcounter{qC}{0}\n",
          suffix    = "  \\par\n"),
    XProc(element   = "Table",
          textOut   = 0,
          preProcs  = ((cdrlatextables.openTable, ()), ),
          postProcs = ((cdrlatextables.closeTable, ()), )),
    XProc(element   = "TGroup",
          textOut   = 0,
          preProcs  = ((cdrlatextables.openGroup, ()), ),
          postProcs = ((cdrlatextables.closeGroup, ()), )),
    XProc(element   = "THead",
          textOut   = 0,
          preProcs  = ((cdrlatextables.openHeader, ()), ),
          postProcs = ((cdrlatextables.closeSection, ()), )),
    XProc(element   = "TBody",
          textOut   = 0,
          preProcs  = ((cdrlatextables.openBody, ()), ),
          postProcs = ((cdrlatextables.closeSection, ()), )),
    XProc(element   = "TFoot",
          textOut   = 0,
          preProcs  = ((cdrlatextables.openFooter, ()), ),
          postProcs = ((cdrlatextables.closeSection, ()), )),
    XProc(element   = "Row",
          textOut   = 0,
          preProcs  = ((cdrlatextables.openRow, ()), ),
          postProcs = ((cdrlatextables.closeRow, ()), )),
    XProc(element   = "entry",
          filters   = [stripLines],
          preProcs  = ((cdrlatextables.openCell, ()), ),
          postProcs = ((cdrlatextables.closeCell, ()), )),
    XProc(element   = "Note",
          prefix    = "{\it Note: ",
          suffix    = "}"),
    XProc(element   = "SummaryRef",
          prefix    = "\\emph{",
          suffix    = "}"),
    XProc(element   = "ExternalRef",
          prefix    = "\\emph{",
          suffix    = "}"),
    XProc(element   = "ProtocolLink",
          prefix    = "\\emph{",
          suffix    = "}"),
    XProc(element   = "GlossaryTermRef",
          prefix    = "\\emph{",
          suffix    = "}"),
    XProc(element   = "Emphasis",
          prefix    = "\\emph{",
          suffix    = "}"),
    XProc(element   = "GeneName",
          prefix    = "\\emph{",
          suffix    = "}"),
    XProc(element   = "DrugName"),
    XProc(element   = "ForeignWord",
          prefix    = "\\emph{",
          suffix    = "}"),
    XProc(element   = "InterventionName"),
    XProc(element   = "ScientificName",
          prefix    = "\\emph{",
          suffix    = "}"),
    XProc(element   = "Strong",
          prefix    = "\\textbf{",
          suffix    = "}"),
    XProc(element   = "Superscript",
          prefix    = "$^{",
          suffix    = "}$"),
    XProc(element   = "Subscript",
          prefix    = "$_{",
          suffix    = "}$"),
    XProc(element   = "TT",
          prefix    = "\\texttt{\\small{",
          suffix    = "}}",
          filters   = [preserveLines])
    )

#------------------------------------------------------------------
# Board Summaries
#
#   Instructions for formatting all board summary mailers
#------------------------------------------------------------------

DocumentSummaryBody = (
    XProc(element   = "/Summary/SummarySection",
          order     = XProc.ORDER_PARENT,
          prefix    = "\n  \\begin{cbunit}\n",
          suffix    = "\n  \\end{cbunit}\n\n"),
    XProc(element   = "/Summary/SummarySection/Title",
          order     = XProc.ORDER_PARENT,
          prefix    = "  \\section{",
          suffix    = "}\n\n",
          filters   = [stripEnds]),
    XProc(element   = "/Summary/SummarySection/SummarySection/Title",
          order     = XProc.ORDER_PARENT,
          prefix    = "  \\subsection{",
          suffix    = "}\n",
          filters   = [stripEnds]),
    XProc(element   = "/Summary/SummarySection/SummarySection/"
                      "SummarySection/Title",
          order     = XProc.ORDER_PARENT,
          prefix    = "  \\subsubsection{",
          suffix    = "}\n",
          filters   = [stripEnds]),
    XProc(element   = "Title",
          prefix    = "\n\n  \\vspace{10pt}\n  \\textbf{",
          suffix    = "} \\\\\n\n",
          filters   = [stripEnds]),
    XProc(element   = "SummarySection",
          textOut   = 0),
    XProc(element   = "CitationLink",
          textOut   = 0,
          preProcs  = ((cite,()),)),
    XProc(element   = "ReferenceList",
          order     = XProc.ORDER_PARENT,
          textOut   = 0,
          prefix    = "\n  \\begin{thebibliography}{999}\n",
          suffix    = "\n  \\end{thebibliography}\n"),
    XProc(element   = "Reference",
          order     = XProc.ORDER_PARENT,
          preProcs  = ( (bibitem, ()), )),
    )

#------------------------------------------------------------------
# Protocol abstracts - initial mailers
#
#   First time mailing of a protocol abstract
#
# Note to Alan: The initial and annual protocol abstract mailers
#               are identical with the exception of the activation
#               date for the initial mailer not being populated.
#               (And most likely a different cover letter created
#                by Bob's code).
#------------------------------------------------------------------

#------------------------------------------------------------------
# Protocol abstracts -
#
#   Putting together the header
#------------------------------------------------------------------

ProtAbstProtID = (
    XProc(prefix=PROTOCOLDEF, order=XProc.ORDER_TOP),

    XProc(element  = "/InScopeProtocol/ProtocolAdminInfo/ProtocolLeadOrg",
          order    = XProc.ORDER_TOP,
          preProcs = ((protLeadOrg, ()),)),

    XProc(element="/InScopeProtocol/ProtocolIDs/PrimaryID/IDString",
          order=XProc.ORDER_TOP,
          prefix=r"  \newcommand{\ProtocolID}{",
          suffix="}\n"),

    # Concatenating Other protocol IDs
    XProc(prefix="  \\newcommand{\OtherID}{\n  ", order=XProc.ORDER_TOP),
    XProc(element="/InScopeProtocol/ProtocolIDs/OtherID/IDString",
          order=XProc.ORDER_TOP,
          prefix="   \\\\",
          suffix="\n  "),
    XProc(prefix="}\n", order=XProc.ORDER_TOP),

    XProc(element="CurrentProtocolStatus",
          order=XProc.ORDER_TOP,
          prefix="  \\newcommand{\ProtocolStatus}{",
          suffix="}\n"),
    XProc(element="LowAge",
          order=XProc.ORDER_TOP,
          prefix="  \\renewcommand{\LowAge}{",
          suffix="}\n"),
    XProc(element="HighAge",
          order=XProc.ORDER_TOP,
          prefix="  \\renewcommand{\HighAge}{",
          suffix="}\n"),
    XProc(element="AgeText",
          order=XProc.ORDER_TOP,
          prefix=r"  \newcommand{\AgeText}{",
          suffix="}\n  "),
    XProc(preProcs  = [[protPhaseAndDesign]],
          order     = XProc.ORDER_TOP)
    )

ProtAbstInfo = (
    XProc(element="ProtocolTitle",
          textOut=0,
          order=XProc.ORDER_TOP,
          preProcs=( (protocolTitle, ()), ),),
    XProc(prefix=PROTOCOLTITLE, order=XProc.ORDER_TOP),
    XProc(prefix=PROTOCOLINFO, order=XProc.ORDER_TOP),
    XProc(preProcs  = [[protRetrievalTerms]],
          order     = XProc.ORDER_TOP),
    XProc(element   = "Objectives",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = sectPrefix("subsection*", "Protocol Objectives")),
    XProc(element   = "Outline",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = sectPrefix("subsection*", "Protocol Outline")),
    XProc(element   = "EntryCriteria",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = sectPrefix("subsection*", "Patient Eligibility")),
    XProc(element   = "DiseaseCharacteristics",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = sectPrefix("subsubsection", "Disease Characteristics")),
    XProc(element   = "PatientCharacteristics",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = sectPrefix("subsubsection", "Patient Characteristics")),
    XProc(element   = "PriorConcurrentTherapy",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = sectPrefix("subsubsection", "Prior/Concurrent Therapy")),
    XProc(element   = "GeneralEligibilityCriteria",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = sectPrefix("subsubsection", "General Criteria")),
    XProc(element   = "ProjectedAccrual",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = sectPrefix("subsection*", "Projected Accrual")),
    XProc(element   = "EndPoints",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          preProcs  = ((optProtSect, ("subsection*", "End Points")), )),
#    XProc(order     = XProc.ORDER_TOP,
#          textOut   = 0,
#          postProcs = ((checkNotAbstracted,
#                       ("EndPoints", "End Points")), )),
    XProc(element   = "Stratification",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          preProcs  = ((optProtSect, ("subsection*",
                                      "Stratification Parameters")), )),
#    XProc(order     = XProc.ORDER_TOP,
#          textOut   = 0,
#          postProcs = ((checkNotAbstracted,
#                       ("Stratification", "Stratification Parameters")), )),
    XProc(element   = "SpecialStudyParameters",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          preProcs  = ((optProtSect, ("subsection*",
                                      "Special Study Parameters")), )),
#    XProc(order     = XProc.ORDER_TOP,
#          textOut   = 0,
#          postProcs = ((checkNotAbstracted,
#                       ("SpecialStudyParameters",
#                        "Special Study Parameters")), )),
    XProc(element   = "DoseSchedule",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          preProcs  = ((optProtSect, ("subsection*", "Dose Schedule")), )),
#    XProc(order     = XProc.ORDER_TOP,
#          textOut   = 0,
#          postProcs = ((checkNotAbstracted,
#                       ("DoseSchedule", "Dose Schedule")), )),
    XProc(element   = "DosageForm",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          preProcs  = ((optProtSect, ("subsection*", "Dosage Form")), )),
#    XProc(order     = XProc.ORDER_TOP,
#          textOut   = 0,
#          postProcs = ((checkNotAbstracted,
#                       ("DosageForm", "Dosage Form")), )),
#    XProc(element   = "Rationale",
#          textOut   = 0,
#          order     = XProc.ORDER_TOP,
#          prefix    = sectPrefix("subsection*", "Protocol Rationale")),
#    XProc(element   = "Purpose",
#          textOut   = 0,
#          order     = XProc.ORDER_TOP,
#          prefix    = sectPrefix("subsection*", "Protocol Purpose")),
#    XProc(element   = "EligibilityText",
#          textOut   = 0,
#          order     = XProc.ORDER_TOP,
#          prefix    = sectPrefix("subsection*", "Eligibility Text")),
#    XProc(element   = "TreatmentIntervention",
#          textOut   = 0,
#          order     = XProc.ORDER_TOP,
#          prefix    = sectPrefix("subsection*", "Treatment/Intervention")),
#    XProc(element   = "ProfessionalDisclaimer",
#          textOut   = 0,
#          order     = XProc.ORDER_TOP,
#          prefix    = sectPrefix("subsection*", "Professional Disclaimer")),
#    XProc(element   = "PatientDisclaimer",
#          textOut   = 0,
#          order     = XProc.ORDER_TOP,
#          prefix    = sectPrefix("subsection*", "Patient Disclaimer")),
    XProc(prefix=PROTOCOLBOILER, order=XProc.ORDER_TOP),

    # Mask these out.
    XProc(element   = "GlossaryTerm",
          textOut   = 0,
          descend   = 0),
    XProc(element   = "/InScopeProtocol/ProtocolAbstract/Patient",
          textOut   = 0,
          descend   = 0),
    XProc(element   = "ProfessionalDisclaimer",
          textOut   = 0,
          descend   = 0),
    )

#------------------------------------------------------------------
# Organization Mailer Instructions (Body)
#   Instructions for formatting all Organization Mailers
#------------------------------------------------------------------
# --------- START: First section Contact Information ---------
DocumentOrgBody = (\

    XProc(element   = "/Organization/OrganizationNameInformation"
                      "/OfficialName/Name",
          order     = XProc.ORDER_TOP,
          prefix    = "  \\newcommand{\OrgName}{",
          suffix    = "}\n"),
    XProc(element   = "OrganizationLocations",
          preProcs  = ((orgLocs, ()), ),
          textOut   = 0,
          order     = XProc.ORDER_TOP),
    XProc(element   = "OrganizationAffiliations",
          preProcs  = ((orgAffil, ()), ),
          textOut   = 0,
          order     = XProc.ORDER_TOP),

    )

#------------------------------------------------------------------
# Person Mailer Instructions (Body)
#   Instructions for formatting all Person Mailers
#------------------------------------------------------------------
DocumentPersonBody = (

    XProc(element   = "PersonNameInformation",
          order     = XProc.ORDER_TOP,
          preProcs  = ((personName, ()), ),
          textOut   = 0,
          descend   = 0),
    XProc(element   = "PersonLocations",
          order     = XProc.ORDER_TOP,
          preProcs  = ((personLocs, ()), ),
          textOut   = 0,
          descend   = 0),
    XProc(preProcs  = [[personProtocols]],
          order     = XProc.ORDER_TOP),
    XProc(element   = "/Person/ProfessionalInformation/PhysicianDetails" + \
                      "/AdministrativeInformation/Directory/Include",
          order     = XProc.ORDER_TOP,
          preProcs  = ((personDirectoryInclude, ()), ),
          textOut   = 0,
          descend   = 0),
    XProc(prefix=PERSON_MISC_INFO, order=XProc.ORDER_TOP),
    XProc(order=XProc.ORDER_TOP,
          preProcs=((personSpecialties, ()), )),

    )


#------------------------------------------------------------------
# Status and Participant Site Check (non-Coop Groups)
#
#   Instructions for formatting all status and participant mailers
#------------------------------------------------------------------

STATUSDEF=r"""
   %% STATUSDEF %%
   %% --------- %%
   \StatusIntro

   \StatusDefinition
%
% -------
"""


STATUSDEFCCOP=r"""
   %% STATUSDEFCCOP %%
   %% ------------- %%
   \StatusIntro

   \StatusCCOPDefinition


%
% -------
"""


STATUSPROTINFO=r"""
   %% STATUSPROTINFO %%
   %% -------------- %%
  %\newpage
  %\item
  \textit{\ProtocolTitle}
  \renewcommand{\ewidth}{120pt}
  \begin{entry}
     \item[Protocol ID]        \ProtocolID
     \item[Current Status]     \CurrentStatus
     \item[Status Change]      If status has changed, please indicate
                               new status and the status change
                               date (MM/DD/YYYY)
                               \ProtStatDefinition
  \end{entry}
%
% -------
"""

STATUSCHAIRINFO=r"""
   %% STATUSCHAIRINFO %%
   %% -------------- %%
  \begin{entry}
     \item[Lead Organization]        \LeadOrg \secondaryLeadOrg
     \item[Protocol Personnel]       \LeadPerson,  \LeadRole
     \item[Address]                  \LeadAddress
     \item[Phone]                    \LeadPhone
  \end{entry}
%
% -------
"""


DocumentStatusCheckBody = (
    XProc(element   = "/SPSCheck/Protocol/ProtocolTitle",
          order     = XProc.ORDER_TOP,
          prefix    = "  \\newcommand{\\ProtocolTitle}{",
          suffix    = "}\n"),
    XProc(element   = "/SPSCheck/Protocol/CurrentStatus",
          order     = XProc.ORDER_TOP,
          prefix    = "  \\newcommand{\\CurrentStatus}{",
          suffix    = "}\n"),
    XProc(element   = "/SPSCheck/Protocol/ID",
          order     = XProc.ORDER_TOP,
          prefix    = "  \\newcommand{\\ProtocolID}{",
          suffix    = "}\n"),
    XProc(element   = "/SPSCheck/Protocol/LeadOrg",
          order     = XProc.ORDER_TOP,
          prefix    = "  \\newcommand{\\LeadOrg}{",
          suffix    = "}\n"),
    XProc(element   = "/SPSCheck/Protocol/LeadOrgRole",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          preProcs  = [[leadOrgRole]]),
    XProc(element   = "/SPSCheck/PUP",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          preProcs  = [[statPup]]),
    XProc(element   = "/SPSCheck/Protocol/Personnel",
          order     = XProc.ORDER_TOP,
          preProcs  = [[statPersonnel]],
          textOut   = 0,
          suffix    = STATUSPROTINFO + STATUSCHAIRINFO +
                      STATUS_TAB_INTRO + STATUS_TAB),
    XProc(element   = "/SPSCheck/Protocol/ProtocolSites",
          textOut   = 0,
          preProcs  = [[statProtSites]],
          suffix    = END_TABLE,
          order     = XProc.ORDER_TOP),
    )


DocumentStatusCheckCCOPBody = (
    XProc(element="PUP",
          textOut=0, order=XProc.ORDER_TOP),
    XProc(element="/SPSCheck/PUP/Name",
          textOut=1,
          prefix="  \\newcommand{\PUP}{",
          suffix="}\n", order=XProc.ORDER_TOP),
    XProc(element="Title",
          order=XProc.ORDER_PARENT,
          prefix="  \\newcommand{\PUPTitle}{",
          suffix="}\n"),
    XProc(element="/SPSCheck/PUP/Phone",
          prefix="  \\newcommand{\PUPPhone}{",
          suffix="}\n"),
    XProc(element="/SPSCheck/PUP/Street",
          textOut=0,
          preProcs=( (street, ()), )),
    XProc(element="/SPSCheck/PUP/Phone",
          prefix="  \\newcommand{\PUPPhone}{",
          suffix="}\n"),
    XProc(prefix=STATUSDEFCCOP,
          suffix="  \\begin{enumerate}\n", order=XProc.ORDER_TOP),
# --------- END: First section Contact Information ---------
# --------- START: Second section Protocol Information ---------
    XProc(element="Protocol",
          textOut=0,
          suffix=END_TABLE, order=XProc.ORDER_TOP),
    XProc(element="ProtocolTitle",
          order=XProc.ORDER_PARENT,
          prefix="  \\renewcommand{\\ProtocolTitle}{",
          suffix="  }\n "),
    XProc(element="CurrentStatus",
          order=XProc.ORDER_PARENT,
          prefix="  \\renewcommand{\\CurrentStatus}{",
          suffix="  }\n"),
    XProc(element="ID",
          order=XProc.ORDER_PARENT,
          prefix="  \\renewcommand{\\ProtocolID}{",
          suffix="  }\n  "),
    XProc(element="LeadOrg",
          order=XProc.ORDER_PARENT,
          prefix="  \\renewcommand{\\LeadOrg}{",
          suffix="  }\n"),
    # Need to start the table header as a suffix of the Personnel field
    # in order to create the table for each protocol record.
    XProc(element="Personnel",
          order=XProc.ORDER_PARENT,
          textOut=0,
          suffix=STATUSPROTINFO + STATUSCHAIRINFO +
                 STATUS_TAB_CCOPINTRO + STATUS_CCOPMAIN_TAB),
    XProc(element="/SPSCheck/Protocol/Personnel/Name",
          order=XProc.ORDER_PARENT,
          prefix="  \\renewcommand{\\LeadPerson}{",
          suffix="  }\n"),
    XProc(element="/SPSCheck/Protocol/Personnel/Role",
          order=XProc.ORDER_PARENT,
          prefix="  \\renewcommand{\\LeadRole}{",
          suffix="  }\n"),
    XProc(element="/SPSCheck/Protocol/Personnel/Street",
          textOut=0,
          order=XProc.ORDER_PARENT,
          preProcs=( (street, ()), )),
    XProc(element="/SPSCheck/Protocol/Personnel/Phone",
          order=XProc.ORDER_PARENT,
          prefix="  \\renewcommand{\\LeadPhone}{",
          suffix="  }\n"),
# --------- END: Second section Protocol Information ---------
# --------- START: Third section Protocol Information ---------
    # XProc(prefix=STATUS_SITES_TAB),
#    XProc(element="ParticipatingSite",
#          order=XProc.ORDER_PARENT,
#          textOut=0),
    XProc(element="Site",
          order=XProc.ORDER_PARENT,
          suffix="& "),
    XProc(element="PI",
          order=XProc.ORDER_PARENT,
          suffix="& "),
    XProc(element="/SPSCheck/Protocol/ParticipatingSite/Phone",
          order=XProc.ORDER_PARENT,
          postProcs=((yesno,("Phone","Recruiting",)),)),
    # XProc(prefix=END_TABLE),
    XProc(prefix="  \\end{enumerate}", order=XProc.ORDER_TOP),
    )


DocumentTestBody =(
    XProc(prefix=FONT, order=XProc.ORDER_TOP),
    )

# ###########################################################
# Creating the different types of Headers for each mailer
# ###########################################################

DocumentProtocolHeader =(
    XProc(prefix=LATEXHEADER, order=XProc.ORDER_TOP),
    #XProc(prefix=DRAFT, order=XProc.ORDER_TOP),
    XProc(prefix=FONT, order=XProc.ORDER_TOP),
    XProc(prefix=ENTRYBFLIST, order=XProc.ORDER_TOP),
    XProc(prefix=QUOTES, order=XProc.ORDER_TOP),
    XProc(prefix=CITATION, order=XProc.ORDER_TOP),
   #============================================================
   #   RMK 2002-09-14:
   #     1. Alan's code doesn't support relative path notation.
   #     2. If it did, we'd have duplicate command definitions for
   #        \ProtocolID
   #XProc(element="ProtocolIDs/PrimaryID/IDString",
   #      prefix=r"  \newcommand{\ProtocolID}{",
   #  suffix="}", order=XProc.ORDER_TOP),
   #============================================================
    XProc(prefix=PROTOCOL_HDRTEXT, order=XProc.ORDER_TOP),
    XProc(prefix=FANCYHDR, order=XProc.ORDER_TOP),
    XProc(prefix=ENDPROTOCOLPREAMBLE, order=XProc.ORDER_TOP)
    )

DocumentSummaryHeader =(
    XProc(prefix=LATEXHEADER, order=XProc.ORDER_TOP),
    #XProc(prefix=DRAFT, order=XProc.ORDER_TOP),
    XProc(prefix=FONT, order=XProc.ORDER_TOP),
    XProc(prefix=TOCHEADER, order=XProc.ORDER_TOP),
    XProc(prefix=QUOTES, order=XProc.ORDER_TOP),
    XProc(prefix=CITATION, order=XProc.ORDER_TOP),
    XProc(element="SummaryTitle",
          prefix=r"  \newcommand{\SummaryTitle}{",
          suffix="}", order=XProc.ORDER_TOP),
    XProc(prefix=SUMMARY_HDRTEXT, order=XProc.ORDER_TOP),
    XProc(prefix=FANCYHDR, order=XProc.ORDER_TOP),
    XProc(prefix=ENDSUMMARYPREAMBLE, order=XProc.ORDER_TOP)
    )

DocumentOrgHeader =(
    XProc(prefix=LATEXHEADER, order=XProc.ORDER_TOP),
    #XProc(prefix=DRAFT, order=XProc.ORDER_TOP),
    XProc(prefix=FONT, order=XProc.ORDER_TOP),
    XProc(prefix=STYLES, order=XProc.ORDER_TOP),
    XProc(prefix=ENTRYLIST, order=XProc.ORDER_TOP),
    XProc(prefix=QUOTES, order=XProc.ORDER_TOP),
    XProc(prefix=ORG_HDRTEXT, order=XProc.ORDER_TOP),
    XProc(prefix=FANCYHDR, order=XProc.ORDER_TOP),
    XProc(prefix=TEXT_BOX, order=XProc.ORDER_TOP),
    XProc(prefix="  \\setlength{\\textheight}{7.0in}\n", order=XProc.ORDER_TOP),
    XProc(prefix=PHONE_RULER, order=XProc.ORDER_TOP),
    XProc(prefix=ALTENDPREAMBLE, order=XProc.ORDER_TOP),
    XProc(prefix=r"""\
  \thispagestyle{myheadings}
  \setlength{\textheight}{8.0in}
""", order=XProc.ORDER_TOP)
    )

DocumentPersonHeader =(
    XProc(prefix=LATEXHEADER, order=XProc.ORDER_TOP),
    #XProc(prefix=DRAFT, order=XProc.ORDER_TOP),
    XProc(prefix=FONT, order=XProc.ORDER_TOP),
    XProc(prefix=STYLES, order=XProc.ORDER_TOP),
    XProc(prefix=ENTRYLIST, order=XProc.ORDER_TOP),
    XProc(prefix=QUOTES, order=XProc.ORDER_TOP),
    XProc(prefix=PERSON_HDRTEXT, order=XProc.ORDER_TOP),
    XProc(prefix=FANCYHDR, order=XProc.ORDER_TOP),
    XProc(prefix=TEXT_BOX, order=XProc.ORDER_TOP),
    XProc(prefix="  \\setlength{\\textheight}{7.0in}\n", order=XProc.ORDER_TOP),
    XProc(prefix=PHONE_RULER, order=XProc.ORDER_TOP),
    XProc(prefix=ALTENDPREAMBLE, order=XProc.ORDER_TOP),
    XProc(prefix=r"""\
  \thispagestyle{myheadings}
  \setlength{\textheight}{8.0in}
""", order=XProc.ORDER_TOP)
    )

DocumentStatusCheckHeader =(
    XProc(prefix=LATEXHEADER, order=XProc.ORDER_TOP),
    #XProc(prefix=DRAFT, order=XProc.ORDER_TOP),
    XProc(prefix=FONT, order=XProc.ORDER_TOP),
    XProc(prefix=STYLES, order=XProc.ORDER_TOP),
    XProc(prefix=ENTRYBFLIST, order=XProc.ORDER_TOP),
    XProc(prefix=QUOTES, order=XProc.ORDER_TOP),
    XProc(prefix=STATPART_HDRTEXT, order=XProc.ORDER_TOP),
    XProc(prefix=FANCYHDR, order=XProc.ORDER_TOP),
    XProc(prefix=TEXT_BOX, order=XProc.ORDER_TOP),
    XProc(prefix=PHONE_RULER, order=XProc.ORDER_TOP),
    XProc(prefix=STATPART_TITLE, order=XProc.ORDER_TOP),
    XProc(prefix=ALTENDPREAMBLE, order=XProc.ORDER_TOP),
    )


DocumentTestHeader =(
    XProc(prefix=LATEXHEADER, order=XProc.ORDER_TOP),
    #XProc(prefix=DRAFT, order=XProc.ORDER_TOP),
    XProc(prefix=FONT, order=XProc.ORDER_TOP),
    XProc(prefix=STYLES, order=XProc.ORDER_TOP),
    XProc(prefix=ENTRYBFLIST, order=XProc.ORDER_TOP),
    XProc(prefix=QUOTES, order=XProc.ORDER_TOP),
    XProc(prefix=FANCYHDR, order=XProc.ORDER_TOP),
    XProc(prefix=ALTENDPREAMBLE, order=XProc.ORDER_TOP)
    )

# ###########################################################
# Creating the different types of footers for each mailer
# ###########################################################

# Creating section with return address and allow to sign and
# date the mailer.
# -----------------------------------------------------------
ORG_APPROVAL=r"""
  %% ORG_APPROVAL %%
  %% -------- %%
    \newcommand{\approveWhat}{your organization's listing}
    \subsection*{Approval}
    \approval
%
% -----
"""

PERSON_APPROVAL=r"""
  %% PERSON_APPROVAL %%
  %% -------- %%
    \newcommand{\approveWhat}{your listing}
    \subsection*{Approval}
    \approval
%
% -----
"""


# End tag for the LaTeX document
# ------------------------------
DOCFTR=r"""
  %% DOCFTR %%
  %% ------ %%
  \vfill
  \end{document}
%
% -----
"""

# Putting together static footer sections for each mailer
# -------------------------------------------------------
DocumentProtocolFooter =(
    XProc(element='InScopeProtocol',
          suffix=DOCFTR,
          order=XProc.ORDER_TOP,
          textOut = 0),
    )

DocumentSummaryFooter =(
    XProc(prefix=DOCFTR, order=XProc.ORDER_TOP),
    )

DocumentOrgFooter =(
    XProc(prefix=ORG_APPROVAL, order=XProc.ORDER_TOP),
    XProc(prefix=DOCFTR, order=XProc.ORDER_TOP),
    )

DocumentPersonFooter =(
    XProc(prefix=PERSON_APPROVAL, order=XProc.ORDER_TOP),
    XProc(prefix=DOCFTR, order=XProc.ORDER_TOP),
    )

DocumentStatusCheckFooter =(
    XProc(prefix=DOCFTR, order=XProc.ORDER_TOP),
    )

ProtAbstUpdateInstructions =(
    XProc(prefix=DOCFTR, order=XProc.ORDER_TOP),
    )

DocumentTestFooter =(
    XProc(prefix=DOCFTR, order=XProc.ORDER_TOP),
    )


# Putting the three main sections of document together
# Header + Body + Footer
# ----------------------------------------------------
ProtocolInstructions =     \
  DocumentProtocolHeader + \
  ProtAbstProtID         + \
  ProtAbstInfo           + \
  CommonMarkupRules      + \
  DocumentProtocolFooter

SummaryInstructions =      \
  DocumentSummaryHeader  + \
  CommonMarkupRules      + \
  DocumentSummaryBody    + \
  DocumentSummaryFooter

OrgInstructions =     \
  DocumentOrgHeader + \
  DocumentOrgBody   + \
  DocumentOrgFooter

# ADDRESS              +
PersonInstructions =     \
  DocumentPersonHeader + \
  DocumentPersonBody   + \
  DocumentPersonFooter

StatusCheckInstructions =     \
  DocumentStatusCheckHeader + \
  DocumentStatusCheckBody   + \
  DocumentStatusCheckFooter

StatusCheckCCOPInstructions =   \
  DocumentStatusCheckHeader   + \
  DocumentStatusCheckCCOPBody + \
  DocumentStatusCheckFooter

#---------------------------------
# For Testing Purposes only
#---------------------------------
TestInstructions = \
  DocumentTestHeader + \
  DocumentTestBody   + \
  DocumentTestFooter


###################################################################
# Access to instructions
###################################################################

#------------------------------------------------------------------
# ControlTable
#
#   This dictionary enables us to find the control information
#   for processing a mailer.
#   Value must be past as second parameter on command prompt.
#   (First parameter being the XML document being processed.)
#
#   Table contains:
#       Key = tuple of (output format, output format subtype)
#     Value = tuple of (XProc list name, number of reqd. LaTeX passes)
#------------------------------------------------------------------
ControlTable = {\
    ("Protocol",         ""):(ProtocolInstructions, 2),\
    ("Protocol",  "initial"):(ProtocolInstructions, 2),\
    ("InScopeProtocol",  ""):(ProtocolInstructions, 2),\
    ("InScopeProtocol", "initial"):(ProtocolInstructions, 2),\
    ("Summary",          ""):(SummaryInstructions, 2),\
    ("Summary",   "initial"):(SummaryInstructions, 2),\
    ("Organization",     ""):(OrgInstructions, 2),\
    ("Person",           ""):(PersonInstructions, 3),\
    ("StatusCheck",      ""):(StatusCheckInstructions, 2),\
    ("InScopeProtocol", "StatusCheck"):(StatusCheckInstructions, 2),\
    ("StatusCheckCCOP",  ""):(StatusCheckCCOPInstructions, 2),\
    ("Test",             ""):(TestInstructions, 2)\
}


####################################################################
####################################################################
###                                                              ###
###                        DEBUGGING STUFF                       ###
###                                                              ###
####################################################################
####################################################################

# Return a printable form of a value
def showVal (val):
    if val == None:
        return 'None'
    if type(val) in (type(''), type(u'')):
        return val
    if type(val) == type(1):
        return '%d' % val
    raise StandardError ("showVal with unexpected type: %s" % str(type(val)))
