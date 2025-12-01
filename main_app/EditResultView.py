# EditResultView.py
from django.shortcuts import get_object_or_404, render, redirect
from django.views import View
from django.contrib import messages
from .models import Subject, Staff, Student, StudentResult
from .forms import EditResultForm
from django.urls import reverse
import django.forms as forms   # <-- NEW : needed for the inline form tweak


class EditResultView(View):

    def get(self, request, *args, **kwargs):
        staff = get_object_or_404(Staff, admin=request.user)

        # ----  NEW : tiny inline form so we can set the label  ----
        class CustomEditForm(EditResultForm):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                # restrict students to courses this staff teaches
                subs = Subject.objects.filter(staff=staff)
                students = Student.objects.filter(
                    course__in=subs.values_list('course', flat=True)
                ).select_related('admin').order_by('admin__first_name')

                self.fields['student'].queryset = students
                # show  "First Last, Reg-no"  in the drop-down
                self.fields['student'].label_from_instance = (
                    lambda st: f"{st.admin.get_full_name}, {st.registration_number}"
                )

        resultForm = CustomEditForm()
        resultForm.fields['subject'].queryset = Subject.objects.filter(staff=staff)

        context = {
            'form': resultForm,
            'page_title': "Edit Student's Result"
        }
        return render(request, "staff_template/edit_student_result.html", context)

    # 100 % ORIGINAL  –  no changes at all
    def post(self, request, *args, **kwargs):
        form = EditResultForm(request.POST)
        context = {'form': form, 'page_title': "Edit Student's Result"}
        if form.is_valid():
            try:
                student = form.cleaned_data.get('student')
                subject = form.cleaned_data.get('subject')
                test = form.cleaned_data.get('test')
                exam = form.cleaned_data.get('exam')
                result = StudentResult.objects.get(student=student, subject=subject)
                result.exam = exam
                result.test = test
                result.save()
                messages.success(request, "Result Updated")
                return redirect(reverse('edit_student_result'))
            except Exception as e:
                messages.warning(request, "Result Could Not Be Updated")
        else:
            messages.warning(request, "Result Could Not Be Updated")
        return render(request, "staff_template/edit_student_result.html", context)