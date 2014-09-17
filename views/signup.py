# Standard Library
import datetime
# Third Party
import flask
import pyotp
import werkzeug.local
# Local
import forms
import main
import models
import utils

signup = flask.Blueprint('signup', __name__, url_prefix='/signup',
                         template_folder='../templates/signup')
_security = werkzeug.local.LocalProxy(lambda: main.app.extensions['security'])


@signup.route('/step_one', methods=['GET', 'POST'])
def step_one():
    user = flask.ext.security.current_user
    if user.has_role('admin'):
        return flask.redirect(flask.url_for('admin.index'))
    if not user.is_anonymous():
        return flask.redirect(flask.url_for('manage.actions'))
    if flask.request.method == 'POST':
        if flask.request.form.getlist('action'):
            actions = flask.request.form.getlist('action', type=int)
            flask.session['actions'] = actions
            return flask.redirect(utils.get_redirect('.step_two'))
        else:
            message = 'Uh oh. You need to pick at least one action.'
            flask.flash(message, 'error')
    return flask.render_template('step_one.html',
                                 methods=models.approved_methods())


@signup.route('/step_two', methods=['GET', 'POST'])
def step_two():
    user = flask.ext.security.current_user
    if user.has_role('admin'):
        return flask.redirect(flask.url_for('admin.index'))
    if not user.is_anonymous():
        return flask.redirect(flask.url_for('manage.schedule'))
    if not flask.session.get('actions'):
        return flask.redirect(flask.url_for('.step_one'))
    form = forms.ScheduleForm()
    if form.validate_on_submit():
        flask.session.update(form.data)
        return flask.redirect(utils.get_redirect('.step_three'))
    for key in (x for x in flask.session if hasattr(form, x)):
        value = flask.session[key]
        if key == 'minute':
            value = '{:02d}'.format(int(value))
        getattr(form, key).data = value
    return flask.render_template('step_two.html', form=form,
                                 back=flask.url_for('.step_one'))


@signup.route('/step_three', methods=['GET', 'POST'])
def step_three():
    user = flask.ext.security.current_user
    if user.has_role('admin'):
        return flask.redirect(flask.url_for('admin.index'))
    if not user.is_anonymous():
        return flask.redirect(flask.url_for('manage.contact'))
    if not flask.session.get('actions'):
        return flask.redirect(flask.url_for('.step_one'))
    if not flask.session.get('timezone'):
        return flask.redirect(flask.url_for('.step_two'))
    form = forms.ContactForm()
    previous = False
    if form.validate_on_submit():
        query = models.User.query
        if query.filter_by(phone=form.data['phone']).first():
            previous = True
        if form.data['email'] and not previous:
            if query.filter_by(email=form.data['email']).first():
                previous = True
        if previous and not main.app.debug:
            message = '''Hrm. Are you sure you haven't been here before?'''
            flask.flash(message, 'error')
            login_url = flask.ext.security.utils.url_for_security('login')
            return flask.redirect(login_url)
        flask.session.update(form.data)
        return flask.redirect(flask.url_for('.confirm'))
    for key in (x for x in flask.session if hasattr(form, x)):
        getattr(form, key).data = flask.session[key]
    return flask.render_template('step_three.html', form=form,
                                 back=flask.url_for('.step_two'))


def _days_label():
    days_of_week = flask.session['days_of_week']
    days_dict = dict(forms.weekday_choices)
    if len(days_of_week) == 1:
        days_label = days_dict[days_of_week[0]]
    elif len(days_of_week) == 2:
        days_label = ' and '.join(days_dict[x] for x in days_of_week)
    elif len(days_of_week) == 5 and {1, 2, 3, 4, 5} == set(days_of_week):
        days_label = 'Weekdays'
    elif len(days_of_week) == 7:
        days_label = 'Every day'
    else:
        days_label = ', '.join(days_dict[x] for x in days_of_week[:-1])
        days_label += ', and {}'.format(days_dict[days_of_week[-1]])
    return days_label


@signup.route('/confirm')
@signup.route('/confirm/<action>')
def confirm(action=None):
    if flask.ext.securitycurrent_user.has_role('admin'):
        return flask.redirect(flask.url_for('admin.index'))
    if not flask.ext.security.current_user.is_anonymous():
        return flask.redirect(flask.url_for('manage.actions'))
    if not (flask.session.get('email') or flask.session.get('phone')):
        return flask.redirect(flask.url_for('.step_one'))
    if not flask.session.get('actions'):
        return flask.redirect(flask.url_for('.step_two'))
    phone = utils.format_phone(flask.session)
    if action == 'submit':
        user = None
        query = models.User.query
        email = flask.session.get('email', '')
        if phone:
            user = query.filter_by(phone=phone)
            user = user.first()
        if email and not user:
            user = query.filter_by(email=email).first()
        if not user:
            user = models.User()
        user.phone = phone
        user.email = email
        for action_id in flask.session['actions']:
            action = models.Action.query.get(action_id)
            user.actions.append(action)
        name = flask.session.get('method_name')
        if name:
            method = models.Method.query.filter_by(name=name).first()
            user.method = method
        time = '{hour}:{minute} {am_pm}'.format(**flask.session)
        time = datetime.datetime.strptime(time, '%I:%M %p').time()
        for day_of_week in flask.session['days_of_week']:
            crontab = models.Crontab(day_of_week=day_of_week, time=time,
                                     timezone=flask.session['timezone'])
            user.schedule.append(crontab)
        user.secret = pyotp.random_base32()
        models.db.session.add(user)
        models.db.session.commit()
        redirect = 'index'
        if user.email and user.email_confirmed_at is None:
            confirmable = flask.ext.security.confirmable
            token = confirmable.generate_confirmation_token(user)
            link = flask.url_for('.confirm_signup', token=token,
                                 _external=True)
            msg = flask.ext.security.utils.get_message('CONFIRM_REGISTRATION',
                                                       email=user.email)
            flask.flash(*msg)
            subject = 'Thank You for Signing Up for Love Touches!'
            flask.ext.security.utils.send_mail(subject, user.email,
                                               'signup', user=user,
                                               confirmation_link=link)
            redirect = 'index'
        if user.phone and user.phone_confirmed_at is None:
            utils.send_code(user)
            flask.session['_user_id'] = user.id
            redirect = 'confirm_mobile'
        for key in (x for x in flask.session.keys() if not x.startswith('_')):
            del flask.session[key]
        return flask.redirect(flask.url_for(redirect))
    actions = [models.Action.query.get(x) for x in flask.session['actions']]
    return flask.render_template('confirm.html', actions=actions, phone=phone,
                                 days_label=_days_label())


@signup.route('/confirm_signup/<token>')
def confirm_signup(token):
    """View function which handles a email confirmation request."""
    get_url = flask.ext.security.utils.get_url
    ret = flask.ext.security.confirmable.confirm_email_token_status(token)
    expired, invalid, user = ret
    if not user or invalid:
        invalid = True
        flask.flash('Invalid confirmation token.', 'error')
    if expired:
        flask.ext.security.confirmable.send_confirmation_instructions(user)
        message = 'You did not confirm your email within {}. New instructions '
        message += 'to confirm your email have been sent to {}.'
        message = message.format(_security.confirm_email_within, user.email)
        flask.flash(message, 'error')
    if invalid or expired:
        return flask.redirect(get_url(_security.confirm_error_view) or
                              flask.url_for('send_confirmation'))
    if user != flask.ext.security.current_user:
        flask.ext.security.utils.logout_user()
        flask.ext.security.utils.login_user(user)
    if user.email_confirmed_at is None:
        user.email_confirmed_at = datetime.datetime.utcnow()
        models.db.session.add(user)
        models.db.session.commit()
        message = 'Thank you for confirming your email address. You will now'
        message += ' start receving your scheduled actions.'
        flask.flash(message)
    else:
        flask.flash('Your email address has already been confirmed.')
    message = 'You may want to <a href="{}">register</a> so you can change '
    message += 'your schedule and actions.'
    user.secret = pyotp.random_base32()
    models.db.session.add(user)
    models.db.session.commit()
    code = pyotp.HOTP(user.secret).at(user.email_hotp)
    register_url = flask.url_for('register', email=user.email, code=code)
    flask.flash(message.format(register_url))
    message = "(If you don't register now, you can register at"
    message += ' any time from the top menu.)'
    flask.flash(message)
    return flask.redirect(flask.url_for('index'))
