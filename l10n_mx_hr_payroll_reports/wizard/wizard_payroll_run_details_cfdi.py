# -*- coding: utf-8 -*-

import io
import xlsxwriter
import base64
from lxml import etree as ET

from datetime import date, datetime, time
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class payrollRunDetailsCfdi(models.TransientModel):
    _name = "payroll.run.details.cfdi.wizard"
    _description = 'Details CFDI'

    # Columns
    estructure_ids = fields.Many2many('hr.payroll.structure', required=True,
                                      default=lambda self: self.env['hr.payslip.run'].browse([self._context.get('active_id')]).mapped('slip_ids.struct_id')._ids,
                                      domain=lambda self: [('id', 'in', self.env['hr.payslip.run'].browse([self._context.get('active_id')]).mapped('slip_ids.struct_id')._ids)])
    company_ids = fields.Many2many('res.company', required=True,
                                   default=lambda self: self.env['hr.payslip.run'].browse([self._context.get('active_id')]).mapped('slip_ids.company_id')._ids,
                                   domain=lambda self: [('id', 'in', self.env['hr.payslip.run'].browse([self._context.get('active_id')]).mapped('slip_ids.company_id')._ids)])

    def prepare_header(self):
        header = [
            {'name': 'Estado', 'larg': 20, 'col': {}},
            {'name': 'Fecha', 'larg': 20, 'col': {}},
            {'name': 'Versión', 'larg': 14, 'col': {}},
            {'name': 'Serie', 'larg': 14, 'col': {}},
            {'name': 'Folio', 'larg': 14, 'col': {}},
            {'name': 'UUID', 'larg': 20, 'col': {}},
            {'name': 'Rfc Receptor', 'larg': 20, 'col': {}},
            {'name': 'Nombre Receptor', 'larg': 20, 'col': {}},
            {'name': 'UsoCFDI', 'larg': 20, 'col': {}},
            {'name': 'NumSeguridadSocial', 'larg': 20, 'col': {}},
            {'name': 'RegimenFiscal', 'larg': 20, 'col': {}},
            {'name': 'RegistroPatronal', 'larg': 20, 'col': {}},
            {'name': 'RfcPatronOrigen', 'larg': 20, 'col': {}},
            {'name': 'Versión Nómina', 'larg': 20, 'col': {}},
            {'name': 'TipoNomina', 'larg': 20, 'col': {}},
            {'name': 'FechaPago', 'larg': 20, 'col': {}},
            {'name': 'FechaInicialPago', 'larg': 20, 'col': {}},
            {'name': 'FechaFinalPago', 'larg': 20, 'col': {}},
            {'name': 'NumDiasPagados', 'larg': 20, 'col': {}},
            {'name': 'TotalPercepciones', 'larg': 20, 'col': {}},
            {'name': 'TotalDeducciones', 'larg': 20, 'col': {}},
            {'name': 'TotalOtrosPagos', 'larg': 20, 'col': {}},
            {'name': 'SubTotal', 'larg': 20, 'col': {}},
            {'name': 'Descuento', 'larg': 20, 'col': {}},
            {'name': 'Total', 'larg': 20, 'col': {}},
            {'name': 'ReceptorCurp', 'larg': 20, 'col': {}},
            {'name': 'FechaInicioRelLaboral', 'larg': 20, 'col': {}},
            {'name': 'Antigüedad', 'larg': 20, 'col': {}},
            {'name': 'TipoContrato', 'larg': 20, 'col': {}},
            {'name': 'Sindicalizado', 'larg': 20, 'col': {}},
            {'name': 'TipoJornada', 'larg': 20, 'col': {}},
            {'name': 'TipoRegimen', 'larg': 20, 'col': {}},
            {'name': 'NumEmpleado', 'larg': 20, 'col': {}},
            {'name': 'Departamento', 'larg': 20, 'col': {}},
            {'name': 'Puesto', 'larg': 20, 'col': {}},
            {'name': 'RiesgoPuesto', 'larg': 20, 'col': {}},
            {'name': 'PeriodicidadPago', 'larg': 20, 'col': {}},
            {'name': 'Banco', 'larg': 20, 'col': {}},
            {'name': 'CuentaBancaria', 'larg': 20, 'col': {}},
            {'name': 'SalarioBaseCotApor', 'larg': 20, 'col': {}},
            {'name': 'SalarioDiarioIntegrado', 'larg': 20, 'col': {}},
            {'name': 'ClaveEntFed', 'larg': 20, 'col': {}},
            {'name': 'SubContRfcLabora', 'larg': 20, 'col': {}},
            {'name': 'SubContPorcentajeTiempo', 'larg': 20, 'col': {}},
            {'name': 'TotalSueldosPer', 'larg': 20, 'col': {}},
            {'name': 'TotalSeparacionIndemnizacionPer', 'larg': 20, 'col': {}},
            {'name': 'TotalJubilacionPensionRetiroPer', 'larg': 20, 'col': {}},
            {'name': 'TotalGravadoPercepcion', 'larg': 20, 'col': {}},
            {'name': 'TotalExentoPercepcion', 'larg': 20, 'col': {}},
            {'name': 'TotalOtrasDeducciones', 'larg': 20, 'col': {}},
            {'name': 'TotalImpuestosRetenidosDed', 'larg': 20, 'col': {}},
            {'name': 'P004_GastosMedicosExe', 'larg': 20, 'col': {}},
            {'name': 'P004_GastosMedicosGra', 'larg': 20, 'col': {}},
            {'name': 'P020_PrimDomExe', 'larg': 20, 'col': {}},
            {'name': 'P020_PrimDomGra', 'larg': 20, 'col': {}},
            {'name': 'P021_PrimVacacionalExe', 'larg': 20, 'col': {}},
            {'name': 'P021_PrimVacacionalGra', 'larg': 20, 'col': {}},
            {'name': 'P025_IndemnizacionesExe', 'larg': 20, 'col': {}},
            {'name': 'P025_IndemnizacionesGra', 'larg': 20, 'col': {}},
            {'name': 'P038_OtrosingresosExe', 'larg': 20, 'col': {}},
            {'name': 'P038_OtrosingresosGra', 'larg': 20, 'col': {}},
            {'name': 'D001_SeguroSocial', 'larg': 20, 'col': {}},
            {'name': 'D002_ISR', 'larg': 20, 'col': {}},
            {'name': 'OP001_ReintegroISRExceso', 'larg': 20, 'col': {}},
            {'name': 'OP002_SubsidioEmpleo', 'larg': 20, 'col': {}},
            {'name': 'OP002_SubsidioCausado', 'larg': 20, 'col': {}},
            {'name': 'OP003_Viaticos', 'larg': 20, 'col': {}},
            {'name': 'OP007_ISRAjustadoSubsidio', 'larg': 20, 'col': {}},
            {'name': 'OP008_SubsidioEfectEnt', 'larg': 20, 'col': {}},
            {'name': 'Conceptos', 'larg': 20, 'col': {}},
            {'name': 'LugarDeExpedicion', 'larg': 20, 'col': {}},
        ]
        return header

    def print_report(self):
        '''
           This method prints the payroll details report, taking into account the selected criteria
        '''
        doc_ids = self._context.get('active_ids')
        print(doc_ids)
        payslips = self.env['hr.payslip'].search([('payslip_run_id', 'in', doc_ids),
                                                  ('struct_id', 'in', self.estructure_ids._ids),
                                                  ('company_id', 'in', self.company_ids._ids),
                                                  ('state', 'in', ['done']),
                                                  ('invoice_status', 'in', ['right_bill', 'problems_canceled']),
                                                  ])
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        bold = workbook.add_format({'bold': True})
        header_format = workbook.add_format({'bold':True, 'bg_color': '#100D57', 'font_color': '#FFFFFF', 'border': 1,
                                             'top': 1, 'font_size': 8, 'align': 'center', 'valign': 'vcenter',
                                             'font_name': 'MS Sans Serif'})
        middle = workbook.add_format({'bold': True, 'top': 1})
        left = workbook.add_format({'left': 1, 'top': 1, 'bold': True})
        right = workbook.add_format({'right': 1, 'top': 1})
        top = workbook.add_format({'top': 1})
        lang_code = self.env.user.lang or 'en_US'
        date_format = self.env['res.lang']._lang_get(lang_code).date_format
        report_format = workbook.add_format({'border': 1, 'bold': True, 'font_size': 8, 'fg_color': '#BFBFBF',
                                             'align': 'center', 'font_name': 'MS Sans Serif'})
        report_format2 = workbook.add_format({'border': 1, 'bold': False, 'font_size': 8, 'font_name': 'MS Sans Serif',
                                              'align': 'left'})
        num_format = '_($* #,##0.00_);_($* (#,##0.00);_($* "0"??_);_(@'
        currency_format = workbook.add_format({'num_format': num_format, 'bold': False, 'border': 1, 'top': 1,
                                               'font_size': 8, 'align': 'right', 'valign': 'vcenter',
                                               'font_name': 'MS Sans Serif'})
        row = 1
        col = 0
        NSMAP = {
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            'cfdi': 'http://www.sat.gob.mx/cfd/3',
            'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital',
            'nomina12': 'http://www.sat.gob.mx/nomina12',
        }
        def _header_sheet(sheet):
            sheet.set_column(0, 1, 16)
            sheet.set_column(5, 5, 30)
            sheet.set_column(6, 6, 15)
            sheet.set_column(7, 7, 30)
            sheet.set_column(8, 8, 12)
            sheet.set_column(9, 9, 15)
            sheet.set_column(10, 10, 25)
            sheet.set_column(11, 12, 15)
            sheet.set_column(13, 13, 12)
            sheet.set_column(14, 14, 15)
            sheet.set_column(15, 17, 12)
            sheet.set_column(18, 21, 15)
            sheet.set_column(22, 24, 12)
            sheet.set_column(25, 25, 20)
            sheet.set_column(26, 26, 15)
            sheet.set_column(27, 27, 12)
            sheet.set_column(28, 28, 20)
            sheet.set_column(29, 31, 12)
            sheet.set_column(32, 32, 15)
            sheet.set_column(33, 34, 20)
            sheet.set_column(35, 39, 15)
            sheet.set_column(40, 41, 12)
            sheet.set_column(42, 42, 15)
            sheet.set_column(43, 44, 20)
            sheet.set_column(45, 46, 25)
            sheet.set_column(47, 70, 20)
            for j, h in enumerate(self.prepare_header()):
                sheet.write(0, j, h['name'], header_format)

        if payslips:
            today = fields.Date.today().strftime("%d/%b/%Y").title()
            f_name = '%s %s' % (payslips[0].payslip_run_id.name, today)
            sheet = workbook.add_worksheet(payslips[0].payslip_run_id.name)
            _header_sheet(sheet)
            i = 0
            for payslip in payslips:
                def _get_data_float(data):
                    if data is None or not data:
                        return 0.0
                    else:
                        return "{0:.2f}".format(payslip.company_id.currency_id.round(data) + 0.0)

                xml_timbre = payslip.cfdi_ids.mapped('xml_timbre')[0]
                xml = base64.decodebytes(xml_timbre.datas)
                document = ET.fromstring(xml)
                Complemento = document.find('cfdi:Complemento', NSMAP)
                TimbreFiscalDigital = Complemento.find('tfd:TimbreFiscalDigital', NSMAP)
                nomina12 = Complemento.find('nomina12:Nomina', NSMAP)
                Receptor = document.find('cfdi:Receptor', NSMAP)
                Emisor = document.find('cfdi:Emisor', NSMAP)
                Conceptos = document.find('cfdi:Conceptos', NSMAP)
                Concepto = Conceptos.getchildren()[0]
                i += row
                Emisor12 = False
                Receptor12 = False
                SubContratacion12 = False
                Percepciones12 = False
                Deducciones12 = False
                OtrosPagos12 = False
                P004_GastosMedicosExe = ''
                P004_GastosMedicosGra = ''
                P020_PrimDomExe = ''
                P020_PrimDomGra = ''
                P021_PrimVacacionalExe = ''
                P021_PrimVacacionalGra = ''
                P025_IndemnizacionesExe = ''
                P025_IndemnizacionesGra = ''
                P038_OtrosingresosExe = ''
                P038_OtrosingresosGra = ''
                D001_SeguroSocial = ''
                D002_ISR = ''
                OP001_ReintegroISRExceso = ''
                OP002_SubsidioEmpleo = ''
                OP002_SubsidioCausado = ''
                OP003_Viaticos = ''
                OP007_ISRAjustadoSubsidio = ''
                OP008_SubsidioEfectEnt = ''
                for t in nomina12.getchildren():
                    if t.tag == '{http://www.sat.gob.mx/nomina12}Emisor':
                        Emisor12 = t.attrib
                    if t.tag == '{http://www.sat.gob.mx/nomina12}Receptor':
                        Receptor12 = t.attrib
                    if t.tag == '{http://www.sat.gob.mx/nomina12}SubContratacion':
                        SubContratacion12 = t.attrib
                    if t.tag == '{http://www.sat.gob.mx/nomina12}Percepciones':
                        Percepciones12 = t.attrib
                        for p in t.getchildren():
                            if p.attrib.get('TipoPercepcion') == '004':
                                P004_GastosMedicosExe = '$ '+str(_get_data_float(float(p.attrib.get('ImporteExento'))))
                                P004_GastosMedicosGra = '$ '+str(_get_data_float(float(p.attrib.get('ImporteGravado'))))
                            if p.attrib.get('TipoPercepcion') == '020':
                                P020_PrimDomExe = '$ '+str(_get_data_float(float(p.attrib.get('ImporteExento'))))
                                P020_PrimDomGra = '$ '+str(_get_data_float(float(p.attrib.get('ImporteGravado'))))
                            if p.attrib.get('TipoPercepcion') == '021':
                                P021_PrimVacacionalExe = '$ '+str(_get_data_float(float(p.attrib.get('ImporteExento'))))
                                P021_PrimVacacionalGra =  '$ '+str(_get_data_float(float(p.attrib.get('ImporteGravado'))))
                            if p.attrib.get('TipoPercepcion') == '025':
                                P025_IndemnizacionesExe = '$ '+str(_get_data_float(float(p.attrib.get('ImporteExento'))))
                                P025_IndemnizacionesGra = '$ '+str(_get_data_float(float(p.attrib.get('ImporteGravado'))))
                            if p.attrib.get('TipoPercepcion') == '038':
                                P038_OtrosingresosExe = '$ '+str(_get_data_float(float(p.attrib.get('ImporteExento'))))
                                P038_OtrosingresosGra = '$ '+str(_get_data_float(float(p.attrib.get('ImporteGravado'))))
                    if t.tag == '{http://www.sat.gob.mx/nomina12}Deducciones':
                        Deducciones12 = t.attrib
                        for d in t.getchildren():
                            if d.attrib.get('TipoDeduccion') == '001':
                                D001_SeguroSocial = '$ '+str(_get_data_float(float(d.attrib.get('Importe'))))
                            if d.attrib.get('TipoDeduccion') == '002':
                                D002_ISR = '$ '+str(_get_data_float(float(d.attrib.get('Importe'))))
                    if t.tag == '{http://www.sat.gob.mx/nomina12}OtrosPagos':
                        OtrosPagos12 = t.attrib
                        for op in t.getchildren():
                            if op.attrib.get('TipoOtroPago') == '001':
                                OP001_ReintegroISRExceso = '$ '+str(_get_data_float(float(op.attrib.get('Importe'))))
                            if op.attrib.get('TipoOtroPago') == '002':
                                OP002_SubsidioEmpleo = '$ '+str(_get_data_float(float(op.attrib.get('Importe'))))
                                OP002_SubsidioCausado = '$ '+str(_get_data_float(float(op.getchildren()[0].attrib.get('SubsidioCausado'))))
                            if op.attrib.get('TipoOtroPago') == '003':
                                OP003_Viaticos = '$ '+str(_get_data_float(float(op.attrib.get('Importe'))))
                            if op.attrib.get('TipoOtroPago') == '007':
                                OP007_ISRAjustadoSubsidio = '$ '+str(_get_data_float(float(op.attrib.get('Importe'))))
                            if op.attrib.get('TipoOtroPago') == '008':
                                OP008_SubsidioEfectEnt = '$ '+str(_get_data_float(float(op.attrib.get('Importe'))))
                TipoContrato = payslip.contract_id.contract_type
                TipoContrato2 = dict(payslip.contract_id._fields['contract_type']._description_selection(self.env)).get(payslip.contract_id.contract_type)
                state = ''
                if payslip.invoice_status == 'right_bill':
                    state = 'Vigente'
                elif payslip.invoice_status == 'problems_canceled':
                    state = 'Cancelado'
                sheet.write(i, 0, state, report_format2)
                sheet.write(i, 1, document.attrib['Fecha'], report_format2)
                sheet.write(i, 2, document.attrib['Version'], report_format2)
                sheet.write(i, 3, document.attrib['Serie'], report_format2)
                sheet.write(i, 4, document.attrib['Folio'], report_format2)
                sheet.write(i, 5, TimbreFiscalDigital.attrib['UUID'], report_format2)
                sheet.write(i, 6, Receptor.attrib['Rfc'], report_format2)
                sheet.write(i, 7, Receptor.attrib['Nombre'], report_format2)
                sheet.write(i, 8, Receptor.attrib['UsoCFDI'] + '-' + dict(payslip._fields['cfdi_use']._description_selection(self.env)).get(Receptor.attrib['UsoCFDI']), report_format2)
                sheet.write(i, 9, Receptor12.get('NumSeguridadSocial'), report_format2)
                sheet.write(i, 10, Emisor.attrib['RegimenFiscal'] + '-' + dict(payslip.company_id._fields['l10n_mx_edi_fiscal_regime']._description_selection(self.env)).get(Emisor.attrib['RegimenFiscal']), report_format2)
                sheet.write(i, 11, Emisor12.get('RegistroPatronal'), report_format2)
                sheet.write(i, 12, Emisor12.get('RfcPatronOrigen'), report_format2)
                sheet.write(i, 13, nomina12.attrib['Version'], report_format2)
                sheet.write(i, 14, nomina12.attrib['TipoNomina'] + '-' + dict(payslip._fields['payroll_type']._description_selection(self.env)).get(nomina12.attrib['TipoNomina']), report_format2)
                sheet.write(i, 15, nomina12.attrib['FechaPago'], report_format2)
                sheet.write(i, 16, nomina12.attrib['FechaInicialPago'], report_format2)
                sheet.write(i, 17, nomina12.attrib['FechaFinalPago'], report_format2)
                sheet.write(i, 18, nomina12.attrib['NumDiasPagados'], report_format2)
                if nomina12.get('TotalPercepciones'):
                    sheet.write(i, 19, '$ ' + str(_get_data_float(float(nomina12.get('TotalPercepciones')))), currency_format)
                else:
                    sheet.write(i, 19, nomina12.get('TotalPercepciones'), report_format2)
                if nomina12.get('TotalDeducciones'):
                    sheet.write(i, 20, '$ ' + str(_get_data_float(float(nomina12.get('TotalDeducciones')))), currency_format)
                else:
                    sheet.write(i, 20, nomina12.get('TotalDeducciones'), report_format2)
                if nomina12.get('TotalOtrosPagos'):
                    sheet.write(i, 21, '$ ' + str(_get_data_float(float(nomina12.get('TotalOtrosPagos')))), currency_format)
                else:
                    sheet.write(i, 21, nomina12.get('TotalOtrosPagos'), report_format2)
                sheet.write(i, 22, '$ ' + str(_get_data_float(float(document.get('SubTotal')))), currency_format)
                if Concepto.get('Descuento'):
                    sheet.write(i, 23, '$ ' + str(_get_data_float(float(Concepto.get('Descuento')))), currency_format)
                else:
                    sheet.write(i, 23, Concepto.get('Descuento'), currency_format)
                sheet.write(i, 24, '$ ' + str(_get_data_float(float(document.get('Total')))), currency_format)
                sheet.write(i, 25, Receptor12.get('Curp'), report_format2)
                sheet.write(i, 26, Receptor12.get('FechaInicioRelLaboral'), report_format2)
                sheet.write(i, 27, Receptor12.get('Antigüedad'), report_format2)
                sheet.write(i, 28, '%s - %s' % (TipoContrato, TipoContrato2), report_format2)
                sheet.write(i, 29, Receptor12.get('Sindicalizado'), report_format2)
                TipoJornadaGet = ''
                TipoJornada = ''
                if Receptor12.get('TipoJornada'):
                    TipoJornadaGet = Receptor12.get('TipoJornada')
                    TipoJornada = dict(payslip.employee_id._fields['type_working_day']._description_selection(self.env)).get(Receptor12.get('TipoJornada'))
                sheet.write(i, 30, TipoJornadaGet + '-' + TipoJornada, report_format2)
                sheet.write(i, 31, Receptor12.get('TipoRegimen') + '-' + dict(payslip._fields['contracting_regime']._description_selection(self.env)).get(Receptor12.get('TipoRegimen')), report_format2)
                sheet.write(i, 32, Receptor12.get('NumEmpleado'), report_format2)
                sheet.write(i, 33, Receptor12.get('Departamento'), report_format2)
                sheet.write(i, 34, Receptor12.get('Puesto'), report_format2)
                if Receptor12.get('RiesgoPuesto'):
                    sheet.write(i, 35, '%s-%s' % (Receptor12.get('RiesgoPuesto', ''), dict(payslip.employee_id.employer_register_id._fields['job_risk']._description_selection(self.env)).get(Receptor12.get('RiesgoPuesto')) or ''), report_format2)
                else:
                    sheet.write(i, 35, '', report_format2)
                sheet.write(i, 36, Receptor12.get('PeriodicidadPago') + '-' + 'Otro periodo' if Receptor12.get('PeriodicidadPago') == '99' else dict(payslip._fields['payroll_period']._description_selection(self.env)).get(Receptor12.get('PeriodicidadPago')), report_format2)
                sheet.write(i, 37, Receptor12.get('Banco'), report_format2)
                sheet.write(i, 38, Receptor12.get('CuentaBancaria'), report_format2)
                if Receptor12.get('SalarioBaseCotApor'):
                    sheet.write(i, 39, '$ ' + str(_get_data_float(float(Receptor12.get('SalarioBaseCotApor')))), report_format2)
                else:
                    sheet.write(i, 39, Receptor12.get('SalarioBaseCotApor'), report_format2)
                if Receptor12.get('SalarioDiarioIntegrado'):
                    sheet.write(i, 40, '$ ' + str(_get_data_float(float(Receptor12.get('SalarioDiarioIntegrado')))), report_format2)
                else:
                    sheet.write(i, 40, Receptor12.get('SalarioDiarioIntegrado'), report_format2)
                sheet.write(i, 41, Receptor12.get('ClaveEntFed'), report_format2)
                if SubContratacion12:
                    sheet.write(i, 42, SubContratacion12.get('RfcLabora'), report_format2)
                    sheet.write(i, 43, SubContratacion12.get('PorcentajeTiempo'), report_format2)
                else:
                    sheet.write(i, 42, '', report_format2)
                    sheet.write(i, 43, '', report_format2)
                if Percepciones12:
                    if Percepciones12.get('TotalSueldos'):
                        sheet.write(i, 44, '$ ' + str(_get_data_float(float(Percepciones12.get('TotalSueldos')))), currency_format)
                    else:
                        sheet.write(i, 44, Percepciones12.get('TotalSueldos'), report_format2)
                    if Percepciones12.get('TotalSeparacionIndemnizacion'):
                        sheet.write(i, 45, '$ ' + str(_get_data_float(float(Percepciones12.get('TotalSeparacionIndemnizacion')))), currency_format)
                    else:
                        sheet.write(i, 45, Percepciones12.get('TotalSeparacionIndemnizacion'), report_format2)
                    if Percepciones12.get('TotalJubilacionPensionRetiro'):
                        sheet.write(i, 46, '$ ' + str(_get_data_float(float(Percepciones12.get('TotalJubilacionPensionRetiro')))), currency_format)
                    else:
                        sheet.write(i, 46, Percepciones12.get('TotalJubilacionPensionRetiro'), report_format2)
                    if Percepciones12.get('TotalGravado'):
                        sheet.write(i, 47, '$ ' + str(_get_data_float(float(Percepciones12.get('TotalGravado')))), currency_format)
                    else:
                        sheet.write(i, 47, Percepciones12.get('TotalGravado'), report_format2)
                    if Percepciones12.get('TotalExento'):
                        sheet.write(i, 48, '$ ' + str(_get_data_float(float(Percepciones12.get('TotalExento')))), currency_format)
                    else:
                        sheet.write(i, 48, Percepciones12.get('TotalExento'), report_format2)
                else:
                    sheet.write(i, 44, '', report_format2)
                    sheet.write(i, 45, '', report_format2)
                    sheet.write(i, 46, '', report_format2)
                    sheet.write(i, 47, '', report_format2)
                    sheet.write(i, 48, '', report_format2)
                if Deducciones12:
                    if Deducciones12.get('TotalOtrasDeducciones'):
                        sheet.write(i, 49, '$ ' + str(_get_data_float(float(Deducciones12.get('TotalOtrasDeducciones')))), currency_format)
                    else:
                        sheet.write(i, 49, Deducciones12.get('TotalOtrasDeducciones'), report_format2)
                    if Deducciones12.get('TotalImpuestosRetenidos'):
                        sheet.write(i, 50, '$ ' + str(_get_data_float(float(Deducciones12.get('TotalImpuestosRetenidos')))), currency_format)
                    else:
                        sheet.write(i, 50, Deducciones12.get('TotalImpuestosRetenidos'), report_format2)
                else:
                    sheet.write(i, 49, '', report_format2)
                    sheet.write(i, 50, '', report_format2)
                sheet.write(i, 51, P004_GastosMedicosExe, currency_format)
                sheet.write(i, 52, P004_GastosMedicosGra, currency_format)
                sheet.write(i, 53, P020_PrimDomExe, currency_format)
                sheet.write(i, 54, P020_PrimDomGra, currency_format)
                sheet.write(i, 55, P021_PrimVacacionalExe, currency_format)
                sheet.write(i, 56, P021_PrimVacacionalGra, currency_format)
                sheet.write(i, 57, P025_IndemnizacionesExe, currency_format)
                sheet.write(i, 58, P025_IndemnizacionesGra, currency_format)
                sheet.write(i, 59, P038_OtrosingresosExe, currency_format)
                sheet.write(i, 60, P038_OtrosingresosGra, currency_format)
                sheet.write(i, 61, D001_SeguroSocial, currency_format)
                sheet.write(i, 62, D002_ISR, currency_format)
                sheet.write(i, 63, OP001_ReintegroISRExceso, currency_format)
                sheet.write(i, 64, OP002_SubsidioEmpleo, currency_format)
                sheet.write(i, 65, OP002_SubsidioCausado, currency_format)
                sheet.write(i, 66, OP003_Viaticos, currency_format)
                sheet.write(i, 67, OP007_ISRAjustadoSubsidio, currency_format)
                sheet.write(i, 68, OP008_SubsidioEfectEnt, currency_format)
                sheet.write(i, 69, Concepto.get('Descripcion'), currency_format)
                sheet.write(i, 70, document.attrib['LugarExpedicion'], currency_format)
            workbook.close()
            xlsx_data = output.getvalue()
            export_id = self.env['wizard.file.download'].create(
                {'file': base64.encodestring(xlsx_data),
                 'name': f_name + '.xlsx'})
            return {
                'view_mode': 'form',
                'res_id': export_id.id,
                'res_model': 'wizard.file.download',
                'type': 'ir.actions.act_window',
                'target': 'new',
            }
        else:
            raise UserError(_('bruto'))
