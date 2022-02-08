$(document).ready(function() {
    $('.Ot_ShowHidePassword').each(function(ev) {
        var oe_website_login_container = this;
        $(oe_website_login_container).on('click', 'div.input-group-append button.btn.btn-secondary', function() {
            var icon = $(this).find('i.fa.fa-eye').length
            if (icon == 1) {
                $(this).find('i.fa.fa-eye').removeClass('fa-eye').addClass('fa-eye-slash');
                $(this).parent().prev('input[type="password"]').prop('type', 'text');
            } else {
                $(this).find('i.fa.fa-eye-slash').removeClass('fa-eye-slash').addClass('fa-eye');
                $(this).parent().prev('input[type="text"]').prop('type', 'password');
            }
        });
    });

//	$('#wrap_home_mx').each(function(ev) {
//	    var ot_addEffectContainer = this;
//	    $('#ot__rec__img__20').effect("bounce", "delay-4s").focus();
//	    $(ot_addEffectContainer).focus('#ot__rec__img__20', function() {
//            console.log("@@@@@@@@@@@@@@@");
//            console.log("@@@@@@@@@@@@@@@");
//            console.log("@@@@@@@@@@@@@@@");
//	        });
//	    });
//    });
