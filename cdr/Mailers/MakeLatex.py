#----------------------------------------------------------------------
#
# $Id: MakeLatex.py,v 1.1 2001-07-09 14:53:30 bkline Exp $
#
# Create Summary mailer.
#
# $Log: not supported by cvs2svn $
#
#----------------------------------------------------------------------
import sys, xml.dom.minidom, re

#----------------------------------------------------------------------
# Global variables.
#----------------------------------------------------------------------
funnyChars = re.compile("([\"%<>])")
sectNames  = ['section','subsection','subsubsection',
              'paragraph','subparagraph']
def addBackslash(match): 
    char = match.group(0)
    if char == '%': return "$\\%$"
    if char == '"': return "\\tQ "
    return "$" + char + "$"

def cleanupText(s):
    return re.sub(funnyChars, addBackslash, s)

#----------------------------------------------------------------------
# Extract the text content of a DOM element.
#----------------------------------------------------------------------
def getTextContent(node):
    text = ''
    for n in node.childNodes:
        if n.nodeType == xml.dom.minidom.Node.TEXT_NODE:
            text = text + n.nodeValue
    return cleanupText(text)

def handleFootnote(footnote):
    text = getTextContent(footnote)
    sys.stdout.write("\\footnote{%s}" % text)

def handleListItems(list):
    for node in list.childNodes:
        if node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
            if node.nodeName == "ListItem":
                print r"\item ",
                handleMarkedUpText(node)

def handleOrderedList(list):
    print r"\begin{enumerate}"
    handleListItems(list)
    print r"\end{enumerate}"
    print ""

def handleItemizedList(list):
    print r"\begin{itemize}"
    handleListItems(list)
    print r"\end{itemize}"
    print ""

def handleMarkedUpText(node):
    print "\\setcounter{qC}{0}"
    for node in node.childNodes:
        if node.nodeType == xml.dom.minidom.Node.TEXT_NODE:
            text = cleanupText(node.nodeValue)
            if text: sys.stdout.write(text)
        elif node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
            if node.nodeName == "Footnote":
                handleFootnote(node)
            elif node.nodeName == "ZLNK":
                sys.stdout.write(getTextContent(node))
            elif node.nodeName == "OrderedList":
                print ""
                handleOrderedList(node)
            elif node.nodeName == "ItemizedList":
                print ""
                handleItemizedList(node)
                
def handlePara(para):
    handleMarkedUpText(para)
    print ""

def handleSection(section, level):
    title = getTextContent(section.getElementsByTagName("Title")[0])
    print """\
\\%s{%s}
""" % (sectNames[level], cleanupText(title))
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
\\documentclass{article}
\\usepackage{ifthen}
\\newcounter{qC}
\\newcommand{\\tQ}{%%
  \\addtocounter{qC}{1}%%
  \\ifthenelse{\\isodd{\\value{qC}}}{``}{\'\'}%%
}
\\begin{document}
\\begin{center}
{\\Large %s }
\\end{center}
\\raggedright
""" % cleanupText(title)
for node in docElem.childNodes:
    if node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
        if node.nodeName == "SummarySection":
            handleSection(node, 0)
print r"\end{document}"
