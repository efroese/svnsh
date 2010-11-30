import smtplib
import config

def addauth_email(user, repo, path, mode):
    """Email a user to let them know they've been granted access to a repository path."""

    fromaddr = config.EMAIL_FROM
    toaddrs  = '%s@%s' % (user, config.EMAIL_DOMAIN)

    if mode == 'rw':
        mode = 'write'
    else:
        mode = 'read'

    fmt_args = {
        'user': user,
        'mode': mode,
        'path': path,
        'url': repo.url
    }

    msg = """
        Hello %(user)s,

        You've been granted %(mode)s access on %(path)s for the repository located at %(url)s.

        Have fun!
        SVN Admins
    """ % fmt_args

    server = smtplib.SMTP(config.SMTP_HOST)
    server.sendmail(fromaddr, toaddrs, msg)
    server.quit()
