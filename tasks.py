# Standard Library
import os
import random

# Third Party
import celery
import flask_security
import twilio.rest

# Local
import main

session = main.db.create_scoped_session()


def make_celery(app):
    broker = app.config.get("CELERY_BROKER_URL") or "amqp://guest@localhost//"
    celery_app = celery.Celery(app.import_name, broker=broker)
    celery_app.conf.update(app.config)
    return celery_app


celery_app = make_celery(main.app)


@celery.signals.task_postrun.connect
def close_session(**kwargs):
    session.remove()


@celery_app.task
def send_email(user_id):
    user = session.query(main.models.User).get(user_id)
    action = random.choice(user.actions)
    subject = "Love Touches - Today's Action"
    with main.app.app_context():
        flask_security.utils.send_mail(
            subject, user.email, "action", user=user, action=action
        )
    history = main.models.History(user=user, action=action)
    session.add(history)
    session.commit()


@celery_app.task
def send_sms(user_id):
    user = session.query(main.models.User).get(user_id)
    action = random.choice(user.actions)
    client = twilio.rest.Client(os.getenv("ACCOUNT_SID"), os.getenv("AUTH_TOKEN"))
    from_number = client.incoming_phone_numbers.list()[0].phone_number
    client.messages.create(body=action, from_=from_number, to=user.phone)
    history = main.models.History(user=user, action=action)
    session.add(history)
    session.commit()
