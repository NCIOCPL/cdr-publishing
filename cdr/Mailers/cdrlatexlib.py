"""CdrXmlLatexSummaryInst: Processing instructions for generating a summary"""

import sys, re, xml.dom.minidom, UnicodeToLatex, cdrlatextables

#-------------------------------------------------------------------
# getAttribute
#   Find an attribute in a DOM node by its name.
#
# Pass:
#   Reference to DOM node.
#   Name of the attribute to find.
#
# Return:
#   Value of the attribute, converted from Unicode to Latex/Latin 1.
#   None if the attribute is not found.
#-------------------------------------------------------------------
def getAttribute (domNode, attrName):
    # Get a list of all attributes in this node
    attrs = domNode.attributes
    i = 0
    while i < attrs.length:
        # Is this the one we want
        if attrs.item(i).nodeName == attrName:
            # Yes - Convert Unicode to Latin1
            return UnicodeToLatex.convert (attrs.item(i).nodeValue)
        i += 1

    # Attribute not found
    return None

#----------------------------------------------------------------------
# getText
#   Extracts and concatenates the text nodes from an element.
#----------------------------------------------------------------------
def getText(nodelist):
    result = ""
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            result = result + node.data
    return result

#-------------------------------------------------------------------
# XProc
#
#   All information needed to perform one step in a conversion.
#
#   A control table defined in cdrlatexlib.py will contain a tuple
#   of these which describes how to process a document in a format.
#
# Fields:
#
#   element   - XML element to process, None if this is pure processing
#               Elements may be specifed as simple names, or as fully
#                qualified names starting at the root, e.g.:
#                  Title
#                 or:
#                  /Summary/SummarySection/Title
#               The program will search for a match on the fully qualified
#                name first and, only if it doesn't find anything, will it
#                look to see if there is an XProc for a simple name.
#                Therefore if both "Title" and "/Summary...Title" are
#                specified, the Title for the SummarySection will be
#                processed according to the SummarySection/Title rule
#                and all other Titles will be processed according to the
#                other rule.
#               Full XPath notation is NOT supported.
#   attr      - Attribute specification.  If not None, only process this
#                element if the specification fits the element.
#                Valid specifications are:
#                  attrname=attrValue
#                 or
#                  attrname!=attrValue
#                Only used if there is an element tag.
#   occs      - Max num occs to process, 0 = unlimited
#                Only used if there is an element tag
#   order     - How we order an xml element during output, one of:
#                XProc.ORDER_DOCUMENT:
#                  This is the default order for processing document nodes.
#                  If no other order is specified the nodes are processed 
#                  in the order they appear in the input document.  For
#                  this ordering mode, the order in which the processing
#                  rules are specified is not significant.
#                XProc.ORDER_TOP:
#                  A processing rule can be specified to use ORDER_TOP to
#                  cause the matching nodes to be processed before any other
#                  nodes or after all other nodes.  Place all ORDER_TOP
#                  rules which should be processed first at the beginning
#                  of the list of rules.  These rules will be processed in
#                  their order of appearance in the list.  Place all ORDER_TOP
#                  rules which should be processed last at the end of the
#                  list of rules.  These, too, will be processed in their
#                  order of appearance in the list.
#                XProc.ORDER_PARENT:
#                  This mode of ordering behaves similarly to ORDER_TOP,
#                  but only with respect to the sibling elements which
#                  are children of the same parent element.  In other words,
#                  the engine collects all of the nodes which are children
#                  of a given parent, and finds the rule which matches
#                  each of those nodes.  The nodes in this set whose rules are
#                  designated as ORDER_PARENT, and whose rules are specified
#                  before any ORDER_DOCUMENT rules in this set will be
#                  processed first (in the order in which these rules appear
#                  in the rule list), followed by the nodes whose matching
#                  rules are designated as ORDER_DOCUMENT (in the order
#                  of node appearance in the input document), followed by
#                  those nodes matching the remaining ORDER_PARENT rules 
#                  (that is, ORDER_PARENT rules which were specified
#                  following an ORDER_DOCUMENT rule within the set of rules
#                  which match this set of siblings).
#               Example showing how XProc.ORDER_DOCUMENT works:
#                Instructions:
#                  Element='A', order=XProc.ORDER_TOP
#                  Element='B', order=XProc.ORDER_TOP
#                  Element='C', order=XProc.ORDER_DOCUMENT
#                  Element='D', order=XProc.ORDER_DOCUMENT
#                  Element='E', order=XProc.ORDER_TOP
#                Input record has elements in following order:
#                  C1 C2 D3 A4 B5 C6 E7 C8 D9
#                Output record gets:
#                  A4 B5 C1 C2 D3 C6 C8 D9 E7
#                (That's perfectly clear, isn't it?)
#                Only used if there is an element tag.
#   prefix    - Latex constant string to output prior to processing
#   preProcs  - List of routines+parms to call before textOut output
#   textOut   - True=Output the text of this element
#                Only used if there is an element tag
#   descend   - True=Examine children of element, else skip them
#                Only used if there is an element tag
#   postProcs - List of routines+parms tuples to call at end
#   suffix    - Latex constant string to output after processing
#   filters   - Optional sequence of filters to be applied to the
#               collected output for the children of a node; each 
#               filter must be a function which takes a string 
#               and returns a string.
#
#-------------------------------------------------------------------
class XProc:
    # Pattern for checking attribute name =/!= value
    attrPat = re.compile(r'([A-Za-z_]+)\s*(!?)=\s*(.*)')
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
            matchObj = attrPat.search (attr)
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


#-------------------------------------------------------------------
# ProcParms
#
#   A reference to an instance of procParms is passed to any preProc
#   or postProc executed during the conversion.
#
#   It acts as a container for information made available to the
#   procedure, and for information coming back.
#
#   Fields include:
#
#       topNode - Reference to DOM node at top of XML document, i.e.
#                 the document element.
#       curNode - The current DOM node, i.e., the one for the current
#                 element.  This may be None if the procedure is
#                 is invoked outside the context of an element (if
#                 XProc.element=None.)
#       args    - A tuple of arguments associated with the current
#                 procedure in the XProc.preProcs or postProcs field.
#       output  - Initially, an empty string.
#                 If the procedure needs to output data, place a string
#                 in ProcParms.output and the conversion driver will
#                 handle it.
#
#   The output element is handled by the conversion driver as follows:
#
#       Initialize output=''
#       Invoke each preProc (or postProc) in the XProc tuple of procedures
#       (Note: each procedure sees the previous output, which may no longer
#           be ''.  Each subsequent procedure can, if desired, examine,
#           replace, or append to the current output.
#       Write the last value of output to the actual Latex output string.
#-------------------------------------------------------------------
class ProcParms:
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


#-------------------------------------------------------------------
# XmlLatexException
#
#   Used for all exceptions thrown back to cdrxmllatex callers.
#-------------------------------------------------------------------
class XmlLatexException(Exception):
    pass

#------------------------------------------------------------------
# findControls
#   Retrieve the instructions for a given doc format and format type.
#------------------------------------------------------------------
def findControls (docFmt, fmtType):
    try:
        ctl = ControlTable[(docFmt, fmtType)]
    except (KeyError):
        sys.stderr.write (
          "No control information stored for '%s':'%s'" % (docFmt, fmtType))
        sys.exit()
    return ctl

#------------------------------------------------------------------
# citations
#   Retrieve the citations and create a list if multiple are present
#------------------------------------------------------------------
def cite (pp):

     # Build output string here
     citeString = ''

     # Get the current citation node
     citeNode = pp.getCurNode()

     # If it's a sibling to another one, we've already processed it
     # Don't neeed to do any more
     prevNode = citeNode.previousSibling
     if prevNode.nodeName == 'CitationLink':
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
        attrValue = getAttribute (citeNode, 'refidx')
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


#------------------------------------------------------------------
# bibitem
#   Create the link between the citations listed within the text
#   and the references as listed in the Reference block of each
#   chapter of a summary.
#------------------------------------------------------------------
def bibitem (pp):

     # Build output string here
     refString = ''

     # Get the current citation node
     refNode = pp.getCurNode()

     # Beginning of the bibitem element
     refString = r"  \bibitem{"

     # Reference index number is in the refidx attribute
     # Extract the attribute value from the Citation
     # tag
     # ------------------------------------------------------
     attrValue = getAttribute (refNode, 'refidx')
     if (attrValue != None):
       refString += attrValue
       ## refString += refNode.nextSibling


     # Terminate the Latex for the list of citation
     refString += r"}"

     # Return info to caller, who will output it to the Latex
     pp.setOutput (refString)

     return 0


#------------------------------------------------------------------
# protocolTitle
#   From the three possible protocol titles only select the
#   Professional Title
#------------------------------------------------------------------
def protocolTitle (pp):

     # Build output string here
     refString = ''

     # Get the current citation node
     refNode = pp.getCurNode()
     txtNode = refNode.firstChild

     # Reference index number is in the refidx attribute
     # Extract the attribute value from the Citation
     # tag
     # ------------------------------------------------------
     attrValue = getAttribute (refNode, 'Type')
     if (attrValue == 'Professional'):
       # Beginning of the ProtocolTitle element
       refString = r"\newcommand\ProtocolTitle{"
       refString += UnicodeToLatex.convert(txtNode.nodeValue)
       # Ending of the ProtocolTitle element
       refString += "}\n  "

     # Return info to caller, who will output it to the Latex
     pp.setOutput (refString)

     return 0


#------------------------------------------------------------------
# address
#   Retrieve multiple address lines and separate each element with
#   a newline to be displayed properly in LaTeX
#------------------------------------------------------------------
def address (pp):

     # Build output string here
     addressString = ''

     # Get the current address node
     addressNode = pp.getCurNode()

     # Beginning of list of one or more address lines
     addressString = "  \\newcommand{\\PUPAddr}{%\n    "

     # If the current AddrLine element is a sibling to another one,
     # we've already processed it as part of the first address line.
     # Don't need to do any more and can exit here.
     # -------------------------------------------------------------
     prevNode = addressNode.previousSibling
     while prevNode != None:
        if prevNode.nodeName == 'AddrLine':
           return 0
        prevNode = prevNode.previousSibling

     # Capture the text of all contiguous address lines separating,
     # them with a LaTeX newline and line break
     # ------------------------------------------------------------
     addressNode = pp.getCurNode()
     count = 0
     while addressNode != None and \
           addressNode.nodeName == 'AddrLine':

        # Comma separator before all but the first one
        if count > 0:
            addressString += " \\newline\n    "

        # The address line text is a child of the AddrLine node
        # Loop through all children of the node to extract the
        # text
        # Note:  If the text nodes are parents to other children
        #        this part will need to be expanded to include those
        # ----------------------------------------------------------
        txtNode = addressNode.firstChild
        while txtNode != None:
           addressString += UnicodeToLatex.convert(txtNode.nodeValue);
           txtNode = txtNode.nextSibling


        # Increment count and check the next sibling
        # Note:  The next sibling is a text node --> need to check
        #        the node after the next to catch an Element node again
        # -------------------------------------------------------------
        for i in (1, 2):
           count += 1
           addressNode = addressNode.nextSibling

     # Terminate the Latex for the list of address line
     addressString += "\n  }\n"

     # Return info to caller, who will output it to the Latex
     pp.setOutput (addressString)

     return 0


#------------------------------------------------------------------
# street
#   Retrieve multiple street lines and separate each element with
#   a newline to be displayed properly in LaTeX
#------------------------------------------------------------------
def street (pp):

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
                 streetString += UnicodeToLatex.convert(txtNode.nodeValue);
              txtNode = txtNode.nextSibling
              count += 1

           streetNode = streetNode.nextSibling


     # Terminate the Latex for the list of street line
     streetString += "\n  }\n"

     # Return info to caller, who will output it to the Latex
     pp.setOutput (streetString)

     return 0


#------------------------------------------------------------------
#  yesno
#    Used to create records within a LaTeX table of the format
#       Description     Yes     No
#    ===============================
#     My Description     X
#     Next Description           X
#
#    After the description field is printed this procedure finds
#    the sibling element with the Yes/No flag information and prints
#    a predefined LaTeX command called
#         \Check{X}
#         with X = Y  -->  Output:     X   space
#              else   -->  Output:    space  X
#
#    If the Description field is a SpecialtyCategory an additional
#    check is set for the board certification.
#------------------------------------------------------------------
def yesno (pp):

     rootField = pp.args[0]
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
     count = 0
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

#----------------------------------------------------------------------
# Remember list style.
#----------------------------------------------------------------------
class List:
    def __init__(self, compact):
        self.compact = compact

listStack = []
def openList(pp):
    node = pp.getCurNode()
    style = node.getAttribute("Style")
    listStyle = ""
    if node.nodeName == "ItemizedList":
        command = "itemize"
    else:
        command = "enumerate"
        listLevel = None
        if len(listStack) == 0: listLevel = "i"
        elif len(listStack) == 1: listLevel = "ii"
        elif len(listStack) == 2: listLevel = "iii"
        elif len(listStack) == 3: listLevel = "iv"
        if listLevel:
            enumStyle = None
            if style == "Arabic": enumStyle = "arabic"
            elif style == "UAlpha": enumStyle = "Alph"
            elif style == "URoman": enumStyle = "Roman"
            elif style == "LAlpha": enumStyle = "alph"
            elif style == "LRoman": enumStyle = "roman"
            if enumStyle:
                listStyle = r"""
  \renewcommand{\theenum%s}{\Roman{enum%s}}
  \renewcommand{\labelenum%s}{\theenum%s.}
""" % (listLevel, listLevel, listLevel, listLevel)

    compact = node.getAttribute("Compact")
    output = "  \\setlength{\\parskip}{0pt}\n"
    if compact == "No": 
        compact = 0
        output += "  \\setlength{\\itemsep}{10pt}\n  \\vspace{6pt}\n"
    else: 
        compact = 1
        output += "  \\setlength{\\itemsep}{-2pt}\n"
    for title in node.getElementsByTagName("ListTitle"):
        output += "  {\\bfseries %s}\n" % getText(title.childNodes)
    listStack.append(List(compact))
    pp.setOutput(output + listStyle + "  \\begin{%s}\n" % command)

#----------------------------------------------------------------------
# Forget list style.
#----------------------------------------------------------------------
def closeList(pp):
    listStack.pop()
    if not listStack:
        pp.setOutput("  \\setlength{\\parskip}{1.2mm}\n")

#----------------------------------------------------------------------
# Filter which adds line preservation to output.
#----------------------------------------------------------------------
def preserveLines(str):
    return str.replace('\n', '\\\\\n')

#----------------------------------------------------------------------
# Filter which removes paragraph breaks.
#----------------------------------------------------------------------
def stripLines(str):
    return str.replace('\r', '').replace('\n', ' ')

#----------------------------------------------------------------------
# Filter which strips leading and trailing whitespace.
#----------------------------------------------------------------------
def stripEnds(str): return str.strip()

#----------------------------------------------------------------------
# Object representing an organization's protocol status.
#----------------------------------------------------------------------
class OrgProtStatus:
    def __init__(self, statuses):
        self.value = None
        self.date  = None
        child      = statuses.firstChild
        while child:
            if child.nodeName == "CurrentOrgStatus":
                for grandchild in child.childNodes:
                    if grandchild.nodeName == "StatusName":
                        self.value = getText(grandchild.childNodes)
                    elif grandchild.nodeName == "StatusDate":
                        self.date = getText(grandchild.childNodes)
                return
            child = child.nextSibling
                
#----------------------------------------------------------------------
# Object representing a person's name.
#----------------------------------------------------------------------
class PersonalName:
    def __init__(self, node):
        self.surname = None
        self.givenName = None
        for child in node.childNodes:
            if child.nodeName == "SurName":
                self.surname = getText(child.childNodes)
            elif child.nodeName == "GivenName":
                self.givenName = getText(child.childNodes)

#----------------------------------------------------------------------
# Object representing an address.
#----------------------------------------------------------------------
class Address:
    def __init__(self):
        self.street = []
        self.city   = None
        self.state  = None
        self.zip    = None

#----------------------------------------------------------------------
# Extract the state name from a PoliticalSubUnit_State element.
#----------------------------------------------------------------------
def getState(node):
    shortName = None
    fullName  = None
    for child in node.childNodes:
        if child.nodeName == "PoliticalSubUnitShortName":
            shortName = getText(child.childNodes)
        elif child.nodeName == "PoliticalSubUnitFullName":
            fullName = getText(child.childNodes)
    return shortName or fullName

#----------------------------------------------------------------------
# Object representing a Protocol Lead Organization person.
#----------------------------------------------------------------------
class LeadOrgPerson:
    def __init__(self, node):
        self.name    = None
        self.phone   = None
        self.role    = None
        self.address = Address()
        self.id      = node.getAttribute("id")
        for child in node.childNodes:
            if child.nodeName == "Person":
                for grandchild in child.childNodes:
                    if grandchild.nodeName == "PersonNameInformation":
                        self.name = PersonalName(grandchild)
                    elif grandchild.nodeName == "Phone":
                        self.phone = getText(grandchild.childNodes)
                    elif grandchild.nodeName == "Street":
                        self.address.street.append(
                                getText(grandchild.childNodes))
                    elif grandchild.nodeName == "City":
                        self.address.city = getText(grandchild.childNodes)
                    elif grandchild.nodeName == "PoliticalSubUnit_State":
                        self.address.state = getState(grandchild)
                    elif grandchild.nodeName == "PostalCode_ZIP":
                        self.zip = getText(grandchild.childNodes)
            elif child.nodeName == "PersonRole":
                self.role = getText(child.childNodes)

#----------------------------------------------------------------------
# Object representing a Protocol Lead Organization.
#----------------------------------------------------------------------
class ProtLeadOrg:
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
                sendMailerTo = getText(child.childNodes)
            elif child.nodeName == "LeadOrgProtocolStatuses":
                self.currentStatus = OrgProtStatus(child)
            elif child.nodeName == "OfficialName":
                for grandchild in child.childNodes:
                    if grandchild.nodeName == "Name":
                        self.officialName = getText(grandchild.childNodes)
            elif child.nodeName == "LeadOrgPersonnel":
                person = LeadOrgPerson(child)
                self.personnel[person.id] = person
                if person.role.upper() == "PROTOCOL CHAIR":
                    self.protChair = person
        if sendMailerTo and self.personnel.has_key(sendMailerTo):
            self.sendMailerTo = self.personnel[sendMailerTo]
                
#----------------------------------------------------------------------
# Extract everything we need from the ProtocolLeadOrg element into macros.
#----------------------------------------------------------------------
def protLeadOrg(pp):

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
        if not leadOrg.protChair.name:
            protChair = "Name Unknown"
        else:
            protChair = "%s, %s" % (
                leadOrg.protChair.name.surname or "No Surname Found",
                leadOrg.protChair.name.givenName or "No Given Name Found")
        phone = leadOrg.protChair.phone or "Not specified"
        if not leadOrg.protChair.address:
            address = "Not specified"
        else:
            addrObj = leadOrg.protChair.address
            address = ""
            for street in addrObj.street:
                address += "  %s \\\\\n" % street
            stateZip = "%s %s" % (addrObj.state or "", addrObj.zip or "")
            stateZip = stateZip.strip()
            city = addrObj.city.strip() or ""
            if city and stateZip:
                comma = ", "
            else:
                comma = ""
            lastLine = "%s%s%s" % (city, comma, stateZip)
            if lastLine:
                address += "  %s \\\\\n" % lastLine
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

def makePrefix(level, name):
    return r"""
  \setcounter{qC}{0}
  \%s{%s}
""" % (level, name)

def optProtSect(pp):
    if pp.getCurNode().hasChildNodes():
        pp.setOutput(r"""
  \setcounter{qC}{0}
  \%s{%s}
""" % (pp.args[0], pp.args[1]))

#----------------------------------------------------------------------
# Check for a missing optional protocol section.
#----------------------------------------------------------------------
def checkNotAbstracted(pp):
    topNode = pp.getTopNode()
    target, section = pp.args
    sys.stderr.write("checking %s\n" % target)
    nodes = topNode.getElementsByTagName(target)
    #if nodes:
    if nodes and nodes[0].hasChildNodes():
        sys.stderr.write("found it\n")
        return
    sys.stderr.write("not abstracted\n")
    pp.setOutput(r"""
  \subsection*{%s}

  Not abstracted.
""" % section)
    
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
  \documentclass[12pt]{article}
  \usepackage{textcomp}
  \usepackage{multirow}
  \usepackage{supertabular}
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
  %% PROTOCOL_HDRTEXT%%
  %% --------------- %%
  \newcommand{\CenterHdr}{{\bfseries Protocol ID \ProtocolID} \\ }
  \newcommand{\RightHdr}{MailerDocID:  @@MailerDocID@@}
  \newcommand{\LeftHdr}{\today}
%
% -----
"""


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
  %% STATPART_HDRTEXT %%
  %% ---------------- %%
  \newcommand{\CenterHdr}{PUP ID: @@PUPID@@ \\ {\bfseries Protocol Update Person: \PUP}}
  \newcommand{\RightHdr}{Mailer ID: @@MAILERID@@ \\ Doc ID: @@DOCID@@ \\}
  \newcommand{\LeftHdr}{PDQ Status \& Participant Site Check \\ \today \\}
%
% -----
"""

# Defining the document header for each page
# Used by:  Organization
# ------------------------------------------
ORG_HDRTEXT=r"""
  %% ORG_HDRTEXT %%
  %% ----------- %%
  \newcommand{\CenterHdr}{Organization ID: @@ORGID@@ \\ {\bfseries XX \OrgName}}
  \newcommand{\RightHdr}{Mailer ID: @@MAILERID@@ \\ Doc ID: @@DOCID@@ \\}
  \newcommand{\LeftHdr}{PDQ Organization Update \\ \today \\}
%
% -----
"""

# Defining the document header for each page
# Used by:  Person
# ------------------------------------------
PERSON_HDRTEXT=r"""
  %% PERSON_HDRTEXT %%
  %% -------------- %%
  \newcommand{\LeftHdr}{PDQ Physician Update \\ \today \\}
  \newcommand{\CenterHdr}{Physician ID: @@PERID@@ \\ {\bfseries \Person}}
  \newcommand{\RightHdr}{Mailer ID: @@MAILERID@@ \\ Doc ID: @@DOCID@@ \\}
%
% -----
"""

FANCYHDR=r"""
  %% FANCYHDR %%
  %% -------- %%
  % Package Fancyhdr for Header/Footer/Reviewer Information
  % -------------------------------------------------------
  \usepackage{fancyhdr}
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
  \setlength{\textheight}{8.5in}
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
  \makeatletter \renewcommand\@biblabel[1]{[#1]} \makeatother

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

SPACING=r"""
  %% SPACING %%
  %% ------- %%
  % Double-spacing
  % \renewcommand\baselinestretch{1.5}
  % Wider Margins
  % \setlength{\oddsidemargin}{12pt}
  % \setlength{\textwidth}{6in}
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
          \setlength{\itemsep}{-2pt}%
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

  % If phone number is missing provide a marker to enter here
  % ---------------------------------------------------------
  \newcommand{\ThePhone}[1]{%
      \ifthenelse{\equal{#1}{}}{ \makebox[200pt]{\hrulefill }} {#1}}

  % Enter either Fax number or ruler
  % --------------------------------
  \newcommand{\TheFax}[1]{%
      \ifthenelse{\equal{#1}{}}{ \makebox[200pt]{\hrulefill }}{#1}}

  % Enter either E-mail or ruler
  % ----------------------------
  \newcommand{\TheEmail}[1]{%
      \ifthenelse{\equal{#1}{}}{ \makebox[200pt]{\hrulefill }}{#1}}

  % Enter either Web address or ruler
  % ---------------------------------
  \newcommand{\TheWeb}[1]{%
      \ifthenelse{\equal{#1}{}}{ \makebox[200pt]{\hrulefill }}{#1}}

  % Define the check marks for the 3 column tables
  % enter \Check{Y} or \Check{N} to set the mark
  % in either the left or right column
  % ----------------------------------------------
  \newcommand{\Check}[1]{%
      \ifthenelse{\equal{#1}{Y}}{ & \centerline{$\surd$} & }{ & &\centerline{$\surd$}}}
%
% -----
"""


ORG_DEFS=r"""
  %% ORG_DEFS %%
  %% -------- %%
  % Variable Definitions
  % --------------------
  \newcommand{\Phone}{oPhone}
  \newcommand{\Fax}{oFax}
  \newcommand{\Email}{oEmail}
  \newcommand{\Web}{oWeb}
  \newcommand{\Street}{oStreet}
  \newcommand{\City}{oCity}
  \newcommand{\PoliticalUnitState}{oState}
  \newcommand{\Country}{oCountry}
  \newcommand{\PostalCodeZIP}{oZip}
%
% -----
"""

PERSON_DEFS=r"""
  %% PERSON_DEFS %%
  %% -------- %%
  % Variable Definitions
  % --------------------
  \newcommand{\OrgName}{pOrg}
  \newcommand{\Phone}{}
  \newcommand{\Fax}{}
  \newcommand{\Email}{}
  \newcommand{\Web}{}
  \newcommand{\Street}{pStreet}
  \newcommand{\City}{pCity}
  \newcommand{\PoliticalUnitState}{pState}
  \newcommand{\Country}{pCountry}
  \newcommand{\PostalCodeZIP}{pZip}
%
% -----
"""

ORG_PRINT_CONTACT=r"""
   %% ORG_PRINT_CONTACT %%
   %% ----------------- %%
   \Person  \\
   \OrgName \\
   \Street  \\
   \City, \PoliticalUnitState\  \PostalCodeZIP \\

   \OrgIntro

   \subsection*{CIPS Contact Information}

   \OrgName     \\
   \Street   \\
   \City, \PoliticalUnitState\  \PostalCodeZIP \\
   \Country  \\

   \newcommand{\ewidth}{180pt}
   \begin{entry}
      \item[Main Organization Phone]    \ThePhone{\Phone}     \\
      \item[Main Organization Fax\footnotemark]
                                         \TheFax{\Fax}         \\
      \item[Main Organization E-Mail]    \TheEmail{\Email}    \\
      \item[Publish E-Mail in PDQ Directory]    \yesno        \\
      \item[Website]                     \TheWeb{\Web}
   \end{entry}
   \footnotetext{For administrative use only}


   \subsection*{Other Locations}

   \begin{enumerate}
%
% -----
"""

PERSON_PRINT_CONTACT=r"""
   %% PERSON_PRINT_CONTACT %%
   %% -------------------- %%
   \Person, \GenSuffix \PerSuffix  \\
   \OrgName    \\
   \Street   \\
   \City, \PoliticalUnitState\  \PostalCodeZIP \\

   \PersonIntro

   \subsection*{CIPS Contact Information}

   \Org     \\
   \Street   \\
   \City, \PoliticalUnitState\  \PostalCodeZIP \\
   \Country  \\

   \newcommand{\ewidth}{180pt}
   \begin{entry}
      \item[Phone]    \ThePhone{\Phone}     \\
      \item[Fax\footnotemark]
                                         \TheFax{\Fax}         \\
      \item[E-Mail]    \TheEmail{\Email}    \\
      \item[Publish E-Mail in PDQ Directory]    \yesno        \\
      \item[Website]                     \TheWeb{\Web}
   \end{entry}
   \footnotetext{For administrative use only}


   \subsection*{Other Practice Locations}

   \begin{enumerate}
%
% -----
"""



ORG_AFFILIATIONS=r"""
   %% ORG_AFFILIATIONS %%
   %% ---------------- %%
   \end{enumerate}


   \subsection*{Affiliations}
   \subsubsection*{Professional Organizations}
%
% -----
"""


PERSON_MISC_INFO=r"""
   %% PERSON_MISC_INFO %%
   %% ---------------- %%
   \end{enumerate}

   \subsection*{Preferred Contact Mode}
   $\bigcirc$ Electronic \qquad $\bigcirc$ Hardcopy

   \subsection*{Practice Information}
    Are you a physician (MD, DO, or foreign equivalent)?    \hfill
        \yesno \\
    Do you currently treat cancer patients?                \hfill
        \yesno  \\
    Are you retired from practice?                         \hfill
        \yesno

 \subsection*{Speciality Information}
%
% -----
"""


PERSON_SPECIALTY_TAB=r"""
   %% PERSON_SPECIALTY_TAB %%
   %% --------------------- %%
    \setlength{\doublerulesep}{0.5pt}
 \begin{longtable}[l]{||p{250pt}||p{35pt}|p{35pt}||p{35pt}|p{35pt}||} \hline
     &\multicolumn{2}{c||}{\bfseries{ }}&\multicolumn{2}{c||}{\bfseries{Board}} \\
     &\multicolumn{2}{c||}{\bfseries{Specialty}}&\multicolumn{2}{c||}{\bfseries{Certification}} \\
      \bfseries{Specialty Name}
     &\multicolumn{1}{c|}{\bfseries{Yes}} &\multicolumn{1}{c||}{\bfseries{No}}
     &\multicolumn{1}{c|}{\bfseries{Yes}} &\multicolumn{1}{c||}{\bfseries{No}}
            \\ \hline \hline
  \endfirsthead
        \multicolumn{5}{l}{(continued from previous page)} \\ \hline
     &\multicolumn{2}{c||}{\bfseries{ }}&\multicolumn{2}{c||}{\bfseries{Board}} \\
     &\multicolumn{2}{c||}{\bfseries{Specialty}}&\multicolumn{2}{c||}{\bfseries{Certification}} \\
      \bfseries{Specialty Name}
     &\multicolumn{1}{c|}{\bfseries{Yes}} &\multicolumn{1}{c||}{\bfseries{No}}
     &\multicolumn{1}{c|}{\bfseries{Yes}} &\multicolumn{1}{c||}{\bfseries{No}}
            \\ \hline \hline
  \endhead
%
% -----
"""


PERSON_TRAINING_TAB=r"""
   %% PERSON_TRAINING_TAB %%
   %% ------------------- %%
   \begin{longtable}[l]{||p{344pt}||p{35pt}|p{35pt}||} \hline
        \bfseries{Specialty Training}   &\multicolumn{1}{c|}{\bfseries{Yes}} &\multicolumn{1}{c||}{\bfseries{No}} \\ \hline \hline
  \endfirsthead
        \multicolumn{3}{l}{(continued from previous page)} \\ \hline
        \bfseries{Specialty Training}   &\multicolumn{1}{c|}{\bfseries{Yes}} &\multicolumn{1}{c||}{\bfseries{No}} \\ \hline \hline
  \endhead
%
% -----
"""


PERSON_SOCIETY_TAB=r"""
   %% PERSON_SOCIETY_TAB %%
   %% ------------------ %%
 \subsection*{Membership Information}

 \subsubsection*{Professional Societies}

  \begin{longtable}[l]{|p{344pt}||p{35pt}|p{35pt}||} \hline
        & \multicolumn{2}{c||}{\bfseries{Member of:}}  \\
          \bfseries{Society Name}
        & \multicolumn{1}{c|}{\bfseries{Yes}} & \multicolumn{1}{c||}{\bfseries{No}} \\
        \hline \hline
  \endfirsthead
        \multicolumn{3}{l}{(continued from previous page)} \\ \hline
        & \multicolumn{2}{c|}{\bfseries{Member of:}}  \\
          \bfseries{Society Name}
        & \multicolumn{1}{c|}{\bfseries{Yes}} & \multicolumn{1}{c|}{\bfseries{No}} \\
        \hline \hline
  \endhead
%
% -----
"""


PERSON_CLINGRP_TAB=r"""
   %% PERSON_CLINGRP_TAB %%
   %% ------------------ %%
\subsubsection*{Clinical Trials Groups}
  \begin{longtable}[l]{|p{344pt}||p{35pt}|p{35pt}||} \hline
       \bfseries{Group Name}
     &\multicolumn{1}{c|}{\bfseries{Yes}}&\multicolumn{1}{c||}{\bfseries{No}}\\
                                        \hline \hline
  \endfirsthead
   \multicolumn{3}{l}{(continued from previous page)} \\ \hline
     \bfseries{Group Name}
     &\multicolumn{1}{c|}{\bfseries{Yes}}&\multicolumn{1}{c||}{\bfseries{No}}\\
                                        \hline \hline
  \endhead
%
% -----
"""


PERSON_CCOP_TAB=r"""
   %% PERSON_CCOP_TAB %%
   %% --------------- %%
\subsubsection*{Clinical Cancer Oncology Programs}
   \CCOPIntro
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
    \bfseries Sites     & \bfseries Investigator/ &
    \bfseries Contact   & \multicolumn{2}{c|}{\bfseries pating} \\
    \bfseries (Main Members) & \bfseries Contact &
    \bfseries Phone     & \multicolumn{1}{c|}{\bfseries Yes} & \multicolumn{1}{c|}{\bfseries No} \\ \hline \hline
\endfirsthead
    \multicolumn{5}{l}{(continued from previous page)} \\ \hline
                        & \bfseries Principal &
                        & \multicolumn{2}{c|}{\bfseries Partici-} \\
    \bfseries Sites     & \bfseries Investigator/ &
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
    \bfseries Sites     & \bfseries Investigator/ &
    \bfseries Contact   & \multicolumn{2}{c|}{\bfseries pating} \\
    \bfseries (Affiliate Members) & \bfseries Contact &
    \bfseries Phone     & \multicolumn{1}{c|}{\bfseries Yes} & \multicolumn{1}{c|}{\bfseries No} \\ \hline \hline
\endfirsthead
    \multicolumn{5}{l}{(continued from previous page)} \\ \hline
                        & \bfseries Principal &
                        & \multicolumn{2}{c|}{\bfseries Partici-} \\
    \bfseries Sites     & \bfseries Investigator/ &
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
    \bfseries           & \bfseries Principal &
    \bfseries           & \multicolumn{2}{c|}{\bfseries Partici-} \\
    \bfseries           & \bfseries Investigator/ &
    \bfseries Contact   & \multicolumn{2}{c|}{\bfseries pating} \\
    \bfseries Sites     & \bfseries Contact &
    \bfseries Phone     & \multicolumn{1}{c|}{\bfseries Yes} & \multicolumn{1}{c|}{\bfseries No} \\ \hline \hline
\endfirsthead
    \multicolumn{5}{l}{(continued from previous page)} \\ \hline
                        & \bfseries Principal &
                        & \multicolumn{2}{c|}{\bfseries Partici-} \\
    \bfseries           & \bfseries Investigator/ &
    \bfseries Contact   & \multicolumn{2}{c|}{\bfseries pating} \\
    \bfseries Sites     & \bfseries Contact &
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


ORG_RESET_OTHER=r"""
   %% ORG_RESET_OTHER %%
   %% --------------- %%
   \renewcommand{\Phone}{}
   \renewcommand{\Fax}{}
   \renewcommand{\Email}{}
   \renewcommand{\Web}{}
   \renewcommand{\OrgName}{}
   \renewcommand{\Street}{}
   \renewcommand{\City}{}
   \renewcommand{\PoliticalUnitState}{}
   \renewcommand{\Country}{}
   \renewcommand{\PostalCodeZIP}{}
%
% -----
"""

PERSON_RESET_OTHER=r"""
   %% PERSON_RESET_OTHER %%
   %% --------------- %%
   \renewcommand{\Org}{}
   \renewcommand{\Phone}{}
   \renewcommand{\Fax}{}
   \renewcommand{\Email}{}
   \renewcommand{\Web}{}
   \renewcommand{\Org}{}
   \renewcommand{\Street}{}
   \renewcommand{\City}{}
   \renewcommand{\PoliticalUnitState}{}
   \renewcommand{\Country}{}
   \renewcommand{\PostalCodeZIP}{}
%
% -----
"""

ORG_PRINT_OTHER=r"""
   %% ORG_PRINT_OTHER %%
   %% --------------- %%
   \item
   \OrgName     \\
   \Street  \\
   \City, \PoliticalUnitState\  \PostalCodeZIP \\
   \Country  \\

     \renewcommand{\ewidth}{180pt}
     \begin{entry}
        \item[Phone] \ThePhone{\Phone}           \\
        \item[Fax]  \TheFax{\Fax}           \\
        \item[E-Mail]  \TheWeb{\Web}        \\
        \item[Publish E-Mail in PDQ Directory] \yesno   \\
        \item[Website]  \TheWeb{\Web}
     \end{entry}
  \vspace{15pt}
%
% -----
"""


PERSON_PRINT_OTHER=r"""
   %% PERSON_PRINT_OTHER %%
   %% --------------- %%
   \item
   \Org     \\
   \Street  \\
   \City, \PoliticalUnitState\  \PostalCodeZIP \\
   \Country  \\

     \renewcommand{\ewidth}{180pt}
     \begin{entry}
        \item[Phone] \ThePhone{\Phone}           \\
        \item[Fax]  \TheFax{\Fax}           \\
        \item[E-Mail]  \TheWeb{\Web}        \\
        \item[Publish E-Mail in PDQ Directory] \yesno   \\
        \item[Website]  \TheWeb{\Web}
     \end{entry}
  \vspace{15pt}
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
%
% -----
"""


ORG_TITLE=r"""
  %% ORG_TITLE %%
  %% --------- %%
  \newcommand{\mailertitle}{%
    National Cancer Institute's PDQ Database \\
    Organization Information Update
  }
%
% -----
"""


PERSON_TITLE=r"""
  %% PERSON_TITLE %%
  %% ------------ %%
  \newcommand{\mailertitle}{%
    National Cancer Institute's PDQ Database \\
    Physician Information Update
  }
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
  %\renewcommand{\theenumii}{\Roman{enumii}}
  %\renewcommand{\labelenumii}{\theenumii.}

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


ENDPROTOCOLPREAMBLE=r"""
  %% ENDPROTOCOLPREAMBLE %%
  %% ----------- %%
  \setlength{\parskip}{1.2mm}
  \setlength{\parindent}{0mm}
  \setlength{\headheight}{48pt}

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
  \ProtocolTitle
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
     \item[Protocol Activation Date]   \ProtocolActiveDate
     \item[Lead Organization]          \ProtocolLeadOrg
     \item[Protocol Chairman]          \ProtocolChair
     \item[Phone]                      \ChairPhone\
     \item[Address]                    \ChairAddress
     \item[Protocol Status]            \ProtocolStatus

     \item[Eligible Patient Age Range] \AgeText
     \item[Lower Age Limit]            \LowAge
     \item[Upper Age Limit]            \HighAge
  \end{entry}
%
% -----
"""

PROTOCOLBOILER=r"""
  %% PROTOCOLBOILER %%
  %% ----------- %%
  % Following Text is Boilerplate

  \newpage
  Please initial this page and fax or send hard copy to the address below.

  If you are requesting any changes to the submitted document please include
  the edited pages of this document.

  You may fax the information to the PDQ Protocol Coordinator at:
  \begin{verse}
      Fax \#:  301-480-8105
  \end{verse}

  \begin{verse}
      PDQ Protocol Coordinator    \\
      Attn: CIAT                  \\
      Cancer Information Products and Systems, NCI, NIH   \\
      6116 Executive Blvd. Suite 3002B MSC-8321           \\
      Bethesda, MD 20892-8321
  \end{verse}

  Please initial here if summary is satisfactory to you.
  \hrulefill

  If the study is permanently closed to patient entry, please give approximate
  date of closure.
  \hrulefill

  Reason for closure.
  \hrulefill      \newline
    \mbox{}\hrulefill \newline
  \mbox{}\hrulefill \newline
  \mbox{}\hrulefill \newline
  \mbox{}\hrulefill

  Please list/attach any citations resulting from this study.
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
          postProcs = ((closeList, ()), ),
	      suffix    = "\n  \\end{itemize}\n"),
    XProc(element   = "OrderedList",
          textOut   = 0,
          preProcs  = ((openList, ()), ),
          postProcs = ((closeList, ()), ),
	      suffix    = "\n  \\end{enumerate}\n"),
    XProc(element   = "ListItem",
	      prefix    = "  \\item ",
          suffix    = "\n",
          filters   = [stripEnds]),
    XProc(element   = "Para",
          filters   = [stripLines],
          prefix    = "\n  \\setcounter{qC}{0}\n",
          suffix    = "\n\n"),
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
          prefix    = "\\texttt{",
          suffix    = "}",
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
    )

ProtAbstInfo = (
    XProc(element="ProtocolTitle",
          textOut=0,
          order=XProc.ORDER_TOP,
          preProcs=( (protocolTitle, ()), ),),
    XProc(prefix=PROTOCOLTITLE, order=XProc.ORDER_TOP),
    XProc(prefix=PROTOCOLINFO, order=XProc.ORDER_TOP),
    XProc(element   = "/InScopeProtocol/Eligibility",
          order     = XProc.ORDER_TOP,
          prefix    = makePrefix("subsection*", "Disease Retrieval Terms")
                    + "  \\begin{itemize}{\\setlength{\\itemsep}{-5pt}}\n"
                      "  \\setlength{\\parskip}{0mm}\n",
          suffix    = "  \\end{itemize}\n  \\setlength{\\parskip}{1.2mm}\n"),
    XProc(element   = "SpecificDiagnosis",
          order     = XProc.ORDER_PARENT,
          prefix    = "  \\item ",
          suffix    = "\n"),
    XProc(element   = "Objectives",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = makePrefix("subsection*", "Protocol Objectives")),
    XProc(element   = "Outline",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = makePrefix("subsection*", "Protocol Outline")),
    XProc(element   = "EntryCriteria",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = makePrefix("subsection*", "Patient Eligibility")),
    XProc(element   = "DiseaseCharacteristics",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = makePrefix("subsubsection", "Disease Characteristics")),
    XProc(element   = "PatientCharacteristics",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = makePrefix("subsubsection", "Patient Characteristics")),
    XProc(element   = "PriorConcurrentTherapy",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = makePrefix("subsubsection", "Prior/Concurrent Therapy")),
    XProc(element   = "GeneralEligibilityCriteria",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = makePrefix("subsubsection", "General Criteria")),
    XProc(element   = "ProjectedAccrual",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = makePrefix("subsection*", "Projected Accrual")),
    XProc(element   = "EndPoints",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          preProcs  = ((optProtSect, ("subsection*", "End Points")), )),
    XProc(order     = XProc.ORDER_TOP,
          textOut   = 0,
          postProcs = ((checkNotAbstracted, 
                       ("EndPoints", "End Points")), )),
    XProc(element   = "Stratification",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          preProcs  = ((optProtSect, ("subsection*", 
                                      "Stratification Parameters")), )),
    XProc(order     = XProc.ORDER_TOP,
          textOut   = 0,
          postProcs = ((checkNotAbstracted, 
                       ("Stratification", "Stratification Parameters")), )),
    XProc(element   = "SpecialStudyParameters",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          preProcs  = ((optProtSect, ("subsection*", 
                                      "Special Study Parameters")), )),
    XProc(order     = XProc.ORDER_TOP,
          textOut   = 0,
          postProcs = ((checkNotAbstracted, 
                       ("SpecialStudyParameters", 
                        "Special Study Parameters")), )),
    XProc(element   = "DoseSchedule",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          preProcs  = ((optProtSect, ("subsection*", "Dose Schedule")), )),
    XProc(order     = XProc.ORDER_TOP,
          textOut   = 0,
          postProcs = ((checkNotAbstracted, 
                       ("DoseSchedule", "Dose Schedule")), )),
    XProc(element   = "DosageForm",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          preProcs  = ((optProtSect, ("subsection*", "Dosage Form")), )),
    XProc(order     = XProc.ORDER_TOP,
          textOut   = 0,
          postProcs = ((checkNotAbstracted, 
                       ("DosageForm", "Dosage Form")), )),
    XProc(element   = "Rationale",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = makePrefix("subsection*", "Protocol Rationale")),
    XProc(element   = "Purpose",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = makePrefix("subsection*", "Protocol Purpose")),
    XProc(element   = "EligibilityText",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = makePrefix("subsection*", "Eligibility Text")),
    XProc(element   = "TreatmentIntervention",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = makePrefix("subsection*", "Treatment/Intervention")),
    XProc(element   = "ProfessionalDisclaimer",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = makePrefix("subsection*", "Professional Disclaimer")),
    XProc(element   = "PatientDisclaimer",
          textOut   = 0,
          order     = XProc.ORDER_TOP,
          prefix    = makePrefix("subsection*", "Patient Disclaimer")),
    XProc(prefix=PROTOCOLBOILER, order=XProc.ORDER_TOP),

    # Mask these out.
    XProc(element   = "GlossaryTerm",
          textOut   = 0,
          descend   = 0),
    ) 

#------------------------------------------------------------------
# Organization Mailer Instructions (Body)
#   Instructions for formatting all Organization Mailers
#------------------------------------------------------------------
# --------- START: First section Contact Information ---------
DocumentOrgBody = (\
XProc(element="OfficialName/Name",
          order=XProc.ORDER_PARENT,
          prefix="  \\newcommand{\OrgName}{",
          suffix="}\n"),
    XProc(element="Name",
          prefix="  \\newcommand{\Person}{",
          suffix="}\n", order=XProc.ORDER_TOP),
    XProc(element="Address",
          textOut=0, order=XProc.ORDER_TOP),
    XProc(element="Street",
          textOut=0,
          preProcs=( (street, ()), )),
    XProc(element="City",
          prefix="  \\renewcommand{\City}{",
          suffix="}\n"),
    XProc(element="PoliticalUnit_State",
          prefix="  \\renewcommand{\PoliticalUnitState}{",
          suffix="}\n"),
    XProc(element="Country",
          prefix="  \\renewcommand{\Country}{",
          suffix="}\n"),
    XProc(element="PostalCode_ZIP",
          prefix="  \\renewcommand{\PostalCodeZIP}{",
          suffix="}\n"),
    XProc(element="Phone",
          order=XProc.ORDER_TOP,
          prefix="  \\renewcommand{\Phone}{",
          suffix="}\n"),
    XProc(element="Fax",
          order=XProc.ORDER_TOP,
          prefix="  \\renewcommand{\Fax}{",
          suffix="}\n"),
    XProc(element="Email",
          order=XProc.ORDER_TOP,
          prefix="  \\renewcommand{\Email}{",
          suffix="}\n"),
    XProc(element="URI",
          order=XProc.ORDER_TOP,
          prefix="  \\renewcommand{\Web}{",
          suffix="}\n"),
    XProc(prefix=ORG_PRINT_CONTACT),
# --------- END: First section Contact Information ---------
    XProc(element="/OrgMailer/OtherLocation",
          textOut=0,
          order=XProc.ORDER_PARENT,
          prefix=ORG_RESET_OTHER,
          suffix=ORG_PRINT_OTHER),
    XProc(element="/OrgMailer/OtherLocation/Address",
          textOut=0,
          order=XProc.ORDER_PARENT),
    XProc(element="/OrgMailer/OtherLocation/Address/Street",
          textOut=0,
          order=XProc.ORDER_PARENT,
          preProcs=( (street, ()), )),
    XProc(element="/OrgMailer/OtherLocation/Phone",
          order=XProc.ORDER_PARENT,
          prefix="  \\renewcommand{\Phone}{",
          suffix="}\n"),
    XProc(element="/OrgMailer/OtherLocation/Fax",
          order=XProc.ORDER_PARENT,
          prefix="  \\renewcommand{\Fax}{",
          suffix="}\n"),
    XProc(element="/OrgMailer/OtherLocation/Email",
          order=XProc.ORDER_PARENT,
          prefix="  \\renewcommand{\Email}{",
          suffix="}\n"),
    XProc(element="/OrgMailer/OtherLocation/URI",
          order=XProc.ORDER_PARENT,
          prefix="  \\renewcommand{\Web}{",
          suffix="}\n"),
# --------- Start: Affiliations Section ---------
    XProc(prefix=ORG_AFFILIATIONS, order=XProc.ORDER_TOP),
    XProc(prefix="\n  \\begin{itemize}\n", order=XProc.ORDER_TOP),
    XProc(element="ProfessionalOrg",
          order=XProc.ORDER_TOP,
          prefix="\n    \\item "),
    XProc(prefix="\n  \\end{itemize}\n", order=XProc.ORDER_TOP),
    XProc(prefix="\n  \\subsubsection*{Cooperative Groups}",
            order=XProc.ORDER_TOP),
    XProc(prefix="\n  \\begin{itemize}\n", order=XProc.ORDER_TOP),
    XProc(element="MemberOf",
          order=XProc.ORDER_TOP,
          prefix="\n    \\item "),
    XProc(prefix="\n  \\end{itemize}\n", order=XProc.ORDER_TOP)
    )


#------------------------------------------------------------------
# Person Mailer Instructions (Body)
#   Instructions for formatting all Person Mailers
#------------------------------------------------------------------
DocumentPersonBody = (
# --------- START: First section Contact Information ---------
    XProc(element="CIPSContact",
          occs=1,
          textOut=0, order=XProc.ORDER_TOP),
    XProc(element="/Person/PersonLocations/OtherPracticeLocation"
                  "/Organization/Name",
          order=XProc.ORDER_TOP,
          prefix="  \\renewcommand{\OrgName}{",
          suffix="}\n"),
    XProc(element="GivenName",
          order=XProc.ORDER_TOP,
          prefix="  \\newcommand{\Person}{",
          suffix=" "),
    XProc(element="SurName",
          order=XProc.ORDER_TOP,
          suffix="}\n"),
    XProc(element="GenerationSuffix",
          prefix="  \\newcommand{\GenSuffix}{",
          suffix=" }\n", order=XProc.ORDER_TOP),
    XProc(element="StandardProfessionalSuffix",
          prefix="  \\newcommand{\PerSuffix}{",
          suffix="}\n", order=XProc.ORDER_TOP),
    XProc(element="Address",
          textOut=0, order=XProc.ORDER_TOP),
    XProc(element="Street",
          textOut=0,
          order=XProc.ORDER_PARENT,
          preProcs=( (street, ()), )),
    XProc(element="City",
          order=XProc.ORDER_TOP,
          prefix="  \\renewcommand{\City}{",
          suffix="}\n"),
    XProc(element="PoliticalSubUnitShortName",
          order=XProc.ORDER_TOP,
          prefix="  \\renewcommand{\PoliticalUnitState}{",
          suffix="}\n"),
    XProc(element="CountryFullName",
          order=XProc.ORDER_TOP,
          prefix="  \\renewcommand{\Country}{",
          suffix="}\n"),
    XProc(element="PostalCode_ZIP",
          order=XProc.ORDER_TOP,
          prefix="  \\renewcommand{\PostalCodeZIP}{",
          suffix="}\n"),
    XProc(element="SpecificPhone",
          order=XProc.ORDER_TOP,
          prefix="  \\renewcommand{\Phone}{",
          suffix="}\n"),
    XProc(element="SpecificFax",
          order=XProc.ORDER_TOP,
          prefix="  \\renewcommand{\Fax}{",
          suffix="}\n"),
    XProc(element="SpecificEmail",
          order=XProc.ORDER_TOP,
          prefix="  \\renewcommand{\Email}{",
          suffix="}\n"),
    XProc(element="SpecificWeb",
          order=XProc.ORDER_TOP,
          prefix="  \\renewcommand{\Web}{",
          suffix="}\n"),
# --------- END: First section Contact Information ---------
    XProc(prefix=PERSON_PRINT_CONTACT, order=XProc.ORDER_TOP),
    XProc(element="/PersonMailer/OtherLocation",
          textOut=0,
          order=XProc.ORDER_PARENT,
          prefix=PERSON_RESET_OTHER,
          suffix=PERSON_PRINT_OTHER),
    XProc(element="/PersonMailer/OtherLocation/Address",
          textOut=0,
          order=XProc.ORDER_PARENT),
    XProc(element="/PersonMailer/OtherLocation/Address/Street",
          textOut=0,
          order=XProc.ORDER_PARENT,
          preProcs=( (street, ()), )),
    XProc(element="Org",
          order=XProc.ORDER_PARENT,
          prefix="  \\renewcommand{\Org}{",
          suffix="}\n"),
    XProc(element="/PersonMailer/OtherLocation/Phone",
          order=XProc.ORDER_PARENT,
          prefix="  \\renewcommand{\Phone}{",
          suffix="}\n"),
    XProc(element="/PersonMailer/OtherLocation/Fax",
          order=XProc.ORDER_PARENT,
          prefix="  \\renewcommand{\Fax}{",
          suffix="}\n"),
    XProc(element="/PersonMailer/OtherLocation/Email",
          order=XProc.ORDER_PARENT,
          prefix="  \\renewcommand{\Email}{",
          suffix="}\n"),
    XProc(element="/PersonMailer/OtherLocation/URI",
          order=XProc.ORDER_PARENT,
          prefix="  \\renewcommand{\Web}{",
          suffix="}\n"),
    XProc(prefix=PERSON_MISC_INFO, order=XProc.ORDER_TOP),
    XProc(prefix=PERSON_SPECIALTY_TAB, order=XProc.ORDER_TOP),
    XProc(element="SpecialtyCategory",
          textOut=0, order=XProc.ORDER_TOP),
    XProc(element="BoardCertifiedSpecialtyName",
          order=XProc.ORDER_PARENT,
          postProcs=((yesno,("BoardCertifiedSpecialtyName",
                             "BoardCertifiedSpecialtyName",)),)),
    XProc(prefix=END_TABLE, order=XProc.ORDER_TOP),
    XProc(prefix=PERSON_TRAINING_TAB, order=XProc.ORDER_TOP),
    XProc(element="TrainingCategory",
          textOut=0, order=XProc.ORDER_TOP),
    XProc(element="/PersonMailer/TrainingCategory/Name",
          order=XProc.ORDER_PARENT,
          postProcs=((yesno,("Name","YesNo",)),)),
    XProc(prefix=END_TABLE, order=XProc.ORDER_TOP),
    XProc(prefix=PERSON_SOCIETY_TAB, order=XProc.ORDER_TOP),
    XProc(element="ProfSociety",
          textOut=0, order=XProc.ORDER_TOP),
    XProc(element="MemberOfMedicalSociety",
          order=XProc.ORDER_PARENT,
          postProcs=((yesno,("MemberOfMedicalSociety","YesNo",)),)),
    XProc(prefix=END_TABLE, order=XProc.ORDER_TOP),
    XProc(prefix=PERSON_CLINGRP_TAB, order=XProc.ORDER_TOP),
    XProc(element="TrialGroup",
          textOut=0, order=XProc.ORDER_TOP),
    XProc(element="/Person/ProfessionalInformation/PhysicianDetails"
                  "/PhysicianMembershipInformation/MemberOfCooperativeGroup"
                  "/CooperativeGroup/OfficialName/Name",
          order=XProc.ORDER_PARENT,
          postProcs=((yesno,("Name","YesNo",)),)),
    XProc(prefix=END_TABLE, order=XProc.ORDER_TOP),
    XProc(prefix=PERSON_CCOP_TAB, order=XProc.ORDER_TOP),
    )


#------------------------------------------------------------------
# Status and Participant Site Check (non-Coop Groups)
#
#   Instructions for formatting all status and participant mailers
#------------------------------------------------------------------
STATUSPROTOCOLDEF=r"""
   %% STATUSPROTOCOLDEF %%
   %% ----------------- %%
   \newcommand{\ProtocolID}{dummy}
   \newcommand{\NCIID}{dummy}
   \newcommand{\ProtocolKey}{dummy}
   \newcommand{\ProtocolTitle}{dummy}
   \newcommand{\CurrentStatus}{dummy}
   \newcommand{\LeadOrg}{dummy}
   \newcommand{\LeadPerson}{}
   \newcommand{\LeadRole}{}
   \newcommand{\Street}{}
   \newcommand{\LeadPhone}{}
%
% ---------
"""


STATUSPUPADDRESS=r"""
   %% PUPADDRESS %%
   %% ---------- %%
   \PUP\ , \PUPTitle \\
   \PUPOrg  \\
   \Street
   Ph:  \PUPPhone

%
% -------
"""


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
  \newpage
  \item
  \textit{\ProtocolTitle}
  \renewcommand{\ewidth}{120pt}
  \begin{entry}
     \item[Protocol ID]        \ProtocolID
     \item[Current Status]     \CurrentStatus
     \item[Status Change]      Please indicate new status and the
                               status change date (MM/DD/YYYY)
                               \ProtStatDefinition
  \end{entry}
%
% -------
"""

STATUSCHAIRINFO=r"""
   %% STATUSCHAIRINFO %%
   %% -------------- %%
  \begin{entry}
     \item[Lead Organization]        \LeadOrg
     \item[Protocol Personnel]       \LeadPerson,  \LeadRole
     \item[Address]                  \Street
     \item[Phone]                    \LeadPhone
  \end{entry}
%
% -------
"""


DocumentStatusCheckBody = (
# --------- START: First section Contact Information ---------
    XProc(prefix=STATUSPROTOCOLDEF, order=XProc.ORDER_TOP),
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
    XProc(element="Org",
          prefix="  \\newcommand{\PUPOrg}{",
          suffix="}\n", order=XProc.ORDER_TOP),
    XProc(element="/SPSCheck/PUP/Phone",
          prefix="  \\newcommand{\PUPPhone}{",
          suffix="}\n"),
    XProc(element="/SPSCheck/PUP/Street",
          textOut=0,
          preProcs=( (street, ()), )),
    XProc(element="/SPSCheck/PUP/Phone",
          prefix="  \\newcommand{\PUPPhone}{",
          suffix="}\n"),
    XProc(prefix=STATUSPUPADDRESS, order=XProc.ORDER_TOP),
    XProc(prefix=STATUSDEF,
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
                 STATUS_TAB_INTRO + STATUS_TAB),
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
    XProc(element="ParticipatingSite",
          order=XProc.ORDER_PARENT,
          textOut=0),
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


DocumentStatusCheckCCOPBody = (
# --------- START: First section Contact Information ---------
    XProc(prefix=STATUSPROTOCOLDEF, order=XProc.ORDER_TOP),
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
    XProc(element="Org",
          prefix="  \\newcommand{\PUPOrg}{",
          suffix="}\n", order=XProc.ORDER_TOP),
    XProc(element="/SPSCheck/PUP/Phone",
          prefix="  \\newcommand{\PUPPhone}{",
          suffix="}\n"),
    XProc(element="/SPSCheck/PUP/Street",
          textOut=0,
          preProcs=( (street, ()), )),
    XProc(element="/SPSCheck/PUP/Phone",
          prefix="  \\newcommand{\PUPPhone}{",
          suffix="}\n"),
    XProc(prefix=STATUSPUPADDRESS, order=XProc.ORDER_TOP),
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
    XProc(element="ParticipatingSite",
          order=XProc.ORDER_PARENT,
          textOut=0),
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
    XProc(prefix=DRAFT, order=XProc.ORDER_TOP),
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
    XProc(prefix=DRAFT, order=XProc.ORDER_TOP),
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
    XProc(prefix=DRAFT, order=XProc.ORDER_TOP),
    XProc(prefix=FONT, order=XProc.ORDER_TOP),
    XProc(prefix=STYLES, order=XProc.ORDER_TOP),
    XProc(prefix=ENTRYLIST, order=XProc.ORDER_TOP),
    XProc(prefix=QUOTES, order=XProc.ORDER_TOP),
    XProc(prefix=ORG_HDRTEXT, order=XProc.ORDER_TOP),
    XProc(prefix=FANCYHDR, order=XProc.ORDER_TOP),
    XProc(prefix=TEXT_BOX, order=XProc.ORDER_TOP),
    XProc(prefix=PHONE_RULER, order=XProc.ORDER_TOP),
    XProc(prefix=ORG_DEFS, order=XProc.ORDER_TOP),
    XProc(prefix=ORG_TITLE, order=XProc.ORDER_TOP),
    XProc(prefix=ENDPREAMBLE, order=XProc.ORDER_TOP),
    )

DocumentPersonHeader =(
    XProc(prefix=LATEXHEADER, order=XProc.ORDER_TOP),
    XProc(prefix=DRAFT, order=XProc.ORDER_TOP),
    XProc(prefix=FONT, order=XProc.ORDER_TOP),
    XProc(prefix=STYLES, order=XProc.ORDER_TOP),
    XProc(prefix=ENTRYLIST, order=XProc.ORDER_TOP),
    XProc(prefix=QUOTES, order=XProc.ORDER_TOP),
    XProc(prefix=PERSON_HDRTEXT, order=XProc.ORDER_TOP),
    XProc(prefix=FANCYHDR, order=XProc.ORDER_TOP),
    XProc(prefix=TEXT_BOX, order=XProc.ORDER_TOP),
    XProc(prefix=PHONE_RULER, order=XProc.ORDER_TOP),
    XProc(prefix=PERSON_DEFS, order=XProc.ORDER_TOP),
    XProc(prefix=PERSON_TITLE, order=XProc.ORDER_TOP),
    XProc(prefix=ENDPREAMBLE, order=XProc.ORDER_TOP)
    )

DocumentStatusCheckHeader =(
    XProc(prefix=LATEXHEADER, order=XProc.ORDER_TOP),
    XProc(prefix=DRAFT, order=XProc.ORDER_TOP),
    XProc(prefix=FONT, order=XProc.ORDER_TOP),
    XProc(prefix=STYLES, order=XProc.ORDER_TOP),
    XProc(prefix=ENTRYBFLIST, order=XProc.ORDER_TOP),
    XProc(prefix=QUOTES, order=XProc.ORDER_TOP),
    XProc(prefix=STATPART_HDRTEXT, order=XProc.ORDER_TOP),
    XProc(prefix=FANCYHDR, order=XProc.ORDER_TOP),
    XProc(prefix=TEXT_BOX, order=XProc.ORDER_TOP),
    XProc(prefix=PHONE_RULER, order=XProc.ORDER_TOP),
    XProc(prefix=STATPART_TITLE, order=XProc.ORDER_TOP),
    XProc(prefix=ENDPREAMBLE, order=XProc.ORDER_TOP)
    )


DocumentTestHeader =(
    XProc(prefix=LATEXHEADER, order=XProc.ORDER_TOP),
    XProc(prefix=DRAFT, order=XProc.ORDER_TOP),
    XProc(prefix=FONT, order=XProc.ORDER_TOP),
    XProc(prefix=STYLES, order=XProc.ORDER_TOP),
    XProc(prefix=ENTRYBFLIST, order=XProc.ORDER_TOP),
    XProc(prefix=QUOTES, order=XProc.ORDER_TOP),
    XProc(prefix=FANCYHDR, order=XProc.ORDER_TOP),
    XProc(prefix=ENDPREAMBLE, order=XProc.ORDER_TOP)
    )

# ###########################################################
# Creating the different types of footers for each mailer
# ###########################################################

# Creating section with return address and allow to sign and
# date the mailer.
# -----------------------------------------------------------
APPROVAL=r"""
  %% APPROVAL %%
  %% -------- %%
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
    XProc(prefix=APPROVAL, order=XProc.ORDER_TOP),
    XProc(prefix=DOCFTR, order=XProc.ORDER_TOP),
    )

DocumentPersonFooter =(
    XProc(prefix=APPROVAL, order=XProc.ORDER_TOP),
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
#------------------------------------------------------------------
ControlTable = {\
    ("Protocol",         ""):ProtocolInstructions,\
    ("Summary",          ""):SummaryInstructions,\
    ("Summary",      "initial"):SummaryInstructions,\
    ("Organization",     ""):OrgInstructions,\
    ("Person",           ""):PersonInstructions,\
    ("StatusCheck",      ""):StatusCheckInstructions,\
    ("StatusCheckCCOP",  ""):StatusCheckCCOPInstructions,\
    ("Test",             ""):TestInstructions\
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
    if type(val) == type(''):
        return val
    if type(val) == type(1):
        return '%d' % val

