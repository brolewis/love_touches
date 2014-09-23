# Third Party
import sqlalchemy
# Local
import main


def worker():
    ready = []
    active = sqlalchemy.or_(main.models.User.phone_confirmed_at != None,
                            main.models.User.email_confirmed_at != None)
    count = 0
    for count, crontab in enumerate(main.models.Crontab.query.filter(active)):
        if crontab.is_ready:
            ready.append(crontab)
    print count, len(ready)
    print ready


if __name__ == '__main__':
    worker()
