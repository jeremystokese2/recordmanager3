from django import forms
from .models import CustomField

class CustomFieldForm(forms.ModelForm):
    class Meta:
        model = CustomField
        fields = ['name', 'display_name', 'field_type', 'description', 'order', 
                 'show_in_header', 'is_mandatory', 'visible_on_create', 'term_set']

    def clean(self):
        cleaned_data = super().clean()
        is_mandatory = cleaned_data.get('is_mandatory')
        visible_on_create = cleaned_data.get('visible_on_create')
        field_type = cleaned_data.get('field_type')
        term_set = cleaned_data.get('term_set')

        # Debug print statements
        print(f"Form validation - is_mandatory: {is_mandatory}, visible_on_create: {visible_on_create}")

        if is_mandatory and not visible_on_create:
            raise forms.ValidationError({
                'visible_on_create': 'Mandatory fields must be visible on creation wizard'
            })

        needs_term_set = field_type in [
            'dropdown_single', 'dropdown_multi', 
            'radio', 'combobox_single', 'combobox_multi'
        ]

        if needs_term_set and not term_set:
            raise forms.ValidationError({
                'term_set': 'Term Set is required for this field type'
            })

        return cleaned_data 