#----------------------------------------------------------------------
#
# $Id: cdrlatextables.py,v 1.3 2003-01-06 21:01:29 bkline Exp $
#
# Module for generating LaTeX for tables in CDR documents.
#
# $Log: not supported by cvs2svn $
# Revision 1.2  2002/11/07 21:19:44  bkline
# Better multirow cell support.
#
# Revision 1.1  2002/09/15 15:53:37  bkline
# Module for generating LaTeX for tables.
#
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
    def __init__(self, cols, framing, colSep, rowSep, outerTab):
        self.cols    = cols
        self.framing = framing
        self.colSep  = colSep
        self.rowSep  = rowSep
        self.where   = IN_NOTHING
        self.tail    = "}"
        self.curRow  = None
        self.rowBuf  = ""
        self.head    = []
        self.body    = []
        self.foot    = []
        self.outer   = outerTab

    # Recursively assemble the LaTeX for a block of cells.
    #def assembleRows(self, startRow, startCol, numRows, numCols, outer = 0):
    def assembleRows(self, block, outer = 0, endOfParent = 0):
        #sys.stderr.write("outer=%d endOfParent=%d\n" % (outer, endOfParent))
        if not block: return ""
        output      = ""
        curRow      = 0
        lastRow     = 0
        rowsLeft    = len(block)
        while rowsLeft > 0:
            row = block[curRow]
            #sys.stderr.write("curRow=%d rowsLeft = %d numCols=%d\n" % 
            #       (curRow, rowsLeft, len(row)))
            if not row:
                raise StandardError(
                        "Internal Error: empty row in assembleRows()")
            maxCellHeight = 1
            minCellHeight = sys.maxint
            for cell in row:
                #sys.stderr.write("cell.numRows=%d\n" % cell.numRows)
                if maxCellHeight < cell.numRows:
                    maxCellHeight = cell.numRows
                if minCellHeight > cell.numRows:
                    minCellHeight = cell.numRows
            if maxCellHeight > rowsLeft:
                raise StandardError(
                        "Row ranges for spanning cells cannot overlap")
            if maxCellHeight == rowsLeft:
                lastRow = 1
            if minCellHeight == maxCellHeight:
                latex, allHline = self.setEvenRow(row, 
                        lastRow and endOfParent and 1 or 0)
                output += latex + "\\setcounter{qC}{0}\\tabularnewline\n"

                if outer:

                    # We add an \hline here if all of the cells had a frame
                    # line beneath in order to have the line repeated at the
                    # beginning of the next row if the table is split for a
                    # new page.  LaTeX does the right thing if no page break
                    # occurs; that is, the extra \hline does not cause a
                    # doubly-thick line to appear.
                    #sys.stderr.write("lastRow=%d allHline=%d\n" % (lastRow, 
                    #                                               allHline))
                    if allHline and (not lastRow or not endOfParent):
                        output += "\\hline\n"
            else:
                rows = block[curRow:curRow + maxCellHeight]
                output += self.setMixedRow(rows, lastRow)
                output += "\\setcounter{qC}{0}\\tabularnewline\n"
                if not lastRow or not endOfParent:
                    output += "\\hline\n"
            rowsLeft -= maxCellHeight
            curRow   += maxCellHeight
        return output

    def setMixedRow(self, rows, lastRow):
        output      = r"\begin{tabular}[t]{"
        content     = ""
        ampersand   = ""
        leftSep     = ""
        hline       = ""
        topRow      = rows[0]
        numCells    = len(topRow)
        i           = 0
        #sys.stderr.write("setMixedRow: %d rows\n" % len(topRow))
        while i < numCells:
            cell = topRow[i]
            if cell.numRows == len(rows):
                rightSep = ""
                # XXX Try to use this to prevent unwanted horizontal bars,
                #     instead of automatically adding the bar in the 
                #     assembleRows() method.
                #if cell.rowSep and not lastRow:
                #   #hline = "  \\tabularnewline \\hline\n"
                if cell.colSep:
                    if i < numCells - 1:
                        rightSep = "|"
                else:
                    leftSep = ""
                output += "%s%sp{%fin}%s" % (leftSep,
                                             cell.getAlignmentMacro(),
                                             cell.spanWidth,
                                             rightSep)
                leftSep = ""
                content += "%s%s" % (ampersand, cell.getContent())
                i       += 1
            else:
                # Assemble a new sub-block and process it recursively.
                # The lastCol variable is really a sentinal, marking
                # one past the column number we want.
                newRow   = [cell]
                newBlock = [newRow]
                firstCol = cell.colPos
                lastCol  = firstCol + cell.numCols
                while i < numCells:
                    i += 1
                    if i >= numCells or topRow[i].numRows == len(rows):
                        break
                    newRow.append(topRow[i])
                    lastCol += topRow[i].numCols
                for row in rows[1:]:
                    newRow = []
                    for cell in row:
                        if cell.colPos >= firstCol and cell.colPos < lastCol:
                            newRow.append(cell)
                    if newRow:
                        newBlock.append(newRow)
                
                assembledRows = self.assembleRows(newBlock, endOfParent = 
                        i >= numCells and 1 or 0)
                output += "@{}l@{}"
                content += "%s\\begin{tabular}[t]{@{}l@{}}%s"\
                           "\\end{tabular}" % (ampersand, assembledRows)
                leftSep = "|"
            ampersand = " & "
        return output + "}\n" + content + "\n" + hline + "\\end{tabular}\n"

    def setEvenRow(self, row, skipBottomFrame):
        output      = r"\begin{tabular}[t]{"
        content     = ""
        clines      = ""
        ampersand   = ""
        colNum      = 1
        allHline    = not skipBottomFrame and 1 or 0
        for cell in row:
            sep = ""
            if colNum < len(row) and cell.colSep:
                sep = "|"
            output += "%sp{%fin}%s" % (cell.getAlignmentMacro(),
                                       cell.spanWidth, sep)
            content += "%s%s" % (ampersand, cell.getContent())
            ampersand = " & "
            if not skipBottomFrame and cell.rowSep:
                if not clines:
                    clines = "\\setcounter{qC}{0}\\tabularnewline"
                clines += "\\cline{%d-%d}" % (colNum, colNum)
            else:
                allHline = 0
            colNum += 1
        return (output + "}\n" + content + "\n" + clines + "\\end{tabular}\n",
                allHline)

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
    def toString(self):
        return "Column(name=%s num=%s width=%s colSep=%s rowSep=%s "\
               "moreRows=%s colSpan=%s spanWidth=%s)" % (
                   self.name, str(self.num), str(self.width), str(self.colSep),
                   str(self.rowSep), str(self.moreRows), str(self.colSpan),
                   str(self.spanWidth))

#----------------------------------------------------------------------
# Object used for calculating actual column width.
#----------------------------------------------------------------------
class WidthSpec:
    def __init__(self, type, amount):
        self.type   = type
        self.amount = amount

#----------------------------------------------------------------------
# Object representing an output cell.
#
# Attributes:
#   group       reference to table group object we're in.
#   content     LaTeX content of cell (set later).
#   colPos      which column does this cell start in?
#   colSep      1: separate cell from right neighbor; 0: don't
#   rowSep      2: separate cell from lower neighbor; 0: don't
#   align       "Center"; "Right"; "Left"; "Justify"; or ""
#   numRows     how many rows does this cell span?
#   numCols     how many columns does this cell span?
#   spanWidth   how wide is the cell physically?
#   where       IN_THEAD, IN_TFOOT, or IN_TBODY
#----------------------------------------------------------------------
class Cell:
    def getContent(self):
        if self.where == IN_THEAD: return "{\\bf %s }" % self.content
        elif self.where == IN_TFOOT: return "{\\it %s }" % self.content
        elif self.where == IN_TBODY: return " %s " % self.content
    def __init__(self, group, pp):
        self.group      = group
        self.content    = ''
        self.where      = group.where

        i = group.currentColumn
        if i >= len(group.cols):
            raise StandardError("Too many table cells, Herr Mozart!")
        col = group.cols[i]

        # Skip past any columns spanning additional rows.
        #sys.stderr.write("i=%d len(group.cols)=%d col.moreRows=%d\n" %
        #       (i, len(group.cols), col.moreRows))
        while i < len(group.cols) and col.moreRows > 0:
            col.moreRows -= 1
            i += col.colSpan
            #sys.stderr.write("i is now %d\n" % i)
            if i >= len(group.cols):
                raise StandardError("Too many table cells, Herr Mozart!")
            col = group.cols[i]
        self.colPos     = i

        # Pull out the attributes for this cell.
        cellNode = pp.getCurNode()
        moreRows = cellNode.getAttribute("MoreRows")
        nameSt   = cellNode.getAttribute("NameSt")
        nameEnd  = cellNode.getAttribute("NameEnd")
        colSep   = cellNode.getAttribute("ColSep")
        rowSep   = cellNode.getAttribute("RowSep")
        align    = cellNode.getAttribute("Align")
        try: self.colSep = int(colSep)
        except: self.colSep = group.colSep
        try: self.rowSep = int(rowSep)
        except: self.rowSep = group.rowSep
        self.align = align

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
        self.numRows = col.moreRows + 1
            
        # See if we are spanning multiple columns with this cell.
        col.colSpan   = 1
        self.spanWidth = col.width
        if nameSt and not nameEnd:
            raise StandardError(
                    "NameSt attribute must be accompanied by NameEnd")
        if nameEnd and not nameSt:
            raise StandardError(
                    "NameEnd attribute must be accompanied by NameSt")
        if nameSt:
            if nameSt != col.name:
                raise StandardError(
                    "NameSt (%s) does not match name of current column (%s)" % 
                    (nameSt, col.name))
            spanEnd  = -1
            for j in range(i, len(group.cols)):
                if j > i:
                    self.spanWidth += group.cols[j].width
                if nameEnd == group.cols[j].name:
                    spanEnd = j
                    break
            if spanEnd == -1:
                raise StandardError("No column with name %s follows %s" % 
                                   (nameEnd, nameSt))
            col.colSpan = spanEnd + 1 - i
        else:
            spanEnd = i
        self.numCols = col.colSpan
        if self.numCols > 1:
            self.spanWidth += (RULE_WIDTH + TAB_COL_SEP * 2) \
                            * (self.numCols - 1)

        # Move to the next position on the row.
        group.currentColumn = spanEnd + 1

    def getAlignmentMacro(self):
        if self.align == "Center":
            return ">{\\centering}"
        elif self.align == "Right":
            return ">{\\raggedleft}"
        elif self.align == "Left":
            return ">{\\raggedright}"
        elif self.align == "Justify":
            return ""
        elif self.align == "Char":
            raise StandardError("No current support for Char alignment")
        elif self.align:
            raise StandardError("Invalid alignment request: %s" % self.align)
        elif self.where == IN_THEAD:
            return ">{\\centering}"
        else:
            return ">{\\raggedright}"

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
                cols.append(Column("_col%d" % (i + 1), i + 1, "1*",
                                   colSep, rowSep))
    nCols = len(cols)
    #sys.stderr.write("nCols=%d\n" % nCols)

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
                    amount /= 72.0
                elif widthType == "pc":
                    widthType = "in"
                    amount /= 6.0
                elif widthType == "cm":
                    widthType = "in"
                    amount /= 2.54
                elif widthType == "mm":
                    widthType = "in"
                    amount /= 25.4
                elif widthType != "*":
                    raise StandardError("Illegal ColWidth: %s" % col.width)
            except:
                raise StandardError("Illegal ColWidth: %s" % col.width)
        else:
            amount = 1
            widthType = "*"
        widthSpecs.append(WidthSpec(widthType, amount))
        #sys.stderr.write("widthType: %s; amount: %f\n" % (widthType, amount))

    # Determine how much space is used by the explicitly specified widths.
    # During this pass we also total up the proportional units.
    usableSpace = TEXT_WIDTH - (nCols * 2 * TAB_COL_SEP + 
                               (nCols + 1) * RULE_WIDTH)
    #sys.stderr.write("usableSpace = %f; nCols=%d\n" % (usableSpace, nCols))
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
    if len(tableStack) > 1 or len(table.groupStack) > 0:
        outer     = 0
        tableType = "tabular"
        sideFrame = ""
        hline     = ""
    else:
        outer     = 1
        tableType = "longtable"
        sideFrame = framing.sides and "|" or ""
        hline     = framing.top and "  \\hline\n" or ""
    pp.setOutput("""\
  {\\small  
  \\setlength{\\arraycolsep}{.05in}
  \\setlength{\\tabcolsep}{.05in}
  \\setlength{\\arrayrulewidth}{.015in}
  \\begin{%s}[t]{%s@{}l@{}%s}%s
""" % (tableType, sideFrame, sideFrame, hline))

    #for col in cols:
    #   sys.stderr.write("%s\n" % col.toString())

    # Push this group onto the stack.
    table.groupStack.append(Group(cols, framing, colSep, rowSep, outer))

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
    headEnds = 1
    bodyEnds = 1
    footEnds = 1
    #sys.stderr.write("len(group.head)=%d\n" % len(group.head))
    #sys.stderr.write("len(group.body)=%d\n" % len(group.body))
    #sys.stderr.write("len(group.foot)=%d\n" % len(group.foot))
    if group.body: 
        headEnds = 0
    if group.foot:
        headEnds = 0
        bodyEnds = 0
    if not group.outer:
        hline    = ""
        tabEnd   = "  \\end{tabular}}\n"
        vspace   = ""
        headEnds = bodyEnds = footEnds = 0
    else:
        hline    = group.framing.bottom and "\\hline\n" or ""
        tabEnd   = "  \\end{longtable}}\n"
        vspace   = "  \\vspace{6pt}\n"
    #sys.stderr.write("headEnds=%d bodyEnds=%d footEnds=%d\n" % (headEnds,
    #                                                            bodyEnds,
    #                                                            footEnds))
    body = group.assembleRows(group.head, group.outer, headEnds) + \
           group.assembleRows(group.body, group.outer, bodyEnds) + \
           group.assembleRows(group.foot, group.outer, footEnds)

    pp.setOutput(body + "\n" + hline + tabEnd + vspace)

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
    group.currentCellRow = []
    #sys.stderr.write("where? %d\n" % group.where)
    #sys.stderr.write("len(group.head)=%d\n" % len(group.head))
    #sys.stderr.write("len(group.body)=%d\n" % len(group.body))
    #sys.stderr.write("len(group.foot)=%d\n" % len(group.foot))
    if   group.where == IN_THEAD: group.head.append(group.currentCellRow)
    elif group.where == IN_TBODY: group.body.append(group.currentCellRow)
    elif group.where == IN_TFOOT: group.foot.append(group.currentCellRow)
    else:
        raise StandardError(
            "openRow(): group doesn't know what section it's in")
    return

    # XXX
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

    # Finish off multi-row leftovers
    i = group.currentColumn
    while i < len(group.cols):
        col = group.cols[i]
        if col.moreRows > 0:
            col.moreRows -= 1
        i += col.colSpan

    # XXX
    group.currentCellRow = None
    return

    row = group.row
    if not row:
        raise StandardError("Internal error: no current row found")

    # Do we have any pending cells (that is, cells which span multiple
    # rows, for which we haven't yet seen all the row data yet)?
    # If so, just keep going until we get all the row data we need.
    pendingRows = len(group.block)
    for cell in group.block[0]:
        if cell.numRows > pendingRows:
            return

    # We have all the row data we need.  Create a composite row.
    group.assembleRows(0, 0, len(group.block), len(group.cols))
    return

    # XXX
    # Finish off multi-row leftovers
    output = ""
    i = group.currentColumn
    leftMark = group.framing.sides and "|" or ""
    while i < len(group.cols):
        col = group.cols[i]
        if col.moreRows > 0:
            col.moreRows -= 1
            if i + col.colSpan >= len(group.cols):
                rightMark = group.framing.sides and "|" or ""
            else:
                rightMark = col.colSep and "|" or ""
            output += " & \\multicolumn{%d}{%sp{%fin}%s}{}\n" % \
                  (col.colSpan, leftMark, col.spanWidth, rightMark)
        i += col.colSpan
        leftMark = ""
    pp.setOutput(output + "  \\\\\n")

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
    group.currentCellRow.append(Cell(group, pp))
    return

    # XXX
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
    if not group.currentCellRow:
        raise StandardError("Internal error: no open cell found")
    group.currentCellRow[-1].content = pp.procNode.releaseOutput().strip()
    #sys.stderr.write("CONTENT: %s\n" % group.currentCellRow[-1].content)
    #pp.setOutput("%s\n" % group.tail)
