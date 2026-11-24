from django.db import models


class EmailCredential(models.Model):
    """Encrypted email-provider credential set by an administrator.

    Render (and similar hosts) cannot always be updated from the development
    machine, and a mistyped environment variable is invisible until an email
    silently fails. This singleton lets an administrator install or rotate the
    Brevo key from the dashboard instead. The value is encrypted at rest with
    ``TEMPLATE_ENCRYPTION_KEY`` and is only ever read by the email backend; the
    environment variable remains the fallback and is never modified.
    """

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    api_key_ciphertext = models.BinaryField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Email credential"
        verbose_name_plural = "Email credential"

    def save(self, *args, **kwargs):
        # Enforce the singleton: there is exactly one credential row.
        self.id = 1
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Email credential (updated {self.updated_at:%Y-%m-%d %H:%M})"
