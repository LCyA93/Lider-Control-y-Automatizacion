odoo.define('stock_3dview.3DViewModel', function (require) {
    "use strict";
    const ajax = require('web.ajax');
    const AbstractModel = require('web.AbstractModel');

    /** This object stores the information needed by the renderer:
     * it will be updated when the user changes the selection of locations.
     */    
    var modelData = {};
    
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
            return {
                data: modelData  // data are taken from the object modelData defined above
            };
        },

        /**
         * Initialize the object that stores the data
         *
         * @override
         */
        init: function (parent, context) {
            modelData.parent = parent;
            modelData.warehouses = {};
            modelData.allLocations = [];
            modelData.selectedLocations = [];
            modelData.legendItems = [];
            modelData.warehousesLoaded = false;
            modelData.selectedLocationsLoaded = false;
            modelData.allLocationsLoaded = false;
            modelData.legendLoaded = false;
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
            var self = this;
            /*
            this.modelName = params.modelName;
            this.fieldNames = params.fieldNames;

            if (!this.preload_def) {
                this.preload_def = $.Deferred();
                $.when(
                    this._rpc({model: this.modelName, method: 'check_access_rights', args: ["write", false]}),
                    this._rpc({model: this.modelName, method: 'check_access_rights', args: ["unlink", false]}),
                    this._rpc({model: this.modelName, method: 'check_access_rights', args: ["create", false]})
                ).then(function (write, unlink, create) {
                    self.write_right = write;
                    self.unlink_right = unlink;
                    self.create_right = create;
                    self.preload_def.resolve();
                });
            }
            */
            
            modelData.customdata_request_type = sessionStorage.getItem('customdata_request_type');
            sessionStorage.removeItem('customdata_request_type');
            
            return $.when(
                this._loadWarehouses(params),
                this._loadAllLocations(params),
                this._loadSelectedLocations(params),
                this._loadLegend(params)
            ).then(function (warehousesLoaded, allLocationsLoaded, selectedLocationsLoaded, legendLoaded) {
                modelData.warehousesLoaded = warehousesLoaded;
                modelData.allLocationsLoaded = allLocationsLoaded;
                modelData.selectedLocationsLoaded = selectedLocationsLoaded;
                modelData.legendLoaded = legendLoaded;
            });
        },

        /**
         * Reload the selected locations.
         * Information about the warehouse and all the locations are not fetched: we already have them
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
            //console.log("reload()");
            modelData.selectedLocationsLoaded = false;
            return $.when(
                this._loadSelectedLocations(params)
            ).then(function(selectedLocationsLoaded) {
                modelData.selectedLocationsLoaded = selectedLocationsLoaded;
            })
        },

        //--------------------------------------------------------------------------
        // Private
        //--------------------------------------------------------------------------

        /**
         * Load the information about the warehouse.
         * We assume that a warehouse stores a planimetry and has 3D sizes.
         * It is responsibility of the python controller to filter out warehouses that don't.
         * This function stores the information in the object modelData.warehouses, where the key is
         * the id of the warehouse.
         *
         * @param {Object} params
         * @returns {Deferred}
         */
        _loadWarehouses: function (params) {
            return ajax.jsonRpc("/3dview/get_warehouses", 'call', { 'domain': [] }).then(function(data) {
                var items = JSON.parse(data);
                //console.log(items);
                items.forEach(function(wh) {
                    modelData.warehouses[wh.id] = wh;
                });
                return true;
            });
        },

        /**
         * Load the information about all the locations.
         * All the locations are needed by the renderer for the wireframes.
         * This function stores the information in the object modelData.allLocations as an array.
         *
         * @param {Object} params
         * @returns {Deferred}
         */
        _loadAllLocations: function (params) {
            return ajax.jsonRpc("/3dview/get_locations/all", 'call', { 'domain': [['usage','=','internal']] }).then(function(data) {
                modelData.allLocations = JSON.parse(data);
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
            let request_type = modelData.customdata_request_type || 'tagged';
            return ajax.jsonRpc("/3dview/get_legend/" + request_type, 'call', { 'domain': [] }).then(function(data) {
                modelData.legendItems = JSON.parse(data);
                return true;
            });
        },

        /**
         * Load the information about the selected locations.
         * This function stores the information in the object modelData.selectedLocations as an array.
         *
         * @param {Object} params
         * @returns {Deferred}
         */
        _loadSelectedLocations: function (params) {
            let request_type = modelData.customdata_request_type || 'tagged';
            return ajax.jsonRpc("/3dview/get_locations/"+request_type, 'call', { 'domain': params.domain  }).then(function(data) {
                modelData.selectedLocations = JSON.parse(data);
                //console.log('selected locations:');
                //console.log(modelData.selectedLocations);
                return true;
            });
        },
        
    });
    return ThreeDModel;
});
