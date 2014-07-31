# Third Party
import flask
import flask.ext.security
import werkzeug.local
# Local
import forms
import main
import models
import utils

_security = werkzeug.local.LocalProxy(lambda: main.app.extensions['security'])


@main.app.route('/register', methods=['GET', 'POST'])
def register():
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
        models.db.session.commit()
        url = flask.ext.security.utils.get_post_register_redirect()
        if user.phone:
            utils.send_code(user)
            flask.session['_user_id'] = user.id
            return flask.redirect(flask.url_for('confirm_mobile', next=url))
        elif user.email:
            confirmable = flask.ext.security.confirmable
            link, token = confirmable.generate_confirmation_link(user)
            msg = flask.ext.security.utils.get_message('CONFIRM_REGISTRATION',
                                                       email=user.email)
            flask.flash(*msg)
            subject = 'Welcome to Love Touches'
            flask.ext.security.utils.send_mail(subject, user.email, 'welcome',
                                               user=user,
                                               confirmation_link=link)
            return flask.redirect(url)
    template = flask.ext.security.utils.config_value('REGISTER_USER_TEMPLATE')
    return flask.render_template(template, register_user_form=form)


@main.app.route('/post_login')
@flask.ext.security.login_required
def post_login():
    try:
        return flask.redirect(flask.url_for('contact'))
    except:
        flask.flash('An error occurred logging in', 'error')
        logout_url = flask.ext.security.utils.url_for_security('logout')
        return flask.redirect(logout_url)


@main.app.route('/post_register')
def post_register():
    return flask.redirect(flask.ext.security.utils.url_for_security('login'))


@main.app.route('/post_confirm')
def post_confirm():
    return flask.redirect(flask.url_for('index'))
