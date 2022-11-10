/** @odoo-module alias=3dview.3DViewModel **/

import ajax from "web.ajax";
import AbstractModel from "web.AbstractModel";

var ThreeDModel = AbstractModel.extend({
    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * This method returns the complete state necessary for the renderer
     * to display the currently viewed data. Since data are stored in the modelData
     * object, it returns an object with a reference to it.
     *
     * @override
     * @returns {*}
     */
    get: function () {
        return {data: this.data};
    },

    /**
     * Initialize the object that stores the data
     *
     * @param {ViewAdapter} parent the view Adapter, a factory class
     * @param {object} context passed at instation from the View with its own this.modelParams
     * @param {string} context.allAreas url endpoint
     * @param {string} context.allItems url endpoint
     * @param {string} context.selectedItems url endpoint
     * @param {string} context.legend url endpoint
     * @param {string} context.areaId The Field name representing the "area" concrete object name
     * @override
     */
    init: function (parent, context) {
        this.calls = {
            allAreas: context.allAreas,
            allItems: context.allItems,
            selectedItems: context.selectedItems,
            legend: context.legend,
        };
        this.fields = {
            areaId: context.areaId,
        };
        this.data = {
            context: context,
            parent: parent,
            areas: {},
            allItems3d: [],
            selectedItems3d: [],
            legendItems: [],
            areasLoaded: false,
            selectedItems3dLoaded: false,
            allItems3dLoaded: false,
            legendLoaded: false,
        };
        this._super.apply(this, arguments);
    },

    /**
     * Load the data from Odoo.
     * The load method is called once in a model, when we load the data for the
     * first time.  The method returns (a deferred that resolves to) some kind
     * of token/handle.  The handle can then be used with the get method to
     * access a representation of the data.
     *
     * @override
     * @param {Object} params
     * @param {string} params.modelName the name of the model
     * @returns {Deferred} The deferred resolves to some kind of handle
     */
    load: async function (params) {
        this.domain = params.domain || this.domain || [];
        this.data.customdata_request_type = params.context.request_type;

        return $.when(
            this._loadAreas(params),
            this._loadAllItems3d(params),
            this._loadSelectedItems3d(params),
            this._loadLegend(params)
        ).then((areasLoaded, allItems3dLoaded, selectedItems3dLoaded, legendLoaded) => {
            this.data.areasLoaded = areasLoaded;
            this.data.allItems3dLoaded = allItems3dLoaded;
            this.data.selectedItems3dLoaded = selectedItems3dLoaded;
            this.data.legendLoaded = legendLoaded;
        });
    },

    /**
     * Reload the selected items3d (e.g. locations and workcenters).
     * Information about the area and all the items3d are not fetched: we already have them
     * When something changes, the data may need to be refetched.  This is the
     * job for this method: reloading (only if necessary) all the data and
     * making sure that they are ready to be redisplayed.
     *
     * @override
     * @param id // this is not documented, but it is passed when called
     * @param {Object} params
     * @returns {Deferred}
     */
    reload: function (id, params) {
        console.log("reload()");
        this.data.selectedItems3dLoaded = false;
        return $.when(this._loadSelectedItems3d(params)).then((selectedItems3dLoaded) => {
            this.data.selectedItems3dLoaded = selectedItems3dLoaded;
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Load the information about the area (e.g. a warehouse or a factory).
     * We assume that an area stores a planimetry and has 3D sizes.
     * It is responsibility of the python controller to filter out areas that don't.
     * This function stores the information in the object this.data.areas, where the key is
     * the id of the area.
     *
     * @param {Object} params
     * @returns {Deferred}
     */
    _loadAreas: function (params) {
        return ajax.jsonRpc(this.calls.allAreas, "call", {domain: []}).then((data) => {
            var items = JSON.parse(data);
            items.forEach((wh) => {
                this.data.areas[wh.id] = wh;
            });
            return true;
        });
    },

    /**
     * Load the information about all the items3d (e.g. locations and workcenters).
     * All the items3d are needed by the renderer for the wireframes.
     * This function stores the information in the object this.data.allItems3d as an array.
     *
     * @param {Object} params
     * @returns {Deferred}
     */
    _loadAllItems3d: function (params) {
        return ajax
            .jsonRpc(this.calls.allItems, "call", {
                domain: [[this.fields.areaId, "!=", false]],
            })
            .then((data) => {
                this.data.allItems3d = JSON.parse(data);
                console.log("received:");
                console.log(this.data.allItems3d);
                return true;
            });
    },

    /**
     * Load the legend.
     *
     * @param {Object} params
     * @returns {Deferred}
     */
    _loadLegend: function (params) {
        let request_type = this.data.customdata_request_type || "tagged";
        return ajax.jsonRpc(this.calls.legend + request_type, "call", {domain: []}).then((data) => {
            this.data.legendItems = JSON.parse(data);
            return true;
        });
    },

    /**
     * Load the information about the selected items3d.
     * This function stores the information in the object this.data.selectedItems3d as an array.
     *
     * @param {Object} params
     * @returns {Deferred}
     */
    _loadSelectedItems3d: function (params) {
        let request_type = this.data.customdata_request_type || "tagged";
        return ajax
            .jsonRpc(this.calls.selectedItems + request_type, "call", {domain: params.domain})
            .then((data) => {
                this.data.selectedItems3d = JSON.parse(data);
                return true;
            });
    },
});
export default ThreeDModel;
