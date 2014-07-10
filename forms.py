# Third Party
import flask
import flask.ext.security as security
import flask.ext.wtf
import wtforms
import wtforms.ext.sqlalchemy.fields
# Local
import main


def simple_field_filter(field):
    special_fields = (wtforms.HiddenField, wtforms.FileField)
    return not isinstance(field, special_fields)

main.app.jinja_env.filters['simple_field_filter'] = simple_field_filter


class ProfileForm(flask.ext.wtf.Form):
    phone = wtforms.TextField(label='Phone Number')
    email = wtforms.TextField(validators=[wtforms.validators.Email()])


hour_validator = wtforms.validators.NumberRange(min=1, max=12)
minute_validator = wtforms.validators.NumberRange(min=0, max=59)
weekday_choices = [(0, 'Sunday'), (1, 'Monday'), (2, 'Tuesday'),
                   (3, 'Wednesday'), (4, 'Thursday'), (5, 'Friday'),
                   (6, 'Saturday')]


class ScheduleForm(flask.ext.wtf.Form):
    days_of_week = wtforms.SelectMultipleField('Days of the Week',
                                               [wtforms.validators.Required()],
                                               choices=weekday_choices,
                                               coerce=int)
    hour = wtforms.IntegerField(validators=[hour_validator])
    minute = wtforms.IntegerField(validators=[minute_validator], default='00')
    am_pm = wtforms.RadioField('Time of Day',
                               choices=[('am', 'am'), ('pm', 'pm')])


class PasswordChangeForm(flask.ext.wtf.Form):
    new_password = wtforms.PasswordField('New Password',
                                         [wtforms.validators.Required(),
                                          wtforms.validators.EqualTo('confirm',
                                          message='Passwords must match')])
    confirm = wtforms.PasswordField('Repeat Password')


class LoginForm(security.forms.Form, security.forms.NextFormMixin):
    email = wtforms.TextField('Email Address')
    password = wtforms.PasswordField('Password')
    remember = wtforms.BooleanField('Remember Me')
    offset = wtforms.HiddenField()
    submit = wtforms.SubmitField('Login')

    def __init__(self, *args, **kwargs):
        super(LoginForm, self).__init__(*args, **kwargs)

    def validate(self):
        email = self.email.data.strip()
        password = self.password.data
        try:
            flask.session['offset'] = int(self.offset.data)
        except:
            flask.session['offset'] = 360

        if not super(LoginForm, self).validate():
            return False

        if email == '':
            message = security.utils.get_message('EMAIL_NOT_PROVIDED')[0]
            self.email.errors.append(message)
            return False

        if password.strip() == '' or password is None:
            message = security.utils.get_message('PASSWORD_NOT_PROVIDED')[0]
            self.password.errors.append(message)
            return False

        emails = main.user_datastore.user_model.email.ilike(email)
        self.user = main.user_datastore.user_model.query.filter(emails).first()

        if self.user is None:
            message = security.utils.get_message('USER_DOES_NOT_EXIST')[0]
            self.email.errors.append(message)
            return False
        if self.user.type == 'client':
            success = False
            for case in self.user.cases:
                if password == case.token:
                    flask.session['case_id'] = case.id
                    success = True
        else:
            success = security.utils.verify_and_update_password(password,
                                                                self.user)

        if not success:
            message = security.utils.get_message('INVALID_PASSWORD')[0]
            self.password.errors.append(message)
            return False
        if security.confirmable.requires_confirmation(self.user):
            message = security.utils.get_message('CONFIRMATION_REQUIRED')[0]
            self.email.errors.append(message)
            return False
        if not self.user.is_active():
            message = security.utils.get_message('DISABLED_ACCOUNT')[0]
            self.email.errors.append(message)
            return False
        return True
