/** @odoo-module alias=3dview.3DViewController **/

import ajax from "web.ajax";
import AbstractController from "web.AbstractController";

const ThreeDViewController = AbstractController.extend({
    init: function (parent, model, renderer, params) {
        // Commented as unused
        // const domain = this.context.domain.length > 0 ? this.context.domain[0] : null;
        this._super.apply(this, arguments);
        this.countdownInterval = null;
        const settingsRoute = params.settingsRoute ?? "";

        if (settingsRoute !== "") {
            ajax.jsonRpc(settingsRoute, "call", {domain: []}).then((data) => {
                let settings = JSON.parse(data);
                let refreshPeriod = parseInt(settings["refresh_period"], 10);

                if (refreshPeriod > 0) {
                    let secondsToWait = refreshPeriod;
                    this.countdownInterval = setInterval(() => {
                        $("#refresh_countdown").text(--secondsToWait);
                        if (secondsToWait == 0) {
                            console.log("**** reloading ****");
                            // console.log(domain);
                            this.reload();
                            secondsToWait = refreshPeriod;
                        }
                    }, 1000);
                }
            });
        }
    },

    /**
     * @override
     */
    destroy: function () {
        clearInterval(this.countdownInterval);
        this._super.apply(this, arguments);
    },
});

export default ThreeDViewController;
