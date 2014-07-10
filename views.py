# Third Party
import flask
import flask.ext.security
import flask.ext.security.confirmable
import flask.ext.security.utils
# Local
import forms
import main
import models


@main.app.route('/')
def index():
    return flask.render_template('index.html')


@main.app.route('/step_one', methods=['GET', 'POST'])
def step_one():
    profile_form = forms.ProfileForm()
    previous = False
    if profile_form.validate_on_submit():
        query = models.User.query
        if query.filter_by(phone=profile_form.data['phone']).first():
            previous = True
        if profile_form.data['email'] and not previous:
            if query.filter_by(email=profile_form.data['email']).first():
                previous = True
        if previous and not main.app.debug:
            message = '''Hrm. Are you sure you haven't been here before?'''
            flask.flash(message, 'error')
            return flask.redirect(flask.url_for('security.login'))
        flask.session.update(profile_form.data)
        endpoint = flask.session.get('action') or 'step_two'
        return flask.redirect(flask.url_for(endpoint))
    profile_form.email.data = flask.session.get('email')
    profile_form.phone = flask.session.get('phone')
    return flask.render_template('step_one.html', profile_form=profile_form)


@main.app.route('/step_two', methods=['GET', 'POST'])
def step_two():
    if not (flask.session.get('email') or flask.session.get('phone')):
        return flask.redirect(flask.url_for('step_one'))
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
    return flask.render_template('step_two.html', methods=methods)


@main.app.route('/_get_actions')
def _get_actions():
    method_name = flask.request.args.get('method_name', '')
    if method_name:
        result = {}
        method = models.Method.query.filter_by(name=method_name).first()
        for group in method.groups:
            result[group.name] = {x.id: x.label for x in group.actions}
    else:
        actions = models.Action.query.all()
        result = {'All': {x.id: x.label for x in actions}}
    actions = flask.session.get('actions') or []
    template = flask.render_template('snippets/actions.html', result=result,
                                     method_name=method_name, actions=actions)
    return flask.jsonify(template=template)


@main.app.route('/step_three', methods=['GET', 'POST'])
def step_three():
    if not (flask.session.get('email') or flask.session.get('phone')):
        return flask.redirect(flask.url_for('step_one'))
    if not flask.session.get('actions'):
        return flask.redirect(flask.url_for('step_two'))
    schedule_form = forms.ScheduleForm()
    if schedule_form.validate_on_submit():
        flask.session.update(schedule_form.data)
        return flask.redirect(flask.url_for('confirm'))
    return flask.render_template('step_three.html',
                                 schedule_form=schedule_form)


@main.app.route('/confirm')
@main.app.route('/confirm/<action>')
def confirm(action=None):
    if not (flask.session.get('email') or flask.session.get('phone')):
        return flask.redirect(flask.url_for('step_one'))
    if not flask.session.get('actions'):
        return flask.redirect(flask.url_for('step_two'))
    flask.session['action'] = 'confirm'
    actions = [models.Action.query.get(x) for x in flask.session['actions']]
    days_dict = dict(forms.weekday_choices)
    days_of_week = flask.session['days_of_week']
    if len(days_of_week) == 1:
        days_label = days_dict[days_of_week[0]]
    elif len(days_of_week) == 2:
        days_label = ' and '.join(days_dict[x] for x in days_of_week)
    else:
        days_label = ', '.join(days_dict[x] for x in days_of_week[:-1])
        days_label += ', and {}'.format(days_dict[days_of_week[-1]])
    if action == 'submit':
        user = None
        query = models.User.query
        if flask.session.get('phone'):
            user = query.filter_by(phone=flask.session['phone']).first()
        if flask.session.get('email') and not user:
            user = query.filter_by(email=flask.session['email']).first()
        if not user:
            user = models.User()
        user.email = flask.session['email']
        user.phone = flask.session['phone']
        for action_id in flask.session['actions']:
            action = models.Action.query.get(action_id)
            user.actions.append(action)
        name = flask.session.get('method_name')
        if name:
            method = models.Method.query.filter_by(name=name).first()
            user.method = method
        for day_of_week in days_of_week:
            crontab = models.Crontab(day_of_week=day_of_week,
                                     hour=flask.session['hour'],
                                     minute=flask.session['minute'])
            user.schedule.append(crontab)
        models.db.session.add(user)
        models.db.session.commit()
        if user.email:
            confirmable = flask.ext.security.confirmable
            link = confirmable.generate_confirmation_link(user)[0]
            message = 'Email confirmation instructions have been sent.'
            flask.flash(message)
            flask.ext.security.utils.send_mail('Welcome', user.email,
                                               'welcome', user=user,
                                               confirmation_link=link)
            return flask.redirect(flask.url_for('index'))
    return flask.render_template('confirm.html', actions=actions,
                                 days_label=days_label)


@main.app.route('/cancel')
def cancel():
    if flask.session.get('user'):
        models.db.session.delete(models.User.query.get(flask.session['user']))
        models.db.session.commit()


@main.app.route('/post_login')
@flask.ext.security.login_required
def post_login():
    try:
        return flask.redirect(flask.url_for('admin.index'))
    except:
        flask.flash('An error occurred logging in', 'error')
        return flask.redirect(flask.url_for('security.logout'))


@main.app.route('/profile')
@main.app.route('/profile/<action>', methods=['GET', 'POST'])
@flask.ext.security.login_required
def profile(action=None):
    user = flask.ext.security.current_user
    profile_form = forms.ProfileForm(obj=user)
    password_form = forms.PasswordChangeForm()
    if action == 'profile' and profile_form.validate_on_submit():
        profile_form.populate_obj(user)
        models.db.session.add(user)
        models.db.session.commit()
        flask.flash('Profile updated', 'success')
        return flask.redirect(flask.url_for('profile'))
    if action == 'password' and password_form.validate_on_submit():
        password = password_form.new_password.data
        user.password = flask.ext.security.utils.encrypt_password(password)
        models.db.session.add(user)
        models.db.session.commit()
        flask.flash('Password changed successfully', 'success')
        return flask.redirect(flask.url_for('profile'))
    return flask.render_template('profile.html', profile_form=profile_form,
                                 password_form=password_form)


main.app.extensions['security'].login_form = forms.LoginForm
