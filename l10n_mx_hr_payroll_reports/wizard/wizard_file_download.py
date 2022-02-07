# -*- coding: utf-8 -*-

from collections import defaultdict
from datetime import datetime, date, time
import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class WizardFileEmployees(models.TransientModel):
    _name = 'wizard.file.download'
    _description = 'Wizard File Download'

    name = fields.Char('File')
    file = fields.Binary('Download')

