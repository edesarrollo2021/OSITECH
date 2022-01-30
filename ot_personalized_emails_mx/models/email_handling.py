# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ChannelUsersRelation(models.Model):
    _inherit = 'slide.channel.partner'

    @api.model
    def create(self, vals):
        if 'partner_id' in vals:
            partner = self.env['res.partner'].search([('id', '=', vals.get('partner_id'))])
            slide_channel = self.env['slide.channel'].search([('id', '=', vals.get('channel_id'))])
            company = self.env.user.company_id
            obj_user = self.env.user
            render_context = {
                "company": company,
                "channel": self,
                "obj_user": obj_user,
                "course_name": slide_channel.name,
            }
            template = self.env.ref('ot_personalized_emails_mx.ot_email_template_welcome')
            mail_body = template._render(render_context, engine='ir.qweb', minimal_qcontext=True)
            mail_body = self.env['mail.render.mixin']._replace_local_links(mail_body)
            mail = self.env['mail.mail'].sudo().create({
                'subject': "Bienvenido al curso: %s" % slide_channel.name,
                'email_from': company.catchall_formatted or company.email_formatted,
                'author_id': self.env.user.partner_id.id,
                'email_to': partner.email,
                'body_html': mail_body,
            })
            mail.send()

        return super(ChannelUsersRelation, self).create(vals)

    def write(self, vals):
        if 'completed' in vals:
            if vals.get('completed') == True:
                company = self.env.user.company_id
                obj_user = self.env.user
                render_context = {
                    "company": company,
                    "channel": self,
                    "obj_user": obj_user,
                }
                template = self.env.ref('ot_personalized_emails_mx.ot_email_template_type_b_certificate')
                mail_body = template._render(render_context, engine='ir.qweb', minimal_qcontext=True)
                mail_body = self.env['mail.render.mixin']._replace_local_links(mail_body)
                mail = self.env['mail.mail'].sudo().create({
                    'subject': "Felicidades has completado el curso: %s" % self.channel_id.name,
                    'email_from': company.catchall_formatted or company.email_formatted,
                    'author_id': self.env.user.partner_id.id,
                    'email_to': self.partner_id.email,
                    'body_html': mail_body,
                })
                mail.send()

        return super(ChannelUsersRelation, self).write(vals)
