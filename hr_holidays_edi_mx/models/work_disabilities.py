# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class LeaveSubcategory(models.Model):
    _name = "hr.leave.subcategory"
    _description = 'Inhability subcategories'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='code', required=True)
    active = fields.Boolean('Active', default=True)

    _sql_constraints = [('code_unique', 'unique(name)', "Code must be unique!")]


class LeaveCategory(models.Model):
    _name = "hr.leave.category"
    _description = 'Inhability categories'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='code', required=True)
    subcategory_ids = fields.Many2many('hr.leave.subcategory',
        'hr_leave_category_subcategory_rel',
        'category_id', 'subcategory_id',
        string='Subcategory')
    active = fields.Boolean('Active', default=True)

    _sql_constraints = [
        ('code_unique', 'unique(name)', "Code must be unique!")]


class LeaveClassification(models.Model):
    _name = "hr.leave.classification"
    _description = 'Classification'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)
    category_ids = fields.Many2many('hr.leave.category',
        'hr_leave_classification_category_rel',
        'classification_id', 'category_id',
        string='Category')
    active = fields.Boolean('Active', default=True)

    _sql_constraints = [
        ('code_unique', 'unique(name)', "Code must be unique!")]


class LaboralInhability(models.Model):
    _name = "hr.leave.inhability"
    _description = 'Inhability type'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)
    classification_ids = fields.Many2many('hr.leave.classification',
        'hr_leave_inhability_classification_rel',
        'inhability_id', 'classification_id',
        string='Classification', )
    active = fields.Boolean('Active', default=True)

    _sql_constraints = [
        ('code_unique', 'unique(name)', "Code must be unique!")]

