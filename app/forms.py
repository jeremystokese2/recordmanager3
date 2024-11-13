from django import forms
from django.core.exceptions import ValidationError
from .models import CustomField, CoreField, Role

class CustomFieldForm(forms.ModelForm):
    field_name = forms.CharField(
        max_length=100,
        required=True,
        label='Field Name'
    )

    wizard_position = forms.ChoiceField(
        choices=CustomField.WIZARD_POSITIONS,
        initial=0,
        required=True,
        label='Page Location',
        help_text='Select which page this field should appear on'
    )

    class Meta:
        model = CustomField
        fields = ['field_name', 'display_name', 'field_type', 'description', 'order', 
                 'show_in_header', 'is_mandatory', 'visible_on_create', 'term_set',
                 'wizard_position']

    def __init__(self, *args, record_type=None, **kwargs):
        self.record_type = record_type
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['field_name'].initial = self.instance.name

    def clean_field_name(self):
        field_name = self.cleaned_data['field_name']
        
        if not self.record_type:
            raise ValidationError("Record type is required for validation")

        # Check if name exists in CoreFields
        core_field_exists = CoreField.objects.filter(
            record_type=self.record_type,
            name__iexact=field_name
        ).exists()
        
        if core_field_exists:
            raise ValidationError(f"A core field with the name '{field_name}' already exists")

        # Check if name exists in Roles
        role_exists = Role.objects.filter(
            record_type=self.record_type,
            name__iexact=field_name
        ).exists()
        
        if role_exists:
            raise ValidationError(f"A role with the name '{field_name}' already exists")

        # Check if name exists in CustomFields (excluding current instance if editing)
        custom_field_query = CustomField.objects.filter(
            record_type=self.record_type,
            name__iexact=field_name
        )
        if self.instance and self.instance.pk:
            custom_field_query = custom_field_query.exclude(pk=self.instance.pk)
        
        if custom_field_query.exists():
            raise ValidationError(f"A custom field with the name '{field_name}' already exists")

        return field_name

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.name = self.cleaned_data['field_name']
        if commit:
            instance.save()
        return instance

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

        # Skip wizard position validation for role fields
        if field_type in ['dropdown_single', 'dropdown_multi', 'radio', 'combobox_single', 'combobox_multi']:
            wizard_position = cleaned_data.get('wizard_position')
            if wizard_position not in [0, 1]:
                raise forms.ValidationError({
                    'wizard_position': 'Invalid wizard position. Must be Record Information (0) or Record Response (1)'
                })

        return cleaned_data 

class RoleForm(forms.ModelForm):
    name = forms.CharField(
        max_length=100,
        required=True,
        label='Role Name'
    )

    class Meta:
        model = Role
        fields = ['name', 'display_name', 'description', 'stage', 'order', 'allow_multiple']

    def __init__(self, *args, record_type=None, **kwargs):
        self.record_type = record_type
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['name'].initial = self.instance.name

    def clean_name(self):
        name = self.cleaned_data['name']
        
        if not self.record_type:
            raise ValidationError("Record type is required for validation")

        # Check if name exists in CoreFields
        core_field_exists = CoreField.objects.filter(
            record_type=self.record_type,
            name__iexact=name
        ).exists()
        
        if core_field_exists:
            raise ValidationError(f"A core field with the name '{name}' already exists")

        # Check if name exists in CustomFields
        custom_field_exists = CustomField.objects.filter(
            record_type=self.record_type,
            name__iexact=name
        ).exists()
        
        if custom_field_exists:
            raise ValidationError(f"A custom field with the name '{name}' already exists")

        # Check if name exists in Roles (excluding current instance if editing)
        role_query = Role.objects.filter(
            record_type=self.record_type,
            name__iexact=name
        )
        if self.instance and self.instance.pk:
            role_query = role_query.exclude(pk=self.instance.pk)
        
        if role_query.exists():
            raise ValidationError(f"A role with the name '{name}' already exists")

        return name 