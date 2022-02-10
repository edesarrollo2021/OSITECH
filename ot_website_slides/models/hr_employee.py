# -*- coding: utf-8 -*-

from datetime import date

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression

class HrEmployeePrivate(models.Model):  
    _inherit = "hr.employee"
    
    def write(self, vals):
        # ~ print ("vals", vals)
        # ~ user_id = self.env['res.users'].sudo().search([('login', '=', self.work_email)], limit=1)
        # ~ user_group = self.env['res.groups'].sudo().search([('users', 'in', user_id.id),('category_id', 'in', category.id)])
        # ~ res = super(HrEmployeePrivate, self).write(vals)
        return res

  
