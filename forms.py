# Third Party
import flask
import flask.ext.security
import flask.ext.wtf
import phonenumbers
import pytz
import wtforms
import wtforms.ext.sqlalchemy.fields
# Local
import main
import models
import utils


def simple_field_filter(field):
    special_fields = (wtforms.HiddenField, wtforms.FileField,
                      wtforms.SubmitField)
    return not isinstance(field, special_fields)

main.app.jinja_env.filters['simple_field_filter'] = simple_field_filter


def valid_user_email(form, field):
    try:
        utils.format_phone(form.data)
    except phonenumbers.NumberParseException:
        raise wtforms.ValidationError('Invalid mobile number.')


class ContactFormMixin(object):
    country_code = wtforms.TextField(default='1')
    phone = wtforms.TextField(label='Mobile Number')
    email = wtforms.TextField(validators=[wtforms.validators.Email(),
                                          wtforms.validators.Optional(),
                                          valid_user_email])


class ContactForm(flask.ext.wtf.Form, ContactFormMixin):
    def validate(self):
        if not super(ContactForm, self).validate():
            return False
        if not (self.email.data or utils.format_phone(self.data)):
            message = 'Please provide either a mobile number or email address.'
            self.phone.errors.append(message)
            self.email.errors.append(message)
            return False
        return True


hour_validator = wtforms.validators.NumberRange(min=1, max=12)
minute_validator = wtforms.validators.NumberRange(min=0, max=59)
weekday_choices = [(0, 'Sunday'), (1, 'Monday'), (2, 'Tuesday'),
                   (3, 'Wednesday'), (4, 'Thursday'), (5, 'Friday'),
                   (6, 'Saturday')]
timezone_choices = zip(pytz.common_timezones, pytz.common_timezones)
timezone_choices.insert(0, ('', ''))


class ScheduleForm(flask.ext.wtf.Form):
    days_of_week = wtforms.SelectMultipleField('Days of the Week',
                                               [wtforms.validators.Required()],
                                               choices=weekday_choices,
                                               coerce=int)
    hour = wtforms.IntegerField(validators=[hour_validator])
    minute = wtforms.IntegerField(validators=[minute_validator], default='00')
    am_pm = wtforms.RadioField('Time of Day',
                               choices=[('am', 'am'), ('pm', 'pm')])
    timezone = wtforms.SelectField('Time Zone', choices=timezone_choices,
                                   validators=[wtforms.validators.Required()])


class MobileVerifyForm(flask.ext.wtf.Form,
                       flask.ext.security.forms.NextFormMixin):
    code = wtforms.IntegerField()

    def __init__(self, *args, **kwargs):
        super(MobileVerifyForm, self).__init__(*args, **kwargs)
        if not self.next.data:
            self.next.data = flask.request.args.get('next', '')


class PasswordChangeForm(flask.ext.wtf.Form):
    new_password = wtforms.PasswordField('New Password',
                                         [wtforms.validators.Required(),
                                          wtforms.validators.EqualTo('confirm',
                                          message='Passwords must match')])
    confirm = wtforms.PasswordField('Repeat Password')


def unique_user_email(form, field):
    user = models.User.query.filter_by(email=field.data).first()
    if user is not None and user.confirmed_at is not None:
        get_message = flask.ext.security.utils.get_message
        msg = get_message('EMAIL_ALREADY_ASSOCIATED', email=field.data)[0]
        raise wtforms.ValidationError(msg)


class LoginForm(flask.ext.wtf.Form, flask.ext.security.forms.NextFormMixin,
                ContactFormMixin):
    password = wtforms.PasswordField('Password')
    remember = wtforms.BooleanField('Remember Me')
    submit = wtforms.SubmitField('Login')

    def validate(self):
        if not super(LoginForm, self).validate():
            return False
        security = flask.ext.security
        email = self.email.data
        phone = utils.format_phone(self.data)
        password = self.password.data
        if not (email or phone):
            message = 'Please enter either an email address or phone number.'
            self.phone.errors.append(message)
            self.email.errors.append(message)
            return False
        if password.strip() == '' or password is None:
            message = security.utils.get_message('PASSWORD_NOT_PROVIDED')[0]
            self.password.errors.append(message)
            return False
        self.user = main.user_datastore.get_user(self.email.data)
        if self.user is None and phone:
            query = main.user_datastore.user_model.query
            self.user = query.filter_by(phone=phone).first()
        if self.user is None:
            message = security.utils.get_message('USER_DOES_NOT_EXIST')[0]
            if phone:
                self.phone.errors.append(message)
            if email:
                self.email.errors.append(message)
            return False
        if not self.user.password:
            message = security.utils.get_message('PASSWORD_NOT_SET')[0]
            self.password.errors.append(message)
            return False
        if not security.utils.verify_and_update_password(self.password.data,
                                                         self.user):
            message = security.utils.get_message('INVALID_PASSWORD')[0]
            self.password.errors.append(message)
            return False
        if security.confirmable.requires_confirmation(self.user):
            message = security.utils.get_message('CONFIRMATION_REQUIRED')[0]
            if phone:
                self.phone.errors.append(message)
            if email:
                self.email.errors.append(message)
            return False
        if not self.user.is_active():
            message = security.utils.get_message('DISABLED_ACCOUNT')[0]
            if phone:
                self.phone.errors.append(message)
            if email:
                self.email.errors.append(message)
            return False
        return True


class ConfirmRegisterForm(flask.ext.wtf.Form, ContactFormMixin,
                          flask.ext.security.forms.RegisterFormMixin):
    password = wtforms.PasswordField('Password',
                                     [wtforms.validators.Required(),
                                      wtforms.validators.Length(6, 128)])

    def validate(self):
        url_for_security = flask.ext.security.utils.url_for_security
        if not super(ConfirmRegisterForm, self).validate():
            return False
        email = self.email.data
        phone = utils.format_phone(self.data)
        if not (email or phone):
            message = 'Please enter either an email address or phone number.'
            self.phone.errors.append(message)
            self.email.errors.append(message)
            return False
        user = main.user_datastore.get_user(self.email.data)
        if user is None and phone:
            query = main.user_datastore.user_model.query
            user = query.filter_by(phone=phone).first()
        email_confirmed = (email and user.password and user.confirmed_at)
        phone_confirmed = (phone and user.password and user.phone_confirmed_at)
        if user and (email_confirmed or phone_confirmed):
            login_url = url_for_security('login')
            forgot_url = url_for_security('forgot_password')
            message = 'You have already successfully registered. You should be'
            message += ' able to <a href="{}" class="alert-link">login</a>. If'
            message += 'you have forgotten your password, please visit the'
            message += ' <a href="{}" class="alert-link">forgotten'
            message += ' password</a> page.'
            flask.flash(message.format(login_url, forgot_url), 'error')
            errors = self.phone.errors if phone else self.email.errors
            errors.append('Already registered')
            return False
        if user and email and user.confirmed_at is None:
            confirm_url = url_for_security('send_confirmation')
            message = 'You have already registered but need to confirm your'
            message += ' email address. If you have deleted or did not receive'
            message += ' your confirmation email, you may <a href="{}"'
            message += ' class="alert-link">send a new request</a>.'
            flask.flash(message.format(confirm_url), 'error')
            self.email.errors.append('Registration pending')
            return False
        if user and phone and user.phone_confirmed_at is None:
            next_url = flask.ext.security.utils.get_post_register_redirect()
            confirm_url = flask.url_for('confirm_mobile', action='re-send',
                                        next=next_url)
            message = 'You have already registered but need to confirm your'
            message += ' mobile number. If you have deleted or did not receive'
            message += ' your confirmation SMS, you may <a href="{}"'
            message += ' class="alert-link">send a new request</a>.'
            flask.flash(message.format(confirm_url), 'error')
            self.phone.errors.append('Registration pending')
            return False
        return True

main.app.extensions['security'].login_form = LoginForm
