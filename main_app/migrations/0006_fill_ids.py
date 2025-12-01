from django.db import migrations

def fill_numbers(apps, schema_editor):
    Student = apps.get_model('main_app', 'Student')
    Staff   = apps.get_model('main_app', 'Staff')
    Admin   = apps.get_model('main_app', 'Admin')

    for stu in Student.objects.filter(registration_number__isnull=True):
        stu.registration_number = f"STU-{stu.id:04d}"
        stu.save(update_fields=['registration_number'])

    for stf in Staff.objects.filter(staff_id_number__isnull=True):
        stf.staff_id_number = f"STF-{stf.id:04d}"
        stf.save(update_fields=['staff_id_number'])

    for adm in Admin.objects.filter(admin_id_number__isnull=True):
        adm.admin_id_number = f"ADM-{adm.id:04d}"
        adm.save(update_fields=['admin_id_number'])

class Migration(migrations.Migration):
    dependencies = [('main_app', '0005_admin_admin_id_number_admin_phone_staff_phone_and_more')]   # ← use real previous number
    operations = [migrations.RunPython(fill_numbers, reverse_code=migrations.RunPython.noop)]