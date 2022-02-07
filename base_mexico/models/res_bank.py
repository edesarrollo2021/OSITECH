# -*- coding: utf-8 -*-

from odoo import fields, models, api, _



class resBank(models.Model):
    _inherit = "res.bank"
    
    business_name = fields.Char("Business name", copy=False, required=False)
    clabe = fields.Char("Clabe", copy=False, required=False)
    code = fields.Char("Code", copy=False, required=False)
    number = fields.Char("No. Inst.", copy=False, required=False)
