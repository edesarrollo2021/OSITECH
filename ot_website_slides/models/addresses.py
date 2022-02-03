# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class Addresses(models.Model):
    _name = 'slide.addresses'

    name = fields.Char("Direcciones", required=True)
    image = fields.Binary(string="Imagen", required=True)
    job_positions_ids = fields.One2many('slide.job.positions', 'addresses_id', string="Puestos de trabajo", required=True)

class JobPositions(models.Model):
    _name = 'slide.job.positions'

    name = fields.Char("Puestos de trabajo", required=True)
    image = fields.Binary(string="Imagen", required=True)
    addresses_id = fields.Many2one('slide.addresses', string="Direcciones")
    order_by = fields.Float("Order")
    
