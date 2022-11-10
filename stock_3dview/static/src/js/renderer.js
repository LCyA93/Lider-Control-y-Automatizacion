odoo.define("stock_3dview.3DViewRenderer", function (require) {
    "use strict";
    const BaseThreeDRenderer = require("3dview.3DViewRenderer");

    var ThreeDViewRenderer = BaseThreeDRenderer.extend({
        messages: {
            noAreaLoaded:
                "No warehouses have been loaded. Please check whether the warehouses have a planimetry image and the dimensions correctly set.",
            noProduct: "No product is stored here.",
        },
        calls: {
            item3dInfo: "/stock_3dview/get_location_info",
            gltf3dModel: "/stock_3dview/get_gltf_3d_model/",
        },
        fields: {
            area: "warehouse",
        },
    });
    return ThreeDViewRenderer;
});
