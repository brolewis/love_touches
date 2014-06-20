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
    if flask.request.method == 'POST' and profile_form.validate_on_submit():
        user = models.User()
        profile_form.populate_obj(user)
        models.db.session.add(user)
        models.db.session.commit()
        flask.session['user'] = user.id
        return flask.redirect(flask.url_for('step_two'))
    return flask.render_template('step_one.html', profile_form=profile_form)


@main.app.route('/step_two')
def step_two():
    methods = models.Method.query.all()
    return flask.render_template('step_two.html', methods=methods)


@main.app.route('/_get_actions')
def _get_actions():
    method_name = flask.request.args.get('method_name', '')
    print method_name
    if method_name:
        result = {}
        method = models.Method.query.filter_by(name=method_name).first()
        for group in method.groups:
            result[group.name] = {x.id: x.label for x in group.actions}

        print result
    else:
        actions = models.Action.query.all()
        result = {'All': {x.id: x.label for x in actions}}
    return flask.jsonify(result=result)


@main.app.route('/step_three', methods=['GET', 'POST'])
def step_three(method=''):
    if flask.request.method == 'POST':
        user = models.User.query.get(flask.session['user'])
        for action_id in flask.request.form.getlist('action'):
            action = models.Action.query.get(action_id)
            user.actions.append(action)
        models.db.session.commit()
        return flask.render_template('step_three.html')
    else:
        return flask.redirect(flask.url_for('step_two'))


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
