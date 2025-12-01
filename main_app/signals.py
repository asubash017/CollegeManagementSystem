from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Student, Staff, Admin

@receiver(post_save, sender=Student)
def set_stu_reg(sender, instance, created, **kwargs):
    if created and not instance.registration_number:
        instance.registration_number = f"STU-{instance.id:04d}"
        instance.save(update_fields=['registration_number'])

@receiver(post_save, sender=Staff)
def set_staff_id(sender, instance, created, **kwargs):
    if created and not instance.staff_id_number:
        instance.staff_id_number = f"STF-{instance.id:04d}"
        instance.save(update_fields=['staff_id_number'])

@receiver(post_save, sender=Admin)
def set_admin_id(sender, instance, created, **kwargs):
    if created and not instance.admin_id_number:
        instance.admin_id_number = f"ADM-{instance.id:04d}"
        instance.save(update_fields=['admin_id_number'])