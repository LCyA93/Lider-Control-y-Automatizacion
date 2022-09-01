odoo.define('stock_3dview.3DViewController', function (require) {
    "use strict";

    var ajax = require('web.ajax');
    var core = require('web.core');
    const AbstractController = require('web.AbstractController');

    const ThreeDController = AbstractController.extend({});

    const ThreeDViewController = ThreeDController.extend({

        init: function (parent, context) {
            scope = this;
            this.context = context;
            this._super.apply(this, arguments);
        },

    return ThreeDViewController;
    });

