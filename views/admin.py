# Standard Library
import datetime
# Third Party
import flask
import werkzeug.datastructures
import werkzeug.local
# Local
import forms
import main
import models
import utils

admin = flask.Blueprint('admin', __name__, url_prefix='/admin',
                        template_folder='../templates/admin')
_security = werkzeug.local.LocalProxy(lambda: main.app.extensions['security'])


@admin.route('/contact', methods=['GET', 'POST'])
@flask.ext.security.login_required
def contact():
    user = flask.ext.security.current_user
    form = forms.ContactForm()
    if form.validate_on_submit():
        redirect = 'contact'
        email = form.email.data
        if user.email != email:
            # TODO: This probably should pull a different form
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
    return flask.render_template('contact.html', form=form, group='admin')


@admin.route('/actions', methods=['GET', 'POST'])
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
    form = utils._get_actions_for_method(user.method, header='admin')
    methods = models.Method.query.all()
    modal = flask.render_template('snippets/methods_dialog.html',
                                  methods=methods, method_name=user.method)
    return flask.render_template('actions.html', form=form, modal=modal,
                                 group='admin')


@admin.route('/schedule', methods=['GET', 'POST'])
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
    return flask.render_template('schedule.html', form=form, group='admin')


@admin.route('/change_password', methods=['GET', 'POST'])
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


@admin.route('/suggest_method', methods=['GET', 'POST'])
@flask.ext.security.login_required
def suggest_method():
    pass
