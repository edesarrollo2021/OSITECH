odoo.define('hr_employe_mexico.ActionManager', function (require) {
"use strict";

/**
 * The purpose of this file is to add the support of Odoo actions of type
 * 'ir_actions_account_report_download' to the ActionManager.
 */

var ActionManager = require('web.ActionManager');
var framework = require('web.framework');
var session = require('web.session');

ActionManager.include({
    _executeEmployeeReportDownloadAction: function (action) {
        var self = this;
        framework.blockUI();

        return new Promise(function (resolve, reject) {
            session.get_file({
                url: '/employee_reports',
                data: action.data,
                success: resolve,
                error: (error) => {
                    self.call('crash_manager', 'rpc_error', error);
                    reject();
                },
                complete: framework.unblockUI,
            });
        });
    },
    _handleAction: function (action, options) {
        if (action.type === 'ir_actions_employee_report_download') {
            return this._executeEmployeeReportDownloadAction(action, options);
        }
        return this._super.apply(this, arguments);
    },
});

});
