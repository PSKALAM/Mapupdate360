// Create viewer.
var viewer = new Marzipano.Viewer(document.getElementById('pano'));

// Create source.
var source = Marzipano.ImageUrlSource.fromString(
    "image.jpg"
);

// Create geometry.
var geometry = new Marzipano.EquirectGeometry([{
    width: 8192
}]);

// Create view.
var limiter = Marzipano.RectilinearView.limit.traditional(8192, 100 * Math.PI / 180);
var initialView = { yaw:0, pitch:0, roll:0 };
var view = new Marzipano.RectilinearView(initialView, limiter);

// Create scene.
var scene = viewer.createScene({
    source: source,
    geometry: geometry,
    view: view,
    pinFirstLevel: true
});

// Display scene.
scene.switchTo();

function SetImageFilter(brightness, contrast, saturation) {
    var pano = document.getElementById('pano');
    if (!pano) {
        return;
    }
    var filterValue = 'brightness(' + brightness + '%) contrast(' + contrast + '%) saturate(' + saturation + '%)';
    pano.style.filter = filterValue;
    pano.style.webkitFilter = filterValue;
}

var viewChangeHandler = function() {
    var yaw = view.yaw();
    var d_yaw = yaw / (Math.PI / 180);
    var verticalFov = view.fov();
    var pano = document.getElementById('pano');
    var width = pano && pano.clientWidth ? pano.clientWidth : 1;
    var height = pano && pano.clientHeight ? pano.clientHeight : 1;
    var horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * width / height);
    var d_fov = horizontalFov / (Math.PI / 180);
    console.log(d_yaw + ',' + d_fov);
};

view.addEventListener('change', viewChangeHandler);
viewChangeHandler();
