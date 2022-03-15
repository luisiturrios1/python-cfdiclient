import os

from lxml import etree


class Utils():

    internal_nsmap = {
        's': 'http://schemas.xmlsoap.org/soap/envelope/',
        'o': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd',
        'u': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd',
        'des': 'http://DescargaMasivaTerceros.sat.gob.mx',
        '': 'http://www.w3.org/2000/09/xmldsig#',
        #'': 'http://DescargaMasivaTerceros.gob.mx',
    }

    external_nsmap = {
        '': 'http://DescargaMasivaTerceros.sat.gob.mx',
        's': 'http://schemas.xmlsoap.org/soap/envelope/',
        'u': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd',
        'o': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd',
        'h':'http://DescargaMasivaTerceros.sat.gob.mx',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'xsd': 'http://www.w3.org/2001/XMLSchema',
    }

    xml_name: str = None

    def __init__(self) -> None:
        self.read_xml(self.xml_name)

    def read_xml(self, xml_name: str) -> etree.Element:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        xml_path = os.path.join(current_dir, xml_name)
        parser = etree.XMLParser(remove_blank_text=True)
        self.element_root = etree.parse(xml_path, parser).getroot()
        return self.element_root

    def get_element(self, xpath: str) -> etree.Element:
        return self.element_root.find(xpath, self.internal_nsmap)

    def get_element_external(self, element: etree.Element, xpath: str) -> etree.Element:
        return element.find(xpath, self.external_nsmap)

    def set_element_text(self, xpath: str, text: str) -> None:
        element = self.element_root.find(xpath, self.internal_nsmap)
        element.text = text

    @classmethod
    def element_to_bytes(cls, element: etree.Element) -> bytes:
        return etree.tostring(element, method='c14n', exclusive=1)
