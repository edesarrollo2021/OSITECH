# -*- coding: utf-8 -*-

from datetime import date

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression

class HrEmployeePrivate(models.Model):  
    _inherit = "hr.employee"
    
    def write(self, vals):
        if "job_id" in vals:
            user_id = self.env['res.users'].sudo().search([('login', '=', self.work_email)], limit=1)
            slide_job = self.env['slide.job.positions'].sudo().search([('job_id', '=', vals.get("job_id"))], limit=1)
            group = slide_job.enroll_group_id
            group.write({'users': [[6, False, [user_id.id]]]})
        if "active" in vals:
            print("AAAAA")
            if not vals.get("active"):
                user = self.user_id
                user.update({"active":False})
            elif vals.get("active"):
                user = self.user_id
                user.update({"active":True})
        return super(HrEmployeePrivate, self).write(vals)

  
