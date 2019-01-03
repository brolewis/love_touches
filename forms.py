# Standard Library
import datetime

# Third Party
import flask
import flask_admin.form
import flask_security
import flask_wtf
import phonenumbers
import pyotp
import pytz
import wtforms
import wtforms.ext.sqlalchemy.fields

# Local
import main
import models
import utils


def simple_field_filter(field):
    special_fields = (wtforms.HiddenField, wtforms.FileField, wtforms.SubmitField)
    return not isinstance(field, special_fields)


def time_since(in_dt):
    """
    Calculate time since a given (date)time.

    Takes a datetime object and returns the time between it and now as a nicely
    formatted string, e.g. "10 minutes".  If d occurs after now, then "0 minutes" is
    returned.
    """
    chunks = (
        (60 * 60 * 24 * 365, "{} year"),
        (60 * 60 * 24 * 30, "{} month"),
        (60 * 60 * 24 * 7, "{} week"),
        (60 * 60 * 24, "{} day"),
        (60 * 60, "{} hour"),
        (60, "{} minute"),
    )
    # Convert datetime.date to datetime.datetime for comparison.
    if not isinstance(in_dt, datetime.datetime):
        in_dt = datetime.datetime(in_dt.year, in_dt.month, in_dt.day)
    now = datetime.datetime.utcnow()

    delta = now - in_dt
    # ignore microseconds
    since = delta.days * 24 * 60 * 60 + delta.seconds
    if since <= 0:
        # in_dt is in the future compared to now, stop processing.
        return "0 minutes"
    for i, (seconds, name) in enumerate(chunks):
        count = since // seconds
        if count != 0:
            break
    result = name.format(count)
    if count > 1:
        result += "s"
    if i + 1 < len(chunks):
        # Now get the second item
        seconds2, name2 = chunks[i + 1]
        count2 = (since - (seconds * count)) // seconds2
        if count2 != 0:
            result += ", {}".format(name2.format(count2))
            if count2 > 1:
                result += "s"
    return result


main.app.jinja_env.filters["simple_field_filter"] = simple_field_filter
main.app.jinja_env.filters["time_since"] = time_since

REQUIRED = wtforms.validators.DataRequired()


def valid_user_email(form, field):
    try:
        utils.format_phone(form.data)
    except phonenumbers.NumberParseException:
        raise wtforms.ValidationError("Invalid mobile number.")


class ContactFormMixin(object):
    country_code = wtforms.StringField(default="1")
    phone = wtforms.StringField(label="Mobile Number")
    email = wtforms.StringField(
        validators=[
            wtforms.validators.Email(),
            wtforms.validators.Optional(),
            valid_user_email,
        ]
    )


class ContactForm(
    flask_wtf.FlaskForm, ContactFormMixin, flask_security.forms.NextFormMixin
):
    def __init__(self, *args, **kwargs):  # noqa: D107
        if "next" in flask.session:
            del flask.session["next"]
        super(ContactForm, self).__init__(*args, **kwargs)
        if not self.next.data:
            self.next.data = flask.request.args.get("next", "")

    def validate(self):
        if not super(ContactForm, self).validate():
            return False
        if not (self.email.data or utils.format_phone(self.data)):
            message = "Please provide either a mobile number or email address."
            self.phone.errors.append(message)
            self.email.errors.append(message)
            return False
        return True


minutes = [(x, "{:02d}".format(x)) for x in range(0, 60, 15)]
weekday_choices = [
    (6, "Sunday"),
    (0, "Monday"),
    (1, "Tuesday"),
    (2, "Wednesday"),
    (3, "Thursday"),
    (4, "Friday"),
    (5, "Saturday"),
]
timezone_choices = list(zip(pytz.common_timezones, pytz.common_timezones))
timezone_choices.insert(0, ("", ""))


class ScheduleForm(flask_wtf.FlaskForm, flask_security.forms.NextFormMixin):
    days_of_week = wtforms.SelectMultipleField(
        "Days of the Week", [REQUIRED], choices=weekday_choices, coerce=int
    )
    hour = wtforms.SelectField(
        choices=[(x, x) for x in range(1, 13)],
        validators=[REQUIRED],
        default=6,
        coerce=int,
    )
    minute = wtforms.SelectField(choices=minutes, coerce=int)
    am_pm = wtforms.RadioField("Time of Day", choices=[("am", "am"), ("pm", "pm")])
    timezone = flask_admin.form.Select2Field(
        choices=timezone_choices, validators=[REQUIRED]
    )

    def __init__(self, *args, **kwargs):  # noqa: D107
        if "next" in flask.session:
            del flask.session["next"]
        super(ScheduleForm, self).__init__(*args, **kwargs)
        if not self.next.data:
            self.next.data = flask.request.args.get("next", "")


class MobileVerifyForm(flask_wtf.FlaskForm, flask_security.forms.NextFormMixin):
    code = wtforms.IntegerField()

    def __init__(self, *args, **kwargs):  # noqa: D107
        super(MobileVerifyForm, self).__init__(*args, **kwargs)
        if not self.next.data:
            self.next.data = flask.request.args.get("next", "")


class SuggestMethodForm(flask_wtf.FlaskForm):
    name = wtforms.StringField(label="Method Name", validators=[REQUIRED])
    section = wtforms.FieldList(
        wtforms.StringField(validators=[REQUIRED]), label="Sections", min_entries=2
    )


class SuggestActionForm(flask_wtf.FlaskForm):
    action_name = flask_admin.form.Select2TagsField(save_as_list=True)


class FeedbackForm(flask_wtf.FlaskForm):
    message = wtforms.TextAreaField(validators=[REQUIRED])


class TwoFactorConfirmationForm(
    flask_wtf.FlaskForm, flask_security.forms.NextFormMixin
):
    token = wtforms.StringField(validators=[REQUIRED])

    def __init__(self, *args, **kwargs):  # noqa: D107
        super(TwoFactorConfirmationForm, self).__init__(*args, **kwargs)
        if not self.next.data:
            self.next.data = flask.request.args.get("next", "")

    def validate_token(self, field):
        if field.data:
            user = getattr(self, "user", flask_security.current_user)
            totp = pyotp.TOTP(user.secret)
            if not totp.verify(field.data):
                raise wtforms.ValidationError("Invalid token")


def unique_user_email(form, field):
    user = models.User.query.filter_by(email=field.data).first()
    if user is not None and user.confirmed_at is not None:
        get_message = flask_security.utils.get_message
        msg = get_message("EMAIL_ALREADY_ASSOCIATED", email=field.data)[0]
        raise wtforms.ValidationError(msg)


class LoginForm(
    flask_wtf.FlaskForm, flask_security.forms.NextFormMixin, ContactFormMixin
):
    password = wtforms.PasswordField("Password")
    remember = wtforms.BooleanField("Remember Me")
    submit = wtforms.SubmitField("Login")

    def __init__(self, *args, **kwargs):  # noqa: D107
        super(LoginForm, self).__init__(*args, **kwargs)
        if not self.next.data:
            self.next.data = flask.request.args.get("next", "")

    def validate(self):
        if not super(LoginForm, self).validate():
            return False
        security = flask_security
        email = self.email.data
        phone = utils.format_phone(self.data)
        password = self.password.data
        if not (email or phone):
            message = "Please enter either an email address or phone number."
            self.phone.errors.append(message)
            self.email.errors.append(message)
            return False
        if password.strip() == "" or password is None:
            message = security.utils.get_message("PASSWORD_NOT_PROVIDED")[0]
            self.password.errors.append(message)
            return False
        self.user = main.user_datastore.get_user(self.email.data)
        if self.user is None and phone:
            query = main.user_datastore.user_model.query
            self.user = query.filter_by(phone=phone).first()
        if self.user is None:
            message = security.utils.get_message("USER_DOES_NOT_EXIST")[0]
            if phone:
                self.phone.errors.append(message)
            if email:
                self.email.errors.append(message)
            return False
        if not self.user.password:
            message = security.utils.get_message("PASSWORD_NOT_SET")[0]
            self.password.errors.append(message)
            return False
        if not security.utils.verify_and_update_password(self.password.data, self.user):
            message = security.utils.get_message("INVALID_PASSWORD")[0]
            self.password.errors.append(message)
            return False
        if security.confirmable.requires_confirmation(self.user):
            message = security.utils.get_message("CONFIRMATION_REQUIRED")[0]
            if phone:
                self.phone.errors.append(message)
            if email:
                self.email.errors.append(message)
            return False
        if not self.user.is_active():
            message = security.utils.get_message("DISABLED_ACCOUNT")[0]
            if phone:
                self.phone.errors.append(message)
            if email:
                self.email.errors.append(message)
            return False
        return True


class ConfirmRegisterForm(
    flask_wtf.FlaskForm, ContactFormMixin, flask_security.forms.RegisterFormMixin
):
    password = wtforms.PasswordField(
        "Password", [REQUIRED, wtforms.validators.Length(6, 128)]
    )

    def validate(self):
        url_for_security = flask_security.utils.url_for_security
        if not super(ConfirmRegisterForm, self).validate():
            return False
        email = self.email.data
        phone = utils.format_phone(self.data)
        if not (email or phone):
            message = "Please enter either an email address or phone number."
            self.phone.errors.append(message)
            self.email.errors.append(message)
            return False
        user = main.user_datastore.get_user(self.email.data)
        if user is None and phone:
            query = main.user_datastore.user_model.query
            user = query.filter_by(phone=phone).first()
        if user and user.password and user.confirmed_at:
            login_url = flask.url_for("login")
            forgot_url = url_for_security("forgot_password")
            message = "You have already successfully registered. You should be"
            message += ' able to <a href="{}" class="alert-link">login</a>. If'
            message += "you have forgotten your password, please visit the"
            message += ' <a href="{}" class="alert-link">forgotten'
            message += " password</a> page."
            flask.flash(message.format(login_url, forgot_url), "error")
            errors = self.phone.errors if phone else self.email.errors
            errors.append("Already registered")
            return False
        if user and email and user.password and user.confirmed_at is None:
            confirm_url = url_for_security("send_confirmation")
            message = "You have already registered but need to confirm your"
            message += " email address. If you have deleted or did not receive"
            message += ' your confirmation email, you may <a href="{}"'
            message += ' class="alert-link">send a new request</a>.'
            flask.flash(message.format(confirm_url), "error")
            self.email.errors.append("Registration pending")
            return False
        if user and phone and user.password and user.confirmed_at is None:
            next_url = flask_security.utils.get_post_register_redirect()
            confirm_url = flask.url_for(
                "confirm_mobile", action="re-send", next=next_url
            )
            message = "You have already registered but need to confirm your"
            message += " mobile number. If you have deleted or did not receive"
            message += ' your confirmation SMS, you may <a href="{}"'
            message += ' class="alert-link">send a new request</a>.'
            flask.flash(message.format(confirm_url), "error")
            self.phone.errors.append("Registration pending")
            return False
        return True
