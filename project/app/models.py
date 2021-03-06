# Django
# Standard Libary
import os
import secrets

# First-Party
from address.models import AddressField
from django.contrib.auth.models import AbstractBaseUser
from django.db import models
from django.utils.deconstruct import deconstructible
from hashid_field import HashidAutoField
from model_utils import Choices
from nameparser import HumanName
from phonenumber_field.modelfields import PhoneNumberField

# Local
from .managers import UserManager


class Person(models.Model):
    name = models.CharField(
        max_length=100,
        blank=False,
        default='',
    )
    formal_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Formal Name"
    )
    familiar_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Familiar Name"
    )
    greeting_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Greeting Name"
    )
    prefix = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Name Prefix',
    )
    first_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="First Name",
    )
    last_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Last Name",
    )
    middle_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Middle Name",
    )
    nick_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Nick Name",
    )
    suffix = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Name Suffix",
    )
    address = AddressField(
        blank=True,
        null=True,
        on_delete=models.CASCADE,
    )
    email = models.EmailField(
        blank=False,
        null=True,
    )
    phone = PhoneNumberField(
        blank=False,
        null=True,
    )

    def save(self, *args, **kwargs):
        instance = self._parse(name=self.name)
        d = instance.as_dict()
        setattr(self, 'formal_name', f'{d["title"]} {d["first"]} {d["last"]} {d["suffix"]}'.strip())
        greeting = d['nickname'] if d['nickname'] else d['first']
        setattr(self, 'greeting_name', greeting)
        setattr(self, 'familiar_name', f'{greeting} {d["last"]}'.strip())
        # Remap
        remapping = {
            'title': 'prefix',
            'first': 'first_name',
            'middle': 'middle_name',
            'last': 'last_name',
            'nickname': 'nick_name',
            'suffix': 'suffix',
        }
        for attr, val in d.items():
            setattr(self, remapping[attr], val)
        super().save(*args, **kwargs)

    @classmethod
    def _parse(cls, name):
        """
        Parses and returns a `HumanName` instance.
        """
        instance = HumanName(
            full_name=name,
        )
        return instance

    class Meta:
        abstract = True


class Recipient(Person):
    id = HashidAutoField(
        primary_key=True,
    )
    SIZE = Choices(
        (110, 'small', 'Small (1-15 bags)'),
        (120, 'medium', 'Medium (16-30 bags)'),
        (130, 'large', 'Large (31+ bags)'),
    )
    size = models.IntegerField(
        blank=False,
        choices=SIZE,
        help_text='Yard Size',
    )
    is_dog = models.BooleanField(
        blank=False,
        help_text="""If you have a dog, it must be contained in your home for us to rake.  Also, you must clean up all animal waste before we arrive or our volunteer group will not be able to rake.""",
    )
    notes = models.TextField(
        max_length=2000,
        blank=True,
        default='',
        help_text="""Please add any other notes you think we should know.""",
    )
    bags = models.IntegerField(
        blank=True,
        null=True,
        help_text='Actual Bags Used',
    )
    hours = models.FloatField(
        blank=True,
        null=True,
        help_text='Actual Hours Worked',
    )
    adults = models.IntegerField(
        blank=True,
        null=True,
        help_text='Actual Adults',
    )
    children = models.IntegerField(
        blank=True,
        null=True,
        help_text='Actual Children',
    )
    created = models.DateTimeField(
        auto_now_add=True,
    )
    updated = models.DateTimeField(
        auto_now=True,
    )
    user = models.OneToOneField(
        'app.User',
        on_delete=models.SET_NULL,
        related_name='recipient',
        null=True,
        unique=True,
    )

    def is_assigned(self):
        return bool(self.assignments.count())

    @property
    def total(self):
        return self.volunteers.aggregate(
            s=models.Sum('number')
        )['s']


class Volunteer(Person):
    id = HashidAutoField(
        primary_key=True,
    )
    SIZE = Choices(
        (110, 'xs', 'Extra-Small (1-2 Adults)'),
        (120, 'small', 'Small (3-5 Adults)'),
        (130, 'medium', 'Medium (5-9 Adults)'),
        (140, 'large', 'Large (10-15 Adults)'),
        (150, 'xl', 'Extra-Large (15+ Adults)'),
    )
    size = models.IntegerField(
        blank=False,
        choices=SIZE,
        help_text='The size of your group',
    )
    number = models.IntegerField(
        blank=True,
        null=True,
        help_text="""Number in your group.""",
    )
    adults = models.IntegerField(
        blank=True,
        null=True,
        help_text="""Number of adults in your group.""",
    )
    children = models.IntegerField(
        blank=True,
        null=True,
        help_text="""Number of children in your group.""",
    )
    assignment = models.ForeignKey(
        'Recipient',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments',
    )
    notes = models.TextField(
        max_length=512,
        blank=True,
        default='',
        help_text="""Notes.""",
    )
    created = models.DateTimeField(
        auto_now_add=True,
    )
    updated = models.DateTimeField(
        auto_now=True,
    )
    user = models.OneToOneField(
        'app.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='volunteer',
        unique=True,
    )

    def is_assigned(self):
        return bool(self.assignments.count())


@deconstructible
class UploadPath(object):
    def __init__(self, name):
        self.name = name

    def __call__(self, instance, filename):
        short = secrets.token_urlsafe()[:8]
        return os.path.join(
            self.name,
            short,
        )


class Picture(models.Model):
    id = HashidAutoField(
        primary_key=True,
    )
    image = models.ImageField(
        upload_to=UploadPath('image'),
        blank=True,
    )
    created = models.DateTimeField(
        auto_now_add=True,
    )
    updated = models.DateTimeField(
        auto_now=True,
    )


class User(AbstractBaseUser):
    id = HashidAutoField(
        primary_key=True,
    )
    username = models.CharField(
        max_length=150,
        blank=False,
        null=False,
        unique=True,
    )
    data = models.JSONField(
        null=True,
        editable=False,
    )
    name = models.CharField(
        max_length=100,
        blank=True,
        default='(Unknown)',
        verbose_name="Name",
        editable=False,
    )
    email = models.EmailField(
        blank=True,
        null=True,
        editable=False,
    )
    is_active = models.BooleanField(
        default=True,
    )
    is_admin = models.BooleanField(
        default=False,
    )
    created = models.DateTimeField(
        auto_now_add=True,
    )
    updated = models.DateTimeField(
        auto_now=True,
    )

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = [
    ]

    objects = UserManager()

    @property
    def is_staff(self):
        return self.is_admin

    def __str__(self):
        return str(self.username)

    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True
