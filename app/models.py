from django.db import models
from django.core.validators import MaxLengthValidator, RegexValidator
from django.core.exceptions import ValidationError

class RecordType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    prefix = models.CharField(max_length=4, unique=True)
    description = models.CharField(max_length=250, blank=True)
    colour = models.CharField(max_length=7, default='#000000')
    category = models.CharField(max_length=50)
    order = models.IntegerField(default=0)
    is_enabled = models.BooleanField(default=True)
    enable_correspondence = models.BooleanField(default=False)
    correspondence_mandatory = models.BooleanField(default=False)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

class Stage(models.Model):
    record_type = models.ForeignKey(RecordType, on_delete=models.CASCADE, related_name='stages')
    name = models.CharField(max_length=50)
    order = models.IntegerField()

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.record_type.name} - {self.name}"

class CoreField(models.Model):
    record_type = models.ForeignKey(RecordType, on_delete=models.CASCADE, related_name='core_fields')
    name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100)
    field_type = models.CharField(max_length=20)
    description = models.CharField(
        max_length=300, 
        blank=True,
        null=True,
        validators=[MaxLengthValidator(300)]
    )
    is_active = models.BooleanField(default=True)
    is_mandatory = models.BooleanField(default=True)
    visible_on_create = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        # Special handling for Title and Topic fields
        if self.name == 'title':
            self.field_type = 'text'
            if not self.description:
                self.description = "Capture the subject in a short, one line title. This will appear at the top of the briefing pack."
        elif self.name == 'ABCTopicSummary':
            self.field_type = 'text'
            if not self.description:
                self.description = "Summarise the issue and context into a concise sentence. This will appear in the final briefing pack and the Dashboard record entry."
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.record_type.name} - {self.display_name}"

class CustomField(models.Model):
    FIELD_TYPES = [
        (1, 'Text Input'),
        (2, 'Single Select Dropdown'),
        (3, 'Multi Select Dropdown'),
        (4, 'Single User Role'),
        (5, 'Date Only'),
        (6, 'Time Only'),
        (7, 'Date and Time'),
        (8, 'Multi User Role'),
        (9, 'Text Area'),
        (10, 'Radio')
    ]

    WIZARD_POSITIONS = [
        (0, 'Record Information'),
        (1, 'Record Response'),
    ]

    record_type = models.ForeignKey(RecordType, on_delete=models.CASCADE, related_name='custom_fields')
    name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100, default='')
    field_type = models.IntegerField(choices=FIELD_TYPES)
    description = models.CharField(
        max_length=300, 
        blank=True,
        validators=[MaxLengthValidator(300)]
    )
    order = models.IntegerField(default=0)
    show_in_header = models.BooleanField(default=False)
    is_mandatory = models.BooleanField(default=False)
    visible_on_create = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    term_set = models.CharField(
        max_length=100,
        blank=True,
        validators=[
            RegexValidator(
                regex='^[A-Za-z0-9\s]*$',
                message='Term Set can only contain alphanumeric characters and spaces'
            )
        ]
    )
    wizard_position = models.IntegerField(
        choices=WIZARD_POSITIONS,
        default=0,
        help_text="Page where this field will appear"
    )

    class Meta:
        ordering = ['order', 'name']
        unique_together = ['record_type', 'name']

    def clean(self):
        if self.is_mandatory and not self.visible_on_create:
            raise ValidationError('Mandatory fields must be visible on creation wizard')
        
        needs_term_set = self.field_type in [
            'dropdown_single', 'dropdown_multi', 
            'radio', 'combobox_single', 'combobox_multi'
        ]
        if needs_term_set and not self.term_set:
            raise ValidationError('Term Set is required for this field type')

    def __str__(self):
        return f"{self.record_type.name} - {self.display_name}"

class Role(models.Model):
    record_type = models.ForeignKey(RecordType, on_delete=models.CASCADE)
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE, related_name='roles')
    name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100, default='')
    description = models.CharField(max_length=250, blank=True)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_mandatory = models.BooleanField(default=False)  # Add this line
    allow_multiple = models.BooleanField(default=False)  # Add this if missing
    
    class Meta:
        unique_together = ('record_type', 'stage', 'name')
        ordering = ['order', 'name']
    
    def save(self, *args, **kwargs):
        # If display_name is empty, use name
        if not self.display_name:
            self.display_name = self.name
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} - {self.stage.name} - {self.record_type.name}"

class Field(models.Model):
    # Existing fields...
    is_active = models.BooleanField(default=True)
    stage = models.CharField(max_length=100)  # For role fields
    term_set_name = models.CharField(max_length=100)  # For dropdown/combo fields
    
    # Add any missing fields that you want to track

