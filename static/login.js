$(document).ready(function () {
    $('#submitForm').validate({
        rules: {
            email: {
                required: true,
                email: true
            },
            password: {
                required: true
            }
        },

        messages: {
            email: {
                required: "An email is required!",
                email: "It must be a valid email address!"
            },
            password: {
                required: "A password is required"
            }
        }
    });
});