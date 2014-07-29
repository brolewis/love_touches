# Standard Library
import datetime
# Third Party
import flask
# Local
import forms
import main
import models
import utils


@main.app.route('/contact', methods=['GET', 'POST'])
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
                flask.session['_email_sent'] = True
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


@main.app.route('/actions', methods=['GET', 'POST'])
@flask.ext.security.login_required
def actions():
    user = flask.ext.security.current_user
    if flask.request.method == 'POST':
        if flask.request.form.getlist('action'):
            actions = []
            for action_id in flask.request.form.getlist('action', type=int):
                actions.append(models.Action.query.get(action_id))
            if {str(x) for x in user.actions} != {str(x) for x in actions}:
                models.db.session.add(user)
                models.db.session.commit()
                flask.flash('Actions saved.', 'success')
        else:
            message = 'Uh oh. You need to pick at least one action.'
            flask.flash(message, 'error')
    actions = [x.id for x in user.actions]
    form = utils._get_actions_for_method(user.method.name, actions, 'actions')
    return flask.render_template('actions.html', form=form, group='admin')


@main.app.route('/schedule', methods=['GET', 'POST'])
@flask.ext.security.login_required
def schedule():
    user = flask.ext.security.current_user
    time_str = user.schedule[0].time.strftime('%I:%M %p')
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
    form.days_of_week.data = [x.day_of_week for x in user.schedule]
    form.hour.data = int(time_str[:2])
    form.minute.data = time_str[3:5]
    form.am_pm.data = time_str[-2:].lower()
    form.timezone.data = user.schedule[0].timezone
    return flask.render_template('schedule.html', form=form, group='admin')
