/** @odoo-module alias=stock_3dview.OWL3DViewRenderer **/
const {useState} = owl.hooks;
import AbstractRendererOwl from "web.AbstractRendererOwl";
import QWeb from "web.QWeb";
import session from "web.session";
import {onDestroyed} from "@web/core/utils/hooks";
const {jsonRpc} = require("web.ajax");

class OWL3DViewRenderer extends AbstractRendererOwl {
    constructor(_parent, props) {
        super(...arguments);
        this.qweb = new QWeb(this.env.isDebug(), {_s: session.origin});
        // TODO: Keep this for later to get arch attrs from here
        // This will be important when the Controller will be removed
        // this.state = useState({
        //     // todo
        // });
        // console.log("this.props.arch.attrs", this.props.arch.attrs);
        // if (this.props.arch.attrs.count_field) {
        //     Object.assign(this.state, {
        //         countField: this.props.arch.attrs.count_field,
        //     });
        // }
    }

    setup() {
        super.setup();
        this.scope = {};
        this.scope.areaObjects = {
            wireframes: [], // for all items3d
            meshes: [], // for selected items3d
            gltfModels: [], // for rendered GLTF models
            gltfObjects: {}, // a container of GLTF objects and their accessories
        };
        this.scope.currentArea = null;
        this.context = {};
        this.loader = new THREE.ObjectLoader(); // see https://threejs.org/docs/#api/en/loaders/ObjectLoader
        this.GLTFLoader = new THREE.GLTFLoader();

        onDestroyed(() => {
            console.log("Cleanup onDestroyed");
            this.scope.scene.traverse(dispose);
            for (const [_key, value] of Object.entries(this.scope.areaObjects)) {
                if (Array.isArray(value)) {
                    value.forEach(dispose);
                }
            }
            this.scope.scene.dispose();
            this.scope.controls.dispose();
            this.renderer.dispose();
            this.scope.raycaster = {};
            this.scope.mouse = {};
            this.scope = {};
            this.loader = {};
            this.GLTFLoader = {};
            this.renderer = {};
            this.context = {};

            function dispose(threeJSObject) {
                if (threeJSObject.geometry) {
                    threeJSObject.geometry.dispose();
                }
                if (threeJSObject.material) {
                    if (Array.isArray(threeJSObject.material)) {
                        threeJSObject.material.forEach((mtl) => mtl.dispose());
                    } else {
                        threeJSObject.material.dispose();
                    }
                }
            }
        });
    }

    async willUpdateProps(nextProps) {
        await super.willUpdateProps(nextProps);
        this.showMeshesForSelectedItems3d();
        this.renderScope();
    }

    mounted() {
        if (
            this.props.data.allItems3dLoaded &&
            this.props.data.selectedItems3dLoaded &&
            this.props.data.areasLoaded &&
            this.props.data.legendLoaded
        ) {
            if (!this.renderer) {
                // We can get correct area from context
                this.scope.currentArea = this.props.activeAreaId
                    ? this.props.data.areas[this.props.activeAreaId]
                    : this.props.data.areas[Object.keys(this.props.data.areas)[0]];

                if (this.scope.currentArea) {
                    this._initRefSys(this.scope.currentArea);
                    this.init3d();
                    this._addEventHandlers();
                    this.showWireframesForAllItems3d();
                } else {
                    this._showInformationDialog(this.props.noAreaLoaded);
                }
            }

            this.scope.currentArea && this.showMeshesForSelectedItems3d();
            $("#loading_icon").hide();
        }
    }
    /**
     * Initialize threejs world
     *
     * @private
     */
    init3d() {
        // camera
        this.scope.camera = new THREE.PerspectiveCamera(
            this.scope.refSys.camFov,
            window.innerWidth / window.innerHeight,
            1,
            3000
        );
        this.scope.camera.position.fromArray(
            this._realTo3dvSizes(
                this.scope.refSys.camPosX_real,
                -this.scope.refSys.camPosY_real,
                this.scope.refSys.camPosZ_real
            )
        );
        // controls
        this.scope.controls = new THREE.OrbitControls(
            this.scope.camera,
            this.el.querySelector("#threedview_container")
        );
        this.scope.controls.rotateSpeed = 1.0;
        this.scope.controls.zoomSpeed = 1.2;
        this.scope.controls.panSpeed = 0.8;
        this.scope.controls.enableZoom = true;
        this.scope.controls.enablePan = true;
        this.scope.controls.enableDamping = true;
        this.scope.controls.dampingFactor = 0.3;
        // controls.keys = [ 65, 83, 68 ];
        this.scope.controls.addEventListener("change", this.renderScope.bind(this));
        this.scope.controls.render = this.renderScope; // rendering function

        // raycaster
        this.scope.raycaster = new THREE.Raycaster();
        this.scope.mouse = new THREE.Vector2();

        // world
        this.scope.scene = new THREE.Scene();

        // target object to camera
        this.scope.target = new THREE.Mesh(
            new THREE.BoxGeometry(4, 4, 4),
            new THREE.MeshPhongMaterial({
                color: new THREE.Color("red"),
                opacity: 1,
                transparent: true,
            })
        );
        this.scope.target.position.fromArray(
            this._realTo3dvSizes(
                this.scope.refSys.targetX_real,
                -this.scope.refSys.targetY_real,
                this.scope.refSys.targetZ_real
            )
        );
        this.scope.target.name = "target";
        this.scope.target.visible = false;
        this.scope.scene.add(this.scope.target);

        this.scope.camera.updateProjectionMatrix();

        this.createGround();

        // lights
        this.scope.scene.add(new THREE.AmbientLight(0xffffff));

        // renderer
        this.renderer = new THREE.WebGLRenderer({antialias: true});
        this.renderer.setClearColor(0xdfdfdf);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this._setRendererSize();
        this.renderer.shadowMap.enabled = true;
        this.dom3DContainer = document.getElementById("threedview_container");
        this.dom3DContainer.appendChild(this.renderer.domElement);

        this.scope.camera.lookAt(this.scope.target);
        this.scope.camera.userData.scene = this.scope.scene;
        this.scope.controls.target.copy(this.scope.target.position);
        this.scope.controls.update();

        this.activateAreaChoice();

        // we need to put this in the event loop because of slow loading of background image
        setTimeout(this.renderScope.bind(this), 0);
    }

    willUnmount() {
        this._unbindEventHandlers();
    }

    /**
     * Show the legend
     *
     * @private
     */
    showLegend(legend) {
        $("#legend_data").empty();
        if (this.props.data.legendItems.length > 0) {
            $("#legend_data").append($("<ul/>").attr("id", "legend_ul"));
            var items = [];
            $(this.props.data.legendItems).each(function (index, info) {
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
    }

    /**
     * Create the ground by placing the image stored in the database.
     *
     * This function uses the information stored in the currentArea object.
     *
     * @private
     */
    createGround() {
        // we remove the ground that might be there
        this.removeObject("ground");
        this.removeObject("underground");
        this.removeObject("grid");

        var groundImage = document.createElement("img");
        var texture = new THREE.Texture(groundImage);
        groundImage.onload = function () {
            texture.needsUpdate = true;
        };

        groundImage.src = "data:image/png;base64," + this.scope.currentArea.ground.planimetry_image;

        texture.wrapS = THREE.ClampToEdgeWrapping;
        texture.wrapT = THREE.ClampToEdgeWrapping;

        var groundGeometry = new THREE.BoxBufferGeometry(
            this.scope.refSys.groundX_3dv,
            2,
            this.scope.refSys.groundZ_3dv
        );

        var groundMaterial = new THREE.MeshStandardMaterial({
            map: texture,
            flatShading: true,
        });
        var ground = new THREE.Mesh(groundGeometry, groundMaterial);
        ground.position.fromArray(
            this._realTo3dvCoords(
                0,
                0,
                0,
                this.scope.refSys.groundX_real,
                this.scope.refSys.groundY_real,
                0
            )
        ).y = -1;

        // the mesh used for the ground will show its texture on the under face, which we don't want
        // so, here's a simple hack: we create a different mesh just to cover it
        var underground = new THREE.Mesh(
            new THREE.BoxGeometry(this.scope.refSys.groundX_3dv, 2, this.scope.refSys.groundZ_3dv),
            new THREE.MeshPhongMaterial({
                color: new THREE.Color("gray"),
                opacity: 1,
                transparent: false,
            })
        );
        underground.position.fromArray(
            this._realTo3dvCoords(
                0,
                0,
                0,
                this.scope.refSys.groundX_real,
                this.scope.refSys.groundY_real,
                0
            )
        ).y = -3;
        ground.name = "ground";
        underground.name = "underground";
        this.scope.scene.add(ground);
        this.scope.scene.add(underground);

        var grid = new THREE.GridHelper(
            2000,
            (2 * this.scope.refSys.groundX_real) / this.scope.refSys.groundX_3dv
        );
        grid.position.x = this.scope.refSys.groundX_3dv / 2;
        grid.position.y = -1;
        grid.position.z = -this.scope.refSys.groundZ_3dv / 2;
        grid.name = "grid";
        this.scope.scene.add(grid);
    }

    /**
     * Fill the dropdown list of available areas.
     *
     * @private
     */
    activateAreaChoice() {
        var area_ids = Object.keys(this.props.data.areas);
        if (area_ids.length > 1) {
            area_ids.forEach((id) => {
                $("#area_id").append(
                    $("<option>", {
                        value: id,
                        text: this.props.data.areas[id].name,
                        id: "wh" + id,
                    })
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
            $("#area_id").change((event) => {
                this.changeArea($("#area_id").val());
            });
        }
    }

    /**
     * Change area.
     *
     * @param area_id
     * @private
     */
    changeArea(area_id) {
        this.scope.currentArea = this.props.data.areas[area_id];

        this._initRefSys(this.scope.currentArea);
        console.log("The area is currently:", area_id);

        ["wireframes", "meshes"].forEach((item) => {
            this.scope.areaObjects[item].forEach((obj) => {
                obj.visible = obj.userData.area == this.scope.currentArea.id;
            });
        });
        this.createGround();
        this.manageGLTFObjectsVisibility();

        // we need to put the rendering in the event loop
        setTimeout(this.renderScope.bind(this), 0);
    }

    /**
     * Remove an object from the 3D scene.
     *
     * @param the name of the object, as defined in the object itself before being added to the scene
     * @private
     */
    removeObject(name) {
        var object = this.scope.scene.getObjectByName(name);
        if (object) {
            this.scope.scene.remove(object);
            if (object.geometry) object.geometry.dispose();
            if (object.material) object.material.dispose();
        }
    }

    /**
     * Add a new mesh for an item3d.
     *
     * This is used for the selected items3d, that must be shown in full color (or gray).
     *
     * @param item3d
     * @private
     */
    addMesh(item3d) {
        this.addObject(item3d, "mesh");
    }

    /**
     * Add a new wireframe for a warehose item3d.
     *
     * This is used for all the items3d, that must be shown anyway.
     *
     * @param item3d
     * @private
     */
    addWireframe(item3d) {
        this.addObject(item3d, "wireframe");
    }

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
    addObject(item3d, type) {
        var size = this._realTo3dvSizes(
            item3d.sizex,
            item3d.sizey,
            item3d.sizez,
            this.props.data.areas[item3d[this.props.rendererArea]].scale
        );

        var geometry;
        var scale_factor = 1;
        var customObj;

        if (item3d.geometry) {
            customObj = this.scope.loader.parse(JSON.parse(atob(item3d.geometry)));

            scale_factor = parseFloat(item3d.scale_factor, 10);
        } else {
            geometry = new THREE.BoxBufferGeometry(size[0], size[1], size[2]);
        }

        switch (type) {
            case "mesh":
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
                            child.userData.area = item3d[this.props.rendererArea];
                            child.userData.parent = customObj;
                            this.scope.areaObjects["meshes"].push(child);
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
            this._realTo3dvCoords(
                parseInt(item3d.posx, 10),
                parseInt(item3d.posy, 10),
                parseInt(item3d.posz, 10),
                parseInt(item3d.sizex, 10),
                parseInt(item3d.sizey, 10),
                parseInt(item3d.sizez, 10),
                this.props.data.areas[item3d[this.props.rendererArea]].scale
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
        obj.userData.area = item3d[this.props.rendererArea];
        //console.log('checks');
        //console.log([obj.userData, this.scope.currentArea]);

        obj.visible = true; //obj.userData.area == this.scope.currentArea.id;  LORIS
        this.scope.scene.add(obj);
        this.scope.areaObjects[key].push(obj);

        //console.log(this.scope.areaObjects);
    }

    /**
     * Show the wireframes for all the items3d.
     *
     * @private
     */
    showWireframesForAllItems3d() {
        //console.log("showing wireframes...");
        //console.log(this.props.data);

        this.props.data.allItems3d.forEach((item3d) => {
            this.addWireframe(item3d);
        });
        this.renderScope();
    }

    /**
     * Show the meshes for the selected items3d.
     *
     * Since this is called every time a new selection is done, we
     * switch area when all selected items3d belong to one area only.
     *
     * @private
     */
    showMeshesForSelectedItems3d() {
        // first, we remove all existing meshes from the scene
        this.scope.areaObjects.meshes.forEach((obj) => {
            this.removeObject(obj.name);
        });
        this.scope.areaObjects.meshes = [];

        // we use this object as a set to store areas' ids
        let areas = {};

        this.props.data.selectedItems3d.forEach((item3d) => {
            this.addMesh(item3d);
            if (item3d[this.props.rendererArea]) {
                areas[item3d[this.props.rendererArea]] = true;
            }

            if (item3d.gltf != "") {
                this.showGLTFModel(item3d);
            }
        });

        console.log("***areas loaded: " + JSON.stringify(areas));

        // if all selected items3d are in the same area, we switch to it
        // by changing the option in the dropdown menu
        if (Object.keys(areas).length == 1) {
            $("#area_id").val(Object.keys(areas)[0]).change();
        }
        this.manageGLTFObjectsVisibility();

        this.renderScope();
    }

    manageGLTFObjectsVisibility() {
        for (let key in this.scope.areaObjects.gltfObjects) {
            this.scope.areaObjects.gltfObjects[key].model.visible =
                this.scope.areaObjects.gltfObjects[key].area == this.scope.currentArea.id;
            this.scope.areaObjects.gltfObjects[key].light.intensity =
                this.scope.areaObjects.gltfObjects[key].area == this.scope.currentArea.id ? 7 : 0;
        }

        this.renderScope();
    }

    showGLTFModel(item3d) {
        //console.log("I should get the gltf model for id= " + item3d.gltf);
        //console.log("I know the area, it is " + item3d[this.props.rendererArea]);
        if (this.scope.areaObjects.gltfModels.indexOf(item3d.gltf) > -1) {
            //console.log("already shown, skipping...");
            return;
        }

        this.GLTFLoader.load(this.props.gltf3dModel + item3d.gltf, (gltf) => {
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
                this._realTo3dvCoords(
                    parseInt(item3d.posx, 10),
                    parseInt(item3d.posy, 10),
                    parseInt(item3d.posz, 10),
                    parseInt(item3d.sizex, 10),
                    parseInt(item3d.sizey, 10),
                    parseInt(item3d.sizez, 10),
                    this.props.data.areas[item3d[this.props.rendererArea]].scale
                )
            );

            mod.rotation.fromArray([
                (Math.PI * parseInt(item3d.rotx, 10)) / 180,
                (Math.PI * parseInt(item3d.roty, 10)) / 180,
                (Math.PI * parseInt(item3d.rotz, 10)) / 180,
            ]);

            mod.castShadow = true;
            mod.receiveShadow = true;

            mod.visible = item3d[this.props.rendererArea] == this.scope.currentArea.id;

            this.scope.scene.add(mod);

            let plight = new THREE.PointLight(0xffffff, 7, 140, 2); // color : Integer, intensity : Float, distance : Number, decay : Float
            plight.position.set(mod.position.x + 20, this.scope.refSys.heightY_3dv, mod.position.z + 15);
            plight.castShadow = true;

            plight.shadow.mapSize.width = 1024;
            plight.shadow.mapSize.height = 1024;
            plight.shadow.radius = 2;

            this.scope.scene.add(plight);

            this.scope.areaObjects.gltfModels.push(item3d.gltf);
            this.scope.areaObjects.gltfObjects[item3d.gltf] = {
                model: mod,
                light: plight,
                area: item3d[this.props.rendererArea],
            };

            // console.log("gltfObjects so far");
            // console.log(this.scope.areaObjects.gltfObjects);

            /*
                  const pointLightHelper = new THREE.PointLightHelper( plight, 2 );
                  this.scope.scene.add( pointLightHelper );
                  
                  const helper = new THREE.CameraHelper( plight.shadow.camera );
                  this.scope.scene.add( helper );
                  */

            //console.log("object added to scene!");
            this.renderScope();
        });
    }

    // find item3d position

    /**
     * Find a item3d by using the raycaster.
     *
     * This function only searches the meshes array (thus, only selected items3d)
     *
     * @private
     */
    findItem3d(event) {
        // console.log("looking for matches...");
        if ($("#item3d_info").data("current") !== 0) {
            // console.log("out" + $("#item3d_info").data("current"));
            return;
        }
        // console.log("checking...");
        this.scope.mouse.x =
            ((event.clientX - $("#threedview_container").offset().left - 10) /
                this.renderer.domElement.clientWidth) *
                2 -
            1;
        this.scope.mouse.y =
            -(
                (event.clientY - $("#threedview_container").offset().top - 10) /
                this.renderer.domElement.clientHeight
            ) *
                2 +
            1;
        this.scope.raycaster.setFromCamera(this.scope.mouse, this.scope.camera);

        var intersects = this.scope.raycaster.intersectObjects(
            this.scope.areaObjects.meshes.filter((obj) => obj.userData.area == this.scope.currentArea.id)
        );
        if (intersects.length > 0) {
            return intersects[0].object;
        }
        return false;
    }

    /**
     * Call the actual ThreeJS Renderer
     *
     * @private
     */
    renderScope() {
        //console.log("ready!");
        if (this.scope) {
            this.scope.target.position.copy(this.scope.controls.target);
            if (!$("#coords_info_icon").is(":visible")) {
                this.showCoordinates();
            }
            this.renderer.render(this.scope.scene, this.scope.camera);
        }
    }

    /**
     * Show the coordinates
     *
     * @private
     */
    showCoordinates() {
        var c = this._realCoords(
            this.scope.camera.position.x,
            this.scope.camera.position.y,
            this.scope.camera.position.z
        );
        var t = this._realCoords(
            this.scope.target.position.x,
            this.scope.target.position.y,
            this.scope.target.position.z
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
    }

    /**
     * Event handler for mobile devices
     *
     * For the use on mobile devices, where you can use two or three different fingers to do something
     *
     * @private
     */
    onContainerTouchStart(event) {
        event.preventDefault();
        event.clientX = event.touches[0].clientX;
        event.clientY = event.touches[0].clientY;
        onDocumentMouseDown(event);
    }

    /**
     * Double click event handler
     *
     * On double click on a item3d, we retrieve some information from Odoo about that item3d
     *
     * @private
     */
    onContainerDoubleClick(event) {
        event.preventDefault();
        $("#barcode_label").hide();
        var item3d = this.findItem3d(event);
        //console.log(this.scope.areaObjects);
        if (item3d) {
            item3d.material.color.setHex(0xbebebe);

            var wireframe = this.scope.scene.getObjectByName("wireframe" + item3d.userData.item3d.barcode);
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
            jsonRpc(this.props.item3dInfo, "call", {domain: domain}).then(function (data) {
                var info = JSON.parse(data);
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
                      $("#contained_items_data").text(this.scope.messages.noProduct);
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
                        this.scope.camera.position.fromArray(
                            this._realTo3dvSizes(
                                parseInt(info.camx, 10),
                                -parseInt(info.camy, 10),
                                parseInt(info.camz, 10)
                            )
                        );
                        this.scope.target.position.copy(item3d.position);
                        this.scope.camera.lookAt(this.scope.target);
                        this.scope.controls.target.copy(this.scope.target.position);
                        this.scope.controls.update();
                    });
            });

            this.scope.controls.enabled = false;
            this.renderScope();
        }
    }

    /**
     * Mouse move event handler
     *
     * @private
     */
    onContainerMouseMove(event) {
        if ($("#coords_info_icon").is(":visible")) {
            return;
        }
        var item3d = this.findItem3d(event);
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
    }

    /**
     * Window resize event handler
     *
     * @private
     */
    onWindowResize() {
        this._setRendererSize();
    }

    /**
     * Fix the renderer size according to the available space on screen
     *
     * @private
     */
    _setRendererSize() {
        var width;
        var height;
        if ($("#threedview_container").hasClass("fullscreen")) {
            width = $(document).width();
            height = $(document).height();
        } else {
            width = $(".o_content").width();
            height = $(".o_content").height();
        }
        this.scope.camera.aspect = width / height;
        this.scope.camera.updateProjectionMatrix();
        if ($("#threedview_container").hasClass("fullscreen")) {
            this.renderer.setSize(width, height);
        } else {
            this.renderer.setSize(width - 20, height - 20);
        }
        $("#loading_icon").css({
            left: (width - $("#loading_icon").width()) / 2,
            top: (height - $("#loading_icon").height()) / 2,
        });
    }

    /**
     * Add event handlers
     *
     * @private
     */
    _addEventHandlers() {
        $(this.dom3DContainer).dblclick(this.onContainerDoubleClick.bind(this));
        $(this.dom3DContainer).mousemove(this.onContainerMouseMove.bind(this));
        $(window).resize(this.onWindowResize.bind(this));

        $("#close_item3d_info_icon").click((e) => {
            e.preventDefault();
            var item3d = this.scope.scene.getObjectByName("mesh" + $("#item3d_info").data("current"));
            if (item3d) {
                item3d.material.color = new THREE.Color(item3d.userData.item3d.color);
                var wireframe = this.scope.scene.getObjectByName(
                    "wireframe" + item3d.userData.item3d.barcode
                );
                wireframe.material.linewidth = 1;
                wireframe.material.color = new THREE.Color(0x4d4d4d);
            }
            $("#item3d_info").data("current", 0).hide();
            $("#frame_item3d_icon").off("click").hide();
            $("#map_marker_icon").off("click").hide();
            this.scope.controls.enabled = true;
            this.renderScope();
            e.stopPropagation();
        });

        $("#reload_icon").click((e) => {
            e.preventDefault();
            if (!$("#reload_icon").hasClass("clickable")) {
                return;
            }
            this.scope.removeItems3d();
            this.scope.loadItems3d([]);
        });

        $("#fullscreen_icon").click((e) => {
            e.preventDefault();
            $("#threedview_container").toggleClass("fullscreen");
            this._setRendererSize();
            this.renderScope();
        });

        $("#legend_icon").click((e) => {
            e.preventDefault();
            this.showLegend();
            $("#legend").show();
            $("#legend_icon").prop("disabled", true);
        });

        $("#close_legend_icon").click((e) => {
            e.preventDefault();
            $("#legend").hide();
            $("#legend_icon").prop("disabled", false);
        });

        $("#toggle_arrowkeys_meaning_icon").click((e) => {
            e.preventDefault();
            var o = $("#toggle_arrowkeys_meaning_icon");
            o.toggleClass("fa-video-camera").toggleClass("fa-dot-circle-o");
            this.scope.controls.arrowKeys = o.hasClass("fa-video-camera") ? "camera" : "target";
            o.attr(
                "title",
                this.scope.controls.arrowKeys == "camera"
                    ? "Arrow keys move the camera. Click to switch"
                    : "Arrow keys move the target. Click to switch"
            );
        });

        $("#coords_info_icon").click((e) => {
            e.preventDefault();
            $("#coords").show();
            $("#coords_info_icon").hide();
            this.scope.target.visible = true;
            this.showCoordinates();
            this.renderScope();
        });

        $("#coords").click((e) => {
            e.preventDefault();
            $("#coords").hide();
            $("#coords_info_icon").show();
            this.scope.target.visible = false;
            this.renderScope();
        });
    }

    /**
     * Add event handlers
     *
     * @private
     */
    _unbindEventHandlers() {
        console.log("Unbinding events in renderer");
        $(this.dom3DContainer).off();
        $(window).off("resize");
        $("#close_item3d_info_icon").off("click");
        $("#reload_icon").off("click");
        $("#fullscreen_icon").off("click");
        $("#legend_icon").off("click");
        $("#close_legend_icon").off("click");
        $("#toggle_arrowkeys_meaning_icon").off("click");
        $("#coords_info_icon").off("click");
        $("#coords").off("click");
    }

    /**
     * Map millimeters to 3js units (only sizes)
     *
     * @private
     * @returns [*] a three-items array of sizes, scaled
     */
    _realTo3dvSizes(x, y, z, scale = this.scope.scale) {
        return [x / scale, z / scale, y / scale];
    }

    /**
     * Map millimeters to 3js units (coordinates and sizes)
     *
     * @private
     * @returns [*] a three-items array of coordinates, scaled
     */
    _realTo3dvCoords(x, y, z, sizex, sizey, sizez, scale = this.scope.scale) {
        return [(x + sizex / 2) / scale, (z + sizez / 2) / scale, -(y + sizey / 2) / scale];
    }

    /**
     * Map 3js units to millimeters, creating an object
     *
     * @private
     * @returns {} an object with 'x', 'y', and 'z' properties
     */
    _realCoords(xcoord, y, z, scale = this.scope.scale) {
        return {
            x: Math.round(xcoord * scale),
            y: -Math.round(z * scale),
            z: Math.round(y * scale),
        };
    }

    /**
     * Initialize the global reference system used by the renderer
     *
     * @private
     * @param area
     */
    _initRefSys(area) {
        console.log("Initializing reference system...");
        console.log("Areas available:", this.props.data.areas);

        for (let id in this.props.data.areas) {
            let area = this.props.data.areas[id];
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
        this.scope.refSys = this.props.data.areas[area.id].refSys;
        this.scope.scale = this.props.data.areas[area.id].scale;
    }

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
    }
}

// const components = { TreeItem };
OWL3DViewRenderer.components = {};
OWL3DViewRenderer.defaultProps = {
    noAreaLoaded:
        "No area have been loaded. Please check whether the area have a planimetry image and the dimensions correctly set.",
    noProduct: "Nothing is here.",
};
OWL3DViewRenderer.template = "stock_3dview.OWL3DViewRenderer";
OWL3DViewRenderer.props = {
    arch: {
        type: Object,
        optional: true,
    },
    isEmbedded: {
        type: Boolean,
        optional: true,
    },
    noContentHelp: {
        type: String,
        optional: true,
    },
    data: {
        type: Object,
        optional: true,
    },
    activeAreaId: {
        type: Number,
        optional: true,
    },
    item3dInfo: {
        type: String,
        optional: true,
    },
    gltf3dModel: {
        type: String,
        optional: true,
    },
    rendererArea: {
        type: String,
    },
    noAreaLoaded: {
        type: String,
        optional: true,
    },
    noProduct: {
        type: String,
        optional: true,
    },
};

export default OWL3DViewRenderer;
