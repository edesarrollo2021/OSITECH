odoo.define('payroll_sign.payslip_lot', function (require){

var Widget= require('web.Widget');
var widgetRegistry = require('web.widget_registry');
var framework = require('web.framework');
var FieldManagerMixin = require('web.FieldManagerMixin');
var core = require('web.core');

var _t = core._t;

var SignCFDILot = Widget.extend(FieldManagerMixin, {
    events: {
        'click': 'onClick'
    },

    init: function (parent, model, context){
        this._super(parent);
        this.res_model = model.model;
        this.res_context = model.context;

        this.res_id = model.res_id;
        FieldManagerMixin.init.call(this);
        this._super.apply(this, arguments);
    },
    start: function() {
        var self = this;
        this._super.apply(this, arguments);
        var html = _t('<button type="button" class="btn btn-secondary"><i class="fa fa-file o_button_icon"/>Send to Sign CFDI</button>');
        this.$el.html(html);
        this.$el.css({display: 'inline-block'});
    },

    onClick: function(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        return this.callGenerate();
    },
    generate_options: function() {
        var self = this;
        var options = {
            // start at row 1 = skip 0 lines
            skip: 0,
            limit: 50,
        };

        return options;
    },

    callGenerate: function (kwargs) {
        var opts = this.generate_options();

        this.trigger_up('with_client', {callback: function () {
            this.loading.ignore_events = true;
        }});

        return this._batchedGenerate(opts, kwargs, {done: 0, prev: 0})
            .then(null, function (reason) {
                var error = reason.message;
                var event = reason.event;
                // In case of unexpected exception, convert
                // "JSON-RPC error" to an failure, and
                // prevent default handling (warning dialog)
                if (event) { event.preventDefault(); }

                var msg;
                var errordata = error.data || {};
                if (errordata.type === 'xhrerror') {
                    var xhr = errordata.objects[0];
                    switch (xhr.status) {
                    case 504: // gateway timeout
                        msg = _t("Generate timed out. Please retry.");
                        break;
                    default:
                        msg = _t("An unknown issue occurred during generared (possibly lost connection, data limit exceeded or memory limits exceeded). Please retry in case the issue is transient.");
                    }
                } else {
                    msg = errordata.arguments && (errordata.arguments[1] || errordata.arguments[0])
                        || error.message;
                }

                return Promise.resolve({'messages': [{
                    type: 'error',
                    record: false,
                    message: msg,
                }]});
            });
    },

    _batchedGenerate: function (opts, kwargs, rec){
        opts.callback && opts.callback(rec.done || 0);
        var self = this;
        framework.blockUI();

        return this._rpc({
            model: 'hr.payslip.run',
            method: 'send_to_sign',
            args: [self.res_id, opts],
            context: self.res_context,
        }).then(function (results) {
            framework.unblockUI();
            if (!results.continues) {
                // we're done
                window.location.reload();
                return results;
            }
            // do the next batch
            return self._batchedGenerate(
                opts, kwargs, {
                    done: rec.done + (results.ids || []).length,
                }
            ).then(function (r2) {
                framework.unblockUI();
                return {
                    ids: (results.ids || []).concat(r2.ids || []),
                    messages: results.messages.concat(r2.messages),
                    continues: r2.continues
                }
            });

        });
    },
});

widgetRegistry.add('sign_cfdi_lot', SignCFDILot);

});
