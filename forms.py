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


def unique_user_email(form, field):
    user = models.User.query.filter_by(email=field.data).first()
    if user is not None and user.confirmed_at is not None:
        get_message = flask.ext.security.utils.get_message
        msg = get_message('EMAIL_ALREADY_ASSOCIATED', email=field.data)[0]
        raise wtforms.ValidationError(msg)


class ConfirmRegisterForm(flask.ext.wtf.Form,
                          flask.ext.security.forms.RegisterFormMixin):
    email = wtforms.TextField('Email', [wtforms.validators.Required(),
                                        unique_user_email,
                                        wtforms.validators.Email()])
    password = wtforms.PasswordField('Password',
                                     [wtforms.validators.Required(),
                                      wtforms.validators.Length(6, 128)])
    submit = wtforms.SubmitField()

main.app.extensions['security'].confirm_register_form = ConfirmRegisterForm
