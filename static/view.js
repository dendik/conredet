jQuery(function($){
	"use strict"

	var $image = $(".zoom-container img")
	var $navlinks = $("nav.zoom a")
	
	// enable pan & zoom
	$image.panzoom({minScale: 0.5, maxScale: 10})

	// use nav as tabs
	$navlinks.each(function(){
		var $link = $(this)
		$link.click(function(event){
			$image.attr('src', "img-b" + $link.attr('id') + ".png")
		})
	})

	// zoom on mouse wheel
	$image.parent().on('mousewheel.focal', function(event){
		event.preventDefault()
		var delta = event.delta || event.originalEvent.wheelDelta
		var zoomOut = delta ? delta < 0 : event.originalEvent.deltaY > 0
		$image.panzoom('zoom', zoomOut, {
			increment: 0.2,
			animate: false,
			focal: event
		})
	})

})
