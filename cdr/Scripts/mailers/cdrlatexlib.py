"""CdrXmlLatexSummaryInst: Processing instructions for generating a summary"""

import sys, re, xml.dom.minidom, UnicodeToLatex

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
#                XProc.ORDER_TOP:
#                  If this is the Nth listed element with XProc.ORDER_TOP,
#                    output the first N-1 elements, then this one.
#                XProc.ORDER_PARENT:
#                  If this is the Nth listed element within it's parent
#                    so order it in the output.
#                XProc.ORDER_DOCUMENT:
#                  Process this within it's parent, but in the order found.
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
#
#-------------------------------------------------------------------
class XProc:
    # Pattern for checking attribute name =/!= value
    attrPat = re.compile(r'([A-Za-z_]+)\s*(!?)=\s*(.*)')
    ORDER_TOP      = 1  # Process in order given in instructions, at top level
    ORDER_PARENT   = 2  # Process in order given in instructions, within parent
    ORDER_DOCUMENT = 3  # Process in order found in the document

    def __init__(self,\
		 element=None,      # No element involved unless specified\
                 attr=None,         # Attribute specification for element\
                 occs=0,            # Default= all occurrences\
                 order=ORDER_TOP, # Assume element ordered same as list\
                 prefix=None,       # No prefix before output of text\
                 preProcs=None,     # No procedures to run\
                 textOut=1,         # Output the text\
                 descend=1,         # Examine child elements\
                 postProcs=None,    # No procedures to run after output\
                 suffix=None):      # No suffix
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
     if prevNode.nodeName == 'CitationReference':
        return 0

     # Beginning of list of one or more citation numbers
     citeString = r"\cite{"

     # Capture the text of all contiguous citation references,
     #   separating them with commas
     count = 0
     while citeNode != None and \
           citeNode.nodeName == 'CitationReference':

        # Comma separator before all but the first one
        if count > 0:
            citeString += r","

        # Reference index number is in the refidx attribute
        # Extract the attribute value from the CitationReference
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
     # Extract the attribute value from the CitationReference
     # tag
     # ------------------------------------------------------
     attrValue = getAttribute (refNode, 'refidx')
     if (attrValue != None):
        # refString += refNode.nextSibling
        refString += attrValue

     # Terminate the Latex for the list of citation
     refString += r"}"

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
#     Next Desctiption           X
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
              if checkit == "Y":
                 checkString += " \\Check{Y}"
              else:
                 checkString += " \\Check{N}"

              # For the Specialty category loop through the list of
              # siblings again since we may have passed a board
              # certification earlier.  However, the Check{} for this
              # certification must come as a second entry in LaTeX
              # -----------------------------------------------------
              if checkNode.nodeName == "Specialty":
                 while boardNode != None:
                    if boardNode.nodeName == "BoardCertified":
                       txtNode = boardNode.firstChild
                       checkboard = txtNode.nodeValue
                       if checkboard == "Y":
                          checkString += " \\Check{Y}"
                       else:
                          checkString += " \\Check{B}"
                    boardNode = boardNode.nextSibling

           checkNode = checkNode.nextSibling

        # Once we know the YesNo value we can end the LaTeX line and
        # return to the calling program
        # ----------------------------------------------------------
        checkString += " \\\\ \hline\n"
        pp.setOutput (checkString)

        return 0



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
  \newcommand{\Special}[1]{{\fontencoding{T1}\selectfont\symbol{#1}}}

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
  \renewcommand{\familydefault}{\myfont}
  \newcommand{\myfont}{phv}
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
  \newcommand{\CenterHdr}{Organization ID: @@ORGID@@ \\ {\bfseries XX \Org}}
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

# Defining the document header for each page
# Used by:  Protocol
# ------------------------------------------
PROTOCOL_HDRTEXT=r"""
  %% PROTOCOL_HDRTEXT %%
  %% -------------- %%
  \newcommand{\LeftHdr}{                     \\ \today }
  \newcommand{\CenterHdr}{Protocol ID: @@PROTID@@ \\                    }
  \newcommand{\RightHdr}{                        \\ Doc ID: @@DOCID@@ }
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
  %% STYLES %%
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
  \newcommand{\Phone}{}
  \newcommand{\Fax}{}
  \newcommand{\Email}{}
  \newcommand{\Web}{}
  \newcommand{\Street}{}
  \newcommand{\City}{}
  \newcommand{\PoliticalUnitState}{}
  \newcommand{\Country}{}
  \newcommand{\PostalCodeZIP}{}
%
% -----
"""

PERSON_DEFS=r"""
  %% PERSON_DEFS %%
  %% -------- %%
  % Variable Definitions
  % --------------------
  \newcommand{\Org}{}
  \newcommand{\Phone}{}
  \newcommand{\Fax}{}
  \newcommand{\Email}{}
  \newcommand{\Web}{}
  \newcommand{\Street}{}
  \newcommand{\City}{}
  \newcommand{\PoliticalUnitState}{}
  \newcommand{\Country}{}
  \newcommand{\PostalCodeZIP}{}
%
% -----
"""

PROTOCOL_DEFS=r"""
  %% PERSON_DEFS %%
  %% -------- %%
  % Variable Definitions
  % --------------------
  \newcommand{\ProtocolID}{}
%
% -----
"""

ORG_PRINT_CONTACT=r"""
   %% ORG_PRINT_CONTACT %%
   %% ----------------- %%
   \Person  \\
   \Org     \\
   \Street   \\
   \City, \PoliticalUnitState\  \PostalCodeZIP \\

   \OrgIntro

   \subsection*{CIPS Contact Information}

   \Org     \\
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
   \Person, \PerSuffix  \\
   \Org     \\
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
   \renewcommand{\Org}{}
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
    Font: \myfont}
  \end{center}
  \tableofcontents

%%%  \begin{cbunit}

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
  \renewcommand{\theenumii}{\Roman{enumii}}
  \renewcommand{\labelenumii}{\theenumii.}

  %% -- END -- Document Declarations and Definitions


  \begin{document}
  \include{/cdr/mailers/include/template}

  \begin{center}\bfseries \large
    \mailertitle
  \end{center}
  \centerline{Font: \myfont}
%
% -----
"""


ENDPROTPREAMBLE=r"""
  %% ENDPROTPREAMBLE %%
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


ADDRESS = (
    XProc(element="Name",
          occs=0,
          prefix="  \\newcommand{\Person}{",
          suffix="}\n"),
    XProc(element="ProfSuffix",
          occs=0,
          prefix="  \\newcommand{\PerSuffix}{",
          suffix="}\n"),
    XProc(element="Address",
          textOut=0),
    XProc(element="Street",
          occs=0,
          textOut=0,
          order=3,
          preProcs=( (street, ()), )),
    XProc(element="City",
          occs=0,
          order=3,
          prefix="  \\renewcommand{\City}{",
          suffix="}\n"),
    XProc(element="PoliticalUnit_State",
          occs=0,
          order=3,
          prefix="  \\renewcommand{\PoliticalUnitState}{",
          suffix="}\n"),
    XProc(element="Country",
          occs=0,
          order=3,
          prefix="  \\renewcommand{\Country}{",
          suffix="}\n"),
    XProc(element="PostalCode_ZIP",
          occs=0,
          order=3,
          prefix="  \\renewcommand{\PostalCodeZIP}{",
          suffix="}\n"),
    XProc(element="Phone",
          occs=0,
          order=1,
          prefix="  \\renewcommand{\Phone}{",
          suffix="}\n"),
    XProc(element="Fax",
          occs=0,
          order=1,
          prefix="  \\renewcommand{\Fax}{",
          suffix="}\n"),
    XProc(element="Email",
          occs=0,
          order=1,
          prefix="  \\renewcommand{\Email}{",
          suffix="}\n"),
    XProc(element="URI",
          occs=0,
          order=1,
          prefix="  \\renewcommand{\Web}{",
          suffix="}\n")
    )


PROTOCOL_TITLE=r"""
  %% PROTOCOL_TITLE %%
  %% -------------- %%

  \setcounter{qC}{0}
  \subsection*{Protocol Title}
  \ProtocolTitle
%
% -----
"""


PROTOCOL_INFORMATION=r"""
  %% PROTOCOL_INFORMATION %%
  %% -------------------- %%

  \setcounter{qC}{0}
  \subsection*{General Protocol Information}
  \renewcommand{\ewidth}{200pt}
  \begin{entry}
     \item[Protocol ID]                \ProtocolID
                                       \ProtocolOtherID
     \item[Protocol Activation Date]   \ProtocolActiveDate
     \item[Lead Organization]          \ProtocolLeadOrg
     \item[Protocol Chairman]          \ProtocolChair
     \item[Phone]                      \ChairPhone
     \item[Address]                    \ChairAddress
     \item[Protocol Status]            \CurrentStatus

     \item[Eligible Patient Age Range] \AgeRange
     \item[Lower Age Limit]            \LowAge
     \item[Upper Age Limit]            \HighAge
  \end{entry}
%
% -----
"""


DISEASE_TERMS=r"""
  %% DISEASE_TERMS %%
  %% ------------------- %%
  \setcounter{qC}{0}
  \subsection*{Disease Retrieval Terms}
  % \newcommand{\DiseaseTerms}{%
  \begin{list}{$\circ$}{\setlength{\itemsep}{-5pt}}
  \item stage IV rectal cancer
  \end{list}

  % \DiseaseTerms
% }
%
% -----
"""


PROTOCOL_OBJECTIVE=r"""
  %% PROTOCOL_OBJECTIVE %%
  %% ------------------ %%
  \setcounter{qC}{0}
  \subsection*{Protocol Objectives}
  \ProtocolObjectives
%
% -----
"""


PATIENT_ELIGIBILITY=r"""
  %% PATINET_ELIGIBILITY %%
  %% ------------------- %%
  \setcounter{qC}{0}
  \subsection*{Patient Eligibility}
  \subsubsection*{Disease Characteristics}
  \DiseaseCharacteristics

  \subsubsection*{Prior/Concurrent Therapy}
  \PriorTherapy

  \subsubsection*{Patient Characteristics}
  \PatientCharacteristics
%
% -----
"""


PROTOCOL_OUTLINE=r"""
  %% PROTOCOL_OUTLINE %%
  %% ---------------- %%
  \setcounter{qC}{0}
  \subsection*{Protocol Outline}
  \ProtocolOutline
%
% -----
"""


STRATIFICATION_PARAMETERS=r"""
  %% STRATIFICATION_PARAMETERS %%
  %% ------------------------- %%
  \setcounter{qC}{0}
  \subsection*{Stratification Parameters}
  \StratificationParameters
%
% -----
"""


PROJECTED_ACCRUAL=r"""
  %% PROJECTED_ACCRUAL %%
  %% ----------------- %%
  \setcounter{qC}{0}
  \subsection*{Projected Accrual}
  \ProjectedAccrual
%
% -----
"""

ENDPOINTS=r"""
  %% ENDPOINTS %%
  %% --------- %%
  \setcounter{qC}{0}
  \subsection*{End Points}
  \EndPoints
%
% -----
"""

STRATIFICATION=r"""
  %% STRATIFICATION %%
  %% -------------- %%
  \setcounter{qC}{0}
  \subsection*{Stratification}
  \Stratification
%
% -----
"""

STUDY_PARAMETERS=r"""
  %% STUDY_PARAMETERS %%
  %% ------_--------- %%
  \setcounter{qC}{0}
  \subsection*{Study Parameters}
  \StudyParameters
%
% -----
"""

DOSE_SCHEDULE=r"""
  %% DOSE_SCHEDULE %%
  %% ------------- %%
  \setcounter{qC}{0}
  \subsection*{Dose Schedule}
  \DoseSchedule
%
% -----
"""

DOSAGE_FORM=r"""
  %% DOSAGE_FORM %%
  %% ----------- %%
  \setcounter{qC}{0}
  \subsection*{Dosage Formulation}
  \DosageForm
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
#------------------------------------------------------------------
# Board Summaries
#
#   Instructions for formatting all board summary mailers
#------------------------------------------------------------------


DocumentSummaryBody = (\
#    XProc(element="/Summary/SummarySection",\
#	  textOut=0,\
#	  occs=0,\
#          order=2,\
#          suffix=   "\nYY  \\end{cbunit}\n\n"),\
    XProc(element="SummarySection",\
          occs=0,   \
          textOut=1,\
          suffix=   "\n  \\end{cbunit}\n\n"),\
    XProc(element="Title",\
    	  occs=0, \
          order=2,\
          prefix="  \\section{",\
	  suffix=   "}\n\n  \\begin{cbunit}\n"),\
    XProc(element="Para",\
    	  occs=0, \
          order=3,\
          prefix="\n  \\setcounter{qC}{0}\n",\
          suffix="\n\n"),\
    XProc(element="/Summary/SummarySection/SummarySection",\
          textOut=0,\
          occs=0,\
          order=2),\
    XProc(element="/Summary/SummarySection/SummarySection/Title",\
	  occs=0,\
          order=2,\
          prefix="  \\subsection{",\
	  suffix=   "}\n"),\
    XProc(element="/Summary/SummarySection/SummarySection/Para",\
	  occs=0,\
          order=3,\
          prefix="  \\setcounter{qC}{0}\n",\
	  suffix=   "\n\n"),\
    XProc(element="ItemizedList",
          occs=0, \
          order=3,\
          textOut=0,\
          prefix="\n  \\begin{itemize}\n",\
	  suffix="\n  \\end{itemize}\n"),\
    XProc(element="OrderedList",
          occs=0, \
          order=3,\
          textOut=0,\
          prefix="\n  \\begin{enumerate}\n",\
	      suffix="\n  \\end{enumerate}\n"),\
    XProc(element="ListItem",
          occs=0, \
	  order=3,\
	  prefix="  \\item "),
    XProc(element="CitationReference",\
    	  occs=0,\
          order=3,\
          textOut=1,\
          preProcs=((cite,()),)),\
    XProc(element="References",\
	  order=2,\
          textOut=0,\
          prefix="\n  \\begin{thebibliography}{999}\n",\
          suffix="\n  \\end{thebibliography}\n"),\
    XProc(element="Reference",\
    	  occs=0,\
	      order=2,\
	      textOut=1,\
          preProcs=( (bibitem, ()), ))\
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
DocumentProtocolBody =(
    XProc(element="ProtocolTitle",
          order=2,
          occs=1,
          prefix="  \\newcommand{\ProtocolTitle}{",
          suffix="}\n"),
    XProc(prefix=PROTOCOL_TITLE),
    XProc(element="PrimaryID",
          textOut=0,
          order=2,),
    XProc(element="IDString",
          order=2,
          prefix="  \\renewcommand{\ProtocolID}{",
          suffix="}\n"),
    XProc(element="HighAge",
          prefix="  \\newcommand{\HighAge}{",
          suffix="}\n"),
    XProc(element="LowAge",
          prefix="  \\newcommand{\LowAge}{",
          suffix="}\n"),
    XProc(element="AgeText",
          prefix="  \\newcommand{\AgeRange}{",
          suffix="}\n"),
    XProc(element="CurrentProtocolStatus",
          prefix="  \\newcommand{\CurrentStatus}{",
          suffix="}\n"),
    XProc(prefix=PROTOCOL_INFORMATION),
    XProc(prefix=DISEASE_TERMS),
    XProc(element="/InScopeProtocol/ProtocolAbstract/Professional/Objectives/OrderedList",
          textOut=0,
          prefix="  \\newcommand{\\ProtocolObjectives}{%\n  \\renewcommand{\\theenumi}{\\Roman{enumi}}\n  \\renewcommand{\\labelenumi}{\\theenumi.}\n  \\begin{enumerate}\n",
          suffix="  \\end{enumerate}\n}\n"),
    XProc(element="/InScopeProtocol/ProtocolAbstract/Professional/Objectives/OrderedList/ListItem",
          order=2,
          prefix="  \\item ",
          suffix="  \n"),
    XProc(prefix=PROTOCOL_OBJECTIVE),
    XProc(element="/InScopeProtocol/ProtocolAbstract/Professional/EntryCriteria/DiseaseCharacteristics",
          textOut=0,
          prefix="  \\newcommand{\\DiseaseCharacteristics}{%\n",
          suffix="  }\n"),
    XProc(element="/InScopeProtocol/ProtocolAbstract/Professional/EntryCriteria/PatientCharacteristics",
          textOut=0,
          prefix="  \\newcommand{\\PriorTherapy}{\n",
          suffix="  }\n"),
    XProc(element="/InScopeProtocol/ProtocolAbstract/Professional/EntryCriteria/PriorConcurrentTherapy",
          textOut=0,
          prefix="  \\newcommand{\\PatientCharacteristics}{\n",
          suffix="  }\n"),
    XProc(prefix=PATIENT_ELIGIBILITY),
    XProc(element="/InScopeProtocol/ProtocolAbstract/Professional/Outline",
          textOut=0,
          prefix="  \\newcommand{\\ProtocolOutline}{\n",
          suffix="  }\n"),
    XProc(element="/InScopeProtocol/ProtocolAbstract/Professional/Outline/Para",
          order=2,
          suffix="  \n\n"),
    XProc(prefix=PROTOCOL_OUTLINE),
    XProc(element="/InScopeProtocol/ProtocolAbstract/Professional/ProjectedAccrual",
          textOut=0,
          prefix="  \\newcommand{\\ProjectedAccrual}{\n",
          suffix="  }\n"),
    XProc(prefix=PROJECTED_ACCRUAL),
    XProc(element="/InScopeProtocol/ProtocolAbstract/Professional/EndPoints/Para",
          textOut=0),
#         prefix="  \\newcommand{\\EndPoints}{\n",
#         suffix="  }\n"),
#   XProc(prefix=ENDPOINTS),
    XProc(element="/InScopeProtocol/ProtocolAbstract/Professional/Stratification/Para",
          textOut=0),
#         prefix="  \\newcommand{\\Stratification}{\n",
#         suffix="  }\n"),
#   XProc(prefix=STRATIFICATION),
    XProc(element="/InScopeProtocol/ProtocolAbstract/Professional/SpecialStudyParameters/Para",
          textOut=0),
#         prefix="  \\newcommand{\\StudyParameters}{\n",
#         suffix="  }\n"),
#   XProc(prefix=STUDY_PARAMETERS),
     XProc(element="/InScopeProtocol/ProtocolAbstract/Professional/DoseSchedule/Para",
           textOut=0),
#          prefix="  \\newcommand{\\DoseSchedule}{\n",
#          suffix="  }\n"),
#    XProc(prefix=DOSE_SCHEDULE),
     XProc(element="/InScopeProtocol/ProtocolAbstract/Professional/DosageForm/Para",
           textOut=0),
#          prefix="  \\newcommand{\\DosageForm}{\n",
#          suffix="  }\n"),
#    XProc(prefix=DOSAGE_FORM),
    XProc(element="Para",
    	  occs=0,
          order=2,
          prefix="\n  \\setcounter{qC}{0}\n",
          suffix="\n\n"),
#  Within an itemized list is always a ListTitle and a ListItem.  The
#  ListTitle has to be displayed BEFORE the start of the list but ends with
#  the end of the ItemizedList tag
#  -------------------------------------------------------------------------
    XProc(element="ItemizedList",
          textOut=0,
          order=2,
          suffix="  \\end{itemize}"),
    XProc(element="ListTitle",
          order=2,
          prefix="  {\\bfseries \it ",
          suffix="}\n  \\begin{itemize}\n"),
    XProc(element="ListItem",
          order=2,
          prefix="    \\item ",
          suffix="\n"),
        )


#------------------------------------------------------------------
# Organization Mailer Instructions (Body)
#   Instructions for formatting all Organization Mailers
#------------------------------------------------------------------
DocumentOrgBody =(
# --------- START: First section Contact Information ---------
    XProc(element="Org",
          order=2,
          prefix="  \\newcommand{\Org}{",
          suffix="}\n"),
    XProc(element="Name",
          prefix="  \\newcommand{\Person}{",
          suffix="}\n"),
    XProc(element="Address",
          textOut=0),
    XProc(element="Street",
          textOut=0,
          order=3,
          preProcs=( (street, ()), )),
    XProc(element="City",
          order=3,
          prefix="  \\renewcommand{\City}{",
          suffix="}\n"),
    XProc(element="PoliticalUnit_State",
          order=3,
          prefix="  \\renewcommand{\PoliticalUnitState}{",
          suffix="}\n"),
    XProc(element="Country",
          order=3,
          prefix="  \\renewcommand{\Country}{",
          suffix="}\n"),
    XProc(element="PostalCode_ZIP",
          order=3,
          prefix="  \\renewcommand{\PostalCodeZIP}{",
          suffix="}\n"),
    XProc(element="Phone",
          order=1,
          prefix="  \\renewcommand{\Phone}{",
          suffix="}\n"),
    XProc(element="Fax",
          order=1,
          prefix="  \\renewcommand{\Fax}{",
          suffix="}\n"),
    XProc(element="Email",
          order=1,
          prefix="  \\renewcommand{\Email}{",
          suffix="}\n"),
    XProc(element="URI",
          order=1,
          prefix="  \\renewcommand{\Web}{",
          suffix="}\n"),
    XProc(prefix=ORG_PRINT_CONTACT),
# --------- END: First section Contact Information ---------
    XProc(element="/OrgMailer/OtherLocation",
          textOut=0,
          order=2,
          prefix=ORG_RESET_OTHER,
          suffix=ORG_PRINT_OTHER),
    XProc(element="/OrgMailer/OtherLocation/Address",
          textOut=0,
          order=2),
    XProc(element="/OrgMailer/OtherLocation/Address/Street",
          textOut=0,
          order=2,
          preProcs=( (street, ()), )),
    XProc(element="/OrgMailer/OtherLocation/Phone",
          order=2,
          prefix="  \\renewcommand{\Phone}{",
          suffix="}\n"),
    XProc(element="/OrgMailer/OtherLocation/Fax",
          order=2,
          prefix="  \\renewcommand{\Fax}{",
          suffix="}\n"),
    XProc(element="/OrgMailer/OtherLocation/Email",
          order=2,
          prefix="  \\renewcommand{\Email}{",
          suffix="}\n"),
    XProc(element="/OrgMailer/OtherLocation/URI",
          order=2,
          prefix="  \\renewcommand{\Web}{",
          suffix="}\n"),
# --------- Start: Affiliations Section ---------
    XProc(prefix=ORG_AFFILIATIONS),
    XProc(prefix="\n  \\begin{itemize}\n"),
    XProc(element="ProfessionalOrg",
          order=1,
          prefix="\n    \\item "),
    XProc(prefix="\n  \\end{itemize}\n"),
    XProc(prefix="\n  \\subsubsection*{Cooperative Groups}"),
    XProc(prefix="\n  \\begin{itemize}\n"),
    XProc(element="MemberOf",
          order=1,
          prefix="\n    \\item "),
    XProc(prefix="\n  \\end{itemize}\n")
    )


#------------------------------------------------------------------
# Person Mailer Instructions (Body)
#   Instructions for formatting all Person Mailers
#------------------------------------------------------------------
DocumentPersonBody = (
# --------- START: First section Contact Information ---------
    XProc(element="CipsContact",
          occs=1,
          textOut=0),
    XProc(element="/PersonMailer/CipsContact/Org",
          order=1,
          prefix="  \\renewcommand{\Org}{",
          suffix="}\n"),
    XProc(element="/PersonMailer/Name",
          prefix="  \\newcommand{\Person}{",
          suffix="}\n"),
    XProc(element="ProfSuffix",
          prefix="  \\newcommand{\PerSuffix}{",
          suffix="}\n"),
    XProc(element="Address",
          textOut=0),
    XProc(element="Street",
          textOut=0,
          order=3,
          preProcs=( (street, ()), )),
    XProc(element="City",
          order=3,
          prefix="  \\renewcommand{\City}{",
          suffix="}\n"),
    XProc(element="PoliticalUnit_State",
          order=3,
          prefix="  \\renewcommand{\PoliticalUnitState}{",
          suffix="}\n"),
    XProc(element="Country",
          order=3,
          prefix="  \\renewcommand{\Country}{",
          suffix="}\n"),
    XProc(element="PostalCode_ZIP",
          order=3,
          prefix="  \\renewcommand{\PostalCodeZIP}{",
          suffix="}\n"),
    XProc(element="Phone",
          order=1,
          prefix="  \\renewcommand{\Phone}{",
          suffix="}\n"),
    XProc(element="Fax",
          order=1,
          prefix="  \\renewcommand{\Fax}{",
          suffix="}\n"),
    XProc(element="Email",
          order=1,
          prefix="  \\renewcommand{\Email}{",
          suffix="}\n"),
    XProc(element="URI",
          order=1,
          prefix="  \\renewcommand{\Web}{",
          suffix="}\n"),
# --------- END: First section Contact Information ---------
    XProc(prefix=PERSON_PRINT_CONTACT),
    XProc(element="/PersonMailer/OtherLocation",
          textOut=0,
          order=2,
          prefix=PERSON_RESET_OTHER,
          suffix=PERSON_PRINT_OTHER),
    XProc(element="/PersonMailer/OtherLocation/Address",
          textOut=0,
          order=2),
    XProc(element="/PersonMailer/OtherLocation/Address/Street",
          textOut=0,
          order=2,
          preProcs=( (street, ()), )),
    XProc(element="Org",
          order=2,
          prefix="  \\renewcommand{\Org}{",
          suffix="}\n"),
    XProc(element="/PersonMailer/OtherLocation/Phone",
          order=2,
          prefix="  \\renewcommand{\Phone}{",
          suffix="}\n"),
    XProc(element="/PersonMailer/OtherLocation/Fax",
          order=2,
          prefix="  \\renewcommand{\Fax}{",
          suffix="}\n"),
    XProc(element="/PersonMailer/OtherLocation/Email",
          order=2,
          prefix="  \\renewcommand{\Email}{",
          suffix="}\n"),
    XProc(element="/PersonMailer/OtherLocation/URI",
          order=2,
          prefix="  \\renewcommand{\Web}{",
          suffix="}\n"),
    XProc(prefix=PERSON_MISC_INFO),
    XProc(prefix=PERSON_SPECIALTY_TAB),
    XProc(element="SpecialtyCategory",
          textOut=0),
    XProc(element="/PersonMailer/SpecialtyCategory/Name",
          order=2,
          postProcs=((yesno,("Name","Specialty",)),)),
    XProc(prefix=END_TABLE),
    XProc(prefix=PERSON_TRAINING_TAB),
    XProc(element="TrainingCategory",
          textOut=0),
    XProc(element="/PersonMailer/TrainingCategory/Name",
          order=2,
          postProcs=((yesno,("Name","Training",)),)),
    XProc(prefix=END_TABLE),
    XProc(prefix=PERSON_SOCIETY_TAB),
    XProc(element="ProfSociety",
          textOut=0),
    XProc(element="/PersonMailer/ProfSociety/Name",
          order=2,
          postProcs=((yesno,("Name","YesNo",)),)),
    XProc(prefix=END_TABLE),
    XProc(prefix=PERSON_CLINGRP_TAB),
    XProc(element="TrialGroup",
          textOut=0),
    XProc(element="/PersonMailer/TrialGroup/Name",
          order=2,
          postProcs=((yesno,("Name","YesNo",)),)),
    XProc(prefix=END_TABLE),
    XProc(prefix=PERSON_CCOP_TAB),
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
    XProc(prefix=STATUSPROTOCOLDEF),
    XProc(element="PUP",
          textOut=0),
    XProc(element="/SPSCheck/PUP/Name",
          textOut=1,
          prefix="  \\newcommand{\PUP}{",
          suffix="}\n"),
    XProc(element="Title",
          order=2,
          prefix="  \\newcommand{\PUPTitle}{",
	      suffix="}\n"),
    XProc(element="Org",
          prefix="  \\newcommand{\PUPOrg}{",
          suffix="}\n"),
    XProc(element="/SPSCheck/PUP/Phone",
          order=3,
          prefix="  \\newcommand{\PUPPhone}{",
          suffix="}\n"),
    XProc(element="/SPSCheck/PUP/Street",
          textOut=0,
          order=3,
          preProcs=( (street, ()), )),
    XProc(element="/SPSCheck/PUP/Phone",
          order=3,
          prefix="  \\newcommand{\PUPPhone}{",
          suffix="}\n"),
    XProc(prefix=STATUSPUPADDRESS),
    XProc(prefix=STATUSDEF,
          suffix="  \\begin{enumerate}\n"),
# --------- END: First section Contact Information ---------
# --------- START: Second section Protocol Information ---------
    XProc(element="Protocol",
          textOut=0,
          suffix=END_TABLE),
    XProc(element="ProtocolTitle",
          order=2,
          prefix="  \\renewcommand{\\ProtocolTitle}{",
          suffix="  }\n "),
    XProc(element="CurrentStatus",
          order=2,
          prefix="  \\renewcommand{\\CurrentStatus}{",
          suffix="  }\n"),
    XProc(element="ID",
          order=2,
          prefix="  \\renewcommand{\\ProtocolID}{",
          suffix="  }\n  "),
    XProc(element="LeadOrg",
          order=2,
          prefix="  \\renewcommand{\\LeadOrg}{",
          suffix="  }\n"),
    # Need to start the table header as a suffix of the Personnel field
    # in order to create the table for each protocol record.
    XProc(element="Personnel",
          order=2,
          textOut=0,
          suffix=STATUSPROTINFO + STATUSCHAIRINFO + STATUS_TAB_INTRO + STATUS_TAB),
    XProc(element="/SPSCheck/Protocol/Personnel/Name",
          order=2,
          prefix="  \\renewcommand{\\LeadPerson}{",
          suffix="  }\n"),
    XProc(element="/SPSCheck/Protocol/Personnel/Role",
          order=2,
          prefix="  \\renewcommand{\\LeadRole}{",
          suffix="  }\n"),
    XProc(element="/SPSCheck/Protocol/Personnel/Street",
          textOut=0,
          order=2,
          preProcs=( (street, ()), )),
    XProc(element="/SPSCheck/Protocol/Personnel/Phone",
          order=2,
          prefix="  \\renewcommand{\\LeadPhone}{",
          suffix="  }\n"),
# --------- END: Second section Protocol Information ---------
# --------- START: Third section Protocol Information ---------
    # XProc(prefix=STATUS_SITES_TAB),
    XProc(element="ParticipatingSite",
          order=2,
          textOut=0),
    XProc(element="Site",
          order=2,
          suffix="& "),
    XProc(element="PI",
          order=2,
          suffix="& "),
    XProc(element="/SPSCheck/Protocol/ParticipatingSite/Phone",
          order=2,
          postProcs=((yesno,("Phone","Recruiting",)),)),
    # XProc(prefix=END_TABLE),
    XProc(prefix="  \\end{enumerate}"),
    )


DocumentStatusCheckCCOPBody = (
# --------- START: First section Contact Information ---------
    XProc(prefix=STATUSPROTOCOLDEF),
    XProc(element="PUP",
          textOut=0),
    XProc(element="/SPSCheck/PUP/Name",
          textOut=1,
          prefix="  \\newcommand{\PUP}{",
          suffix="}\n"),
    XProc(element="Title",
          order=2,
          prefix="  \\newcommand{\PUPTitle}{",
	      suffix="}\n"),
    XProc(element="Org",
          prefix="  \\newcommand{\PUPOrg}{",
          suffix="}\n"),
    XProc(element="/SPSCheck/PUP/Phone",
          order=3,
          prefix="  \\newcommand{\PUPPhone}{",
          suffix="}\n"),
    XProc(element="/SPSCheck/PUP/Street",
          textOut=0,
          order=3,
          preProcs=( (street, ()), )),
    XProc(element="/SPSCheck/PUP/Phone",
          order=3,
          prefix="  \\newcommand{\PUPPhone}{",
          suffix="}\n"),
    XProc(prefix=STATUSPUPADDRESS),
    XProc(prefix=STATUSDEFCCOP,
          suffix="  \\begin{enumerate}\n"),
# --------- END: First section Contact Information ---------
# --------- START: Second section Protocol Information ---------
    XProc(element="Protocol",
          textOut=0,
          suffix=END_TABLE),
    XProc(element="ProtocolTitle",
          order=2,
          prefix="  \\renewcommand{\\ProtocolTitle}{",
          suffix="  }\n "),
    XProc(element="CurrentStatus",
          order=2,
          prefix="  \\renewcommand{\\CurrentStatus}{",
          suffix="  }\n"),
    XProc(element="ID",
          order=2,
          prefix="  \\renewcommand{\\ProtocolID}{",
          suffix="  }\n  "),
    XProc(element="LeadOrg",
          order=2,
          prefix="  \\renewcommand{\\LeadOrg}{",
          suffix="  }\n"),
    # Need to start the table header as a suffix of the Personnel field
    # in order to create the table for each protocol record.
    XProc(element="Personnel",
          order=2,
          textOut=0,
          suffix=STATUSPROTINFO + STATUSCHAIRINFO + STATUS_TAB_CCOPINTRO + STATUS_CCOPMAIN_TAB),
    XProc(element="/SPSCheck/Protocol/Personnel/Name",
          order=2,
          prefix="  \\renewcommand{\\LeadPerson}{",
          suffix="  }\n"),
    XProc(element="/SPSCheck/Protocol/Personnel/Role",
          order=2,
          prefix="  \\renewcommand{\\LeadRole}{",
          suffix="  }\n"),
    XProc(element="/SPSCheck/Protocol/Personnel/Street",
          textOut=0,
          order=2,
          preProcs=( (street, ()), )),
    XProc(element="/SPSCheck/Protocol/Personnel/Phone",
          order=2,
          prefix="  \\renewcommand{\\LeadPhone}{",
          suffix="  }\n"),
# --------- END: Second section Protocol Information ---------
# --------- START: Third section Protocol Information ---------
    # XProc(prefix=STATUS_SITES_TAB),
    XProc(element="ParticipatingSite",
          order=2,
          textOut=0),
    XProc(element="Site",
          order=2,
          suffix="& "),
    XProc(element="PI",
          order=2,
          suffix="& "),
    XProc(element="/SPSCheck/Protocol/ParticipatingSite/Phone",
          order=2,
          postProcs=((yesno,("Phone","Recruiting",)),)),
    # XProc(prefix=END_TABLE),
    XProc(prefix="  \\end{enumerate}"),
    )


DocumentTestBody =(
    XProc(prefix=FONT),
    )

# ###########################################################
# Creating the different types of Headers for each mailer
# ###########################################################

DocumentSummaryHeader =(
    XProc(prefix=LATEXHEADER),
    XProc(prefix=DRAFT),
    XProc(prefix=FONT),
    XProc(prefix=TOCHEADER),
    XProc(prefix=QUOTES),
    XProc(prefix=CITATION),
    XProc(element="SummaryTitle",
          prefix=r"  \newcommand{\SummaryTitle}{",
	  suffix="}"),
    XProc(prefix=SUMMARY_HDRTEXT),
    XProc(prefix=FANCYHDR),
    XProc(prefix=ENDSUMMARYPREAMBLE)
    )

DocumentOrgHeader =(
    XProc(prefix=LATEXHEADER),
    XProc(prefix=DRAFT),
    XProc(prefix=FONT),
    XProc(prefix=STYLES),
    XProc(prefix=ENTRYLIST),
    XProc(prefix=QUOTES),
    XProc(prefix=ORG_HDRTEXT),
    XProc(prefix=FANCYHDR),
    XProc(prefix=TEXT_BOX),
    XProc(prefix=PHONE_RULER),
    XProc(prefix=ORG_DEFS),
    XProc(prefix=ORG_TITLE),
    XProc(prefix=ENDPREAMBLE),
    )

DocumentPersonHeader =(
    XProc(prefix=LATEXHEADER),
    XProc(prefix=DRAFT),
    XProc(prefix=FONT),
    XProc(prefix=STYLES),
    XProc(prefix=ENTRYLIST),
    XProc(prefix=QUOTES),
    XProc(prefix=PERSON_HDRTEXT),
    XProc(prefix=FANCYHDR),
    XProc(prefix=TEXT_BOX),
    XProc(prefix=PHONE_RULER),
    XProc(prefix=PERSON_DEFS),
    XProc(prefix=PERSON_TITLE),
    XProc(prefix=ENDPREAMBLE)
    )

DocumentStatusCheckHeader =(
    XProc(prefix=LATEXHEADER),
    XProc(prefix=DRAFT),
    XProc(prefix=FONT),
    XProc(prefix=STYLES),
    XProc(prefix=ENTRYBFLIST),
    XProc(prefix=QUOTES),
    XProc(prefix=STATPART_HDRTEXT),
    XProc(prefix=FANCYHDR),
    XProc(prefix=TEXT_BOX),
    XProc(prefix=PHONE_RULER),
    XProc(prefix=STATPART_TITLE),
    XProc(prefix=ENDPREAMBLE)
    )


DocumentProtocolHeader =(
    XProc(prefix=LATEXHEADER),
    XProc(prefix=DRAFT),
    XProc(prefix=FONT),
    XProc(prefix=STYLES),
    XProc(prefix=ENTRYBFLIST),
    XProc(prefix=QUOTES),
    XProc(prefix=PROTOCOL_HDRTEXT),
    XProc(prefix=FANCYHDR),
    XProc(prefix=TEXT_BOX),
    XProc(prefix=PHONE_RULER),
    XProc(prefix=PROTOCOL_DEFS),
    XProc(prefix=ENDPROTPREAMBLE)
    )


DocumentTestHeader =(
    XProc(prefix=LATEXHEADER),
    XProc(prefix=DRAFT),
    XProc(prefix=FONT),
    XProc(prefix=STYLES),
    XProc(prefix=ENTRYBFLIST),
    XProc(prefix=QUOTES),
    XProc(prefix=FANCYHDR),
    XProc(prefix=ENDPREAMBLE)
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


PROTOCOL_APPROVAL=r"""
  %% PROTOCOL_APPROVAL %%
  %% -------- %%
    \subsection*{Approval}
    \protapproval
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
DocumentSummaryFooter =(
    XProc(prefix=DOCFTR),
    )

DocumentOrgFooter =(
    XProc(prefix=APPROVAL),
    XProc(prefix=DOCFTR),
    )

DocumentPersonFooter =(
    XProc(prefix=APPROVAL),
    XProc(prefix=DOCFTR),
    )

DocumentStatusCheckFooter =(
    XProc(prefix=DOCFTR),
    )

DocumentProtocolFooter =(
    XProc(prefix=APPROVAL),
    XProc(prefix=PROTOCOL_APPROVAL),
    XProc(prefix=DOCFTR),
    )

DocumentTestFooter =(
    XProc(prefix=DOCFTR),
    )


# Putting the three main sections of document together
# Header + Body + Footer
# ----------------------------------------------------
SummaryInstructions = \
  DocumentSummaryHeader   + \
  DocumentSummaryBody     + \
  DocumentSummaryFooter

OrgInstructions = \
  DocumentOrgHeader + \
  DocumentOrgBody   + \
  DocumentOrgFooter

# ADDRESS              +
PersonInstructions = \
  DocumentPersonHeader + \
  DocumentPersonBody   + \
  DocumentPersonFooter

StatusCheckInstructions = \
  DocumentStatusCheckHeader + \
  DocumentStatusCheckBody   + \
  DocumentStatusCheckFooter

StatusCheckCCOPInstructions = \
  DocumentStatusCheckHeader + \
  DocumentStatusCheckCCOPBody   + \
  DocumentStatusCheckFooter

ProtocolInstructions = \
  DocumentProtocolHeader  + \
  DocumentProtocolBody    + \
  DocumentProtocolFooter

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
    ("Summary",          ""):SummaryInstructions,\
    ("Summary",      "initial"):SummaryInstructions,\
    ("Organization",     ""):OrgInstructions,\
    ("Person",           ""):PersonInstructions,\
    ("Protocol",         ""):ProtocolInstructions,\
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

