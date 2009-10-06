#----------------------------------------------------------------------
#
# $Id: cdrlatextables.py,v 1.8 2008/09/25 12:50:04 bkline Exp $
#
# Module for generating LaTeX for tables in CDR documents.
#
# $Log: cdrlatextables.py,v $
# Revision 1.8  2008/09/25 12:50:04  bkline
# Exception cleanup.
#
# Revision 1.7  2008/06/03 21:28:07  bkline
# Replaced StandardError with Exception objects.
#
# Revision 1.6  2003/12/16 20:31:11  bkline
# Added conditional debugging output.
#
# Revision 1.5  2003/07/02 21:22:53  bkline
# Added code to add running head for tables which span multiple pages.
#
# Revision 1.4  2003/05/19 18:41:57  bkline
# Modified handling of citations in table cells to allow line breaking
# after a comma in a series of citation numbers (request #735)
#
# Revision 1.3  2003/01/06 21:01:29  bkline
# Fixed column width conversion math.
#
# Revision 1.2  2002/11/07 21:19:44  bkline
# Better multirow cell support.
#
# Revision 1.1  2002/09/15 15:53:37  bkline
# Module for generating LaTeX for tables.
#
#----------------------------------------------------------------------
import re, sys, cdr

TEXT_WIDTH  = 5.5
TAB_COL_SEP = .05
RULE_WIDTH  = .015
MIN_WIDTH   = .1
IN_NOTHING  = 0
IN_TBODY    = 1
IN_THEAD    = 2
IN_TFOOT    = 3
WIDTH_EXPR  = re.compile(r"(\d*\.?\d*)([^\d.]+)")

TABLE_DEBUG = False
tableStack = []
tableCellDepth = 0

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
    def assembleRows(self, block, outer = False, endOfParent = False):
        if TABLE_DEBUG:
            sys.stderr.write(" ***** TOP OF assembleRows() *****\n")
            sys.stderr.write("outer=%s endOfParent=%s\n" % (outer,
                                                            endOfParent))
        if not block: return ""
        output      = ""
        curRow      = 0
        lastRow     = False
        rowsLeft    = len(block)
        while rowsLeft > 0:
            row = block[curRow]
            if TABLE_DEBUG:
                sys.stderr.write("TOP OF LOOP IN assembleRows(): ")
                sys.stderr.write("curRow=%d rowsLeft=%d numCols=%d\n" % 
                                 (curRow, rowsLeft, len(row)))
            if not row:
                raise cdr.Exception("Internal Error: "
                                    "empty row in assembleRows()")
            maxCellHeight = 1
            minCellHeight = sys.maxint
            for cell in row:
                if TABLE_DEBUG:
                    sys.stderr.write("cell.numRows=%d\n" % cell.numRows)
                if maxCellHeight < cell.numRows:
                    maxCellHeight = cell.numRows
                if minCellHeight > cell.numRows:
                    minCellHeight = cell.numRows
            if TABLE_DEBUG:
                sys.stderr.write("maxCellHeight: %s\n" % maxCellHeight)
                sys.stderr.write("rowsLeft: %s\n" % rowsLeft)
            if maxCellHeight > rowsLeft:
                if TABLE_DEBUG:
                    sys.stderr.write("cell content: %s\n" % cell.content)
                raise cdr.Exception("Row ranges for spanning cells "
                                    "cannot overlap")
            if maxCellHeight == rowsLeft:
                lastRow = True
            if minCellHeight == maxCellHeight:
                latex, allHline = self.setEvenRow(row, lastRow and endOfParent)
                output += latex + "\\setcounter{qC}{0}\\tabularnewline\n"

                if outer:

                    # We add an \hline here if all of the cells had a frame
                    # line beneath in order to have the line repeated at the
                    # beginning of the next row if the table is split for a
                    # new page.  LaTeX does the right thing if no page break
                    # occurs; that is, the extra \hline does not cause a
                    # doubly-thick line to appear.
                    if TABLE_DEBUG:
                        sys.stderr.write("lastRow=%s allHline=%d\n" %
                                         (lastRow, allHline))
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
        if TABLE_DEBUG:
            sys.stderr.write("setMixedRow: %d rows %d cols\n" % (len(rows),
                                                                  numCells))
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
                
                assembledRows = self.assembleRows(newBlock,
                                                  endOfParent = i >= numCells)
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
            raise cdr.Exception("Too many table cells, Herr Mozart!")
        col = group.cols[i]

        # Skip past any columns spanning additional rows.
        if TABLE_DEBUG:
            sys.stderr.write("i=%d len(group.cols)=%d col.moreRows=%d\n" %
                             (i, len(group.cols), col.moreRows))
        while i < len(group.cols) and col.moreRows > 0:
            col.moreRows -= 1
            i += col.colSpan
            if TABLE_DEBUG:
                sys.stderr.write("i is now %d\n" % i)
            if i >= len(group.cols):
                raise cdr.Exception("Too many table cells, Herr Mozart!")
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
                    raise cdr.Exception("Invalid value for MoreRows: %s" %
                                        moreRows)
            except:
                raise cdr.Exception("Invalid value for MoreRows: %s" % moreRows)
        self.numRows = col.moreRows + 1
            
        # See if we are spanning multiple columns with this cell.
        col.colSpan   = 1
        self.spanWidth = col.width
        if nameSt and not nameEnd:
            raise cdr.Exception("NameSt attribute must be accompanied by "
                                "NameEnd")
        if nameEnd and not nameSt:
            raise cdr.Exception("NameEnd attribute must be accompanied by "
                                "NameSt")
        if nameSt:
            if nameSt != col.name:
                raise cdr.Exception("NameSt (%s) does not match name "
                                "of current column (%s)" % (nameSt, col.name))
            spanEnd  = -1
            for j in range(i, len(group.cols)):
                if j > i:
                    self.spanWidth += group.cols[j].width
                if nameEnd == group.cols[j].name:
                    spanEnd = j
                    break
            if spanEnd == -1:
                raise cdr.Exception("No column with name %s follows %s" % 
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
            raise cdr.Exception("No current support for Char alignment")
        elif self.align:
            raise cdr.Exception("Invalid alignment request: %s" % self.align)
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
        raise cdr.Exception("Internal error: empty table stack")
    tableStack.pop()
    pp.setOutput("\n")

#----------------------------------------------------------------------
# Start a table group.
#----------------------------------------------------------------------
def openGroup(pp):

    # Find the current table.
    if not tableStack:
        raise cdr.Exception("Internal error: empty table stack")
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
    if TABLE_DEBUG:
        sys.stderr.write("nCols=%d\n" % nCols)

    # Parse the width specifications for each column.
    widthSpecs = []
    for col in cols:
        match = WIDTH_EXPR.match(col.width)
        if match and match.group(1):
            try:
                amount    = float(match.group(1))
                widthType = match.group(2)
                if amount <= 0:
                    raise cdr.Exception("Illegal ColWidth: %s" % col.width)
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
                    raise cdr.Exception("Illegal ColWidth: %s" % col.width)
            except:
                raise cdr.Exception("Illegal ColWidth: %s" % col.width)
        else:
            amount = 1
            widthType = "*"
        widthSpecs.append(WidthSpec(widthType, amount))
        if TABLE_DEBUG:
            sys.stderr.write("widthType: %s; amount: %f\n" % (widthType,
                                                              amount))

    # Determine how much space is used by the explicitly specified widths.
    # During this pass we also total up the proportional units.
    usableSpace = TEXT_WIDTH - (nCols * 2 * TAB_COL_SEP + 
                               (nCols + 1) * RULE_WIDTH)
    if TABLE_DEBUG:
        sys.stderr.write("usableSpace = %f; nCols=%d\n" % (usableSpace, nCols))
    propTotal = 0
    propCols  = 0
    for spec in widthSpecs:
        if spec.type == "*":
            propTotal += spec.amount
            propCols  += 1
        else:
            usableSpace -= spec.amount
    if usableSpace < MIN_WIDTH * propCols:
        raise cdr.Exception("Total of explicit ColWidth too large")
    propUnit = usableSpace / propTotal

    # Divide up the remaining space proportionally as requested.
    for i in range(len(widthSpecs)):
        spec = widthSpecs[i]
        col  = cols[i]
        if spec.type == "*":
            spec.amount *= propUnit
            if spec.amount < MIN_WIDTH:
                raise cdr.Exception("Column %d width too small: %s; "
                                    "inches: %s; proportional unit: %s; "
                                    "number of columns: %d; "
                                    "usable for proportional widths: %s; "
                                    "proportional total: %s; text width: %s" %
                                    (i + 1, col.width, spec.amount,
                                     propUnit, nCols, usableSpace, propTotal,
                                     TEXT_WIDTH))
        col.width = spec.amount

    # Tell the caller what to put in the output stream.
    if len(tableStack) > 1 or len(table.groupStack) > 0:
        outer     = False
        tableType = "tabular"
        sideFrame = ""
        hline     = ""
    else:
        outer     = True
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

    if TABLE_DEBUG:
        for col in cols:
            sys.stderr.write("%s\n" % col.toString())

    # Push this group onto the stack.
    table.groupStack.append(Group(cols, framing, colSep, rowSep, outer))

#----------------------------------------------------------------------
# Finish a table group.
#----------------------------------------------------------------------
def closeGroup(pp):

    # Find the current table.
    if not tableStack:
        raise cdr.Exception("Internal error: empty table stack")
    table = tableStack[-1]
    if not table.groupStack:
        raise cdr.Exception("Internal error: empty Group stack")
    group = table.groupStack.pop()
    headEnds = bodyEnds = footEnds = True
    if TABLE_DEBUG:
        stars = 70 * "*"
        label = "CLOSE GROUP"
        sys.stderr.write("\n%s\n*%39s%30s\n%s\n\n" % (stars, label, "*", stars))
        sys.stderr.write("len(group.head)=%d\n" % len(group.head))
        sys.stderr.write("len(group.body)=%d\n" % len(group.body))
        sys.stderr.write("len(group.foot)=%d\n" % len(group.foot))
    if group.body: 
        headEnds = False
    if group.foot:
        headEnds = False
        bodyEnds = False
    if not group.outer:
        hline    = ""
        tabEnd   = "  \\end{tabular}}\n"
        vspace   = ""
        headEnds = bodyEnds = footEnds = False
    else:
        hline    = group.framing.bottom and "\\hline\n" or ""
        tabEnd   = "  \\end{longtable}}\n"
        vspace   = "  \\vspace{6pt}\n"
    if TABLE_DEBUG:
        sys.stderr.write("headEnds=%s bodyEnds=%s footEnds=%s\n" % (headEnds,
                                                                    bodyEnds,
                                                                    footEnds))
    endHead = group.head and "  \\endhead\n" or ""       
    body = (group.assembleRows(group.head, group.outer, headEnds) + endHead +
            group.assembleRows(group.body, group.outer, bodyEnds) +
            group.assembleRows(group.foot, group.outer, footEnds))

    pp.setOutput(body + "\n" + hline + tabEnd + vspace)

#----------------------------------------------------------------------
# Start the main body of the table.
#----------------------------------------------------------------------
def openBody(pp):

    # Find the current table.
    if not tableStack:
        raise cdr.Exception("Internal error: empty table stack")
    table = tableStack[-1]
    if not table.groupStack:
        raise cdr.Exception("Internal error: empty Group stack")
    group = table.groupStack[-1]
    group.where = IN_TBODY

#----------------------------------------------------------------------
# Start the table header.
#----------------------------------------------------------------------
def openHeader(pp):

    # Find the current table.
    if not tableStack:
        raise cdr.Exception("Internal error: empty table stack")
    table = tableStack[-1]
    if not table.groupStack:
        raise cdr.Exception("Internal error: empty Group stack")
    group = table.groupStack[-1]
    group.where = IN_THEAD

#----------------------------------------------------------------------
# Start the table footer.
#----------------------------------------------------------------------
def openFooter(pp):

    # Find the current table.
    if not tableStack:
        raise cdr.Exception("Internal error: empty table stack")
    table = tableStack[-1]
    if not table.groupStack:
        raise cdr.Exception("Internal error: empty Group stack")
    group = table.groupStack[-1]
    group.where = IN_TFOOT

#----------------------------------------------------------------------
# Finish a table body, header, or footer.
#----------------------------------------------------------------------
def closeSection(pp):

    # Find the current table.
    if not tableStack:
        raise cdr.Exception("Internal error: empty table stack")
    table = tableStack[-1]
    if not table.groupStack:
        raise cdr.Exception("Internal error: empty Group stack")
    group = table.groupStack[-1]
    group.where = IN_NOTHING

#----------------------------------------------------------------------
# Start a table row.
#----------------------------------------------------------------------
def openRow(pp):

    # Find the current table.
    if not tableStack:
        raise cdr.Exception("Internal error: empty table stack")
    table = tableStack[-1]
    if not table.groupStack:
        raise cdr.Exception("Internal error: empty Group stack")
    group = table.groupStack[-1]
    group.currentColumn = 0

    rowNode = pp.getCurNode()
    rowSep  = rowNode.getAttribute("RowSep")
    try: rowSep = int(rowSep)
    except: rowSep = group.rowSep
    group.row = Row(rowSep)
    group.currentCellRow = []
    if TABLE_DEBUG:
        sys.stderr.write("where? %d\n" % group.where)
        sys.stderr.write("len(group.head)=%d\n" % len(group.head))
        sys.stderr.write("len(group.body)=%d\n" % len(group.body))
        sys.stderr.write("len(group.foot)=%d\n" % len(group.foot))
    if   group.where == IN_THEAD: group.head.append(group.currentCellRow)
    elif group.where == IN_TBODY: group.body.append(group.currentCellRow)
    elif group.where == IN_TFOOT: group.foot.append(group.currentCellRow)
    else:
        raise cdr.Exception("openRow(): group doesn't know what section "
                            "it's in")

#----------------------------------------------------------------------
# Finish up a table row.
#----------------------------------------------------------------------
def closeRow(pp):

    # Find the current table.
    if not tableStack:
        raise cdr.Exception("Internal error: empty table stack")
    table = tableStack[-1]
    if not table.groupStack:
        raise cdr.Exception("Internal error: empty Group stack")
    group = table.groupStack[-1]

    # Finish off multi-row leftovers
    i = group.currentColumn
    while i < len(group.cols):
        col = group.cols[i]
        if col.moreRows > 0:
            col.moreRows -= 1
        i += col.colSpan

    group.currentCellRow = None

#----------------------------------------------------------------------
# Start a table cell.
#----------------------------------------------------------------------
def openCell(pp):

    # Find the current table.
    if not tableStack:
        raise cdr.Exception("Internal error: empty table stack")
    table = tableStack[-1]
    if not table.groupStack:
        raise cdr.Exception("Internal error: empty Group stack")
    global tableCellDepth
    tableCellDepth += 1
    group = table.groupStack[-1]
    group.currentCellRow.append(Cell(group, pp))

#----------------------------------------------------------------------
# Finish up a table cell.
#----------------------------------------------------------------------
def closeCell(pp):

    # Find the current table.
    if not tableStack:
        raise cdr.Exception("Internal error: empty table stack")
    table = tableStack[-1]
    if not table.groupStack:
        raise cdr.Exception("Internal error: empty Group stack")
    group = table.groupStack[-1]
    if not group.currentCellRow:
        raise cdr.Exception("Internal error: no open cell found")
    group.currentCellRow[-1].content = pp.procNode.releaseOutput().strip()
    global tableCellDepth
    tableCellDepth -= 1
    if TABLE_DEBUG:
        sys.stderr.write("CONTENT: %s\n" % group.currentCellRow[-1].content)
