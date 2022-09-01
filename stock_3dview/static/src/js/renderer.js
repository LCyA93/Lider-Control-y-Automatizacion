odoo.define('stock_3dview.3DViewRenderer', function (require) {
    "use strict";

    var ajax = require('web.ajax');
    var core = require('web.core');
    var AbstractRenderer = require('web.AbstractRenderer');
    var data_manager = require('web.data_manager');
    var session = require('web.session');
    var view_registry = require('web.view_registry');
    var _lt = core._lt;
    const QWeb = require("web.QWeb");


    var container;  // the DOM object where the scene is rendered
    var scope;  // a global object used to store all the data needed

    var ThreeDViewRenderer = AbstractRenderer.extend({
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
            scope.warehouseObjects = {
                wireframes: [],   // for all locations
                meshes: []     // for selected locations
            };
            scope.currentWarehouse = null;
            this.context = {};
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
            var waiting = setInterval(function() {
                if (
                    scope.state.data.allLocationsLoaded &&
                    scope.state.data.selectedLocationsLoaded &&
                    scope.state.data.warehousesLoaded &&
                    scope.state.data.legendLoaded
                ) {
                    if (! scope.renderer) {
                        // we will use the first warehouse for the first rendering
                        scope.currentWarehouse = scope.state.data.warehouses[Object.keys(scope.state.data.warehouses)[0]];
                        if (scope.currentWarehouse) {
                            scope._initRefSys(scope.currentWarehouse);
                            scope.init3d();
                            scope._addEventHandlers();
                            scope.showWireframesForAllLocations();
                        }
                        else {
                            scope._showInformationDialog("No warehouses have been loaded. Please check whether the warehouses have a planimetry image and the dimensions correctly set.");
                        }
                    }

                    scope.currentWarehouse && scope.showMeshesForSelectedLocations();
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
        init3d: function() {
            //console.log("initializing 3d...");
            // camera
            scope.camera = new THREE.PerspectiveCamera( scope.refSys.camFov, window.innerWidth / window.innerHeight, 1, 3000 );
            scope.camera.position.fromArray( scope._realTo3dvSizes( scope.refSys.camPosX_real, -scope.refSys.camPosY_real, scope.refSys.camPosZ_real ) );
            // controls
            scope.controls = new THREE.OrbitControls( scope.camera, document.getElementById( 'threedview_container' ) );
            scope.controls.rotateSpeed = 1.0;
            scope.controls.zoomSpeed = 1.2;
            scope.controls.panSpeed = 0.8;
            scope.controls.enableZoom = true;
            scope.controls.enablePan = true;
            scope.controls.enableDamping = true;
            scope.controls.dampingFactor = 0.3;
            // controls.keys = [ 65, 83, 68 ];
            scope.controls.addEventListener( 'change', scope.render );
            scope.controls.render = scope.render;  // rendering function

            // raycaster
            scope.raycaster = new THREE.Raycaster();
            scope.mouse = new THREE.Vector2();

            // world
            scope.scene = new THREE.Scene();

            var grid = new THREE.GridHelper(2000, 2*scope.refSys.groundX_real/scope.refSys.groundX_3dv);
            grid.position.x=scope.refSys.groundX_3dv/2;
            grid.position.y=-1;
            grid.position.z=-scope.refSys.groundZ_3dv/2;
            scope.scene.add(grid);

            // target object to camera
            scope.target = new THREE.Mesh(
                new THREE.BoxGeometry( 4, 4, 4 ),
                new THREE.MeshPhongMaterial( { color: new THREE.Color("red"), opacity: 1, transparent: true } )
            );
            scope.target.position.fromArray( scope._realTo3dvSizes( scope.refSys.targetX_real, -scope.refSys.targetY_real, scope.refSys.targetZ_real ) );
            scope.target.name = "target";
            scope.target.visible = false;
            scope.scene.add(scope.target);

            scope.camera.updateProjectionMatrix();

            scope.createGround();

            // lights
            scope.scene.add( new THREE.AmbientLight( 0xFFFFFF) );

            // renderer
            scope.renderer = new THREE.WebGLRenderer( { antialias: true } );
            scope.renderer.setClearColor( 0xDFDFDF );
            scope.renderer.setPixelRatio( window.devicePixelRatio );
            scope._setRendererSize();
            container = document.getElementById( 'threedview_container' );
            container.appendChild( scope.renderer.domElement );

            scope.camera.lookAt(scope.target);
            scope.camera.userData.scene = scope.scene;
            scope.controls.target.copy(scope.target.position);
            scope.controls.update();

            scope.activateWarehouseChoice();

            // we need to put this in the event loop because of slow loading of background image
            setTimeout( scope.render, 0 );
        },

        /**
         * Show the legend
         *
         * @private
         */
        showLegend: function( legend ) {
            $("#legend_data").empty();
            if ( scope.state.data.legendItems.length > 0 ) {
                $('#legend_data').append($('<ul/>').attr('id', 'legend_ul'));
                var items=[];
                $( scope.state.data.legendItems ).each(function( index, info ) {
                    $('#legend_ul').append(
                        $('<li/>').append(
                            $('<span/>').addClass('colorbox').css('background-color', info.color).html("&nbsp;")
                        ).append(
                            $('<span/>').text(info.name)
                        )
                    );
                });
            }
        },

        /**
         * Create the ground by placing the image stored in the database.
         *
         * This function uses the information stored in the currentWarehouse object.
         *
         * @private
         */
        createGround: function() {

            // we remove the ground that might be there
            scope.removeObject("ground");
            scope.removeObject("underground");

            var groundImage = document.createElement( 'img' );
            var texture = new THREE.Texture( groundImage );
            groundImage.onload = function()  {
                texture.needsUpdate = true;
            };

            groundImage.src = "data:image/png;base64," +scope.currentWarehouse.ground.planimetry_image;

            texture.wrapS = THREE.ClampToEdgeWrapping;
            texture.wrapT = THREE.ClampToEdgeWrapping;

            var groundGeometry = new THREE.BoxBufferGeometry( scope.refSys.groundX_3dv, 2, scope.refSys.groundZ_3dv );

            var groundMaterial = new THREE.MeshStandardMaterial( { map: texture, flatShading: true } );
            var ground = new THREE.Mesh( groundGeometry, groundMaterial );
            ground.position.fromArray(scope._realTo3dvCoords (0, 0, 0, scope.refSys.groundX_real, scope.refSys.groundY_real, 0)).y=-1;

            // the mesh used for the ground will show its texture on the under face, which we don't want
			// so, here's a simple hack: we create a different mesh just to cover it
            var underground= new THREE.Mesh(
                new THREE.BoxGeometry( scope.refSys.groundX_3dv, 2, scope.refSys.groundZ_3dv ),
                new THREE.MeshPhongMaterial( { color: new THREE.Color("gray"), opacity: 1, transparent: false } )
            );
            underground.position.fromArray(scope._realTo3dvCoords (0, 0, 0, scope.refSys.groundX_real, scope.refSys.groundY_real, 0)).y=-3;
            ground.name = "ground";
            underground.name = "underground";
            scope.scene.add( ground );
            scope.scene.add( underground );
        },

        /**
         * Fill the dropdown list of available warehouses.
         *
         * @private
         */
        activateWarehouseChoice: function() {
            var warehouse_ids = Object.keys(scope.state.data.warehouses);
            if (warehouse_ids.length>1) {
                warehouse_ids.forEach(function(id) {
                    //console.log(id);
                    //console.log(scope.state.data.warehouses[id].name);
                    $("#warehouse_id").append($('<option>', { value: id, text: scope.state.data.warehouses[id].name, id: 'wh'+id }));
                });
                // we don't want the event to be reflected on the canvas
                $("#warehouses").show().bind('blur change click dblclick error focus focusin focusout hover keydown keypress keyup load mousedown mouseenter mouseleave mousemove mouseout mouseover mouseup resize scroll select submit', function(event) {
                    event.stopPropagation();
                });
                $("#warehouse_id").change(function(event) {
                    scope.changeWarehouse($("#warehouse_id").val());
                });
            }
        },

        /**
         * Change warehouse.
         *
         * @param warehouse_id
         * @private
         */
        changeWarehouse: function(warehouse_id) {
            scope.currentWarehouse = scope.state.data.warehouses[warehouse_id];

            scope._initRefSys(scope.currentWarehouse);

            ['wireframes', 'meshes'].forEach(function(item) {
                scope.warehouseObjects[item].forEach(function(obj) {
                    obj.visible = obj.userData.warehouse == scope.currentWarehouse.id;
                });
            });
            scope.createGround();

            // we need to put the rendering in the event loop
            setTimeout( scope.render, 0 );
        },

        /**
         * Remove an object from the 3D scene.
         *
         * @param the name of the object, as defined in the object itself before being added to the scene
         * @private
         */
        removeObject: function( name ) {
            var object = scope.scene.getObjectByName( name );
            if ( object ) {
                scope.scene.remove( object );
                if (object.geometry) object.geometry.dispose();
                if (object.material) object.material.dispose();
            }
        },

        /**
         * Add a new mesh for a warehose location.
         *
         * This is used for the selected locations, that must be shown in full color (or gray).
         *
         * @param location
         * @private
         */
        addMesh: function(location){
            scope.addObject(location, 'mesh');
        },

        /**
         * Add a new wireframe for a warehose location.
         *
         * This is used for all the locations, that must be shown anyway.
         *
         * @param location
         * @private
         */
        addWireframe: function(location) {
            scope.addObject(location, 'wireframe');
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
         * @param location
         * @param type, either 'mesh' or 'wireframe'
         * @private
         */
        addObject: function (location, type) {
        	var size = scope._realTo3dvSizes (location.sizex, location.sizey, location.sizez);
            var geometry = new THREE.BoxBufferGeometry( size[0], size[1], size[2] );

            switch (type) {
                case 'mesh':
                    var material = new THREE.MeshStandardMaterial( { color: new THREE.Color(location.color), flatShading: true, opacity: parseInt(location.opacity, 10)/1000, transparent: true } );
                    var obj = new THREE.Mesh( geometry, material );
                    var key = 'meshes';
                    break;
                case 'wireframe':
                    var edges = new THREE.EdgesGeometry( geometry ); // or WireframeGeometry
                    var material = new THREE.LineBasicMaterial( { color: 0x4D4D4D, linewidth: 1 } );
                    var obj = new THREE.LineSegments( edges, material );
                    var key = 'wireframes';
                    break;
            }

            obj.position.fromArray( scope._realTo3dvCoords (
                parseInt(location.posx, 10),
                parseInt(location.posy, 10),
                parseInt(location.posz, 10),
                parseInt(location.sizex, 10),
                parseInt(location.sizey, 10),
                parseInt(location.sizez, 10)
                ));
            obj.name = type + location.barcode;
            obj.userData.location = location;
            obj.userData.warehouse = location.warehouse;
            obj.visible = obj.userData.warehouse == scope.currentWarehouse.id;
            scope.scene.add( obj );
            scope.warehouseObjects[key].push(obj);
        },

        /**
         * Show the wireframes for all the locations.
         *
         * @private
         */
        showWireframesForAllLocations: function() {
            scope.state.data.allLocations.forEach(function (location) {
                scope.addWireframe(location);
            });
            scope.render();
        },

        /**
         * Show the meshes for the selected locations.
         *
         * Since this is called every time a new selection is done, we
         * switch warehouse when all selected locations belong to one warehouse only.
         *
         * @private
         */
        showMeshesForSelectedLocations: function() {
            // first, we remove all existing meshes from the scene
            scope.warehouseObjects.meshes.forEach(function(obj) {
                scope.removeObject(obj.name);
            });
            scope.warehouseObjects.meshes = [];

            // we use this object as a set to store warehouses' ids
            let warehouses = {};

            scope.state.data.selectedLocations.forEach(function (location) {
                scope.addMesh(location);
                if (location.warehouse) {
                    warehouses[location.warehouse]=true;
                }
            });

            // if all selected locations are in the same warehouse, we switch to it
            // by changing the option in the dropdown menu
            if (Object.keys(warehouses).length == 1) {
                $("#warehouse_id").val(Object.keys(warehouses)[0]).change();
            }

            scope.render();
        },

        // find location position

        /**
         * Find a location by using the raycaster.
         *
         * This function only searches the meshes array (thus, only selected locations)
         *
         * @private
         */
        findLocation: function ( event ) {
            if ( $('#location_info').data('current')!==0 )
            {
                return;
            }
            scope.mouse.x = ( (event.clientX - $('#threedview_container').offset().left -10 ) / scope.renderer.domElement.clientWidth ) * 2 - 1;
            scope.mouse.y = - ( (event.clientY - $('#threedview_container').offset().top -10) / scope.renderer.domElement.clientHeight ) * 2 + 1;
            scope.raycaster.setFromCamera( scope.mouse, scope.camera );
            var intersects = scope.raycaster.intersectObjects( scope.warehouseObjects.meshes.filter( obj => obj.userData.warehouse == scope.currentWarehouse.id ));
            if ( intersects.length > 0 ) {
                return intersects[ 0 ].object;
            }
            return false;
        },

        /**
         * Call the actual ThreeJS Renderer
         *
         * @private
         */
        render: function() {
            //console.log("ready!");
        	var self = this;
            scope.target.position.copy(scope.controls.target);
            if (!$("#coords_info_icon").is(":visible")) {
                scope.showCoordinates();
            }
            scope.renderer.render( scope.scene, scope.camera );
        },

        /**
         * Show the coordinates
         *
         * @private
         */
        showCoordinates() {
            var c = scope._realCoords( scope.camera.position.x, scope.camera.position.y, scope.camera.position.z );
            var t = scope._realCoords( scope.target.position.x, scope.target.position.y, scope.target.position.z );
            $("#coords").html(
                'camera: ' + c.x + ', ' + c.y + ', ' + c.z + '<br />' +
                'target: ' + t.x + ', ' + t.y + ', ' + t.z );
        },


        /**
         * Event handler for mobile devices
         *
         * For the use on mobile devices, where you can use two or three different fingers to do something
         *
         * @private
         */
        onContainerTouchStart: function( event ) {
            event.preventDefault();
            event.clientX = event.touches[0].clientX;
            event.clientY = event.touches[0].clientY;
            onDocumentMouseDown( event );
        },


        /**
         * Double click event handler
         *
         * On double click on a location, we retrieve some information from Odoo about that location
         *
         * @private
         */
        onContainerDoubleClick: function( event ) {
            event.preventDefault();
            $( "#barcode_label" ).hide();
            var location = scope.findLocation( event );
            //console.log(scope.warehouseObjects);
            if ( location ) {
                //console.log(location);
                location.material.color.setHex( 0xBEBEBE );
                var wireframe = scope.scene.getObjectByName('wireframe' + location.userData.location.barcode);
                wireframe.material.linewidth = 2;
                wireframe.material.color.setHex( 0xA3498B );
                $("#location_info")
                    .css({
                        'top': event.clientY - $('#threedview_container').offset().top - 10,
                        'left': event.clientX - $('#threedview_container').offset().left - 10
                        })
                    .data('current', location.userData.location.barcode)
                    .show()
                    ;
                if ( parseInt($("#location_info").css("right"), 10 ) < 0 )
                {
                    $("#location_info").css('left', event.clientX - $('#threedview_container').offset().left - $("#location_info").width() - 30 );
                }
                if ( parseInt($("#location_info").css("bottom"), 10 ) < 0 )
                {
                    $("#location_info").css('top', event.clientY - $('#threedview_container').offset().top - $("#location_info").height() - 30 );
                }
                $("#location_data").text(location.userData.barcode + ", retrieving info...");
                var domain = [['barcode', '=', location.userData.location.barcode]];
                ajax.jsonRpc("/3dview/get_info", 'call', {'domain': domain }).then( function (data) {
                    var info = JSON.parse(data);
                    //console.log("info received");
                    //console.log(info);
                    $("#location_data").text(info.barcode);
                    var stock_info = "empty";
                    if ( info.product_qty ) {
                        stock_info = info.product_name + " (" + info.product_qty + ")";
                    }
                    if ( session.debug ) {
                        $("#location_data").text($("#location_data").text() + ' (id: ' + info['id'] + ')');
                    }
                    $("#products_data").empty();
                    if ( info.products.length ) {
                        $('#products_data').append($('<ul/>').attr('id', 'products_ul'));
                        var items=[];
                        $( info.products ).each(function( index, sq ) {
                            $('#products_ul').append($('<li/>').text( '[' + sq.product_code + '] ' + sq.product_name + ' (' + sq.product_qty + ')' ));
                        });
                    } else
                    {
                        $("#products_data").text('No product is stored here.');
                    }
                    $( "#location_info" ).height( 20 + $("#products_data").height() );
                    if ( parseInt($("#location_info").css("bottom"), 10 ) < 0 )
                    {
                        $("#location_info").css('top', event.clientY - $('#threedview_container').offset().top - $("#location_info").height() - 30 );
                    }
                    $("#frame_location_icon").show().click( function( event ) {
                        event.preventDefault();
                        scope.camera.position.fromArray( scope._realTo3dvSizes( parseInt(info.camx, 10), -parseInt(info.camy, 10), parseInt(info.camz, 10) ) );
                        scope.target.position.copy(location.position);
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
        onContainerMouseMove: function( event ) {
            if ($("#coords_info_icon").is(":visible"))
            {
                return;
            }
            var location = scope.findLocation( event );
            if ( location ) {
                $( "#barcode_label" )
                    .text( location.userData.barcode )
                    .css({ 'top': event.clientY - $('#threedview_container').offset().top - 5, 'left': event.clientX - $('#threedview_container').offset().left + 20})
                    .show();
            }
            else {
                $( "#barcode_label" ).hide();
            }
        },

        /**
         * Window resize event handler
         *
         * @private
         */
        onWindowResize: function() {
            scope._setRendererSize();
        },

        /**
         * Fix the renderer size according to the available space on screen
         *
         * @private
         */
        _setRendererSize: function() {
            var width;
            var height;
            if ( $("#threedview_container" ).hasClass( "fullscreen" ) ) {
                width = $(document).width();
                height = $(document).height();
            } else {
                width = $('.o_content').width();
                height = $('.o_content').height();
            }
            scope.camera.aspect = width / height;
            scope.camera.updateProjectionMatrix();
            if ( $("#threedview_container").hasClass( "fullscreen" ) ) {
                scope.renderer.setSize( width, height );
            } else {
                scope.renderer.setSize( width -20 , height -20  );
            }
            $("#loading_icon").css( {
                'left': (width - $("#loading_icon").width() ) / 2,
                'top': (height - $("#loading_icon").height() ) / 2,
                } );
        },

        /**
         * Add event handlers
         *
         * @private
         */
        _addEventHandlers: function() {

            $( container ).dblclick( this.onContainerDoubleClick );
            $( container ).mousemove( this.onContainerMouseMove );
            $( window ).resize ( this.onWindowResize );

            $("#close_location_info_icon").click(function(e) {
                e.preventDefault();
                //console.log("Closing window");
                var location = scope.scene.getObjectByName( "mesh" + $("#location_info").data("current") );
                if ( location )
                {
                    location.material.color = new THREE.Color(location.userData.location.color);
                    var wireframe = scope.scene.getObjectByName('wireframe' + location.userData.location.barcode);
                    wireframe.material.linewidth = 1;
                    wireframe.material.color = new THREE.Color( 0x4D4D4D );
                }
                $("#location_info").data("current", 0).hide();
                $("#frame_location_icon").off("click").hide();
                $("#map_marker_icon").off("click").hide();
                scope.controls.enabled = true;
                scope.render();
                e.stopPropagation();
            });

            $("#reload_icon").click(function(e) {
                e.preventDefault();
                if ( !$("#reload_icon").hasClass('clickable') )
                {
                    return;
                }
                scope.removeLocations();
                scope.loadLocations([]);
            });

            $("#fullscreen_icon").click(function(e) {
                e.preventDefault();
                $("#threedview_container").toggleClass("fullscreen");
                scope._setRendererSize();
                scope.render();
            });

            $("#legend_icon").click(function(e) {
                e.preventDefault();
                scope.showLegend();
                $("#legend").show();
                $("#legend_icon").prop('disabled', true);
            });

            $("#close_legend_icon").click(function(e) {
                e.preventDefault();
                $("#legend").hide();
                $("#legend_icon").prop('disabled', false);
            });

            $("#toggle_arrowkeys_meaning_icon").click(function(e) {
                e.preventDefault();
                var o = $("#toggle_arrowkeys_meaning_icon");
                o.toggleClass("fa-video-camera").toggleClass("fa-dot-circle-o");
                scope.controls.arrowKeys = o.hasClass("fa-video-camera") ? 'camera': 'target';
                o.attr("title", scope.controls.arrowKeys=='camera' ?
                    "Arrow keys move the camera. Click to switch":
                    "Arrow keys move the target. Click to switch"
                    );
            });

            $("#coords_info_icon").click(function(e) {
                e.preventDefault();
                $("#coords").show();
                $("#coords_info_icon").hide();
                scope.target.visible = true;
                scope.showCoordinates();
                scope.render();
            });

            $("#coords").click(function(e) {
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
        _realTo3dvSizes: function(x, y, z) {
            return [x / scope.scale, z / scope.scale, y / scope.scale];
        },

        /**
         * Map millimeters to 3js units (coordinates and sizes)
         *
         * @private
         * @returns [*] a three-items array of coordinates, scaled
         */
        _realTo3dvCoords: function(x, y, z, sizex, sizey, sizez) {
            return [ (x + sizex/2) / scope.scale, (z + sizez/2) / scope.scale, - (y +sizey/2) / scope.scale];
        },

        /**
         * Map 3js units to millimeters, creating an object
         *
         * @private
         * @returns {} an object with 'x', 'y', and 'z' properties
         */
        _realCoords: function ( x, y, z ) {
            return { 'x': Math.round( x * scope.scale ), 'y': - Math.round( z * scope.scale ), 'z': Math.round( y * scope.scale ) };
        },

        /**
         * Initialize the global reference system used by the renderer
         *
         * @private
         * @param warehouse
         */
        _initRefSys: function(warehouse) {
            scope.refSys = {
                groundX_real: warehouse.ground.sizex,
                groundY_real: warehouse.ground.sizey,
                heightZ_real: warehouse.ground.sizez,
                camPosX_real: warehouse.camera.camx,
                camPosY_real: warehouse.camera.camy,
                camPosZ_real: warehouse.camera.camz,
                camFov: warehouse.camera.camfov
            };
            scope.refSys.targetX_real = warehouse.ground.sizex / 2;
            scope.refSys.targetY_real = warehouse.ground.sizey / 2;
            scope.refSys.targetZ_real = 0;
            scope.refSys.groundX_3dv = 500;
            scope.refSys.groundZ_3dv = Math.round( scope.refSys.groundY_real / scope.refSys.groundX_real * scope.refSys.groundX_3dv );
            scope.refSys.heightY_3dv = Math.round( scope.refSys.heightZ_real / scope.refSys.groundX_real * scope.refSys.groundX_3dv );
            scope.scale = scope.refSys.groundX_real / scope.refSys.groundX_3dv;
        },

        _showInformationDialog(text) {
            //alert(text);
            $('#dialog').html(text).show();
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

    });

    return ThreeDViewRenderer;
    });
