# -*- coding: utf-8 -*-

from datetime import date

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression

class HrEmployeePrivate(models.Model):  
    _inherit = "hr.employee"
    
    def write(self, vals):
        print ("vals", vals)
        user_id = self.env['res.users'].sudo().search([('login', '=', self.work_email)], limit=1)
        print ("user_id", user_id)
        category = self.env['ir.module.category'].sudo().search([('xml_id', 'in', 'base.module_category_website_elearning')], limit=1)
        print ("category", category)
        print ("category.name", category.name)
        user_group = self.env['res.groups'].sudo().search([('users', 'in', user_id.id),('category_id', 'in', category.id)])
        print ("user_group", user_group)
        res = super(HrEmployeePrivate, self).write(vals)
        print ("self", self.job_id.name)
        return res

  
