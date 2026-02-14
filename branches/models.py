from django.db import models

class Branch(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
