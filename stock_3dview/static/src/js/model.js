/** @odoo-module alias=stock_3dview.3DViewModel **/

import BaseThreeDModel from "3dview.3DViewModel";

var ThreeDModel = BaseThreeDModel.extend({
    calls: {
        allAreas: "/stock_3dview/get_warehouses",
        allItems: "/stock_3dview/get_locations/all",
        selectedItems: "/stock_3dview/get_locations/",
        legend: "/stock_3dview/get_legend/",
    },
    fields: {
        areaId: "warehouse_id",
    },
});
export default ThreeDModel;
