import lxml.etree as etree
import re

class SystemSubset:
    def __init__(self, node):
        self.name = node.find("SubsetName").text
        self.specs = []
        self.publish_if_warnings = "No"
        for child in node.findall("SubsetSpecifications/SubsetSpecification"):
            self.specs.append(self.Specification(child))
        for child in node.findall("SubsetOptions/SubsetOption"):
            option = self.Option(child)
            if option.name == "PublishIfWarnings":
                self.publish_if_warnings = option.value
    def has_queries(self):
        for spec in self.specs:
            if spec.real_queries:
                return True
        return False
    def user_select_allowed(self):
        for spec in self.specs:
            if spec.user_select_types:
                return True
        return False
    class Specification:
        empty = "SELECT document.id FROM document WHERE document.id = 0"
        def __init__(self, node):
            self.user_select_types = set()
            self.real_queries = False
            for child in node.findall("SubsetSelection"):
                for dt in child.findall("UserSelect/UserSelectDoctype"):
                    self.user_select_types.add(dt.text)
                for sql in child.findall("SubsetSQL"):
                    if self.real_query(sql.text):
                        self.real_queries = True
        def real_query(self, sql):
            sql = re.sub("\\s+", " ", sql.strip())
            if sql == self.empty:
                return False
            if not sql.startswith("SELECT TOP"):
                raise Exception(sql)
            return True
    class Option:
        def __init__(self, node):
            self.name = node.find("OptionName").text
            self.value = node.find("OptionValue").text

tree = etree.parse("Primary.xml")
for node in tree.getroot().findall("SystemSubset"):
    subset = SystemSubset(node)
    print("%-3s %s %s %s" % (subset.publish_if_warnings,
                             subset.user_select_allowed() and "Y" or "N",
                             subset.has_queries() and "Y" or "N",
                             subset.name))
