from django.core.mail import EmailMultiAlternatives


def send_email(
    subject: str,
    to_email: list[str],
    html: str,
    cc_email: list[str] | None = None,
) -> None:
    email = EmailMultiAlternatives(
        subject=subject,
        body=html,
        to=to_email,
        cc=cc_email or [],
    )
    email.attach_alternative(html, "text/html")
    email.send()
