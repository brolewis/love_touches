# Third Party
import flask
import flask.ext.security
import pyotp
import werkzeug.local
# Local
import forms
import main
import models
import utils

_security = werkzeug.local.LocalProxy(lambda: main.app.extensions['security'])


@main.app.route('/register', methods=['GET', 'POST'])
@main.app.route('/register/<int:code>', methods=['GET', 'POST'])
def register(code=None):
    '''View function which handles a registration request.'''
    form = forms.ConfirmRegisterForm()
    if form.validate_on_submit():
        phone = utils.format_phone(form.data)
        user = models.User.query.filter_by(email=form.email.data).first()
        if not user and phone:
            user = models.User.query.filter_by(phone=phone).first()
        if not user:
            user = models.User(email=form.email.data, phone=phone)
        user.active = True
        passwd = flask.ext.security.utils.encrypt_password(form.password.data)
        user.password = passwd
        models.db.session.add(user)
        models.db.session.commit()
        if user.phone:
            utils.send_code(user)
            flask.session['_user_id'] = user.id
            url = flask.url_for('confirm_mobile', action='login_confirm')
            return flask.redirect(url)
        elif user.email:
            if code == pyotp.HOTP(user.secret).at(user.email_hotp):
                flask.ext.security.utils.login_user(user)
                flask.ext.security.confirmable.confirm_user(user)
                utils = flask.ext.security.utils
                url = utils.get_post_login_redirect(form.next.data)
                return flask.redirect(url)
            url = flask.ext.security.utils.get_post_register_redirect()
            confirmable = flask.ext.security.confirmable
            link, token = confirmable.generate_confirmation_link(user)
            msg = flask.ext.security.utils.get_message('CONFIRM_REGISTRATION',
                                                       email=user.email)
            flask.flash(*msg)
            subject = 'Thank You for Registering with Love Touches!'
            flask.ext.security.utils.send_mail(subject, user.email, 'welcome',
                                               user=user,
                                               confirmation_link=link)
            return flask.redirect(url)
    if flask.request.args.get('email'):
        form.email.data = flask.request.args.get('email')
    template = flask.ext.security.utils.config_value('REGISTER_USER_TEMPLATE')
    return flask.render_template(template, register_user_form=form)
