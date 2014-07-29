# Standard Library
import datetime
# Third Party
import flask
import flask.ext.security
import flask.ext.security.confirmable
import flask.ext.security.utils
import pyotp
import werkzeug.datastructures
import werkzeug.local
# Local
import forms
import main
import models
import utils


@main.app.route('/')
def index():
    for key in ('_email_sent', '_phone_sent'):
        if key in flask.session:
            del flask.session[key]
    return flask.render_template('index.html')


@main.app.route('/step_one', methods=['GET', 'POST'])
def step_one():
    user = flask.ext.security.current_user
    if not user.is_anonymous():
        flask.redirect(flask.url_for('contact'))
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
            return flask.redirect(flask.url_for('security.login'))
        flask.session.update(form.data)
        endpoint = flask.session.get('action') or 'step_two'
        return flask.redirect(flask.url_for(endpoint))
    keys = ('phone', 'country_code', 'email')
    for key in (x for x in keys if flask.session.get(x)):
        getattr(form, key).data = flask.session[key]
    return flask.render_template('step_one.html', form=form, group='signup')


@main.app.route('/step_two', methods=['GET', 'POST'])
def step_two():
    if not (flask.session.get('email') or flask.session.get('phone')):
        return flask.redirect(flask.url_for('step_one'))
    user = flask.ext.security.current_user
    if not user.is_anonymous():
        flask.redirect(flask.url_for('actions'))
    if flask.request.method == 'POST':
        if flask.request.form.getlist('action'):
            method_name = flask.request.form.get('method_name', '')
            flask.session['method_name'] = method_name
            actions = flask.request.form.getlist('action', type=int)
            flask.session['actions'] = actions
            endpoint = flask.session.get('action') or 'step_three'
            return flask.redirect(flask.url_for(endpoint))
        else:
            message = 'Uh oh. You need to pick at least one action.'
            flask.flash(message, 'error')
    methods = models.Method.query.all()
    return flask.render_template('step_two.html', methods=methods,
                                 group='signup')


def _get_actions_for_method(method_name, actions, link, signup=False):
    if method_name:
        result = {}
        method = models.Method.query.filter_by(name=method_name).first()
        for group in method.groups:
            result[group.name] = {x.id: x.label for x in group.actions}
    else:
        actions = models.Action.query.all()
        result = {'All': {x.id: x.label for x in actions}}
    return flask.render_template('snippets/actions.html', result=result,
                                 method_name=method_name, actions=actions,
                                 link=link, signup=signup)


@main.app.route('/_get_actions')
def _get_actions():
    method_name = flask.request.args.get('method_name')
    actions = flask.session.get('actions') or []
    template = _get_actions_for_method(method_name, actions, 'step_two',
                                       signup=True)
    return flask.jsonify(template=template)


@main.app.route('/step_three', methods=['GET', 'POST'])
def step_three():
    if not (flask.session.get('email') or flask.session.get('phone')):
        return flask.redirect(flask.url_for('step_one'))
    if not flask.session.get('actions'):
        return flask.redirect(flask.url_for('step_two'))
    form = forms.ScheduleForm()
    user = flask.ext.security.current_user
    if not user.is_anonymous():
        flask.redirect(flask.url_for('schedule'))
    if form.validate_on_submit():
        flask.session.update(form.data)
        return flask.redirect(flask.url_for('confirm'))
    return flask.render_template('step_three.html', form=form, group='signup')


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


@main.app.route('/confirm')
@main.app.route('/confirm/<action>')
def confirm(action=None):
    if not (flask.session.get('email') or flask.session.get('phone')):
        return flask.redirect(flask.url_for('step_one'))
    if not flask.session.get('actions'):
        return flask.redirect(flask.url_for('step_two'))
    phone = utils.format_phone(flask.session)
    flask.session['action'] = 'confirm'
    actions = [models.Action.query.get(x) for x in flask.session['actions']]
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
        if user.email and not flask.session.get('_email_sent') \
                and user.confirmed_at is not None:
            confirmable = flask.ext.security.confirmable
            link = confirmable.generate_confirmation_link(user)[0]
            flask.flash('Email confirmation instructions have been sent.')
            subject = 'Welcome to Love Touches!'
            flask.ext.security.utils.send_mail(subject, user.email,
                                               'welcome', user=user,
                                               confirmation_link=link)
            flask.session['_email_sent'] = True
            redirect = 'index'
        if user.phone and not flask.session.get('_phone_sent'):
            utils.send_code(user)
            flask.session['_user_id'] = user.id
            redirect = 'verify_phone'
            flask.session['_phone_sent'] = True
        for key in (x for x in flask.session.keys() if not x.startswith('_')):
            del flask.session[key]
        return flask.redirect(flask.url_for(redirect))
    return flask.render_template('confirm.html', actions=actions, phone=phone,
                                 days_label=_days_label(), group='signup')


@main.app.route('/verify_phone', methods=['GET', 'POST'])
@main.app.route('/verify_phone/<action>', methods=['GET', 'POST'])
def verify_phone(action=None):
    user = models.User.query.get(flask.session['_user_id'])
    if action == 're-send':
        utils.send_code(user)
    verify_form = forms.PhoneVerifyForm()
    if verify_form.validate_on_submit():
        if verify_form.data['code'] == pyotp.HOTP(user.secret).at(0):
            user.phone_confirmed_at = datetime.datetime.now()
            models.db.session.add(user)
            models.db.session.commit()
            flask.flash('Mobile Number confirmed')
            return flask.redirect(flask.url_for('index'))
        else:
            flask.flash('Verification code does not match.', 'error')
    return flask.render_template('verify_phone.html', verify_form=verify_form,
                                 group='signup')


@main.app.route('/cancel')
def cancel():
    for key in (x for x in flask.session.keys() if not x.startswith('_')):
        del flask.session[key]
    return flask.redirect(flask.url_for('index'))

_security = werkzeug.local.LocalProxy(lambda: main.app.extensions['security'])

_datastore = werkzeug.local.LocalProxy(lambda: _security.datastore)


@main.app.route('/register', methods=['GET', 'POST'])
def register():
    '''View function which handles a registration request.'''
    if flask.request.json:
        form_data = werkzeug.datastructures.MultiDict(flask.request.json)
    else:
        form_data = flask.request.form
    form = forms.ConfirmRegisterForm(form_data)
    if form.validate_on_submit():
        user = register_user(**form.to_dict())
        form.user = user
        if not _security.confirmable or _security.login_without_confirmation:
            flask.after_this_request(flask.ext.security.views._commit)
            flask.ext.security.utils.login_user(user)
        if not flask.request.json:
            url = flask.ext.security.utils.get_post_register_redirect()
            return flask.redirect(url)
        return flask.ext.security.views._render_json(form,
                                                     include_auth_token=True)
    if flask.request.json:
        return flask.ext.security.views._render_json(form)
    template = flask.ext.security.utils.config_value('REGISTER_USER_TEMPLATE')
    args = flask.ext.security.views._ctx('register')
    return _security.render_template(template, register_user_form=form, **args)


def register_user(**kwargs):
    '''Handle user registration requests.'''
    security = flask.ext.security
    password = security.utils.encrypt_password(kwargs['password'])
    user = models.User.query.filter_by(email=kwargs['email']).first()
    if not user:
        user = models.User(email=kwargs['email'])
    user.active = True
    user.password = password
    models.db.session.commit()
    link, token = security.confirmable.generate_confirmation_link(user)
    msg = security.utils.get_message('CONFIRM_REGISTRATION', email=user.email)
    security.utils.do_flash(*msg)
    subject = 'Welcome to Love Touches'
    security.utils.send_mail(subject, user.email, 'welcome', user=user,
                             confirmation_link=link)
    return user


@main.app.route('/post_login')
@flask.ext.security.login_required
def post_login():
    try:
        return flask.redirect(flask.url_for('contact'))
    except:
        flask.flash('An error occurred logging in', 'error')
        return flask.redirect(flask.url_for('security.logout'))


@main.app.route('/post_register')
def post_register():
    return flask.redirect(flask.url_for('security.login'))


@main.app.route('/contact', methods=['GET', 'POST'])
@flask.ext.security.login_required
def contact():
    user = flask.ext.security.current_user
    form = forms.ContactForm()
    if form.validate_on_submit():
        redirect = 'contact'
        email = form.email.data
        if user.email != email:
            # TODO: This probably should pull a different form
            user.email = email
            if user.email:
                confirmable = flask.ext.security.confirmable
                link = confirmable.generate_confirmation_link(user)[0]
                flask.flash('Email confirmation instructions have been sent.')
                subject = 'Welcome to Love Touches!'
                flask.ext.security.utils.send_mail(subject, user.email,
                                                   'welcome', user=user,
                                                   confirmation_link=link)
                flask.session['_email_sent'] = True
        phone = utils.format_phone(form.data)
        if user.phone != phone:
            user.phone = phone
            if user.phone:
                utils.send_code(user)
                flask.session['_user_id'] = user.id
                redirect = 'verify_phone'
        models.db.session.add(user)
        models.db.session.commit()
        flask.flash('Contact information updated', 'success')
        return flask.redirect(flask.url_for(redirect))
    if user.phone:
        country_code, phone = user.phone[1:].split(' ', 1)
        form.country_code.data = country_code
        form.phone.data = phone
    form.email.data = user.email
    return flask.render_template('contact.html', form=form, group='admin')


@main.app.route('/actions', methods=['GET', 'POST'])
@flask.ext.security.login_required
def actions():
    user = flask.ext.security.current_user
    if flask.request.method == 'POST':
        if flask.request.form.getlist('action'):
            actions = []
            for action_id in flask.request.form.getlist('action', type=int):
                actions.append(models.Action.query.get(action_id))
            if {str(x) for x in user.actions} != {str(x) for x in actions}:
                models.db.session.add(user)
                models.db.session.commit()
                flask.flash('Actions saved.', 'success')
        else:
            message = 'Uh oh. You need to pick at least one action.'
            flask.flash(message, 'error')
    actions = [x.id for x in user.actions]
    form = _get_actions_for_method(user.method.name, actions, 'actions')
    return flask.render_template('actions.html', form=form, group='admin')


@main.app.route('/schedule', methods=['GET', 'POST'])
@flask.ext.security.login_required
def schedule():
    user = flask.ext.security.current_user
    time_str = user.schedule[0].time.strftime('%I:%M %p')
    form = forms.ScheduleForm()
    if form.validate_on_submit():
        time = '{hour}:{minute} {am_pm}'.format(**form.data)
        time = datetime.datetime.strptime(time, '%I:%M %p').time()
        schedule = []
        for day_of_week in form.days_of_week.data:
            crontab = models.Crontab(day_of_week=day_of_week, time=time,
                                     timezone=form.timezone.data)
            schedule.append(crontab)

        if {str(x) for x in user.schedule} != {str(x) for x in schedule}:
            user.schedule = schedule
            models.db.session.add(user)
            models.db.session.commit()
            flask.flash('Schedule saved.', 'success')
    form.days_of_week.data = [x.day_of_week for x in user.schedule]
    form.hour.data = int(time_str[:2])
    form.minute.data = time_str[3:5]
    form.am_pm.data = time_str[-2:].lower()
    form.timezone.data = user.schedule[0].timezone
    return flask.render_template('schedule.html', form=form, group='admin')
