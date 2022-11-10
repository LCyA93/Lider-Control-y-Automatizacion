odoo.define("3dview.3DViewRenderer", function (require) {
    "use strict";

    var ajax = require("web.ajax");
    var core = require("web.core");
    var AbstractRenderer = require("web.AbstractRenderer");
    var data_manager = require("web.data_manager");
    var session = require("web.session");
    var view_registry = require("web.view_registry");
    var _lt = core._lt;
    const QWeb = require("web.QWeb");

    var container; // the DOM object where the scene is rendered
    var scope; // a global object used to store all the data needed

    var ThreeDViewRenderer = AbstractRenderer.extend({
        messages: {
            noAreaLoaded:
                "No areas have been loaded. Please check whether the areas have a planimetry image and the dimensions correctly set.",
            noProduct: "No product.",
        },

        calls: {
            item3dInfo: "/3dview/get_item3d_info",
            gltf3dModel: "/3dview/get_gltf_3d_model/",
        },

        fields: {
            area: "area",
        },

        template: "3DView",

        /**
         * @constructor
         * @override
         * @param {Widget} parent
         * @param {any} state
         * @param {Object} params
         * @param {string} [params.noContentHelp]
         */
        init: function (parent, state, params) {
            this._super.apply(this, arguments);
            scope = this;
            scope.areaObjects = {
                wireframes: [], // for all items3d
                meshes: [], // for selected items3d
                gltfModels: [], // for rendered GLTF models
                gltfObjects: {}, // a container of GLTF objects and their accessories
            };
            scope.currentArea = null;
            this.context = {};
            this.loader = new THREE.ObjectLoader(); // see https://threejs.org/docs/#api/en/loaders/ObjectLoader
            this.GLTFLoader = new THREE.GLTFLoader(); // testing...
        },

        //--------------------------------------------------------------------------
        // Private
        //--------------------------------------------------------------------------

        /**
         * Render the view.
         * Before rendering, we must wait for data to be loaded and threejs renderer
         * to be ready.
         * (Expecially for the latter, it doesn't seem possible to use promises, so
         * we use the little hack of waiting until rendering is possible)
         *
         * When everything is ready, init3d() creates an instance of the renderer.
         * Since _render() is called everytime a new filter is applied, we check if there
         * is already an instance before creating a new one.
         *
         * @override
         * @private
         * @returns {Deferred}
         */
        _render: function () {
            var waiting = setInterval(function () {
                if (
                    scope.state.data.allItems3dLoaded &&
                    scope.state.data.selectedItems3dLoaded &&
                    scope.state.data.areasLoaded &&
                    scope.state.data.legendLoaded
                ) {
                    if (!scope.renderer) {
                        // we will use the first area for the first rendering
                        scope.currentArea = scope.state.data.areas[Object.keys(scope.state.data.areas)[0]];
                        if (scope.currentArea) {
                            scope._initRefSys(scope.currentArea);
                            scope.init3d();
                            scope._addEventHandlers();
                            scope.showWireframesForAllItems3d();
                        } else {
                            scope._showInformationDialog(this.messages.noAreaLoaded);
                        }
                    }

                    scope.currentArea && scope.showMeshesForSelectedItems3d();
                    $("#loading_icon").hide();
                    clearInterval(waiting);
                }
            }, 20);
            /*return $.when();*/
            return Promise.resolve();
        },

        /**
         * Initialize threejs world
         *
         * @private
         */
        init3d: function () {
            //console.log("initializing 3d...");
            // camera
            scope.camera = new THREE.PerspectiveCamera(
                scope.refSys.camFov,
                window.innerWidth / window.innerHeight,
                1,
                3000
            );
            scope.camera.position.fromArray(
                scope._realTo3dvSizes(
                    scope.refSys.camPosX_real,
                    -scope.refSys.camPosY_real,
                    scope.refSys.camPosZ_real
                )
            );
            // controls
            scope.controls = new THREE.OrbitControls(
                scope.camera,
                document.getElementById("threedview_container")
            );
            scope.controls.rotateSpeed = 1.0;
            scope.controls.zoomSpeed = 1.2;
            scope.controls.panSpeed = 0.8;
            scope.controls.enableZoom = true;
            scope.controls.enablePan = true;
            scope.controls.enableDamping = true;
            scope.controls.dampingFactor = 0.3;
            // controls.keys = [ 65, 83, 68 ];
            scope.controls.addEventListener("change", scope.render);
            scope.controls.render = scope.render; // rendering function

            // raycaster
            scope.raycaster = new THREE.Raycaster();
            scope.mouse = new THREE.Vector2();

            // world
            scope.scene = new THREE.Scene();

            // target object to camera
            scope.target = new THREE.Mesh(
                new THREE.BoxGeometry(4, 4, 4),
                new THREE.MeshPhongMaterial({color: new THREE.Color("red"), opacity: 1, transparent: true})
            );
            scope.target.position.fromArray(
                scope._realTo3dvSizes(
                    scope.refSys.targetX_real,
                    -scope.refSys.targetY_real,
                    scope.refSys.targetZ_real
                )
            );
            scope.target.name = "target";
            scope.target.visible = false;
            scope.scene.add(scope.target);

            scope.camera.updateProjectionMatrix();

            scope.createGround();

            // lights
            scope.scene.add(new THREE.AmbientLight(0xffffff));

            // renderer
            scope.renderer = new THREE.WebGLRenderer({antialias: true});
            scope.renderer.setClearColor(0xdfdfdf);
            scope.renderer.setPixelRatio(window.devicePixelRatio);
            scope._setRendererSize();
            scope.renderer.shadowMap.enabled = true;
            container = document.getElementById("threedview_container");
            container.appendChild(scope.renderer.domElement);

            scope.camera.lookAt(scope.target);
            scope.camera.userData.scene = scope.scene;
            scope.controls.target.copy(scope.target.position);
            scope.controls.update();

            scope.activateAreaChoice();

            // we need to put this in the event loop because of slow loading of background image
            setTimeout(scope.render, 0);
        },

        /**
         * Show the legend
         *
         * @private
         */
        showLegend: function (legend) {
            $("#legend_data").empty();
            if (scope.state.data.legendItems.length > 0) {
                $("#legend_data").append($("<ul/>").attr("id", "legend_ul"));
                var items = [];
                $(scope.state.data.legendItems).each(function (index, info) {
                    $("#legend_ul").append(
                        $("<li/>")
                            .append(
                                $("<span/>")
                                    .addClass("colorbox")
                                    .css("background-color", info.color)
                                    .html("&nbsp;")
                            )
                            .append($("<span/>").text(info.name))
                    );
                });
            }
        },

        /**
         * Create the ground by placing the image stored in the database.
         *
         * This function uses the information stored in the currentArea object.
         *
         * @private
         */
        createGround: function () {
            // we remove the ground that might be there
            scope.removeObject("ground");
            scope.removeObject("underground");
            scope.removeObject("grid");

            var groundImage = document.createElement("img");
            var texture = new THREE.Texture(groundImage);
            groundImage.onload = function () {
                texture.needsUpdate = true;
            };

            groundImage.src = "data:image/png;base64," + scope.currentArea.ground.planimetry_image;

            texture.wrapS = THREE.ClampToEdgeWrapping;
            texture.wrapT = THREE.ClampToEdgeWrapping;

            var groundGeometry = new THREE.BoxBufferGeometry(
                scope.refSys.groundX_3dv,
                2,
                scope.refSys.groundZ_3dv
            );

            var groundMaterial = new THREE.MeshStandardMaterial({map: texture, flatShading: true});
            var ground = new THREE.Mesh(groundGeometry, groundMaterial);
            ground.position.fromArray(
                scope._realTo3dvCoords(0, 0, 0, scope.refSys.groundX_real, scope.refSys.groundY_real, 0)
            ).y = -1;

            // the mesh used for the ground will show its texture on the under face, which we don't want
            // so, here's a simple hack: we create a different mesh just to cover it
            var underground = new THREE.Mesh(
                new THREE.BoxGeometry(scope.refSys.groundX_3dv, 2, scope.refSys.groundZ_3dv),
                new THREE.MeshPhongMaterial({
                    color: new THREE.Color("gray"),
                    opacity: 1,
                    transparent: false,
                })
            );
            underground.position.fromArray(
                scope._realTo3dvCoords(0, 0, 0, scope.refSys.groundX_real, scope.refSys.groundY_real, 0)
            ).y = -3;
            ground.name = "ground";
            underground.name = "underground";
            scope.scene.add(ground);
            scope.scene.add(underground);

            var grid = new THREE.GridHelper(
                2000,
                (2 * scope.refSys.groundX_real) / scope.refSys.groundX_3dv
            );
            grid.position.x = scope.refSys.groundX_3dv / 2;
            grid.position.y = -1;
            grid.position.z = -scope.refSys.groundZ_3dv / 2;
            grid.name = "grid";
            scope.scene.add(grid);
        },

        /**
         * Fill the dropdown list of available areas.
         *
         * @private
         */
        activateAreaChoice: function () {
            var area_ids = Object.keys(scope.state.data.areas);
            if (area_ids.length > 1) {
                area_ids.forEach(function (id) {
                    //console.log(id);
                    //console.log(scope.state.data.areas[id].name);
                    $("#area_id").append(
                        $("<option>", {value: id, text: scope.state.data.areas[id].name, id: "wh" + id})
                    );
                });
                // we don't want the event to be reflected on the canvas
                $("#areas")
                    .show()
                    .bind(
                        "blur change click dblclick error focus focusin focusout hover keydown keypress keyup load mousedown mouseenter mouseleave mousemove mouseout mouseover mouseup resize scroll select submit",
                        function (event) {
                            event.stopPropagation();
                        }
                    );
                $("#area_id").change(function (event) {
                    scope.changeArea($("#area_id").val());
                });
            }
        },

        /**
         * Change area.
         *
         * @param area_id
         * @private
         */
        changeArea: function (area_id) {
            scope.currentArea = scope.state.data.areas[area_id];

            scope._initRefSys(scope.currentArea);
            console.log("The area is currently: " + area_id);

            ["wireframes", "meshes"].forEach(function (item) {
                scope.areaObjects[item].forEach(function (obj) {
                    obj.visible = obj.userData.area == scope.currentArea.id;
                });
            });
            scope.createGround();
            scope.manageGLTFObjectsVisibility();

            // we need to put the rendering in the event loop
            setTimeout(scope.render, 0);
        },

        /**
         * Remove an object from the 3D scene.
         *
         * @param the name of the object, as defined in the object itself before being added to the scene
         * @private
         */
        removeObject: function (name) {
            var object = scope.scene.getObjectByName(name);
            if (object) {
                scope.scene.remove(object);
                if (object.geometry) object.geometry.dispose();
                if (object.material) object.material.dispose();
            }
        },

        /**
         * Add a new mesh for an item3d.
         *
         * This is used for the selected items3d, that must be shown in full color (or gray).
         *
         * @param item3d
         * @private
         */
        addMesh: function (item3d) {
            scope.addObject(item3d, "mesh");
        },

        /**
         * Add a new wireframe for a warehose item3d.
         *
         * This is used for all the items3d, that must be shown anyway.
         *
         * @param item3d
         * @private
         */
        addWireframe: function (item3d) {
            scope.addObject(item3d, "wireframe");
        },

        /**
         * Add an actual object to the scene.
         *
         * This called by addMesh() and addWireframe.
         * The object will be a BoxGeometry. According to the second parameter, it will be a mesh
         * or a wireframe.
         *
         * The object will be added both to the scene and to the warehouseObjects collection.
         *
         * @param item3d
         * @param type, either 'mesh' or 'wireframe'
         * @private
         */
        addObject: function (item3d, type) {
            console.log("Adding...");
            console.log(item3d);

            var size = scope._realTo3dvSizes(
                item3d.sizex,
                item3d.sizey,
                item3d.sizez,
                scope.state.data.areas[item3d[scope.fields.area]].scale
            );

            var geometry;
            var scale_factor = 1;
            var customObj;

            if (item3d.geometry) {
                customObj = scope.loader.parse(JSON.parse(atob(item3d.geometry)));

                scale_factor = parseFloat(item3d.scale_factor, 10);
            } else {
                geometry = new THREE.BoxBufferGeometry(size[0], size[1], size[2]);
                //console.log("Created geometry:");
                //console.log(geometry);
            }

            switch (type) {
                case "mesh":
                    console.log("it's a mesh");
                    var material = new THREE.MeshPhongMaterial({
                        color: new THREE.Color(item3d.color),
                        flatShading: true,
                        opacity: parseInt(item3d.opacity, 10) / 1000,
                        transparent: true,
                    });
                    // var obj = new THREE.Mesh( geometry, material );
                    if (item3d.geometry) {
                        obj = customObj;

                        obj.traverse(function (child) {
                            if (child.isMesh) {
                                child.material = material;
                                child.userData.item3d = item3d;
                                child.userData.area = item3d[scope.fields.area];
                                child.userData.parent = customObj;
                                scope.areaObjects["meshes"].push(child);
                            }
                        });

                        obj.scale.set(scale_factor, scale_factor, scale_factor);
                        //obj.updateMatrix();
                    } else {
                        obj = new THREE.Mesh(geometry, material);
                        //console.log("created mesh for object " + item3d.barcode);
                    }
                    obj.receiveShadow = true;
                    var key = "meshes";
                    break;
                case "wireframe":
                    //console.log("it's a wireframe");

                    var material = new THREE.LineBasicMaterial({color: 0x4d4d4d, linewidth: 1});

                    var obj;

                    if (item3d.geometry) {
                        obj = new THREE.Group();

                        customObj.traverse(function (child) {
                            if (child.isMesh) {
                                var wf = new THREE.LineSegments(
                                    new THREE.WireframeGeometry(child.geometry),
                                    material
                                );
                                wf.position.copy(child.position);
                                wf.rotation.copy(child.rotation);
                                obj.add(wf);
                            }
                        });
                        obj.scale.set(scale_factor, scale_factor, scale_factor);
                    } else {
                        var edges = new THREE.EdgesGeometry(geometry); // or WireframeGeometry
                        obj = new THREE.LineSegments(edges, material);
                    }
                    var key = "wireframes";
                    break;
            }

            obj.position.fromArray(
                scope._realTo3dvCoords(
                    parseInt(item3d.posx, 10),
                    parseInt(item3d.posy, 10),
                    parseInt(item3d.posz, 10),
                    parseInt(item3d.sizex, 10),
                    parseInt(item3d.sizey, 10),
                    parseInt(item3d.sizez, 10),
                    scope.state.data.areas[item3d[scope.fields.area]].scale
                )
            );

            //console.log("position:");
            //console.log(obj.position);
            /* LORIS
            if (!item3d.gltf) {
                obj.rotation.fromArray([
                    Math.PI*parseInt(item3d.rotx, 10)/180,
                    Math.PI*parseInt(item3d.roty, 10)/180,
                    Math.PI*parseInt(item3d.rotz, 10)/180,
                ]);
            }
            */
            obj.name = type + item3d.barcode;
            obj.userData.item3d = item3d;
            obj.userData.area = item3d[this.fields.area];
            //console.log('checks');
            //console.log([obj.userData, scope.currentArea]);

            obj.visible = true; //obj.userData.area == scope.currentArea.id;  LORIS
            scope.scene.add(obj);
            console.log(obj); // LORIS

            console.log("added " + item3d.barcode + "!");
            scope.areaObjects[key].push(obj);

            //console.log(scope.areaObjects);
        },

        /**
         * Show the wireframes for all the items3d.
         *
         * @private
         */
        showWireframesForAllItems3d: function () {
            //console.log("showing wireframes...");
            //console.log(scope.state.data);

            scope.state.data.allItems3d.forEach(function (item3d) {
                scope.addWireframe(item3d);
            });
            scope.render();
        },

        /**
         * Show the meshes for the selected items3d.
         *
         * Since this is called every time a new selection is done, we
         * switch area when all selected items3d belong to one area only.
         *
         * @private
         */
        showMeshesForSelectedItems3d: function () {
            // first, we remove all existing meshes from the scene
            scope.areaObjects.meshes.forEach(function (obj) {
                scope.removeObject(obj.name);
            });
            scope.areaObjects.meshes = [];

            // we use this object as a set to store areas' ids
            let areas = {};

            scope.state.data.selectedItems3d.forEach(function (item3d) {
                scope.addMesh(item3d);
                if (item3d[scope.fields.area]) {
                    areas[item3d[scope.fields.area]] = true;
                }

                if (item3d.gltf != "") {
                    scope.showGLTFModel(item3d);
                }
            });

            console.log("***areas loaded: " + JSON.stringify(areas));

            // if all selected items3d are in the same area, we switch to it
            // by changing the option in the dropdown menu
            if (Object.keys(areas).length == 1) {
                $("#area_id").val(Object.keys(areas)[0]).change();
            }
            scope.manageGLTFObjectsVisibility();

            scope.render();
        },

        manageGLTFObjectsVisibility: function () {
            for (let key in scope.areaObjects.gltfObjects) {
                scope.areaObjects.gltfObjects[key].model.visible =
                    scope.areaObjects.gltfObjects[key].area == scope.currentArea.id;
                scope.areaObjects.gltfObjects[key].light.intensity =
                    scope.areaObjects.gltfObjects[key].area == scope.currentArea.id ? 7 : 0;
            }

            scope.render();
        },

        showGLTFModel: function (item3d) {
            //console.log("I should get the gltf model for id= " + item3d.gltf);
            //console.log("I know the area, it is " + item3d[this.fields.area]);
            if (scope.areaObjects.gltfModels.indexOf(item3d.gltf) > -1) {
                //console.log("already shown, skipping...");
                return;
            }

            scope.GLTFLoader.load(this.calls.gltf3dModel + item3d.gltf, function (gltf) {
                //console.log("object parsed");
                let mod = gltf.scene;

                //console.log(gltf);

                //var box = new THREE.Box3().setFromObject( mod );

                //console.log(JSON.stringify(box));

                mod.traverse(function (model) {
                    if (model.isMesh) {
                        model.castShadow = true;
                    }
                });

                mod.scale.set(item3d.scale_factor, item3d.scale_factor, item3d.scale_factor);
                mod.position.set(item3d.posx, item3d.posy, item3d.posz);

                mod.position.fromArray(
                    scope._realTo3dvCoords(
                        parseInt(item3d.posx, 10),
                        parseInt(item3d.posy, 10),
                        parseInt(item3d.posz, 10),
                        parseInt(item3d.sizex, 10),
                        parseInt(item3d.sizey, 10),
                        parseInt(item3d.sizez, 10),
                        scope.state.data.areas[item3d[scope.fields.area]].scale
                    )
                );

                mod.rotation.fromArray([
                    (Math.PI * parseInt(item3d.rotx, 10)) / 180,
                    (Math.PI * parseInt(item3d.roty, 10)) / 180,
                    (Math.PI * parseInt(item3d.rotz, 10)) / 180,
                ]);

                mod.castShadow = true;
                mod.receiveShadow = true;

                mod.visible = item3d[scope.fields.area] == scope.currentArea.id;

                scope.scene.add(mod);

                let plight = new THREE.PointLight(0xffffff, 7, 140, 2); // color : Integer, intensity : Float, distance : Number, decay : Float
                plight.position.set(mod.position.x + 20, scope.refSys.heightY_3dv, mod.position.z + 15);
                plight.castShadow = true;

                plight.shadow.mapSize.width = 1024;
                plight.shadow.mapSize.height = 1024;
                plight.shadow.radius = 2;

                scope.scene.add(plight);

                scope.areaObjects.gltfModels.push(item3d.gltf);
                scope.areaObjects.gltfObjects[item3d.gltf] = {
                    model: mod,
                    light: plight,
                    area: item3d[scope.fields.area],
                };

                console.log("gltfObjects so far");
                console.log(scope.areaObjects.gltfObjects);

                /*
                    const pointLightHelper = new THREE.PointLightHelper( plight, 2 );
                    scope.scene.add( pointLightHelper );
                    
                    const helper = new THREE.CameraHelper( plight.shadow.camera );
                    scope.scene.add( helper );
                    */

                //console.log("object added to scene!");
                scope.render();
            });
        },

        // find item3d position

        /**
         * Find a item3d by using the raycaster.
         *
         * This function only searches the meshes array (thus, only selected items3d)
         *
         * @private
         */
        findItem3d: function (event) {
            console.log("looking for matches...");
            if ($("#item3d_info").data("current") !== 0) {
                console.log("out" + $("#item3d_info").data("current"));
                return;
            }
            console.log("checking...");
            scope.mouse.x =
                ((event.clientX - $("#threedview_container").offset().left - 10) /
                    scope.renderer.domElement.clientWidth) *
                    2 -
                1;
            scope.mouse.y =
                -(
                    (event.clientY - $("#threedview_container").offset().top - 10) /
                    scope.renderer.domElement.clientHeight
                ) *
                    2 +
                1;
            scope.raycaster.setFromCamera(scope.mouse, scope.camera);

            var intersects = scope.raycaster.intersectObjects(
                scope.areaObjects.meshes.filter((obj) => obj.userData.area == scope.currentArea.id)
            );
            if (intersects.length > 0) {
                return intersects[0].object;
            }
            return false;
        },

        /**
         * Call the actual ThreeJS Renderer
         *
         * @private
         */
        render: function () {
            //console.log("ready!");
            var self = this;
            scope.target.position.copy(scope.controls.target);
            if (!$("#coords_info_icon").is(":visible")) {
                scope.showCoordinates();
            }
            scope.renderer.render(scope.scene, scope.camera);
        },

        /**
         * Show the coordinates
         *
         * @private
         */
        showCoordinates() {
            var c = scope._realCoords(
                scope.camera.position.x,
                scope.camera.position.y,
                scope.camera.position.z
            );
            var t = scope._realCoords(
                scope.target.position.x,
                scope.target.position.y,
                scope.target.position.z
            );
            $("#coords").html(
                "camera: " +
                    c.x +
                    ", " +
                    c.y +
                    ", " +
                    c.z +
                    "<br />" +
                    "target: " +
                    t.x +
                    ", " +
                    t.y +
                    ", " +
                    t.z
            );
        },

        /**
         * Event handler for mobile devices
         *
         * For the use on mobile devices, where you can use two or three different fingers to do something
         *
         * @private
         */
        onContainerTouchStart: function (event) {
            event.preventDefault();
            event.clientX = event.touches[0].clientX;
            event.clientY = event.touches[0].clientY;
            onDocumentMouseDown(event);
        },

        /**
         * Double click event handler
         *
         * On double click on a item3d, we retrieve some information from Odoo about that item3d
         *
         * @private
         */
        onContainerDoubleClick: function (event) {
            event.preventDefault();
            $("#barcode_label").hide();
            console.log("double click");
            var item3d = scope.findItem3d(event);
            //console.log(scope.areaObjects);
            if (item3d) {
                console.log(item3d);
                item3d.material.color.setHex(0xbebebe);

                //console.log(item3d);

                var wireframe = scope.scene.getObjectByName("wireframe" + item3d.userData.item3d.barcode);
                wireframe.material.linewidth = 2;
                wireframe.material.color.setHex(0xa3498b);

                $("#item3d_info")
                    .css({
                        top: event.clientY - $("#threedview_container").offset().top - 10,
                        left: event.clientX - $("#threedview_container").offset().left - 10,
                    })
                    .data("current", item3d.userData.item3d.barcode)
                    .show();
                if (parseInt($("#item3d_info").css("right"), 10) < 0) {
                    $("#item3d_info").css(
                        "left",
                        event.clientX -
                            $("#threedview_container").offset().left -
                            $("#item3d_info").width() -
                            30
                    );
                }
                if (parseInt($("#item3d_info").css("bottom"), 10) < 0) {
                    $("#item3d_info").css(
                        "top",
                        event.clientY -
                            $("#threedview_container").offset().top -
                            $("#item3d_info").height() -
                            30
                    );
                }
                $("#item3d_data").text(item3d.userData.item3d.barcode + ", retrieving info...");

                var domain = [["barcode", "=", item3d.userData.item3d.barcode]]; // FIXME the field should be "code", not "barcode"
                ajax.jsonRpc(scope.calls.item3dInfo, "call", {domain: domain}).then(function (data) {
                    var info = JSON.parse(data);
                    console.log("info received");
                    console.log(info);
                    //$("#item3d_data").text(data);
                    $("#item3d_data").text(info.barcode);

                    $("#item3d_specific_info").html(info.specific_info);
                    /*
                    if ( info.products.length ) {
                        $('#contained_items_data').append($('<ul/>').attr('id', 'products_ul'));
                        var items=[];
                        $( info.products ).each(function( index, sq ) {
                            $('#products_ul').append($('<li/>').text( '[' + sq.product_code + '] ' + sq.product_name + ' (' + sq.product_qty + ')' ));
                        });
                    } else
                    {
                        $("#contained_items_data").text(scope.messages.noProduct);
                    }
                    */

                    $("#item3d_info").height(20 + $("#item3d_specific_info").height());
                    if (parseInt($("#item3d_info").css("bottom"), 10) < 0) {
                        $("#item3d_info").css(
                            "top",
                            event.clientY -
                                $("#threedview_container").offset().top -
                                $("#item3d_info").height() -
                                30
                        );
                    }

                    $("#frame_item3d_icon")
                        .show()
                        .click(function (event) {
                            event.preventDefault();
                            scope.camera.position.fromArray(
                                scope._realTo3dvSizes(
                                    parseInt(info.camx, 10),
                                    -parseInt(info.camy, 10),
                                    parseInt(info.camz, 10)
                                )
                            );
                            scope.target.position.copy(item3d.position);
                            scope.camera.lookAt(scope.target);
                            scope.controls.target.copy(scope.target.position);
                            scope.controls.update();
                        });
                });

                scope.controls.enabled = false;
                scope.render();
            }
        },

        /**
         * Mouse move event handler
         *
         * @private
         */
        onContainerMouseMove: function (event) {
            if ($("#coords_info_icon").is(":visible")) {
                return;
            }
            var item3d = scope.findItem3d(event);
            if (item3d) {
                $("#barcode_label")
                    .text(item3d.userData.barcode)
                    .css({
                        top: event.clientY - $("#threedview_container").offset().top - 5,
                        left: event.clientX - $("#threedview_container").offset().left + 20,
                    })
                    .show();
            } else {
                $("#barcode_label").hide();
            }
        },

        /**
         * Window resize event handler
         *
         * @private
         */
        onWindowResize: function () {
            scope._setRendererSize();
        },

        /**
         * Fix the renderer size according to the available space on screen
         *
         * @private
         */
        _setRendererSize: function () {
            var width;
            var height;
            if ($("#threedview_container").hasClass("fullscreen")) {
                width = $(document).width();
                height = $(document).height();
            } else {
                width = $(".o_content").width();
                height = $(".o_content").height();
            }
            scope.camera.aspect = width / height;
            scope.camera.updateProjectionMatrix();
            if ($("#threedview_container").hasClass("fullscreen")) {
                scope.renderer.setSize(width, height);
            } else {
                scope.renderer.setSize(width - 20, height - 20);
            }
            $("#loading_icon").css({
                left: (width - $("#loading_icon").width()) / 2,
                top: (height - $("#loading_icon").height()) / 2,
            });
        },

        /**
         * Add event handlers
         *
         * @private
         */
        _addEventHandlers: function () {
            $(container).dblclick(this.onContainerDoubleClick);
            $(container).mousemove(this.onContainerMouseMove);
            $(window).resize(this.onWindowResize);

            $("#close_item3d_info_icon").click(function (e) {
                e.preventDefault();
                //console.log("Closing window");
                var item3d = scope.scene.getObjectByName("mesh" + $("#item3d_info").data("current"));
                if (item3d) {
                    item3d.material.color = new THREE.Color(item3d.userData.item3d.color);
                    var wireframe = scope.scene.getObjectByName(
                        "wireframe" + item3d.userData.item3d.barcode
                    );
                    wireframe.material.linewidth = 1;
                    wireframe.material.color = new THREE.Color(0x4d4d4d);
                }
                $("#item3d_info").data("current", 0).hide();
                $("#frame_item3d_icon").off("click").hide();
                $("#map_marker_icon").off("click").hide();
                scope.controls.enabled = true;
                scope.render();
                e.stopPropagation();
            });

            $("#reload_icon").click(function (e) {
                e.preventDefault();
                if (!$("#reload_icon").hasClass("clickable")) {
                    return;
                }
                scope.removeItems3d();
                scope.loadItems3d([]);
            });

            $("#fullscreen_icon").click(function (e) {
                e.preventDefault();
                $("#threedview_container").toggleClass("fullscreen");
                scope._setRendererSize();
                scope.render();
            });

            $("#legend_icon").click(function (e) {
                e.preventDefault();
                scope.showLegend();
                $("#legend").show();
                $("#legend_icon").prop("disabled", true);
            });

            $("#close_legend_icon").click(function (e) {
                e.preventDefault();
                $("#legend").hide();
                $("#legend_icon").prop("disabled", false);
            });

            $("#toggle_arrowkeys_meaning_icon").click(function (e) {
                e.preventDefault();
                var o = $("#toggle_arrowkeys_meaning_icon");
                o.toggleClass("fa-video-camera").toggleClass("fa-dot-circle-o");
                scope.controls.arrowKeys = o.hasClass("fa-video-camera") ? "camera" : "target";
                o.attr(
                    "title",
                    scope.controls.arrowKeys == "camera"
                        ? "Arrow keys move the camera. Click to switch"
                        : "Arrow keys move the target. Click to switch"
                );
            });

            $("#coords_info_icon").click(function (e) {
                e.preventDefault();
                $("#coords").show();
                $("#coords_info_icon").hide();
                scope.target.visible = true;
                scope.showCoordinates();
                scope.render();
            });

            $("#coords").click(function (e) {
                e.preventDefault();
                $("#coords").hide();
                $("#coords_info_icon").show();
                scope.target.visible = false;
                scope.render();
            });
        },

        /**
         * Map millimeters to 3js units (only sizes)
         *
         * @private
         * @returns [*] a three-items array of sizes, scaled
         */
        _realTo3dvSizes: function (x, y, z, scale = scope.scale) {
            return [x / scale, z / scale, y / scale];
        },

        /**
         * Map millimeters to 3js units (coordinates and sizes)
         *
         * @private
         * @returns [*] a three-items array of coordinates, scaled
         */
        _realTo3dvCoords: function (x, y, z, sizex, sizey, sizez, scale = scope.scale) {
            return [(x + sizex / 2) / scale, (z + sizez / 2) / scale, -(y + sizey / 2) / scale];
        },

        /**
         * Map 3js units to millimeters, creating an object
         *
         * @private
         * @returns {} an object with 'x', 'y', and 'z' properties
         */
        _realCoords: function (x, y, z, scale = scope.scale) {
            return {x: Math.round(x * scale), y: -Math.round(z * scale), z: Math.round(y * scale)};
        },

        /**
         * Initialize the global reference system used by the renderer
         *
         * @private
         * @param area
         */
        _initRefSys: function (area) {
            console.log("Initializing reference system...");
            console.log("Areas available:");
            console.log(scope.state.data.areas);

            for (let id in scope.state.data.areas) {
                let area = scope.state.data.areas[id];
                area.refSys = {
                    groundX_real: area.ground.sizex,
                    groundY_real: area.ground.sizey,
                    heightZ_real: area.ground.sizez,
                    camPosX_real: area.camera.camx,
                    camPosY_real: area.camera.camy,
                    camPosZ_real: area.camera.camz,
                    camFov: area.camera.camfov,
                };
                area.refSys.targetX_real = area.ground.sizex / 2;
                area.refSys.targetY_real = area.ground.sizey / 2;
                area.refSys.targetZ_real = 0;
                area.refSys.groundX_3dv = 500;
                area.refSys.groundZ_3dv = Math.round(
                    (area.refSys.groundY_real / area.refSys.groundX_real) * area.refSys.groundX_3dv
                );
                area.refSys.heightY_3dv = Math.round(
                    (area.refSys.heightZ_real / area.refSys.groundX_real) * area.refSys.groundX_3dv
                );
                area.scale = area.refSys.groundX_real / area.refSys.groundX_3dv;
            }
            scope.refSys = scope.state.data.areas[area.id].refSys;
            scope.scale = scope.state.data.areas[area.id].scale;
        },

        _showInformationDialog(text) {
            //alert(text);
            $("#dialog").html(text).show();
            /*
            let dialog = $('div').attr('title', title).attr('id', 'infobox');
            dialog.append($('p').html(text));
            console.log(dialog);
            console.log($('#infobox'));
            document.append(dialog);
            //$('#infobox').dialog();
            dialog.dialog();
            */
        },
    });

    return ThreeDViewRenderer;
});
