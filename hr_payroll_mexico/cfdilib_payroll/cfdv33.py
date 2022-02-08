# -*- coding: utf-8 -*-

from .cfdilib import BaseDocument
from .tools import tools


class Payroll12(BaseDocument):
    """Invoice document to comply with
    cfdi: v3.3 for Invoice Mexico Standards."""

    def __init__(self, dict_payroll, certificado, llave_privada, password, tz, url, user, password_pac, pac, debug_mode=False):
        self.template_fname = 'payroll12.xml'
        self.certificado = certificado
        self.llave_privada = llave_privada
        self.password = password
        self.url = url
        self.user = user
        self.password_pac = password_pac
        self.pac = pac
        self.tz = tz
        # ~ self.xslt_fname = '/home/pythonformas/resources/cadenaoriginal_3_3.xslt'
        self.global_namespace = 'http://www.sat.gob.mx/sitio_internet/cfd'
        self.set_template(self.template_fname)
        super(Payroll12, self).__init__(dict_payroll, certificado=certificado, llave_privada=llave_privada, password=password, tz=tz, url=url, user=user, password_pac = password_pac, pac=pac,debug_mode=debug_mode)

    def set_template(self, template_fname):
        self.template = super(Payroll12, self).set_template(template_fname)

    def set_schema(self, schema_fname):
        schema_fname = 'cfdv33.xsd'
        self.schema = super(Payroll12, self).set_schema(schema_fname)

    def set_xslt(self):
        # TODO: Standarize the schema in this way also,
        #       we can not use different algorithms here
        self.xstl = super(Payroll12, self).set_xslt()


def get_payroll(dict_payroll, certificado, llave_privada, password, tz, url, user, password_pac, pac, debug_mode=False):
    return Payroll12(dict_payroll, certificado=certificado, llave_privada=llave_privada, password=password, tz=tz, url=url, user=user, password_pac = password_pac, pac=pac, debug_mode=debug_mode)


