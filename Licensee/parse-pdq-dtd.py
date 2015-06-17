#!/usr/bin/python

import lxml.etree as etree
import sys

#----------------------------------------------------------------------
#
# $Id$
#
# Script to verify that modifications to strip out all elements not
# used by the currently active document types were done correctly,
# and to report which elements were dropped. It does this by comparing
# the original DTD with the modified version. The new version is
# assumed to have the name of the old version with ".new" appended.
# So pdq.dtd would be compared with pdq.dtd.new, and pdqCG.dtd with
# pdqCG.dtd.new. The default name for the old version is pdqCG.dtd,
# which can be overridden with the optional command line argument.
# Reporting is to standard output. Errors are written to standard
# error. The goal is to fix the edited version until there are no
# errors.
#
# Requires a more recent version of lxml than is installed on the
# CDR servers. I'm using version 3.4.2 on my Linux workstation.
#
# Usage:
#   ./parse-dtd.py > dropped-from-cg-dtd.txt
#   ./parse-dtd.py pdq.dtd > dropped-from-vendor-dtd.txt
#
#----------------------------------------------------------------------

DOCTYPES = set([
    "Country",
    "CTGovProtocol",
    "DrugInformationSummary",
    "GENETICSPROFESSIONAL",
    "GlossaryTerm",
    "Media",
    "Organization",
    "PoliticalSubUnit",
    "Protocol",
    "Summary",
    "Term"
])
DROP = set(["Protocol"])
KEEP = DOCTYPES - DROP

#----------------------------------------------------------------------
# Represents on Element in the DTD. One limitation of this script is
# that we're not tracking attributes. So if the modifications to the
# DTD left in attributes for dropped elements, the script would not
# detect that. That wouldn't be problematic, but a more serious problem
# would be if the editing of the script dropped or changed attributes
# for elements which are retained, that wouldn't be caught either.
# That's a much less likely problem, and I'm going to rely on a
# reasonable amount of care on the part of the developer editing the
# DTD to avoid it, rather than make this script more complicated.
# Feel free to add that enhancement if you've got nothing better to do.
#----------------------------------------------------------------------
class Element:
    elements = {}
    keep = set()
    drop = set()
    shown = set()
    def __init__(self, e):
        self.name = e.name
        self.children = []
        self.fetch_children(e.content)
        self.used_by = {}
        self.doc_types = set()
        self.parents_checked = set()
        self.drop = False
    def show_dropped_elements(self, indent=0):
        if self.name in Element.drop:
            print "%s%s" % ("  " * indent, self.name)
            Element.shown.add(self.name)
            for name in self.children:
                child = Element.elements[name]
                child.show_dropped_elements(indent + 1)
    def fetch_children(self, node):
        if node:
            self.fetch_children(node.left)
            if node.name:
                self.children.append(node.name)
            self.fetch_children(node.right)
    def show_children(self):
        for child in self.children:
            print " ", child
    def add_doc_type(self, doc_type):
        if doc_type not in self.doc_types:
            self.doc_types.add(doc_type)
            for name in self.children:
                Element.elements[name].add_doc_type(doc_type)

#----------------------------------------------------------------------
# Parse the original DTD and load the elements defined in it into
# the Element.elements dictionary of Element objects.
#----------------------------------------------------------------------
filename = len(sys.argv) > 1 and sys.argv[1] or "pdqCG.dtd"
dtd = etree.DTD(filename)
for e in dtd.iterelements():
    element = Element(e)
    if element.name in Element.elements:
        print >>sys.stderr, element.name, "HAS MULTIPLE DEFINITIONS"
    else:
        Element.elements[element.name] = element

#----------------------------------------------------------------------
# Walk through the elements, linking child elements with their parents.
#----------------------------------------------------------------------
for element in Element.elements.itervalues():
    for name in element.children:
        child = Element.elements.get(name)
        if not child:
            print >>sys.stderr, name, "DEFINITION NOT FOUND"
        else:
            child.used_by[element.name] = element

#----------------------------------------------------------------------
# Determine the document types in which each element is used.
#----------------------------------------------------------------------
for element in Element.elements.itervalues():
    if not element.used_by:
        element.add_doc_type(element.name)

#----------------------------------------------------------------------
# Find out which elements we should keep, which we need to drop.
#----------------------------------------------------------------------
for element in Element.elements.itervalues():
    if not element.doc_types & KEEP:
        Element.drop.add(element.name)
    else:
        Element.keep.add(element.name)

#----------------------------------------------------------------------
# Show the elements we're dropping in a hierarchically indented report.
#----------------------------------------------------------------------
for doc_type in sorted(DROP):
    Element.elements[doc_type].show_dropped_elements()
for name in sorted(Element.drop - Element.shown):
    print name

#----------------------------------------------------------------------
# Parse the new DTD and identify missing or unwanted elements.
#----------------------------------------------------------------------
dtd = etree.DTD(filename + ".new")
new = set([e.name for e in dtd.iterelements()])
for name in sorted(new):
    if name not in Element.keep:
        print >>sys.stderr, "NEED TO DROP %s" % name
for name in sorted(Element.keep):
    if name not in new:
        print >>sys.stderr, "MISSING %s" % name
