# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class Channel(models.Model):
    _inherit = 'slide.channel'

    training_model = fields.Selection([('online', 'Virtual'), 
                                        ('face', 'Presencial'),
                                        ('mixta', 'Mixta')],string="Modelo de formación", default="online", required=True)
    constancy = fields.Selection([('constancy', 'Constancia'), 
                                  ('certificate', 'Certificado')], string="Documento", default="certificate", required=True)
    general_objective = fields.Text('Objetivo general')
    descriptive_picture = fields.Binary(string="Imagen descriptiva")
    user_id = fields.Many2one('res.users', string='Instructor', default=lambda self: self.env.uid)
    vigencia = fields.Char(string="Vigencia")
    duration = fields.Char(string="Periodicidad")
    year = fields.Integer(string="Años")
    month = fields.Integer(string="Meses")
    duration_hours = fields.Char(string="Duración")
    days = fields.Integer(string="Días")
    hours = fields.Integer(string="Horas")
    minutes = fields.Integer(string="Minutos")
    channel_type_mx = fields.Selection([('inicial', 'Inicial'),
                                    ('formativo', 'Formativo'),
                                    ('inducción', 'Inducción'),
                                    ('familiarización', 'Familiarización'),
                                    ('recurrente', 'Recurrente'),
                                    ('mandatorio', 'Mandatorio'),
                                    ('otro', 'Otro')], string="Tipo", default="inducción", required=True)
    type_course_ids = fields.One2many('type.course', 'course_id', 'Evaluacion')
    life_plan_resource = fields.Binary(string="Icono del curso")
    complementary = fields.Boolean(string="Complementario")

    @api.onchange('hours','minutes')
    def duration_hours_completed(self):
        self.duration_hours = ''
        if self.hours:
            self.duration_hours += str(self.hours) + " Horas "
        if self.minutes:
            self.duration_hours += str(self.minutes) + " Minutos "
            
    @api.onchange('year','month', 'days')
    def duration_completed(self):
        self.duration = ''
        if self.year:
            self.duration += str(self.year) + " Años "
        if self.month:
            self.duration += str(self.month) + " Meses "
        if self.days:
            self.duration += str(self.days) + " Días "
            
    @api.onchange('minutes')
    def duration_hours_user_error(self):
        if self.minutes >= 60:
            raise UserError("Los minutos no pueden ser igual o mayor 60 ya que esto se representa en Horas")
            
    @api.onchange('month','days')
    def duration_user_error(self):
        if self.month >= 12:
            raise UserError("Los Meses no deben de ser igual o mayor a 12 ya que esto se representa con Años")
        if self.days >= 31:
            raise UserError("Los Días no deben de ser igual o mayor a 31 ya que esto se representa con Meses")
            
            
    @api.onchange('enroll_group_ids')
    def slide_visibility(self):
        if self.enroll_group_ids:
            self.visibility = 'members'
        
            
    @api.onchange('visibility')
    def slide_visibility_public(self):
        if self.visibility == 'public':
            self.enroll_group_ids = False
            
    @api.onchange('type_course_ids')
    def _validate_field_type_course_ids(self):
        type_course_ids = self.type_course_ids
        total = 0
        if type_course_ids:
            for type_course in type_course_ids:
                total += type_course.percentage
        if total > 100:
            raise UserError("El porcentaje de calificacón no puede superar el 100%")

    def write(self, vals):
        if 'type_course_ids' in vals:
            type_course_ids = vals.get('type_course_ids')
            total = 0
            des_nam = []
            del_rec = []
            for type_course in type_course_ids:
                val_des = ""
                val_per = 0
                if type_course[0] == 0:
                    val_des = type_course[2].get('description')
                    val_per = type_course[2].get('percentage')
                    if not val_des:
                        raise UserError("No puede dejar descripciones vacías en la calificación del curso.")
                    if val_per < 1:
                        raise UserError("No puede registrar calificaciones en porcentaje inferiores a un 1%.")
                    if val_des in des_nam:
                        raise UserError("La calificación (%s) ha sido agregada en más de una ocasión." % val_des)
                    des_nam.append(val_des)
                    total += type_course[2].get('percentage')
                elif type_course[0] == 1:
                    if 'percentage' in type_course[2]:
                        total += type_course[2].get('percentage')
                    else:
                        record = self.env['type.course'].search([('id', '=', type_course[1])])
                        total += record.percentage
                elif type_course[0] == 2:
                    del_rec.append(type_course[1])
                elif type_course[0] == 4:
                    record = self.env['type.course'].search([('id', '=', type_course[1])])
                    if record.description in des_nam:
                        raise UserError("La calificación %s ha sido agregada en más de una ocasión." % val_des)
                    des_nam.append(record.description)
                    total += record.percentage
            if len(del_rec) == len(type_course_ids):
                pass
            else:
                if total < 100:
                    raise UserError("La calificación total debe ser igual al 100%")
        return super(Channel, self).write(vals)


class TypeCourse(models.Model):
    _name = 'type.course'

    course_id = fields.Many2one('slide.channel', string="Course")
    percentage = fields.Integer('Porcentaje')
    description = fields.Selection([('Participación', 'Participación'),
                                    ('Foros', 'Foros'),
                                    ('Ejercicios', 'Ejercicios'),
                                    ('Prácticas', 'Prácticas'),
                                    ('Tareas', 'Tareas'),
                                    ('Examen', 'Examen')], string="Descripción")
