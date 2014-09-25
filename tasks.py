# Standard Library
import os
import random
# Third Party
import celery
import flask.ext.security
import telapi
# Local
import main


def make_celery(app):
    broker = app.config.get('CELERY_BROKER_URL') or 'amqp://guest@localhost//'
    celery_app = celery.Celery(app.import_name, broker=broker)
    celery_app.conf.update(app.config)
    TaskBase = celery_app.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                self.session = main.db.create_scoped_session()
                return TaskBase.__call__(self, *args, **kwargs)
    celery_app.Task = ContextTask
    return celery_app

celery_app = make_celery(main.app)


@celery.signals.task_postrun.connect
def close_session(**kwargs):
    kwargs['task'].session.close()


@celery_app.task(bind=True)
def send_email(self, user_id):
    user = self.session.query(main.models.User).get(user_id)
    action = random.choice(user.actions)
    subject = "Love Touches - Today's Action"
    flask.ext.security.utils.send_mail(subject, user.email, 'action',
                                       user=user, action=action)


@celery_app.task(bind=True)
def send_sms(self, user_id):
    user = self.session.query(main.models.User).get(user_id)
    message = random.choice(user.actions)
    client = telapi.rest.Client(os.getenv('ACCOUNT_SID'),
                                os.getenv('AUTH_TOKEN'))
    account = client.accounts[client.account_sid]
    from_number = account.incoming_phone_numbers[0].phone_number
    account.sms_messages.create(to_number=user.phone, from_number=from_number,
                                body=message)
