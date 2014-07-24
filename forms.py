# Third Party
import flask
import flask.ext.security as security
import flask.ext.wtf
import phonenumbers
import pytz
import wtforms
import wtforms.ext.sqlalchemy.fields
# Local
import main
import utils


def simple_field_filter(field):
    special_fields = (wtforms.HiddenField, wtforms.FileField)
    return not isinstance(field, special_fields)

main.app.jinja_env.filters['simple_field_filter'] = simple_field_filter


class ProfileForm(flask.ext.wtf.Form):
    country_code = wtforms.TextField(default='1')
    phone = wtforms.TextField(label='Mobile Number')
    email = wtforms.TextField(validators=[wtforms.validators.Email(),
                                          wtforms.validators.Optional()])

    def __init__(self, *args, **kwargs):
        super(ProfileForm, self).__init__(*args, **kwargs)

    def validate(self):
        if not super(ProfileForm, self).validate():
            return False
        try:
            utils.format_phone(self.data)
        except phonenumbers.NumberParseException:
            message = "The phone number doesn't appear to be valid..."
            self.phone.errors.append(message)
            return False
        else:
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


class PhoneVerifyForm(flask.ext.wtf.Form):
    code = wtforms.IntegerField()


class PasswordChangeForm(flask.ext.wtf.Form):
    new_password = wtforms.PasswordField('New Password',
                                         [wtforms.validators.Required(),
                                          wtforms.validators.EqualTo('confirm',
                                          message='Passwords must match')])
    confirm = wtforms.PasswordField('Repeat Password')


class LoginForm(security.forms.Form, security.forms.NextFormMixin):
    country_code = wtforms.TextField(default='1')
    phone = wtforms.TextField(label='Mobile Number')
    email = wtforms.TextField(validators=[wtforms.validators.Email(),
                                          wtforms.validators.Optional()])
    password = wtforms.PasswordField('Password')
    remember = wtforms.BooleanField('Remember Me')
    submit = wtforms.SubmitField('Login')

    def __init__(self, *args, **kwargs):
        super(LoginForm, self).__init__(*args, **kwargs)

    def validate(self):
        if not super(LoginForm, self).validate():
            return False
        try:
            phone = utils.format_phone(self.data)
        except phonenumbers.NumberParseException:
            message = "The phone number doesn't appear to be valid."
            self.phone.errors.append(message)
            return False
        email = self.email.data.strip()
        password = self.password.data
        if not (phone or email):
            message = 'Please enter either an email address or mobile number.'
            self.phone.errors.append(message)
            self.email.errors.append(message)
            return False
        if password.strip() == '' or password is None:
            message = security.utils.get_message('PASSWORD_NOT_PROVIDED')[0]
            self.password.errors.append(message)
            return False
        email_filter = main.user_datastore.user_model.email.ilike(email)
        query = main.user_datastore.user_model.query
        user = query.filter(email_filter).first()
        if user is None:
            user = query.filter_by(phone=phone).first()
        if user is None:
            message = "There doesn't seem to be an account associated with "
            message += 'either the provided email address or mobile number.'
            self.phone.errors.append(message)
            self.email.errors.append(message)
            return False
        if user.phone_confirmed_at is None:
            self.phone.errors.append('Phone number requires confirmation.')
            return False
        if security.confirmable.requires_confirmation(user):
            message = security.utils.get_message('CONFIRMATION_REQUIRED')[0]
            self.email.errors.append(message)
            return False
        success = security.utils.verify_and_update_password(password, user)
        if not success:
            message = security.utils.get_message('INVALID_PASSWORD')[0]
            self.password.errors.append(message)
            return False
        if not user.is_active():
            message = security.utils.get_message('DISABLED_ACCOUNT')[0]
            self.email.errors.append(message)
            return False
        self.user = user
        return True
