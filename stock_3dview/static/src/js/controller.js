/** @odoo-module alias=stock_3dview.3DViewController **/

import BaseThreeDController from "3dview.3DViewController";

var ThreeDViewController = BaseThreeDController.extend({
    config: {
        calls: {
            settings: "/stock_3dview/get_settings",
        },
    },
});

export default ThreeDViewController;
