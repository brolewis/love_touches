# Third Party
import flask
import flask.ext.security
import werkzeug.datastructures
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
    phone = utils.format_phone(kwargs)
    user = models.User.query.filter_by(email=kwargs['email']).first()
    if not user and phone:
        user = models.User.query.filter_by(phone=phone).first()
    if not user:
        user = models.User(email=kwargs['email'], phone=phone)
    user.active = True
    user.password = security.utils.encrypt_password(kwargs['password'])
    models.db.session.commit()
    if user.phone:
        utils.send_code(user)
        flask.session['_user_id'] = user.id
        flask.redirect(flask.url_for('confirm_phone'))
    elif user.email:
        link, token = security.confirmable.generate_confirmation_link(user)
        msg = security.utils.get_message('CONFIRM_REGISTRATION',
                                         email=user.email)
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
