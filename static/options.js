$(function(){

	$("a.advanced")
		.show()
		.click(function(){ $("form.advanced").toggle(); });
	$("form.advanced")
		.hide();

});
