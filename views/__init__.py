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

_security = werkzeug.local.LocalProxy(lambda: main.app.extensions['security'])


@main.app.route('/')
def index():
    for key in ('_email_sent', '_phone_sent'):
        if key in flask.session:
            del flask.session[key]
    return flask.render_template('index.html')


@main.app.route('/confirm_mobile', methods=['GET', 'POST'])
@main.app.route('/confirm_mobile/<action>', methods=['GET', 'POST'])
def confirm_mobile(action=None):
    if not flask.session.get('_user_id'):
        flask.flash('Invalid id', 'error')
        return flask.redirect(flask.url_for('index'))
    user = models.User.query.get(flask.session['_user_id'])
    if action == 're-send':
        utils.send_code(user)
    form = forms.MobileVerifyForm()
    if form.validate_on_submit():
        if form.data['code'] == pyotp.HOTP(user.secret).at(0):
            register_url = flask.url_for('index')
            if action == 'login_confirm':
                user.confirmed_at = datetime.datetime.utcnow()
                if user != flask.ext.security.current_user:
                    flask.ext.security.utils.logout_user()
                    flask.ext.security.utils.login_user(user)
                    get_url = flask.ext.security.utils.get_url
                    register_url = (get_url(_security.post_confirm_view) or
                                    get_url(_security.post_login_view))
            else:
                user.phone_confirmed_at = datetime.datetime.utcnow()
            models.db.session.add(user)
            models.db.session.commit()
            flask.flash('Mobile Number confirmed', 'success')
            return flask.redirect(register_url)
        else:
            flask.flash('Verification code does not match.', 'error')
    return flask.render_template('confirm_mobile.html', form=form)


@main.app.route('/cancel')
def cancel():
    for key in (x for x in flask.session.keys() if not x.startswith('_')):
        del flask.session[key]
    return flask.redirect(flask.url_for('index'))


@main.app.route('/_get_actions')
def _get_actions():
    method_name = flask.request.args.get('method_name')
    flask.session['method_name'] = method_name
    header = flask.request.args.get('header')
    back = flask.request.args.get('back')
    actions = utils._get_actions_for_method(method_name, header=header,
                                            back=back)
    methods = models.Method.query.all()
    modal = flask.render_template('snippets/methods_dialog.html',
                                  methods=methods, method_name=method_name)
    return flask.jsonify(actions=actions, modal=modal)


import views.admin
import views.security
import views.signup  # noqa
