$(document).ready(function() {
    $('.Ot_ShowHidePassword').each(function(ev) {
        var oe_website_login_container = this;
        $(oe_website_login_container).on('click', 'div.input-group-append button.btn.btn-secondary', function() {
            var icon = $(this).find('i.fa.fa-eye').length
            if (icon == 1) {
                $(this).find('i.fa.fa-eye').removeClass('fa-eye').addClass('fa-eye-slash');
                $(this).parent().prev('input[type="password"]').prop('type', 'text');
            } else {
                $(this).find('i.fa.fa-eye-slash').removeClass('fa-eye-slash').addClass('fa-eye');
                $(this).parent().prev('input[type="text"]').prop('type', 'password');
            }
        });
    });
});

odoo.define('ot_website_slides.ot_register_employee_322332', function (require) {
'use strict';

const publicWidget = require('web.public.widget');
var ajax = require('web.ajax');
var core = require('web.core');
var rpc = require('web.rpc');
var session = require('web.session');

publicWidget.registry.otRegisterEmployee = publicWidget.Widget.extend({
    selector: '#ot_web_adresses',
    events: {
        'click .directionAEROMAR': '_getURL',
    },

    _getURL: function () {

        var origin = window.location.href
        console.log("HOLA MUNDO...", origin);
        return ajax.jsonRpc('/registrationhttp', 'call', {
                    'origin': origin,
                    })
                    .then(function (result) {

                    });
    },
});

return publicWidget.registry.otRegisterEmployee;

});