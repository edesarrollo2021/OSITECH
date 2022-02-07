odoo.define('import_employees.employee_import', function (require) {
"use strict";

var core = require('web.core');
var BaseImport = require('base_import.import')

var QWeb = core.qweb;
var _t = core._t;
var _lt = core._lt;

var DataImportStmtEmployee = BaseImport.DataImport.extend({
    init: function (parent, action) {
        this._super.apply(this, arguments);
        console.log('')
        action.display_name = _t('Import Employee'); // Displayed in the breadcrumbs
        this.filename = action.params.filename || {};
        this.first_load = true;
    },
    start: function () {
        var self = this;
        return this._super().then(function (res) {
            self.id = self.parent_context.wizard_id;
            self.$('input[name=import_id]').val(self.id);
            self['loaded_file']();
        });
    },
    create_model: function() {
        return Promise.resolve();
    },
    setup_date_format_picker: function () {
        this.$('input.oe_import_date_format').val('YYYY-MM-DD')
    },
    import_options: function () {
        var options = this._super();
        options['employee_stmt_import'] = true;
//        options['limit'] = 2000;
        return options;
    },
    onfile_loaded: function () {
        var self = this;
        if (this.first_load) {
            this.$('.oe_import_file_show').val(this.filename);
            this.$('.oe_import_file_reload').hide();
            this.first_load = false;
            self['settings_changed']();
        }
        else {
            this.$('.oe_import_file_reload').show();
            this._super();
        }
    },
    call_import: function(kwargs) {
        var self = this;
        var superProm = self._super.apply(this, arguments);
        superProm.then(function (message) {
            if(message.ids){
                self.employee_ids = message.ids
            }
            if(message.messages && message.messages.length > 0) {
                self.import_employee_stmt = message.messages[0].import_employee_stmt
            }
        });
        return superProm;
    },
    exit: function () {
        if (!this.import_employee_stmt) return;
        this.do_action({
            name: 'Empleados Creados',
            type: 'ir.actions.act_window',
            res_model: 'hr.employee',
            domain: [['id','in', this.employee_ids]],
            views: [[false, 'list'], [false, 'form']],
            view_mode: 'list,form',
            target: 'current',
        });
    },

});
core.action_registry.add('import_employee_stmt', DataImportStmtEmployee);

return {
    DataImportStmtEmployee: DataImportStmtEmployee,
};
});