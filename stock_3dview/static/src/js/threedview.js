/** @odoo-module alias=stock_3dview.ThreeDView **/

import AbstractView from "web.AbstractView";
import core from "web.core";
import RendererWrapper from "web.RendererWrapper";
import view_registry from "web.view_registry";

import ThreeDViewController from "stock_3dview.3DViewController";
import ThreeDModel from "stock_3dview.3DViewModel";
import OWL3DViewRenderer from "stock_3dview.OWL3DViewRenderer";

// Old version of the code
// const AbstractRenderer = require("stock_3dview.3DViewRenderer");
// const ThreeDRenderer = AbstractRenderer.extend({});
// const ThreeDController = AbstractController.extend({});
// const ThreeDModel = AbstractModel.extend({});
const _lt = core._lt;

const ThreeDView = AbstractView.extend({
    display_name: _lt("3D"),
    icon: "fa-cubes",
    config: _.extend({}, AbstractView.prototype.config, {
        Model: ThreeDModel,
        Controller: ThreeDViewController,
        Renderer: OWL3DViewRenderer,
    }),
    viewType: "threedview",
    searchMenuTypes: ["filter", "favorite"],

    init: function (viewInfo, params) {
        this._super.apply(this, arguments);
        const {
            allAreas,
            allItems,
            selectedItems,
            legend,
            areaId,
            settings,
            item3dInfo,
            gltf3dModel,
            rendererArea,
            noAreaLoaded,
            noProduct,
        } = this.arch.attrs;
        Object.assign(this.modelParams, {allAreas, allItems, selectedItems, legend, areaId});
        this.controllerParams.settingsRoute = settings;
        Object.assign(this.rendererParams, {
            item3dInfo,
            gltf3dModel,
            rendererArea,
            noAreaLoaded,
            noProduct,
        });
    },

    _deriveActiveAreaIdFromContext(context) {
        let activeAreaId = undefined;
        if (
            context &&
            context.active_id &&
            context.active_model &&
            context.active_model == "stock.warehouse"
        ) {
            activeAreaId = context.active_id;
        }
        return activeAreaId;
    },

    getRenderer(parent, state) {
        let activeAreaId = this._deriveActiveAreaIdFromContext(this.loadParams.context);
        state = Object.assign(state || {}, this.rendererParams, {activeAreaId});
        return new RendererWrapper(parent, this.config.Renderer, state);
    },
});

view_registry.add("threedview", ThreeDView);

export default ThreeDView;
