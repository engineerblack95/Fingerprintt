from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import Member


@receiver(post_delete, sender=Member)
def delete_member_photo(sender, instance: Member, **kwargs):
    if instance.photo:
        instance.photo.delete(save=False)


@receiver(pre_save, sender=Member)
def delete_replaced_photo(sender, instance: Member, **kwargs):
    if not instance.pk:
        return
    old_photo = (
        Member.objects.filter(pk=instance.pk)
        .values_list("photo", flat=True)
        .first()
    )
    new_photo = instance.photo.name if instance.photo else None
    if old_photo and old_photo != new_photo:
        storage = instance.photo.storage
        if storage.exists(old_photo):
            storage.delete(old_photo)
