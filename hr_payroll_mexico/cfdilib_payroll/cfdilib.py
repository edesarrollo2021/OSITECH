# -*- coding: utf-8 -*-
import zeep
import os
from os.path import dirname
from io import StringIO, BytesIO
import re
from OpenSSL import crypto
import base64
from Crypto.Hash import SHA256
from Crypto.Signature import PKCS1_v1_5
from M2Crypto import RSA
from datetime import datetime
import pytz 

from abc import ABCMeta, abstractmethod
from tempfile import NamedTemporaryFile

from lxml import etree
from contextlib import contextmanager
from jinja2 import Environment, FileSystemLoader
from jinja2.exceptions import UndefinedError

from .tools import tools

import tempfile
import pkg_resources
import hashlib


@contextmanager
def change_path():
    old_path = os.getcwd()
    try:
        yield
        os.chdir(old_path)
    finally:
        os.chdir(old_path)


class Struct(object):
    def __init__(self, adict):
        """Convert a dictionary to a class

        @param :adict Dictionary
        """
        self.__dict__.update(adict)
        for k, v in adict.items():
            if isinstance(v, dict):
                self.__dict__[k] = Struct(v)
            if isinstance(v, list):
                # import pdb; pdb.set_trace()
                self.__dict__[k] = [Struct(x) for x in v]


class BaseDocument:
    """An XML document following any format given an XSD file.
    Due to avoid duplication of work we will delegate the
    error management of attributes to the xsd, then the
    `validate` method will make the job of return the correct
    error, due to the standard managed on the invoice.

    The template itself must comply with an specific xsd,
    this is needed to simply pass a dictionary of terms used in
    the template convert them to
    attributes of this Document object using whatever attributes
    comes from that xsd

    Then due to the template itself has all the structure of
    attributes necessaries to comply with the xsd, theoretically
    the xsd should return the logical error which
    we are not complying on such template, see cfdv32.xml
    template to see how you should assembly a new version
    of this template, then set it to the template_fname attribute
    and guala your dict will be magically validated
    and converted to an XML file.

    **Why not assembly with simple lxml?**

    Because it is more readable and configurable,
    it is always more simple
    inherit a class and set an attribute than overwrite
    hundreds of methods when it is a big xml.
    """
    
    xlst_path = os.path.dirname(os.path.abspath(__file__)) + '/templates/cadenaoriginal_3_3.xslt'
    
    @abstractmethod
    def __init__(self, dict_document, certificado, llave_privada, password, tz,  url, user, password_pac, pac, debug_mode=False, cache=1000):
        """Convert a dictionary invoice to a Class with a
        based xsd and xslt element to be signed.

        :param dict dict_document: Dictionary with all entries
            you will need in your template.
        :param bool debug_mode: If debugging or not.
        :param int cache: Time in seconds the url given
            files will be cached on tmp folder.
        """
        self.ups = False
        self.debug_mode = debug_mode
        self.schema_url = None
        self.document = ''
        self.cadena_original = ''
        self.date_timbre = ''
        self.error_timbrado = None
        self.document_path = None
        self.xslt_path = None
        self.xslt_document = None
        self.set_schema_fname()
        self.set_schema(self.schema_fname)
        self.__dict__.update(dict_document)
        for k, v in dict_document.items():
            if isinstance(v, dict):
                self.__dict__[k] = Struct(v)
            if isinstance(v, list):
                # import pdb; pdb.set_trace()
                self.__dict__[k] = [Struct(x) for x in v]

        self.set_xml()
        self.template_fname = ''
        self.schema_fname = self.template_fname.replace('.xml', '.xsd')
        self.templates = os.path.join(dirname(__file__), 'templates')

    __metaclass__ = ABCMeta

    def set_schema_fname(self):
        """The same than template but with .xsd on templates folder."""
        self.schema_fname = self.template_fname.replace('.xml', '.xsd')

    def set_xslt_fname(self):
        """The same than template but with .xslt on templates
        folder this in case you want to use it locally."""
        self.set_xslt()

    def guess_autoescape(self, template_name):
        """Given a template Name I will gues using its
        extension if we should autoscape or not.
        Default autoscaped extensions: ('html', 'xhtml', 'htm', 'xml')
        """
        if template_name is None or '.' not in template_name:
            return False
        ext = template_name.rsplit('.', 1)[1]
        return ext in ('html', 'xhtml', 'htm', 'xml')

    @abstractmethod
    def set_schema(self, schema_fname):
        test_xml = os.path.join(self.templates, schema_fname)
        return test_xml

    @abstractmethod
    def set_template(self, template_fname):
        self.templates = os.path.join(dirname(__file__), 'templates')
        env = Environment(loader=FileSystemLoader(self.templates),
                          extensions=['jinja2.ext.autoescape'],
                          autoescape=self.guess_autoescape)
        return env.get_template(template_fname)

    def validate(self, schema_str, xml_valid):
        """Compare the valid information on an xml from  given schema.

        :param str schema_str: content string from schema file.
        :param str xml_valid: content string from xml file.
        :returns: If it is Valid or Not.
        :rtype: bool
        """
        # TODO: be able to get doc for error given an xsd.
        # Changed path to allow have xsd that are imported by others xsd in the
        # same library, and not call to SAT page each time that is generated
        # a new XML.
        with change_path():
            path = os.path.join(
                os.path.dirname(os.path.realpath(__file__)), 'templates')
            os.chdir(path)
            # ~ schema_root = etree.parse(StringIO(schema_str))
            schema_root = etree.parse(schema_str)
            schema = etree.XMLSchema(schema_root)
        try:
            tree = etree.parse(StringIO(xml_valid.encode('UTF-8')))
            schema.assertValid(tree)
        except etree.DocumentInvalid as ups:
            self.ups = ups
        finally:
            if self.ups:
                self.valid = False
            else:
                self.valid = True
            return self.valid

    def set_xml(self):
        """Set document xml just rendered already
        validated against xsd to be signed.

        :params boolean debug_mode: Either if you want
            the rendered template to be saved either it
        is valid or not with the given schema.
        :returns boolean: Either was valid or not the generated document.
        """
        cached = BytesIO()
        document = u''
        try:
            document = self.template.render(inv=self)
        except UndefinedError as ups:
            self.ups = ups
        # TODO: Here should be called the cleanup 'Just before the validation'.
        valid = self.validate(self.schema, document)
        self.document = document
        if valid:
            document = etree.XML(document)
            document = self.sellar(document)
            documento_timbrado = self.timbrar(self.user, self.password_pac, document)
            if documento_timbrado:
                if self.pac == 'forsedi':
                    if documento_timbrado['xmlTimbrado']:
                        document = etree.XML(documento_timbrado['xmlTimbrado'].encode('utf-8'))
                        document = etree.tostring(document, pretty_print=True, xml_declaration=True, encoding='utf-8')
                        self.document = document
                        cached.write(self.document is not None and self.document or u'')
                        cached.seek(0)
                        self.document_path = cached
                    else:
                        self.error_timbrado = documento_timbrado
                if self.pac == 'sefactura':
                    if documento_timbrado['timbre']:
                        print ('exitoso')
                    else:
                        self.error_timbrado =  {
                                         'codigoError':'Desconocido',
                                         'error':documento_timbrado['status'],
                                         'xmlTimbrado':None
                                        }
                    
            else:
                self.error_timbrado =  {
                                         'codigoError':'Desconocido',
                                         'error':'No se ha podido generar el CFDI',
                                         'xmlTimbrado':None
                                        }

    def get_element_from_clark(self, element):
        """**Helper method:** Given a Clark's Notation
        `{url:schema}Element` element, return the
        valid xpath on your xsd file, frequently
        it is not necesary overwrite this method but
        different xsd from different source
        can have different logic which I do not know now,
        then simply take this as an example and set the
        correct xpath conversion in your project.

        :param str element: Element string following the Clark's Notation"""
        element = element.split('}')[-1]
        xpath_path = \
            '//xs:element[@name="{element}"]' + \
            '/xs:annotation/xs:documentation'.format(element=element)
        return xpath_path

    def get_documentation(self, element, namespace=None, schema_str=None):
        """**Helper method:** should return an schema specific documentation
        given an element parsing or getting the `Clark's Notation`_
        `{url:schema}Element` from the message error on validate method.

        :param str element: Element string following the Clark's Notation
        :param dict namespace: Element string following the Clark's Notation

        :returns: The documentation text if exists
        :rtype: unicode

        .. _`Clark's Notation`: http://effbot.org/zone/element-namespaces.htm
        """
        if namespace is None:
            namespace = {'xs': 'http://www.w3.org/2001/XMLSchema'}
        schema_root = etree.parse(StringIO(self.schema))
        
        document = schema_root.xpath(self.get_element_from_clark(element),
                                     namespaces=namespace)
        return document and document[0].text or ''
        
    def get_certificado_x509(self, certificado_base_64):
        cert64Str = re.sub("(.{64})", "\\1\n", certificado_base_64, 0, re.DOTALL)
        if cert64Str[-1] == '\n':
            cert64WithBE = '-----BEGIN CERTIFICATE-----\n' + cert64Str + '-----END CERTIFICATE-----\n'
        else:
            cert64WithBE = '-----BEGIN CERTIFICATE-----\n' + cert64Str + '\n-----END CERTIFICATE-----\n'
        certificate = crypto.load_certificate(crypto.FILETYPE_PEM, cert64WithBE.encode("utf-8"))
        return certificate
    
    def get_certificado_64(self):
        return self.certificado.decode('utf-8')
    
    def get_no_certificado(self, certificado):
        serial = str(u'{0:0>40x}'.format(certificado.get_serial_number()))
        return serial.replace('33', 'B').replace('3', '').replace(
            'B', '3').replace(' ', '').replace('\r', '').replace(
            '\n', '').replace('\r\n', '')
        
    def get_cadena_original(self, xml=None):
        xslt = etree.parse(self.xlst_path)
        transform = etree.XSLT(xslt)
        cadena_original = transform(xml)
        return (str(cadena_original))        
    
    def base64_to_tempfile(self, b64_str=None, suffix=None, prefix=None):
        """ Convert strings in base64 to a temp file
        @param b64_str : Text in Base_64 format for add in the file
        @param suffix : Sufix of the file
        @param prefix : Name of file in TempFile
        """
        (fileno, file_name) = tempfile.mkstemp(suffix, prefix)
        f_read = open(file_name, 'wb')
        f_read.write(base64.decodestring(b64_str))
        f_read.close()
        os.close(fileno)
        return file_name
    
    
    def get_sello(self, cadena_original):
        key_file = self.base64_to_tempfile(self.llave_privada, '', '')
        (no, pem) = tempfile.mkstemp()
        os.close(no)
        cmd = ('openssl pkcs8 -inform DER -outform PEM'
               ' -in "%s" -passin pass:%s -out %s' % (key_file, self.password, pem))
        os.system(cmd)
        keys = RSA.load_key(pem)
        digest = hashlib.new('sha256', bytes(cadena_original, 'UTF-8')).digest()
        return base64.b64encode(keys.sign(digest, "sha256"))
    
    def sellar(self,document):
        date =  datetime.now()
        UTC = pytz.timezone ("UTC") 
        UTC_date = UTC.localize(date, is_dst=None) 
        date_timbre = UTC_date.astimezone (self.tz)
        date_timbre = str(date_timbre.isoformat())[:19]
        self.date_timbre = date_timbre
        certificado64 = self.get_certificado_64()
        certificado = self.get_certificado_x509(certificado64)
        no_certificado = self.get_no_certificado(certificado)
        document.attrib['Fecha'] = date_timbre
        document.attrib['NoCertificado'] = no_certificado
        document.attrib['Certificado'] = certificado64
        self.cadena_original = self.get_cadena_original(document)
        sello = self.get_sello(self.cadena_original)
        document.attrib['Sello'] = sello
        return etree.tostring(document,
                       pretty_print=False,
                       xml_declaration=True,
                       encoding='utf-8')
                       
    def timbrar(self, usuario, password, cfdi_cellado):
        
        
        print (cfdi_cellado.decode('UTF-8'))
        
        cliente = zeep.Client(wsdl = self.url)
        try:
            if self.pac == 'forsedi':
                accesos_type = cliente.get_type("ns1:accesos")
                accesos = accesos_type(usuario=usuario, password=password)
                cfdi_timbrado = cliente.service.TimbrarCFDI(accesos = accesos, comprobante=cfdi_cellado.decode('UTF-8'))
                return cfdi_timbrado 
            elif self.pac == 'sefactura':
                cfdi_timbrado = cliente.service.timbrado(usuario=usuario, clave=password , cfdi=cfdi_cellado.decode('UTF-8'))
                return cfdi_timbrado 
        except Exception as exception:
            print("Message %s" % exception)
