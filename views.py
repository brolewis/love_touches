# Third Party
import flask
import flask.ext.security
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
    user = None
    if flask.request.method == 'POST' and profile_form.validate_on_submit():
        query = models.User.query
        phone_number = profile_form.data['phone_number']
        if phone_number:
            user = query.filter_by(phone_number=phone_number).first()
        if profile_form.data['email'] and not user:
            user = query.filter_by(email=profile_form.data['email']).first()
        if user and main.app.debug:
            flask.session['user'] = user.id
            return flask.redirect(flask.url_for('step_two'))
        if not user:
            user = models.User()
            profile_form.populate_obj(user)
            models.db.session.add(user)
            models.db.session.commit()
            flask.session['user'] = user.id
            return flask.redirect(flask.url_for('step_two'))
    return flask.render_template('step_one.html', profile_form=profile_form,
                                 user=user)


@main.app.route('/step_two', methods=['GET', 'POST'])
def step_two():
    if not flask.session.get('user'):
        return flask.redirect(flask.url_for('step_one'))
    if flask.request.method == 'POST':
        user = models.User.query.get(flask.session['user'])
        name = flask.request.form.get('method_name', '')
        actions = flask.request.form.getlist('action')
        if actions:
            for action_id in actions:
                action = models.Action.query.get(action_id)
                user.actions.append(action)
            if name:
                method = models.Method.query.filter_by(name=name).first()
                user.method = method
            models.db.session.commit()
            return flask.redirect(flask.url_for('step_three'))
        else:
            flask.flash('Uh oh. You need to pick at least one action.')
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
    return flask.jsonify(result=result, method_name=method_name)


@main.app.route('/step_three', methods=['GET', 'POST'])
def step_three():
    if not flask.session.get('user'):
        return flask.redirect(flask.url_for('step_one'))
    schedule_form = forms.ScheduleForm()
    if flask.request.method == 'POST' and schedule_form.validate_on_submit():
        user = models.User.query.get(flask.session['user'])
        for day_of_week in schedule_form.data['days_of_week']:
            crontab = models.Crontab(day_of_week=day_of_week,
                                     hour=schedule_form.data['hour'],
                                     minute=schedule_form.data['minute'])
            user.schedule.append(crontab)
        models.db.session.commit()
        return flask.redirect(flask.url_for('confirm'))
    return flask.render_template('step_three.html',
                                 schedule_form=schedule_form)


@main.app.route('/confirm')
def confirm():
    if flask.session.get('user'):
        user = models.User.query.get(flask.session['user'])
        return flask.render_template('confirm.html', user=user)
    else:
        return flask.redirect(flask.url_for('step_one'))


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
