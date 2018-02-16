#!/usr/bin/python3

"""
Show publishing control subsystem information
"""

import lxml.etree as etree

def get_child_text(node, name, default=None):
    return get_text(node.find(name))

def get_text(node, default=None):
    return "".join(node.itertext("*")) if node is not None else default

class System:
    def __init__(self, root):
        self.name = get_child_text(root, "SystemName")
        self.desc = get_child_text(root, "SystemDescription")
        self.subsets = [Subset(node) for node in root.findall(Subset.PATH)]
    def show(self):
        print("SYSTEM {}\n".format(self.name))
        for subset in self.subsets:
            subset.show()
        print()

class Subset:
    PATH = "SystemSubset"
    def __init__(self, node):
        self.name = get_child_text(node, "SubsetName")
        self.desc = get_child_text(node, "SubsetDescription")
        self.action = get_child_text(node, "SubsetActionName")
        self.script = get_child_text(node, "ProcessScript")
        self.parms = [Parm(n) for n in node.findall(Parm.PATH)]
        self.options = [Option(n) for n in node.findall(Option.PATH)]
        self.specs = [Spec(n) for n in node.findall(Spec.PATH)]
    def show(self):
        print("SUBSYSTEM {}".format(self.name))
        if self.action:
            print("\taction={}".format(self.action))
        if self.script:
            print("\tscript={}".format(self.script))
        for parm in self.parms:
            parm.show()
        for option in self.options:
            option.show()
        for spec in self.specs:
            spec.show()
        print()

class Spec:
    PATH = "SubsetSpecifications/SubsetSpecification"
    DOCTYPE = "SubsetSelection/UserSelect/UserSelectDoctype"
    def __init__(self, node):
        self.query = get_child_text(node, "SubsetSelection/SubsetSQL")
        self.directory = get_child_text(node, "Subdirectory")
        self.doctypes = [get_text(n) for n in node.findall(self.DOCTYPE)]
        self.filters = [Filters(n) for n in node.findall("SubsetFilters")]
    def show(self):
        if self.query:
            print("\tQUERY:\n{}".format(self.query))
        if self.directory:
            print("\tDIRECTORY={}".format(self.directory))
        if self.doctypes:
            print("\tDOCTYPES={}".format(self.doctypes))
        for filter in self.filters:
            filter.show()

class Filters:
    def __init__(self, node):
        self.__node = node
    def show(self):
        print("\tFILTERS: {}".format(self.filters))
        print("\tPARMS: {}".format(self.parameters))
    @property
    def filters(self):
        if not hasattr(self, "_filters"):
            self._filters = []
            for node in self.__node.findall("SubsetFilter/*"):
                text = get_text(node)
                if text:
                    if node.tag == "SubsetFilterName":
                        if not text.startswith("set:"):
                            text = "name:{}".format(text)
                    elif node.tag != "SubsetFilterId":
                        err = "Unexpected filter element {}"
                        raise Exception(err.format(node.tag))
                    self._filters.append(text)
            if not self._filters:
                raise Exception("No filters in group")
        return self._filters

    @property
    def parameters(self):
        if not hasattr(self, "_parameters"):
            self._parameters = dict()
            for node in self.__node.findall("SubsetFilterParm"):
                name = get_text(node.find("ParmName"))
                value = get_text(node.find("ParmValue"))
                if value is None:
                    raise Exception("parameter value missing")
                self._parameters[name] = value
        return self._parameters

class Parm:
    PATH = "SubsetParameters/SubsetParameter"
    def __init__(self, node):
        self.name = get_child_text(node, "ParmName")
        self.value = get_child_text(node, "ParmValue")
    def show(self):
        print("\tPARM {}={!r}".format(self.name, self.value))

class Option:
    PATH = "SubsetOptions/SubsetOption"
    def __init__(self, node):
        self.name = get_child_text(node, "OptionName")
        self.value = get_child_text(node, "OptionValue")
    def show(self):
        print("\tOPTION {}={!r}".format(self.name, self.value))

for name in ("Primary.xml", "QcFilterSets.xml"):
    System(etree.parse(name).getroot()).show()
