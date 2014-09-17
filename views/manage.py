# Standard Library
import datetime
# Third Party
import flask
import pyotp
import sqlalchemy
import werkzeug.datastructures
import werkzeug.local
# Local
import forms
import main
import models
import utils

manage = flask.Blueprint('manage', __name__, url_prefix='/manage',
                         template_folder='../templates/manage')
_security = werkzeug.local.LocalProxy(lambda: main.app.extensions['security'])


@manage.route('/contact', methods=['GET', 'POST'])
@flask.ext.security.login_required
def contact():
    user = flask.ext.security.current_user
    if user.has_role('admin'):
        return flask.redirect(flask.url_for('admin.index'))
    form = forms.ContactForm()
    if form.validate_on_submit():
        redirect = '.contact'
        email = form.email.data
        if user.email != email:
            user.email = email
            if user.email:
                confirmable = flask.ext.security.confirmable
                link = confirmable.generate_confirmation_link(user)[0]
                flask.flash('Email confirmation instructions have been sent.')
                subject = 'Welcome to Love Touches!'
                flask.ext.security.utils.send_mail(subject, user.email,
                                                   'welcome', user=user,
                                                   confirmation_link=link)
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
    return flask.render_template('contact.html', form=form)


@manage.route('/two-factor', methods=['GET', 'POST'])
@flask.ext.security.login_required
def two_factor():
    user = flask.ext.security.current_user
    form = forms.TwoFactorConfirmationForm()
    if form.validate_on_submit():
        user.totp_enabled = True
        models.db.session.add(user)
        models.db.session.commit()
        flask.flash('Two-Factor Authentication enabled.', 'success')
        return flask.redirect(flask.url_for('.contact'))
    totp = pyotp.TOTP(user.secret)
    uri = totp.provisioning_uri('', issuer_name='Love Touches')
    return flask.render_template('two_factor.html', form=form, uri=uri)


@manage.route('/disable-tfa')
@flask.ext.security.login_required
def disable_tfa():
    user = flask.ext.security.current_user
    user.totp_enabled = False
    models.db.session.add(user)
    models.db.session.commit()
    flask.flash('Two-Factor Authentication disabled.', 'success')
    return flask.redirect(flask.url_for('.contact'))



@manage.route('/actions', methods=['GET', 'POST'])
@flask.ext.security.login_required
def actions():
    user = flask.ext.security.current_user
    if flask.request.method == 'POST':
        commit = False
        name = flask.session.get('method_name')
        method = models.Method.query.filter_by(name=name).first()
        if user.method != method:
            user.method = method
            flask.flash('Method saved.', 'success')
            commit = True
        if flask.request.form.getlist('action'):
            actions = []
            for action_id in flask.request.form.getlist('action', type=int):
                actions.append(models.Action.query.get(action_id))
            if {str(x) for x in user.actions} != {str(x) for x in actions}:
                flask.flash('Actions saved.', 'success')
                commit = True
        elif not commit:
            message = 'Uh oh. You need to pick at least one action.'
            flask.flash(message, 'error')
        if commit:
            models.db.session.add(user)
            models.db.session.commit()
    form = utils.get_actions_for_method(user.method, header='manage')
    modal = flask.render_template('snippets/methods_dialog.html',
                                  methods=models.approved_methods(),
                                  method_name=user.method)
    return flask.render_template('actions.html', form=form, modal=modal)


@manage.route('/schedule', methods=['GET', 'POST'])
@flask.ext.security.login_required
def schedule():
    user = flask.ext.security.current_user
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
    if user.schedule:
        form.days_of_week.data = [x.day_of_week for x in user.schedule]
        time_str = user.schedule[0].time.strftime('%I:%M %p')
        form.hour.data = int(time_str[:2])
        form.minute.data = time_str[3:5]
        form.am_pm.data = time_str[-2:].lower()
        form.timezone.data = user.schedule[0].timezone
    return flask.render_template('schedule.html', form=form)


@manage.route('/change_password', methods=['GET', 'POST'])
@flask.ext.security.login_required
def change_password():
    """View function which handles a change password request."""
    user = flask.ext.security.current_user
    form = _security.change_password_form()
    if form.validate_on_submit():
        password = form.new_password.data
        password = flask.ext.security.utils.encrypt_password(password)
        user.password = password
        models.db.session.add(user)
        models.db.session.commit()
        if user.email:
            flask.ext.security.changeable.send_password_changed_notice(user)
        message = flask.ext.security.utils.get_message('PASSWORD_CHANGE')
        flask.flash(*message)
    return flask.render_template('change_password.html', form=form)


@manage.route('/suggest_method/<method_id>', methods=['GET', 'POST'])
@manage.route('/suggest_method', methods=['GET', 'POST'])
@flask.ext.security.login_required
def suggest_method(method_id=None):
    if method_id and flask.request.method == 'GET':
        disabled = ['name']
        method = models.Method.query.get(method_id)
        data = {'name': method.name}
        for cnt, section in enumerate(method.sections):
            data['section-{}'.format(cnt)] = section.name
        formdata = werkzeug.datastructures.MultiDict(data)
        form = forms.SuggestMethodForm(formdata=formdata)
    else:
        disabled = []
        form = forms.SuggestMethodForm()
    if form.validate_on_submit():
        if method_id:
            method = models.Method.query.get(method_id)
        else:
            status = models.Status.query.filter_by(name='Proposed').first()
            method = models.Method(name=form.name.data, status=status,
                                   author=flask.ext.security.current_user)
            models.db.session.add(method)
        sections = []
        for section_name in form.section.data:
            query = models.Section.query
            section = query.filter_by(name=section_name, method=method).first()
            if not section:
                section = models.Section(name=section_name)
            sections.append(section)
        method.sections = sections
        models.db.session.commit()
        flask.flash('Method suggestion saved', 'success')
        return flask.redirect(flask.url_for('.suggest_method'))
    return flask.render_template('suggest_method.html', form=form,
                                 disabled=disabled)


@manage.route('/suggest_action/<method_id>', methods=['GET', 'POST'])
@manage.route('/suggest_action', methods=['GET', 'POST'])
@flask.ext.security.login_required
def suggest_action(method_id=None):
    user = flask.ext.security.current_user
    all_actions = models.Action.query.filter(models.Status.name == 'Approved')
    if method_id == -1:
        method = None
    elif method_id:
        method = models.Method.query.get(method_id)
    else:
        method = flask.ext.security.current_user.method
    if method:
        actions = {}
        for section in method.sections:
            action_dict = {x.id: x.label for x in section.approved_actions}
            actions[section.name] = action_dict
    else:
        actions = {'': {x.id: x.label for x in all_actions}}
    form_dict = {}
    for section in actions:
        form_dict[section] = forms.SuggestActionForm(prefix=section)
    if all(x.validate_on_submit() for x in form_dict.itervalues()):
        status = models.Status.query.filter_by(name='Proposed').first()
        for section_name in form_dict:
            section = models.Section.query.filter_by(name=section_name,
                                                     method=method).first()
            for label in form_dict[section_name].action_name.data:
                action = models.Action.query.filter_by(label=label).first()
                if not action:
                    action = models.Action(label=label, author=user,
                                           status=status)
                if section not in action.sections:
                    assoc = models.SectionActions(status=status)
                    assoc.action = action
                    section.actions.append(assoc)
        models.db.session.commit()
        flask.flash('Action suggestions saved', 'success')
        return flask.redirect(flask.url_for('.suggest_action'))
    for section in actions:
        choices = []
        for action in (x for x in all_actions if x.id not in actions[section]):
            choices.append(action.label)
        form_dict[section].action_name.select2_choices = ','.join(choices)
    and_filter = sqlalchemy.and_(models.Status.name == 'Proposed',
                                 models.Method.author == user)
    status_filter = sqlalchemy.or_(models.Status.name == 'Approved',
                                   and_filter)
    methods = models.Method.query.filter(status_filter)
    method_name = getattr(method, 'name', '')
    modal = flask.render_template('snippets/methods_dialog.html',
                                  methods=methods, method_name=method_name,
                                  base='.suggest_action')
    return flask.render_template('suggest_action.html', form_dict=form_dict,
                                 method=method, actions=actions, modal=modal)


@manage.route('/feedback', methods=['GET', 'POST'])
def feedback():
    user = flask.ext.security.current_user
    form = forms.FeedbackForm()
    if form.validate_on_submit():
        message = models.Message(message=form.message.data)
        user.messages.append(message)
        models.db.session.add(user)
        models.db.session.commit()
        return flask.redirect(flask.url_for('.feedback'))
    return flask.render_template('feedback.html', form=form)
