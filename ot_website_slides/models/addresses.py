# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class Addresses(models.Model):
    _name = 'slide.addresses'
    
    def _compute_instructions(self):
        self.instructions = 'hola mundo 1'

    direction_id = fields.Many2one('hr.department', string="Direcciones", domain=[('elearning', '=', True)])
    image = fields.Binary(string="Imagen", required=True)
    job_positions_ids = fields.One2many('slide.job.positions', 'addresses_id', string="Puestos de trabajo", required=True)
    instructions = fields.Text(string='Instrucciones', compute='_compute_instructions', readonly=True)

class JobPositions(models.Model):
    _name = 'slide.job.positions'
    _order = 'order_by asc'

    job_id = fields.Many2one('hr.job', string="Puestos de trabajo", required=True)
    image = fields.Binary(string="Imagen", required=True)
    addresses_id = fields.Many2one('slide.addresses', string="Direcciones")
    order_by = fields.Float("Order")
    enroll_group_id = fields.Many2one('res.groups', string='Suscribir grupo', required=True)
    
    
