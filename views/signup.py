# Standard Library
import datetime
# Third Party
import flask
import pyotp
# Local
import forms
import main
import models
import utils


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
            login_url = flask.ext.security.utils.url_for_security('login')
            return flask.redirect(login_url)
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


@main.app.route('/_get_actions')
def _get_actions():
    method_name = flask.request.args.get('method_name')
    actions = flask.session.get('actions') or []
    template = utils._get_actions_for_method(method_name, actions, 'step_two',
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
            redirect = 'confirm_mobile'
            flask.session['_phone_sent'] = True
        for key in (x for x in flask.session.keys() if not x.startswith('_')):
            del flask.session[key]
        return flask.redirect(flask.url_for(redirect))
    return flask.render_template('confirm.html', actions=actions, phone=phone,
                                 days_label=_days_label(), group='signup')
