odoo.define('hr_portal_mx.holidays', function (require) {
'use strict';

var core = require('web.core');
var publicWidget = require('web.public.widget');
var session = require('web.session');
var ajax = require('web.ajax');

var qweb = core.qweb;


publicWidget.registry.HolidaysSubmit = publicWidget.Widget.extend({
    selector: '.o_portal_reason_reject_submit',
    events: {
        'click': '_onClick',
    },
    _onClick: function (event) {
        var $request_form = $('#HolidaysRequestForm');
        var $input_state = $request_form.find('#state_input');
        var $reason_reject = $request_form.find('#reason_reject');
        var $description_reject = $request_form.find('#description_reject');
        $input_state.val('refuse');

        var reason_reject = $('#reason_rejects_form').find('.reason_id').val();
        $reason_reject.val(reason_reject);
        var description = $('#reason_rejects_form').find('.description').val();
        $description_reject.val(description);

        $('.close').click();
        $request_form.find('.o_website_form_send').click();
    },
});


publicWidget.registry.HolidaysCancellation = publicWidget.Widget.extend({
    selector: '.o_portal_reason_cancel_submit',
    events: {
        'click': '_onClick',
    },
    _onClick: function (event) {
        var $request_form = $('#HolidaysCancellationForm');
        var $input_state = $request_form.find('#state_input');
        var $description_cancellation = $request_form.find('#description_cancellation');
        $input_state.val('cancel');

        var description = $('#reason_cancel_form').find('.description').val();
        $description_cancellation.val(description);

        $('.close').click();
        $request_form.find('.o_website_form_send').click();
    },
});


publicWidget.registry.RejectCancellation = publicWidget.Widget.extend({
    selector: '.o_portal_reject_cancel_submit',
    events: {
        'click': '_onClick',
    },
    _onClick: function (event) {
        var $request_form = $('#HolidaysCancellationForm');
        var $description_cancellation = $request_form.find('#description_cancellation');

        var description = $('#reject_cancel_form').find('.description').val();
        $description_cancellation.val(description);

        $('.close').click();
        $request_form.find('.o_website_form_send').click();
    },
});


publicWidget.registry.HolidaysForm = publicWidget.Widget.extend({
    selector: '#holidayForm',
    read_events: {
        'change #holiday_status_id': '_onChangeHolidayStatus',
        'change #dateFrom': '_onChangeHolidayDates',
        'change #dateTo': '_onChangeHolidayDates',
    },
    start: function(){
        this.ElementSelect= $('#holiday_status_id');
        this.id_holiday_type = this.ElementSelect.val();
        this.ElementDateFrom =  $('#dateFrom')
        this.ElementDateTo =  $('#dateTo')
        this.user_id = session.user_id;
        this.date_from = false;
        this.date_to = false;
    },
    _onChangeHolidayStatus: function(){
        this.id_holiday_type = this.ElementSelect.val();
        return this._getDaysAvailable(this.id_holiday_type, this.date_from, this.date_to);
    },
    _onChangeHolidayDates: function(ev){
        this.date_from = $('input[name=request_date_from]').val();
        this.date_to = $('input[name=request_date_to]').val();
        return this._getDaysAvailable(this.id_holiday_type, this.date_from, this.date_to);
    },
    _getDaysAvailable: function(id_holiday_type, date_from, date_to){
        return ajax.jsonRpc('/holidays/get_available_days_holidays', 'call', {
            model: 'hr.leave',
            holiday_type_id: id_holiday_type,
            date_from: date_from,
            date_to: date_to,
            method: 'get_available_days_holidays',
        })
        .then(function (result) {
                var $alert = $('.holidays_remaining');
                var templates_loaded = ajax.loadXML('/hr_portal_mx/static/src/xml/portal_mexico.xml', qweb);
                if(result.error){
                    templates_loaded.then(function () {
                        $alert.replaceWith(qweb.render("hr_portal_mx.status_alert_warning", {
                            responseText : result.error
                        }));
                    });
                }else{
                    templates_loaded.then(function () {
                        $alert.replaceWith(qweb.render("hr_portal_mx.status_alert_info", {
                            responseText : result
                        }));
                    });
                }
        });
    },
});

});