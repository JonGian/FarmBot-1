$(document).ready(function () {
    $('#submitForm').validate({
        rules: {
            email: {
                required: true,
                email: true
            },
            location: {
                required: true
            },
            password: {
                required: true,
            },
            passwordconf: {
                required: true,
                equalTo: "#password"
            }
        },
        messages: {
            email: {
                required: "An email is required!",
                email: "It must be a valid email address!"
            },
            location: {
                required: "A location is required!"
            },
            password: {
                required: "A password is required!"
            },
            passwordconf: {
                required: "A password is required!",
                equalTo: "The passwords do not match!"
            }
        }
    });
});