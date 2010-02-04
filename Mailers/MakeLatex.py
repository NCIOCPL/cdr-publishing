#----------------------------------------------------------------------
#
# $Id$
#
# Create Summary mailer.
#
#----------------------------------------------------------------------
import sys, xml.dom.minidom, re, time

#----------------------------------------------------------------------
# Global variables.
#----------------------------------------------------------------------
footnotes  = []
funnyChars = re.compile(u"([\"%<>_])")
sectNames  = [u'section',u'subsection',u'subsubsection',
              u'paragraph',u'subparagraph']

def cleanup(match): 
    char = match.group(0)
    if char == u'%': return u"$\\%$"
    if char == u'"': return u"\\tQ{}"
    if char == u'_': return u"\\_"
    return u"$" + char + u"$"

def cleanupText(s):
    return re.sub(funnyChars, cleanup, s)

#----------------------------------------------------------------------
# Extract the text content of a DOM element.
#----------------------------------------------------------------------
def getTextContent(node):
    text = u''
    for n in node.childNodes:
        if n.nodeType == xml.dom.minidom.Node.TEXT_NODE:
            text = text + n.nodeValue
    return cleanupText(text)

# XXX Add footnote handling to titles.
def handleFootnote(footnote):
    text = getTextContent(footnote)
    footnotes.append(text)

def flushFootnotes():
    global footnotes
    if footnotes:
        n = len(footnotes)
        sys.stdout.write("\\footnote{%s}" % footnotes[0].encode('latin-1'))
        if n > 1:
            sys.stdout.write("%s" % (n == 2 and "$^,$" or "\\raisebox{.8ex}{-}"))
            if n > 2:
                for fn in footnotes[1:-1]:
                    sys.stdout.write("\\addtocounter{footnote}{1}")
                    sys.stdout.write("\\footnotetext{%s}" % 
                                     fn.encode('latin-1'))
            sys.stdout.write("\\footnote{%s}" % 
                                footnotes[-1].encode('latin-1'))
        footnotes = []
            
def handleListItems(list):
    for node in list.childNodes:
        if node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
            if node.nodeName == "ListItem":
                #print r"\item ",
                print " ",
                handleMarkedUpText(node)

def handleOrderedList(list):
    #print r"\begin{enumerate}"
    handleListItems(list)
    #print r"\end{enumerate}"
    print ""

def handleItemizedList(list):
    #print r"\begin{itemize}"
    handleListItems(list)
    #print r"\end{itemize}"
    print ""

def handleMarkedUpText(node):
    for node in node.childNodes:
        if node.nodeType == xml.dom.minidom.Node.TEXT_NODE:
            text = cleanupText(node.nodeValue).encode('latin-1')
            if text: 
                flushFootnotes()
                sys.stdout.write(text)
        elif node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
            if node.nodeName == "Footnote":
                handleFootnote(node)
            else:
                flushFootnotes()
                if node.nodeName == "ZLNK":
                    sys.stdout.write(getTextContent(node))
                elif node.nodeName == "OrderedList":
                    print ""
                    handleOrderedList(node)
                elif node.nodeName == "ItemizedList":
                    print ""
                    handleItemizedList(node)
    flushFootnotes()
                
def handlePara(para):
    print "\\setcounter{qC}{0}"
    handleMarkedUpText(para)
    print ""

def handleSection(section, level):
    title = getTextContent(section.getElementsByTagName(u"Title")[0])
    print """\
\\%s{%s}
""" % (sectNames[level], cleanupText(title).encode('latin-1'))
    for node in section.childNodes:
        if node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
            if node.nodeName == "Para":
                handlePara(node)
            elif node.nodeName == "OrderedList":
                handleOrderedList(node)
            elif node.nodeName == "ItemizedList":
                handleItemizedList(node)
            elif node.nodeName == "SummarySection":
                handleSection(node, level + 1)

docXml = sys.stdin.read()
docElem = xml.dom.minidom.parseString(docXml).documentElement
title   = getTextContent(docElem.getElementsByTagName("SummaryTitle")[0])
print """\
\\documentclass[letterpaper|11pt]{article}
\\usepackage{ifthen}
\\usepackage{fancyheadings}

\\newcounter{qC}
\\newcommand{\\tQ}{%%
  \\addtocounter{qC}{1}%%
  \\ifthenelse{\\isodd{\\value{qC}}}{``}{\'\'}%%
}

\\setlength{\\parskip}{1.2mm}
\\setlength{\\parindent}{4mm}
%%\\setlength{\\oddsidemargin}{12pt}
%%\\setlength{\\textwidth}{6in}
%%\\setlength{\\topmargin}{40pt}

\\pagestyle{fancy}
%%\\lhead{\\fancyplain{}{Summary Mailer}}
%%\\chead{CDR0000085163}
%%\\lfoot{%%s}
%%\\rfoot{Page \\thepage}

\\begin{document}
\\title{%s}
\\maketitle

%%\\begin{center}
%%{\\Large %s }
%%\\end{center}

%% \\raggedright
""" % (cleanupText(title).encode('latin-1'),
       cleanupText(title).encode('latin-1'))
#time.strftime("%d-%b-%Y", time.localtime()),
for node in docElem.childNodes:
    if node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
        if node.nodeName == "SummarySection":
            handleSection(node, 0)
print r"\end{document}"
