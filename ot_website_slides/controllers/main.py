# -*- coding: utf-8 -*-

import ast
import collections

from odoo import http, models, fields, _
from odoo.http import request
from odoo.addons.portal.controllers.web import Home
from odoo.addons.http_routing.models.ir_http import slug

from odoo.addons.web.controllers.main import Home
from odoo.exceptions import UserError


class Home(Home):

    @http.route()
    def index(self, *args, **kw):
        if request.session.uid and not request.env['res.users'].sudo().browse(request.session.uid).has_group('base.group_user'):
            return http.local_redirect('/home', query=request.params, keep_hash=True)
        return super(Home, self).index(*args, **kw)

    def _login_redirect(self, uid, redirect=None):
        if not redirect and not request.env['res.users'].sudo().browse(uid).has_group('base.group_user'):
            redirect = '/home'
        return super(Home, self)._login_redirect(uid, redirect=redirect)

    @http.route('/web', type='http', auth="none")
    def web_client(self, s_action=None, **kw):
        if request.session.uid and not request.env['res.users'].sudo().browse(request.session.uid).has_group('base.group_user'):
            return http.local_redirect('/home', query=request.params, keep_hash=True)
        return super(Home, self).web_client(s_action, **kw)


class Website(Home):

    @http.route('/web/login', type='http', auth="public", website=True, sitemap=True)
    def index(self, redirect=None, **kw):
        param_obj = request.env['ir.config_parameter'].sudo()
        request.params['disable_footer'] = ast.literal_eval(param_obj.get_param('login_form_disable_footer')) or False
        request.params['disable_database_manager'] = ast.literal_eval(
            param_obj.get_param('login_form_disable_database_manager')) or False
        change_background = ast.literal_eval(param_obj.get_param('login_form_change_background_by_aeromar')) or False
        if change_background:
            request.params['background_src'] = param_obj.get_param('login_form_background_aeromar') or ''
        else:
            request.params['background_src'] = param_obj.get_param('login_form_background_default') or ''
        return super(Website, self).web_login(redirect, **kw)

    @http.route('/', type='http', auth="public", website=True, sitemap=True)
    def index_welcome_aeromar(self, redirect=None, **kw):
        uid = request.session.uid
        if not uid:
            return request.render("ot_website_slides.ot_template_welcome_aeromar")
        else:
            return request.render("ot_website_slides.ot_webHome")

class WebsiteUserRegister(http.Controller):

    @http.route('/web/registration', type='http', auth="public", website=True)
    def ot_met_web_user_register(self, redirect=None, **kw):
        pasw_true = True
        email = kw.get('email')
        email3 = kw.get('email3')
        employe = request.env['hr.employee'].sudo().search([('work_email', '=', email)], limit=1)
        employe_one = request.env['hr.employee'].sudo().search([('work_email', '=', email3)], limit=1)
        print("employe", employe)
        pasw = kw.get('pasw') or ''
        repeat_pasw = kw.get('repeat_pasw') or ''
        if pasw == repeat_pasw and pasw != '' and repeat_pasw != '':
            vals_list = [{'employee_ids': [], 
            'is_published': False, 
            'name': employe_one.name, 
            'email': employe_one.work_email, 
            'login': employe_one.work_email,
            'password': pasw,
            'company_ids': [[6, False, [1]]], 
            'company_id': 1, 
            'sel_groups_1_9_10': 9, 
            'active': True,
            'action_id': False, 'notification_type': 'email',
            'signature': '<p style="margin:0px;font-size:13px;font-family:&quot;Lucida Grande&quot;, Helvetica, Verdana, Arial, sans-serif;"><br></p>', 
            'karma': 0, 
            'livechat_username': False}] 
            user = request.env['res.users']
            user.sudo().create(vals_list)
            user = request.env['res.users'].sudo().search([('login', '=', email3)], limit=1)
            employe = request.env['hr.employee'].sudo().search([('work_email', '=', email3)], limit=1)
            print("user", user)
            print("employe", employe)
            employe.write({"user_id": user.id})
            return http.local_redirect('/web/login', query=request.params, keep_hash=True)
        if pasw != '' and repeat_pasw != '' and pasw != repeat_pasw:
            pasw_true = False
        values = {
            'employe': employe,
            'email': email,
            'pasw_true': pasw_true,
        }
        return request.render("ot_website_slides.ot_web_user_register", values)

class WebsiteAdresses(http.Controller):

    @http.route('/direcciones', type='http', auth="public", website=True)
    def ot_adresses_mx(self, redirect=None, **kw):
        name_adresse = []
        addresses = request.env['slide.addresses'].sudo().search([])
        for add in addresses:
            name_adresse.append(add.id)
        values = {
            'addresses': addresses,
            'name_adresse': name_adresse,
        }
        return request.render("ot_website_slides.ot_web_adresses", values)
        
    @http.route('/miplandevidaycarrera', type='http', auth="public", website=True)
    def ot_my_life_mx(self, redirect=None, **kw):
        uid = request.session.uid
        if uid:
            employe = request.env['hr.employee'].sudo().search([('user_id', '=', uid)], limit=1)
            values = {
            "job_pos": employe.job_id.id
            }
            return request.render("ot_website_slides.ot_web_my_life", values)

    @http.route('/adresses_mx', type='json', auth="public", website=True)
    def ot_met_web_user_register(self, redirect=None, **kw):
        id_add = kw.get("id")
        addresses = request.env['slide.addresses'].sudo().search([('id', '=', id_add)], limit=1)
        name_job = []
        image_job = []
        position_job = []
        list_pos = []
        list_id = []
        for job in addresses:
            for name in job.job_positions_ids:
                name_job.append(name.job_id.name)
                image_job.append(name.image)
                list_id.append(name.id)
                position_job.append(str(name.order_by)[0])
        counter = collections.Counter(position_job)
        clients_sort = sorted(counter.items())
        for val in clients_sort:
            val_1 = val[1]
            for dato in range(val_1):
                list_pos.append(val_1)

        values = {
            'name_job': name_job,
            'image_job': image_job,
            'position_job': position_job,
            'list_id': list_id,
            'name_addresses': addresses.direction_id.name,
            'image_addresses': addresses.image,
            'list_pos': list_pos
        }
        return values
        
    @http.route('/my_life_mx', type='json', auth="public", website=True)
    def ot_my_life_mx_register(self, redirect=None, **kw):
        id_add = kw.get("id")
        job_position = request.env['slide.job.positions'].sudo().search([('id', '=', id_add)], limit=1)
        members = request.env['slide.channel'].sudo().search([('enroll_group_ids', 'in', job_position.enroll_group_id.id)])
        slide_public = request.env['slide.channel'].sudo().search([('visibility', '=', 'public')])
        mandatarios = {}
        public_courses = {}
        name = ""
        acronym = ""

        for public in slide_public:
            image = public.image_1920 or False
            if "|" in public.name:
                position_I = public.name.find('|')
                name = str(public.name)[position_I +1:]
                acronym = str(public.name)[0: position_I]
            else:
                name = public.name
                acronym = False
            public_courses[public.id] = [image, acronym, name]

        for member in members:
            image = member.image_1920 or False
            if "|" in member.name:
                position_I = member.name.find('|')
                name = str(member.name)[position_I +1:]
                acronym = str(member.name)[0: position_I]
            else:
                name = member.name
                acronym = False
            mandatarios[member.id] = [image, acronym, name]

        values = {
        'image': job_position.addresses_id.image,
        'name': job_position.job_id.name,
        'slide_public': slide_public,
        'mandatarios': mandatarios,
        'public_courses': public_courses,
        }

        print("*******************/*/*/*/*/*/*/*")
        print("*******************/*/*/*/*/*/*/*")
        print("*******************/*/*/*/*/*/*/*")

        return values

    @http.route('/controller_my_life_mx', type='json', auth="public", website=True)
    def ot_controller_my_life_mx_register(self, redirect=None, **kw):
        user_id = request.session.uid
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', user_id)], limit=1)
        job_position = request.env['slide.job.positions'].sudo().search([('id', '=', employee.job_id.id)], limit=1)
        members = request.env['slide.channel'].sudo().search(
            [('enroll_group_ids', 'in', job_position.enroll_group_id.id)])
        slide_public = request.env['slide.channel'].sudo().search([('visibility', '=', 'public')])
        mandatarios = {}
        public_courses = {}
        name = ""
        acronym = ""

        print('\nemployee.job_id', employee.job_id.id)
        print("\njob_position::: ", job_position.job_id.id)
        print("\njob_position.enroll_group_id.id::: ", job_position.id)
        print("\njob_position.enroll_group_id.id::: ", job_position.id)
        print("\nmembers::: ", members)

        for public in slide_public:
            image = public.image_1920 or False
            if "|" in public.name:
                position_I = public.name.find('|')
                name = str(public.name)[position_I + 1:]
                acronym = str(public.name)[0: position_I]
            else:
                name = public.name
                acronym = False
            public_courses[public.id] = [image, acronym, name]

        for member in members:
            image = member.image_1920 or False
            if "|" in member.name:
                position_I = member.name.find('|')
                name = str(member.name)[position_I + 1:]
                acronym = str(member.name)[0: position_I]
            else:
                name = member.name
                acronym = False
            mandatarios[member.id] = [image, acronym, name]

        print("\nmandatarios:::", mandatarios)

        values = {
            'image': job_position.addresses_id.image,
            'name': job_position.job_id.name,
            'slide_public': slide_public,
            'mandatarios': mandatarios,
            'public_courses': public_courses,
        }

        print("*******************/*/*/*/*/*/*/*")
        print("*******************/*/*/*/*/*/*/*")
        print("*******************/*/*/*/*/*/*/*")

        print(":D  :D  :D  :D  :D  :D  :D  ")
        print(":D  :D  :D  :D  :D  :D  :D  ")

        return values


