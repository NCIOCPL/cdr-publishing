#----------------------------------------------------------------------
#
# $Id: cdrlatextables.py,v 1.1 2002-09-15 15:53:37 bkline Exp $
#
# Module for generating LaTeX for tables in CDR documents.
#
# $Log: not supported by cvs2svn $
#----------------------------------------------------------------------
import re, sys

TEXT_WIDTH  = 5.5
TAB_COL_SEP = .05
RULE_WIDTH  = .015
MIN_WIDTH   = .1
IN_NOTHING  = 0
IN_TBODY    = 1
IN_THEAD    = 2
IN_TFOOT    = 3
WIDTH_EXPR  = re.compile(r"(\d*\.?\d*)([^\d.]+)")

tableStack = []

#----------------------------------------------------------------------
# Object representing current framing settings.
#----------------------------------------------------------------------
class Framing:
    def __init__(self, frameVal):
        self.top    = 1
        self.bottom = 1
        self.sides  = 1
        if frameVal == "Sides": self.top = self.bottom = 0
        elif frameVal == "Top": self.bottom = self.sides = 0
        elif frameVal == "Bottom": self.top = self.sides = 0
        elif frameVal == "TopBot": self.sides = 0

#----------------------------------------------------------------------
# Object representing setting for one table.
#----------------------------------------------------------------------
class Table:
    def __init__(self, framing, colSep, rowSep):
        self.framing    = framing
        self.colSep     = colSep
        self.rowSep     = rowSep
        self.groupStack = []

#----------------------------------------------------------------------
# Object representing setting for one table group.
#----------------------------------------------------------------------
class Group:
    def __init__(self, cols, framing, colSep, rowSep):
        self.cols    = cols
        self.framing = framing
        self.colSep  = colSep
        self.rowSep  = rowSep
        self.where   = IN_NOTHING
        self.tail    = "}"
        self.curRow  = None
        self.rowBuf  = ""

#----------------------------------------------------------------------
# Object representing setting current row.
#----------------------------------------------------------------------
class Row:
    def __init__(self, rowSep):
        self.rowSep = rowSep

#----------------------------------------------------------------------
# Object representing setting for one table column definition.
#----------------------------------------------------------------------
class Column:
    def __init__(self, name, num, width, colSep, rowSep):
        self.name      = name
        self.num       = num
        self.width     = width
        self.colSep    = colSep
        self.rowSep    = rowSep
        self.moreRows  = 0
        self.colSpan   = 1
        self.spanWidth = width

#----------------------------------------------------------------------
# Object used for calculating actual column width.
#----------------------------------------------------------------------
class WidthSpec:
    def __init__(self, type, amount):
        self.type   = type
        self.amount = amount

#----------------------------------------------------------------------
# Start a table.
#----------------------------------------------------------------------
def openTable(pp):
    tableNode = pp.getCurNode()
    frame   = tableNode.getAttribute("Frame")
    colSep  = tableNode.getAttribute("ColSep")
    rowSep  = tableNode.getAttribute("RowSep")
    framing = Framing(frame)
    try: colSep = int(colSep)
    except: colSep = 1
    try: rowSep = int(rowSep)
    except: rowSep = 1
    tableStack.append(Table(Framing(frame), colSep, rowSep))

#----------------------------------------------------------------------
# Finish the current table.
#----------------------------------------------------------------------
def closeTable(pp):
    if not tableStack:
        raise StandardError("Internal error: empty table stack")
    tableStack.pop()
    pp.setOutput("\n")

#----------------------------------------------------------------------
# Start a table group.
#----------------------------------------------------------------------
def openGroup(pp):

    # Find the current table.
    if not tableStack:
        raise StandardError("Internal error: empty table stack")
    table = tableStack[-1]

    # Extract top-level attributes.
    tGroupNode = pp.getCurNode()
    nCols      = tGroupNode.getAttribute("Cols")
    frame      = tGroupNode.getAttribute("Frame")
    colSep     = tGroupNode.getAttribute("ColSep")
    rowSep     = tGroupNode.getAttribute("RowSep")
    child      = tGroupNode.firstChild
    if frame: framing    = Framing(frame)
    else: framing = table.framing
    try: colSep = int(colSep)
    except: colSep = table.colSep
    try: rowSep = int(rowSep)
    except: rowSep = table.rowSep

    # Parse the column specifications.
    cols = []
    while child:
        if child.nodeName == 'ColSpec': 
            name    = child.getAttribute("ColName")
            num     = child.getAttribute("ColNum")
            width   = child.getAttribute("ColWidth")
            try: num = int(num)
            except: num = len(cols)
            cols.append(Column(name, num, width, colSep, rowSep))
        child = child.nextSibling

    # Fill out any unspecified columns.
    if nCols:
        nCols = int(nCols)
        if nCols > len(cols):
            for i in range(len(cols), nCols):
                cols.append(Column("_col%d" % (i + 1), i + 1, "1*"))
    nCols = len(cols)

    # Parse the width specifications for each column.
    widthSpecs = []
    for col in cols:
        match = WIDTH_EXPR.match(col.width)
        if match and match.group(1):
            try:
                amount    = float(match.group(1))
                widthType = match.group(2)
                if amount <= 0:
                    raise StandardError("Illegal ColWidth: %s" % col.width)
                if widthType == "pt":
                    widthType = "in"
                    amount *= 72
                elif widthType == "pc":
                    widthType = "in"
                    amount *= 6
                elif widthType == "cm":
                    widthType = "in"
                    amount *= 2.54
                elif widthType == "mm":
                    widthType = "in"
                    amount *= 25.4
                elif widthType != "*":
                    raise StandardError("Illegal ColWidth: %s" % col.width)
            except:
                raise StandardError("Illegal ColWidth: %s" % col.width)
        else:
            amount = 1
            widthType = "*"
        widthSpecs.append(WidthSpec(widthType, amount))

    # Determine how much space is used by the explicitly specified widths.
    # During this pass we also total up the proportional units.
    usableSpace = TEXT_WIDTH - (nCols * 2 * TAB_COL_SEP + 
                               (nCols + 1) * RULE_WIDTH)
    propTotal = 0
    propCols  = 0
    for spec in widthSpecs:
        if spec.type == "*":
            propTotal += spec.amount
            propCols  += 1
        else:
            usableSpace -= spec.amount
    if usableSpace < MIN_WIDTH * propCols:
        raise StandardError("Total of explicit ColWidth too large")
    propUnit = usableSpace / propTotal

    # Divide up the remaining space proportionally as requested.
    for i in range(len(widthSpecs)):
        spec = widthSpecs[i]
        col  = cols[i]
        if spec.type == "*":
            spec.amount *= propUnit
            if spec.amount < MIN_WIDTH:
                raise("Column %d width too small: %s" % (i + 1, col.width))
        col.width = spec.amount

    # Tell the caller what to put in the output stream.    
    output = "  {\\small\n  \\begin{supertabular}[t]{|"
    for col in cols:
        output += "p{%fin}|" % col.width
    output += "}\n"
    if framing.top:
        output += "  \\hline\n"
    pp.setOutput(output)

    # Push this group onto the stack.
    table.groupStack.append(Group(cols, framing, colSep, rowSep))

#----------------------------------------------------------------------
# Finish a table group.
#----------------------------------------------------------------------
def closeGroup(pp):

    # Find the current table.
    if not tableStack:
        raise StandardError("Internal error: empty table stack")
    table = tableStack[-1]
    if not table.groupStack:
        raise StandardError("Internal error: empty Group stack")
    group = table.groupStack.pop()
    hline = group.framing.bottom and "  \\hline\n\n" or ""
    pp.setOutput(hline + "  \\end{supertabular}}\n  \\vspace{6pt}\n\n")

#----------------------------------------------------------------------
# Start the main body of the table.
#----------------------------------------------------------------------
def openBody(pp):

    # Find the current table.
    if not tableStack:
        raise StandardError("Internal error: empty table stack")
    table = tableStack[-1]
    if not table.groupStack:
        raise StandardError("Internal error: empty Group stack")
    group = table.groupStack[-1]
    group.where = IN_TBODY

#----------------------------------------------------------------------
# Start the table header.
#----------------------------------------------------------------------
def openHeader(pp):

    # Find the current table.
    if not tableStack:
        raise StandardError("Internal error: empty table stack")
    table = tableStack[-1]
    if not table.groupStack:
        raise StandardError("Internal error: empty Group stack")
    group = table.groupStack[-1]
    group.where = IN_THEAD

#----------------------------------------------------------------------
# Start the table footer.
#----------------------------------------------------------------------
def openFooter(pp):

    # Find the current table.
    if not tableStack:
        raise StandardError("Internal error: empty table stack")
    table = tableStack[-1]
    if not table.groupStack:
        raise StandardError("Internal error: empty Group stack")
    group = table.groupStack[-1]
    group.where = IN_TFOOT

#----------------------------------------------------------------------
# Finish a table body, header, or footer.
#----------------------------------------------------------------------
def closeSection(pp):

    # Find the current table.
    if not tableStack:
        raise StandardError("Internal error: empty table stack")
    table = tableStack[-1]
    if not table.groupStack:
        raise StandardError("Internal error: empty Group stack")
    group = table.groupStack[-1]
    group.where = IN_NOTHING

#----------------------------------------------------------------------
# Start a table row.
#----------------------------------------------------------------------
def openRow(pp):

    # Find the current table.
    if not tableStack:
        raise StandardError("Internal error: empty table stack")
    table = tableStack[-1]
    if not table.groupStack:
        raise StandardError("Internal error: empty Group stack")
    group = table.groupStack[-1]
    group.currentColumn = 0

    rowNode = pp.getCurNode()
    rowSep  = rowNode.getAttribute("RowSep")
    try: rowSep = int(rowSep)
    except: rowSep = group.rowSep
    group.row = Row(rowSep)
    if group.rowBuf:
        pp.setOutput(group.rowBuf)
        group.rowBuf = ""

#----------------------------------------------------------------------
# Finish up a table row.
#----------------------------------------------------------------------
def closeRow(pp):

    # Find the current table.
    if not tableStack:
        raise StandardError("Internal error: empty table stack")
    table = tableStack[-1]
    if not table.groupStack:
        raise StandardError("Internal error: empty Group stack")
    group = table.groupStack[-1]
    row = group.row
    if not row:
        raise StandardError("Internal error: no current row found")
    pp.setOutput("  \\\\\n")

    # Save the rest to be flushed later; replaced by frame at end of group.
    rowBuf = ""

    # Mark the first column that still needs to have a line underneath it.
    colStart = 0
    moreCols = 0
    for i in range(len(group.cols)):
        col = group.cols[i]

        # Any of the following causes the column *not* to get a gridline.
        if col.moreRows > 0 or moreCols or not col.rowSep:
            if colStart < i:
                rowBuf += "  \\cline{%d-%d}\n" % (colStart + 1, i)
            colStart = i + 1
            if moreCols:
                moreCols -= 1
            else:
                moreCols = col.colSpan - 1
    if colStart == 0:
        rowBuf += "  \\hline\n"
    elif colStart < len(group.cols):
        rowBuf += "  \\cline{%d-%d}\n" % (colStart + 1, len(group.cols))
    group.rowBuf = rowBuf + "\n"

#----------------------------------------------------------------------
# Start a table cell.
#----------------------------------------------------------------------
def openCell(pp):

    # Find the current table.
    if not tableStack:
        raise StandardError("Internal error: empty table stack")
    table = tableStack[-1]
    if not table.groupStack:
        raise StandardError("Internal error: empty Group stack")
    group = table.groupStack[-1]
    leftMark = group.framing.sides and "|" or ""
    output = "  "
    i = group.currentColumn
    if i >= len(group.cols):
        raise StandardError("Too many table cells, Herr Mozart!")
    col = group.cols[i]
    if i > 0:
        output += "& "
        leftMark = ""

    # Skip past any columns spanning additional rows.
    while i < len(group.cols) and col.moreRows > 0:
        col.moreRows -= 1
        if i + col.colSpan >= len(group.cols):
            rightMark = group.framing.sides and "|" or ""
        else:
            rightMark = col.colSep and "|" or ""
        output += "\\multicolumn{%d}{%sp{%fin}%s}{}\n  & " % \
                  (col.colSpan, leftMark, col.spanWidth, rightMark)
        i += col.colSpan
        if i >= len(group.cols):
            raise StandardError("Too many table cells, Herr Mozart!")
        col = group.cols[i]
        leftMark = ""

    # Pull out the attributes for this cell.
    cellNode = pp.getCurNode()
    moreRows = cellNode.getAttribute("MoreRows")
    nameSt   = cellNode.getAttribute("NameSt")
    nameEnd  = cellNode.getAttribute("NameEnd")
    colSep   = cellNode.getAttribute("ColSep")
    rowSep   = cellNode.getAttribute("RowSep")
    try: col.colSep = int(colSep)
    except: col.colSep = group.colSep
    try: col.rowSep = int(rowSep)
    except: col.rowSep = group.rowSep

    # See if we are spanning multiple rows with this cell.
    col.moreRows = 0
    if moreRows:
        try:
            moreRows = int(moreRows)
            if moreRows > 0:
                col.moreRows = moreRows
            if moreRows < 0:
                raise StandardError("Invalid value for MoreRows: %s" % 
                                    moreRows)
        except:
            raise StandardError("Invalid value for MoreRows: %s" % moreRows)
        
    # See if we are spanning multiple columns with this cell.
    col.colSpan   = 1
    col.spanWidth = col.width
    if nameSt and not nameEnd:
        raise StandardError("NameSt attribute must be accompanied by NameEnd")
    if nameEnd and not nameSt:
        raise StandardError("NameEnd attribute must be accompanied by NameSt")
    if nameSt:
        if nameSt != col.name:
            raise StandardError(
                "NameSt (%s) does not match name of current column (%s)" % 
                (nameSt, col.name))
        spanEnd  = -1
        for j in range(i, len(group.cols)):
            if j > i:
                col.spanWidth += group.cols[j].width
            if nameEnd == group.cols[j].name:
                spanEnd = j
                break
        if spanEnd == -1:
            raise StandardError("No column with name %s follows %s" % 
                               (nameEnd, nameSt))
        col.colSpan = spanEnd + 1 - i
    else:
        spanEnd = i

    # Create the output for the cell.
    if i + col.colSpan >= len(group.cols):
        rightMark = group.framing.sides and "|" or ""
    else:
        rightMark = col.colSep and "|" or ""
    if col.colSpan > 1:
        col.spanWidth += (RULE_WIDTH + TAB_COL_SEP * 2) * (col.colSpan - 1)
    output += "\\multicolumn{%d}{%sp{%fin}%s}{" % \
               (col.colSpan, leftMark, col.spanWidth, rightMark)
    group.tail = "}"
    if col.moreRows > 0:
        output += "\\multirow{%d}{%fin}{" % (col.moreRows + 1, col.spanWidth)
        group.tail = "}}"

    # Adjust the font if we're in the header or footer.
    if group.where == IN_THEAD:
        output += "\\bf "
    elif group.where == IN_TFOOT:
        output += "\\it "
    elif group.where != IN_TBODY:
        raise StandardError(
            "Entry must be contained within THead, TBody, or TFoot")

    # Adjust the horizontal alignment of the cell's contents.
    align = cellNode.getAttribute("Align")
    if align == "Center":
        output += "\\centering "
    elif align == "Right":
        output += "\\raggedleft "
    elif align == "Left":
        output += "\\raggedright "
    elif align == "Justify":
        pass
    elif align == "Char":
        raise StandardError("No current support for Char alignment")
    elif align:
        raise StandardError("Invalid alignment request: %s" % align)
    elif group.where == IN_THEAD:
        output += "\\centering "
    else:
        output += "\\raggedright "

    # Pump it out and move to the next position on the row.
    pp.setOutput(output)
    group.currentColumn = spanEnd + 1

#----------------------------------------------------------------------
# Finish up a table cell.
#----------------------------------------------------------------------
def closeCell(pp):

    # Find the current table.
    if not tableStack:
        raise StandardError("Internal error: empty table stack")
    table = tableStack[-1]
    if not table.groupStack:
        raise StandardError("Internal error: empty Group stack")
    group = table.groupStack[-1]
    pp.setOutput("%s\n" % group.tail)
