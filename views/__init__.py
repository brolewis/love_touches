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
    user = flask.ext.security.current_user
    if user.has_role('admin'):
        return flask.redirect(flask.url_for('admin.index'))
    else:
        return flask.render_template('index.html')


@main.app.route('/about')
def about():
    return flask.render_template('about.html')


@main.app.route('/login', methods=['GET', 'POST'])
@flask.ext.security.decorators.anonymous_user_required
def login():
    form = forms.LoginForm()
    if form.validate_on_submit():
        next = form.next.data
        remember = form.remember.data
        if form.user.totp_enabled:
            flask.session['tfa_id'] = form.user.id
            if remember:
                flask.session['remember'] = 'set'
            return flask.redirect(flask.url_for('two_factor', next=next))
        else:
            flask.ext.security.utils.login_user(form.user, remember=remember)
            models.db.session.commit()
            url = flask.ext.security.utils.get_post_login_redirect(next)
            return flask.redirect(url)
    return flask.render_template('security/login_user.html', form=form)


@main.app.route('/login/tfa', methods=['GET', 'POST'])
def two_factor():
    if 'tfa_id' not in flask.session:
        return flask.redirect(flask.url_for('login'))
    user = models.User.query.get(flask.session['tfa_id'])
    form = forms.TwoFactorConfirmationForm()
    form.user = user
    if form.validate_on_submit():
        del flask.session['tfa_id']
        flask.ext.security.utils.login_user(user)
        models.db.session.commit()
        url = flask.ext.security.utils.get_post_login_redirect(form.next.data)
        return flask.redirect(url)
    return flask.render_template('security/two_factor.html', form=form)


@main.app.route('/post_login')
@flask.ext.security.login_required
def post_login():
    user = flask.ext.security.current_user
    try:
        if user.has_role('admin'):
            return flask.redirect(flask.url_for('admin.index'))
        else:
            return flask.redirect(flask.url_for('manage.actions'))
    except:
        flask.flash('An error occurred logging in', 'error')
        return flask.redirect(flask.url_for('security.logout'))


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
        if form.data['code'] == pyotp.HOTP(user.secret).at(user.phone_hotp):
            url = flask.url_for('index')
            if action == 'login_confirm':
                user.confirmed_at = datetime.datetime.utcnow()
                if user != flask.ext.security.current_user:
                    flask.ext.security.utils.logout_user()
                    flask.ext.security.utils.login_user(user)
                    get_url = flask.ext.security.utils.get_url
                    url = (get_url(_security.post_confirm_view) or
                           get_url(_security.post_login_view))
            else:
                user.phone_confirmed_at = datetime.datetime.utcnow()
            models.db.session.add(user)
            models.db.session.commit()
            flask.flash('Mobile Number confirmed', 'success')
            return flask.redirect(url)
        else:
            flask.flash('Verification code does not match.', 'error')
    return flask.render_template('confirm_mobile.html', form=form)


@main.app.route('/inbound_email', methods=['POST'])
def inbound_email():
    inbound = flask.request.get_json()
    user = models.User.query.filter_by(email=inbound['Form']).one()
    if utils.unsubscribe_test(inbound['StrippedTextReply']):
        user.email_confirmed_at = None
        subject = 'Unsubcription Request Received'
        flask.ext.security.utils.send_mail(subject, user.email, 'cancel')
    else:
        message = models.Message(message=inbound['StrippedTextReply'])
        user.messages.append(message)
    models.db.session.add(user)
    models.db.session.commit()
    return flask.jsonify({'status': 'ok'})


@main.app.route('/inbound_phone', methods=['POST'])
def inbound_phone():
    phone = utils.format_phone(flask.request.form)
    user = models.User.query.filter_by(phone=phone).one()
    if utils.unsubscribe_test(flask.request.form['Body']):
        user.phone_confirmed_at = None
        message = 'You will no longer receive messages from Love Touches'
        utils.send_sms(phone, message)
    else:
        message = models.Message(message=flask.request.form['Body'])
        user.messages.append(message)
    models.db.session.add(user)
    models.db.session.commit()
    return flask.jsonify({'status': 'ok'})


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
    actions = utils.get_actions_for_method(method_name, header=header,
                                           back=back)
    modal = flask.render_template('snippets/methods_dialog.html',
                                  methods=models.approved_methods(),
                                  method_name=method_name)
    return flask.jsonify(actions=actions, modal=modal)


@main.app.errorhandler(404)
def not_found(e):
    return flask.render_template('errors/404.html'), 404


@main.app.errorhandler(405)
def not_allowed(e):
    return flask.render_template('errors/405.html'), 405


@main.app.errorhandler(500)
def server_error(e):
    return flask.render_template('errors/500.html'), 500


import views.manage
import views.security
import views.signup
import views.admin  # noqa
